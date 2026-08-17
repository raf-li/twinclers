"""
Windows Explorer Active Window Monitor for Twinclers Guard.
Monitors active folders in Windows Explorer using COM Shell.Application,
automatically invokes password prompts when entering, and auto-relocks when windows are closed.
"""

import os
import time
import threading
import urllib.parse
from typing import Callable, Set, List, Optional
import win32com.client
import pythoncom

from core.storage import storage
from core.vault_manager import vault_mgr
from core.nvda_speaker import speaker

class ExplorerMonitor:
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._prompt_callback: Optional[Callable[[str], None]] = None
        self._relock_callback: Optional[Callable[[str], None]] = None
        self._prompted_paths: Set[str] = set() # Path yang sedang menampilkan prompt agar tidak spam

    def set_callbacks(self, on_prompt_unlock: Callable[[str], None], on_auto_relock: Callable[[str], None]):
        self._prompt_callback = on_prompt_unlock
        self._relock_callback = on_auto_relock

    def start(self):
        """Starts the background monitoring thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the monitoring thread."""
        self._running = False

    def clear_prompted_flag(self, path: str):
        """Clears the prompted flag so the user can be prompted again in the future."""
        norm_path = storage.normalize_path(path)
        self._prompted_paths.discard(norm_path)

    def _get_open_explorer_paths(self) -> List[str]:
        """Retrieves a list of all folder paths currently open in Windows Explorer."""
        open_paths = []
        try:
            pythoncom.CoInitialize()
            
            shell = win32com.client.Dispatch("Shell.Application")
            windows = shell.Windows()
            
            for w in windows:
                try:
                    # Ambil LocationURL (format file:///D:/...)
                    url = getattr(w, "LocationURL", "")
                    if url and url.startswith("file:///"):
                        parsed_path = urllib.parse.unquote(url[8:]).replace("/", "\\")
                        if os.path.exists(parsed_path):
                            open_paths.append(storage.normalize_path(parsed_path))
                except Exception:
                    pass
        except Exception:
            pass
        return open_paths

    def force_navigate_away(self, target_path: str):
        """Forces any Explorer window currently at target_path (or subfolders) to navigate up to the parent directory."""
        norm_target = storage.normalize_path(target_path)
        parent_dir = os.path.dirname(norm_target)
        if not os.path.exists(parent_dir):
            parent_dir = "C:\\"

        try:
            pythoncom.CoInitialize()
            shell = win32com.client.Dispatch("Shell.Application")
            windows = shell.Windows()
            
            for w in windows:
                try:
                    url = getattr(w, "LocationURL", "")
                    if url and url.startswith("file:///"):
                        parsed_path = urllib.parse.unquote(url[8:]).replace("/", "\\")
                        norm_parsed = storage.normalize_path(parsed_path)
                        
                        # Jika Explorer sedang di dalam folder yang terkunci
                        if norm_parsed == norm_target or norm_parsed.startswith(norm_target + "\\"):
                            # Paksa kembali / naik ke parent folder
                            w.Navigate(parent_dir)
                except Exception:
                    pass
        except Exception:
            pass

    def _monitor_loop(self):
        while self._running:
            try:
                open_explorer_paths = self._get_open_explorer_paths()

                # 1. Cek folder yang sedang aktif di-unlock untuk Auto-Relock saat Explorer ditutup
                active_unlocked = list(vault_mgr.active_sessions.keys())
                for unlocked_path in active_unlocked:
                    # Periksa apakah ada jendela Explorer yang masih membuka path ini atau subfolder-nya
                    is_still_open = any(
                        p == unlocked_path or p.startswith(unlocked_path + "\\")
                        for p in open_explorer_paths
                    )

                    if not is_still_open:
                        # Jendela Explorer sudah ditutup! Auto Relock!
                        ok, msg = vault_mgr.lock_item(unlocked_path)
                        if ok:
                            name = os.path.basename(unlocked_path) or unlocked_path
                            speaker.speak(f"Folder {name} has been automatically locked.")
                            if self._relock_callback:
                                self._relock_callback(unlocked_path)
                        self.clear_prompted_flag(unlocked_path)

                # 2. Cek apakah ada jendela Explorer yang sedang mengunjungi folder Password Protected yang sedang LOCKED
                monitored_items = storage.get_all()
                for item in monitored_items:
                    path = item["path"]
                    mode = item.get("mode", "")
                    status = item.get("status", "")

                    if mode in ["instant_gate", "aes256_vault"] and status == "protected":
                        # Cek apakah user sedang mencoba membuka folder ini di Explorer
                        for exp_path in open_explorer_paths:
                            if exp_path == path or exp_path.startswith(path + "\\"):
                                if path not in self._prompted_paths:
                                    self._prompted_paths.add(path)
                                    if self._prompt_callback:
                                        self._prompt_callback(path)

            except Exception as e:
                pass

            time.sleep(0.2)  # VLN-08: Diperkecil dari 0.7s ke 0.2s untuk kurangi TOCTOU window

explorer_watcher = ExplorerMonitor()
