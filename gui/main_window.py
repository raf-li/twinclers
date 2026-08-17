"""
Main Application Window for Twinclers Guard.
Minimalist, clean interface, 100% focused on NVDA accessibility and Menu Bar & Keyboard navigation.
Supports Password Protection (Instant Gate 0.01s & AES-256 Vault), Explorer Active Watcher, Auto-Relock, and System Tray.
"""

import os
import wx
from datetime import datetime

from core.i18n import _, i18n
from core.acl_manager import acl_engine
from core.storage import storage
from core.vault_manager import vault_mgr
from core.explorer_monitor import explorer_watcher
from core.nvda_speaker import speaker
from gui.dialogs import AddItemDialog, ChangeModeDialog, TestResultDialog
from gui.password_dialog import PasswordPromptDialog, SetPasswordDialog
from gui.help_dialog import HelpDialog
from gui.tray_icon import TwinclersTrayIcon

# Menu / Action IDs
ID_ADD_FOLDER    = wx.NewIdRef()
ID_ADD_FILE      = wx.NewIdRef()
ID_REFRESH       = wx.NewIdRef()
ID_MINIMIZE_TRAY = wx.NewIdRef()
ID_EXPLORER_REG  = wx.NewIdRef()
ID_PROTECT_SEL   = wx.NewIdRef()
ID_UNPROTECT_SEL = wx.NewIdRef()
ID_PROTECT_ALL   = wx.NewIdRef()
ID_UNPROTECT_ALL = wx.NewIdRef()
ID_TEST_DELETE   = wx.NewIdRef()
ID_CHANGE_MODE   = wx.NewIdRef()
ID_REMOVE_ITEM   = wx.NewIdRef()
ID_HELP_F1       = wx.NewIdRef()
ID_ABOUT         = wx.NewIdRef()

class MainWindow(wx.Frame):
    def __init__(self):
        # Muat preferensi bahasa dari storage (default 'en')
        saved_lang = storage.get_language()
        i18n.set_language(saved_lang)

        super().__init__(
            parent=None,
            title=_("APP_TITLE"),
            size=(940, 580),
            style=wx.DEFAULT_FRAME_STYLE
        )

        self.SetMinSize((700, 420))
        self.lang_menu_items = {}
        
        # Inisialisasi System Tray Icon
        self.tray_icon = TwinclersTrayIcon(self)

        self.init_menu()
        self.init_ui()
        # Inisialisasi Database
        storage.load_data()
        
        # Mulai proses sinkronisasi bahasa di latar belakang (OTA Updates)
        i18n.sync_locales_from_github_background()

        # Gunakan bahasa yang tersimpan di profil pengguna (atau default English)
        self.init_accelerators()
        self.Centre()

        # Daftarkan listener saat bahasa berubah
        i18n.add_language_change_listener(self.on_language_changed)

        # Inisialisasi Explorer Watcher
        explorer_watcher.set_callbacks(
            on_prompt_unlock=self.on_explorer_trigger_prompt,
            on_auto_relock=self.on_explorer_auto_relock
        )
        explorer_watcher.start()

        # Bind event close dan iconize untuk tray
        self.Bind(wx.EVT_CLOSE, self.on_close_window)
        self.Bind(wx.EVT_ICONIZE, self.on_iconize)

        # Load & refresh initial items
        self.refresh_list(initial_load=True)

        # Self-healing: Cek dan perbaiki Registry jika exe dipindah
        acl_engine.repair_context_menu()

        # Mulai IPC Server untuk Single Instance
        self.start_ipc_server()
        
        # Check for updates after a short delay
        wx.CallLater(2000, self.run_update_check)

    def run_update_check(self):
        import threading
        from core.updater import AutoUpdater
        
        def _check():
            metadata = AutoUpdater.check_for_updates()
            if metadata:
                wx.CallAfter(self.prompt_update, metadata)
                
        threading.Thread(target=_check, daemon=True).start()

    def prompt_update(self, metadata: dict):
        version = metadata.get("version", "Unknown")
        notes = metadata.get("release_notes", "")
        msg = f"A new version of Twinclers Guard ({version}) is available!\n\nRelease Notes:\n{notes}\n\nWould you like to download and install it now?"
        
        dlg = wx.MessageDialog(self, msg, "Update Available", wx.YES_NO | wx.ICON_INFORMATION)
        if dlg.ShowModal() == wx.ID_YES:
            self.start_update_download(metadata.get("download_url", ""), metadata.get("signature", ""))
        dlg.Destroy()
        
    def start_update_download(self, download_url: str, signature_hex: str):
        if not download_url or not signature_hex:
            wx.MessageBox("Invalid download URL or missing security signature.", "Update Failed", wx.ICON_ERROR)
            return
            
        progress_dlg = wx.ProgressDialog(
            "Downloading Update",
            "Please wait while the update is downloading...",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        
        import threading
        from core.updater import AutoUpdater
        
        def _download_task():
            def _progress_cb(downloaded, total):
                percent = int((downloaded / total) * 100)
                wx.CallAfter(progress_dlg.Update, percent)
                
            success = AutoUpdater.download_and_install(download_url, signature_hex, _progress_cb)
            if not success:
                wx.CallAfter(progress_dlg.Destroy)
                wx.CallAfter(wx.MessageBox, "Failed to download, or the update signature is invalid (Security Check Failed).", "Update Error", wx.ICON_ERROR)
                
        threading.Thread(target=_download_task, daemon=True).start()

    def start_ipc_server(self):
        import socket
        import threading
        import json
        import secrets
        
        IPC_PORT = 49152
        
        self.ipc_auth_token = secrets.token_hex(32)
        token_file = os.path.join(os.getenv('APPDATA'), 'TwinclersGuard', '.ipc_auth')
        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        try:
            with open(token_file, 'w', encoding='utf-8') as f:
                f.write(self.ipc_auth_token)
        except OSError:
            pass

        def _listen():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', IPC_PORT))
                s.listen()
                s.settimeout(1.0)
                while True:
                    try:
                        conn, addr = s.accept()
                        with conn:
                            conn.settimeout(2.0)
                            data = conn.recv(8192)
                            if data:
                                payload = json.loads(data.decode('utf-8'))
                                if payload.get("token") == self.ipc_auth_token:
                                    wx.CallAfter(self.process_ipc_args, payload.get("args", []))
                    except socket.timeout:
                        continue
                    except json.JSONDecodeError:
                        pass
                    except OSError:
                        pass
        
        t = threading.Thread(target=_listen, daemon=True)
        t.start()

    def process_ipc_args(self, args_list):
        """Receives and processes CLI commands from another instance (context menu)."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--add")
        parser.add_argument("--protect")
        parser.add_argument("--unprotect")
        parser.add_argument("--mode", default=None)
        
        args, _ = parser.parse_known_args(args_list)
        
        target_path = None
        action = None
        mode = args.mode
        
        if args.add:
            target_path = os.path.abspath(args.add)
            action = "add"
        elif args.protect:
            target_path = os.path.abspath(args.protect)
            action = "protect"
        elif args.unprotect:
            target_path = os.path.abspath(args.unprotect)
            action = "unprotect"
            
        if target_path and os.path.exists(target_path):
            # Select item di list untuk diproses oleh GUI event handler standar
            self.select_path_in_list(target_path)
            
            if action == "add":
                # Cek jika sudah terdaftar
                item = storage.get_item(target_path)
                if not item:
                    # Auto-Detect
                    if vault_mgr.has_encrypted_vault_files(target_path):
                        storage.add_item(target_path, mode="aes256_vault")
                        storage.update_item(target_path, status="protected")
                        speaker.speak(f"Auto-detected existing AES-256 Vault.")
                    else:
                        acl_status = acl_engine.check_protection_status(target_path)
                        if acl_status and acl_status.get("protected"):
                            detected_mode = acl_status.get("mode")
                            storage.add_item(target_path, mode=detected_mode if detected_mode != "none" else "anti_delete")
                            storage.update_item(target_path, status="protected")
                            speaker.speak(f"Auto-detected existing protection.")
                        else:
                            storage.add_item(target_path, mode=mode or "anti_delete")
                            speaker.speak(f"{os.path.basename(target_path)} added.")
                self.refresh_list()
            elif action == "protect":
                self.on_protect_selected(None)
            elif action == "unprotect":
                dlg = wx.MessageDialog(
                    self,
                    _("MSG_CONFIRM_IPC_UNPROTECT", name=os.path.basename(target_path) or target_path, default=f"Do you want to unlock {os.path.basename(target_path) or target_path}?"),
                    "Confirm Unlock",
                    wx.YES_NO | wx.ICON_QUESTION
                )
                if dlg.ShowModal() == wx.ID_YES:
                    self.on_unprotect_selected(None)
                dlg.Destroy()
        
        # Bawa jendela ke depan jika disembunyikan
        if not self.IsShown():
            self.Show()
        if self.IsIconized():
            self.Iconize(False)
        self.Raise()
        self.SetFocus()

    def select_path_in_list(self, path: str):
        """Helper to select a row in ListCtrl based on path for IPC actions."""
        for i in range(self.list_ctrl.GetItemCount()):
            item_path = self.list_ctrl.GetItemText(i, 0)
            if item_path.lower() == path.lower():
                self.list_ctrl.Select(i)
                self.list_ctrl.EnsureVisible(i)
                return
        # Jika tidak ketemu, tambahkan sementara ke DB agar bisa diproses
        storage.add_item(path, mode="anti_delete")
        self.refresh_list()
        for i in range(self.list_ctrl.GetItemCount()):
            item_path = self.list_ctrl.GetItemText(i, 0)
            if item_path.lower() == path.lower():
                self.list_ctrl.Select(i)
                self.list_ctrl.EnsureVisible(i)
                return

    def init_menu(self):
        """Creates the full Menu Bar with shortcuts and language options."""
        menu_bar = wx.MenuBar()

        # 1. Menu Berkas (&File)
        file_menu = wx.Menu()
        file_menu.Append(ID_ADD_FOLDER, _("MENU_ADD_FOLDER"))
        file_menu.Append(ID_ADD_FILE, _("MENU_ADD_FILE"))
        file_menu.AppendSeparator()
        file_menu.Append(ID_REFRESH, _("MENU_REFRESH"))
        file_menu.Append(ID_MINIMIZE_TRAY, _("MENU_MINIMIZE_TRAY"))
        file_menu.Append(ID_EXPLORER_REG, _("MENU_EXPLORER_INTEGRATION"))
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, _("MENU_EXIT"))
        menu_bar.Append(file_menu, _("MENU_FILE"))

        # 2. Menu Aksi (&Actions)
        action_menu = wx.Menu()
        action_menu.Append(ID_PROTECT_SEL, _("MENU_PROTECT_SEL"))
        action_menu.Append(ID_UNPROTECT_SEL, _("MENU_UNPROTECT_SEL"))
        action_menu.AppendSeparator()
        action_menu.Append(ID_PROTECT_ALL, _("MENU_PROTECT_ALL"))
        action_menu.Append(ID_UNPROTECT_ALL, _("MENU_UNPROTECT_ALL"))
        action_menu.AppendSeparator()
        action_menu.Append(ID_TEST_DELETE, _("MENU_TEST_DELETE"))
        action_menu.Append(ID_CHANGE_MODE, _("MENU_CHANGE_MODE"))
        action_menu.Append(ID_REMOVE_ITEM, _("MENU_REMOVE_ITEM"))
        menu_bar.Append(action_menu, _("MENU_ACTIONS"))

        # 3. Menu Bahasa (&Language)
        lang_menu = wx.Menu()
        available_langs = i18n.get_available_languages()
        self.lang_menu_items.clear()

        for code, name in available_langs:
            item_id = wx.NewIdRef()
            m_item = lang_menu.AppendRadioItem(item_id, name)
            if code == i18n.current_lang:
                m_item.Check(True)
            self.lang_menu_items[item_id] = code
            self.Bind(wx.EVT_MENU, self.on_select_language, id=item_id)

        menu_bar.Append(lang_menu, _("MENU_LANGUAGE"))

        # 4. Menu Bantuan (&Help)
        help_menu = wx.Menu()
        help_menu.Append(ID_HELP_F1, _("MENU_HELP_F1"))
        help_menu.AppendSeparator()
        help_menu.Append(ID_ABOUT, _("MENU_ABOUT"))
        menu_bar.Append(help_menu, _("MENU_HELP"))

        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_add_folder, id=ID_ADD_FOLDER)
        self.Bind(wx.EVT_MENU, self.on_add_file, id=ID_ADD_FILE)
        self.Bind(wx.EVT_MENU, self.on_refresh, id=ID_REFRESH)
        self.Bind(wx.EVT_MENU, self.on_hide_to_tray, id=ID_MINIMIZE_TRAY)
        self.Bind(wx.EVT_MENU, self.on_toggle_explorer_integration, id=ID_EXPLORER_REG)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), id=wx.ID_EXIT)

        self.Bind(wx.EVT_MENU, self.on_protect_selected, id=ID_PROTECT_SEL)
        self.Bind(wx.EVT_MENU, self.on_unprotect_selected, id=ID_UNPROTECT_SEL)
        self.Bind(wx.EVT_MENU, self.on_protect_all, id=ID_PROTECT_ALL)
        self.Bind(wx.EVT_MENU, self.on_unprotect_all, id=ID_UNPROTECT_ALL)
        self.Bind(wx.EVT_MENU, self.on_test_delete, id=ID_TEST_DELETE)
        self.Bind(wx.EVT_MENU, self.on_change_mode, id=ID_CHANGE_MODE)
        self.Bind(wx.EVT_MENU, self.on_remove_item, id=ID_REMOVE_ITEM)

        self.Bind(wx.EVT_MENU, self.on_help, id=ID_HELP_F1)
        self.Bind(wx.EVT_MENU, self.on_about, id=ID_ABOUT)

    def init_accelerators(self):
        """Registers the Accelerator Table for global shortcuts."""
        entries = [
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('O'), ID_ADD_FOLDER),
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('O'), ID_ADD_FILE),
            wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F5, ID_REFRESH),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('H'), ID_MINIMIZE_TRAY),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('P'), ID_PROTECT_SEL),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('U'), ID_UNPROTECT_SEL),
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('P'), ID_PROTECT_ALL),
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('U'), ID_UNPROTECT_ALL),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('T'), ID_TEST_DELETE),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('M'), ID_CHANGE_MODE),
            wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_DELETE, ID_REMOVE_ITEM),
            wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F1, ID_HELP_F1),
        ]
        accel_tbl = wx.AcceleratorTable(entries)
        self.SetAcceleratorTable(accel_tbl)

    def init_ui(self):
        """Creates the clean main interface without redundant buttons."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Main ListCtrl (Report Mode)
        self.list_ctrl = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )
        self.list_ctrl.SetName(_("APP_TITLE"))
        
        self.setup_columns()

        # Bind events list
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_item_selected)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated)
        self.list_ctrl.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)

        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 6)
        panel.SetSizer(main_sizer)

        # Status Bar
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-3, -1])
        self.update_status_bar(_("STATUS_READY"))

        self.list_ctrl.SetFocus()

    def setup_columns(self):
        """Configures column headers based on active language."""
        self.list_ctrl.ClearAll()
        self.list_ctrl.InsertColumn(0, _("COL_PATH"), width=400)
        self.list_ctrl.InsertColumn(1, _("COL_TYPE"), width=90)
        self.list_ctrl.InsertColumn(2, _("COL_STATUS"), width=170)
        self.list_ctrl.InsertColumn(3, _("COL_MODE"), width=200)
        self.list_ctrl.InsertColumn(4, _("COL_LAST_UPDATED"), width=150)

    def on_select_language(self, event):
        """Handler for language selection from the menu."""
        item_id = event.GetId()
        lang_code = self.lang_menu_items.get(item_id)
        if lang_code and lang_code != i18n.current_lang:
            storage.set_language(lang_code)
            i18n.set_language(lang_code)

    def on_language_changed(self, lang_code: str):
        """Re-renders the interface when language changes."""
        self.SetTitle(_("APP_TITLE"))
        self.init_menu()
        self.setup_columns()
        self.refresh_list()
        speaker.speak(f"Language changed to {i18n.translations.get(lang_code, {}).get('LANGUAGE_NAME', lang_code)}")

    def update_status_bar(self, msg: str):
        """Updates text on the status bar."""
        self.status_bar.SetStatusText(msg, 0)
        items = storage.get_all()
        protected_count = sum(1 for it in items if it.get("status") == "protected")
        self.status_bar.SetStatusText(_("STATUS_COUNT", total=len(items), protected=protected_count), 1)

    def refresh_list(self, initial_load: bool = False):
        """Synchronizes storage data with the ListCtrl view."""
        self.list_ctrl.DeleteAllItems()
        items = storage.get_all()

        mode_labels = {
            "anti_delete": _("MODE_ANTI_DELETE"),
            "instant_gate": _("MODE_INSTANT_GATE"),
            "aes256_vault": _("MODE_AES256_VAULT"),
            "anti_rename_delete": _("MODE_ANTI_RENAME"),
            "append_only": _("MODE_APPEND_ONLY"),
            "read_only": _("MODE_READ_ONLY"),
            "full_lock": _("MODE_FULL_LOCK"),
            "custom": _("MODE_CUSTOM")
        }

        for i, item in enumerate(items):
            path = item["path"]
            mode = item.get("mode", "anti_delete")
            status = item.get("status", "unprotected")

            # Periksa status file/folder
            if not os.path.exists(path):
                status_str = _("STATUS_NOT_FOUND")
            elif status == "protected":
                status_str = _("STATUS_LOCKED")
            else:
                status_str = _("STATUS_UNLOCKED")

            item_type = _("TYPE_FOLDER") if item.get("type") == "folder" else _("TYPE_FILE")
            mode_str = mode_labels.get(mode, mode)
            updated_str = item.get("last_updated", "")[:19].replace("T", " ")

            idx = self.list_ctrl.InsertItem(i, path)
            self.list_ctrl.SetItem(idx, 1, item_type)
            self.list_ctrl.SetItem(idx, 2, status_str)
            self.list_ctrl.SetItem(idx, 3, mode_str)
            self.list_ctrl.SetItem(idx, 4, updated_str)

        self.update_status_bar(_("STATUS_LIST_UPDATED"))

        if initial_load:
            prot_cnt = sum(1 for it in items if it.get("status") == "protected")
            announcement = _("ANNOUNCE_READY", total=len(items), protected=prot_cnt)
            speaker.speak(announcement)

    def get_selected_item_path(self) -> str:
        """Retrieves the path of the currently selected item in ListCtrl."""
        idx = self.list_ctrl.GetFirstSelected()
        if idx >= 0:
            return self.list_ctrl.GetItemText(idx, 0)
        return ""

    def on_item_selected(self, event):
        """When user navigates the list items with arrow keys."""
        idx = event.GetIndex()
        path = self.list_ctrl.GetItemText(idx, 0)
        status = self.list_ctrl.GetItemText(idx, 2)
        mode = self.list_ctrl.GetItemText(idx, 3)
        name = os.path.basename(path) or path
        
        speaker.speak(_("ANNOUNCE_ITEM_SELECTED", name=name, status=status, mode=mode), interrupt=True)
        event.Skip()

    def on_item_activated(self, event):
        """Enter key pressed on list item: Toggle lock/unlock."""
        path = self.get_selected_item_path()
        if not path:
            return
        item = storage.get_item(path)
        if not item:
            return

        if item.get("status") == "protected":
            self.on_unprotect_selected(event)
        else:
            self.on_protect_selected(event)

    def on_list_key_down(self, event):
        """Handles keyboard keys on ListCtrl."""
        key = event.GetKeyCode()
        if key == wx.WXK_DELETE:
            self.on_remove_item(event)
        else:
            event.Skip()

    def on_context_menu(self, event):
        """Right-click menu / context menu key (AppsKey / Shift+F10)."""
        path = self.get_selected_item_path()
        if not path:
            return

        menu = wx.Menu()
        menu.Append(ID_PROTECT_SEL, _("MENU_PROTECT_SEL"))
        menu.Append(ID_UNPROTECT_SEL, _("MENU_UNPROTECT_SEL"))
        menu.AppendSeparator()
        menu.Append(ID_TEST_DELETE, _("MENU_TEST_DELETE"))
        menu.Append(ID_CHANGE_MODE, _("MENU_CHANGE_MODE"))
        menu.AppendSeparator()
        menu.Append(ID_REMOVE_ITEM, _("MENU_REMOVE_ITEM"))

        self.PopupMenu(menu)
        menu.Destroy()

    # --- Explorer Monitor Callbacks ---

    def on_explorer_trigger_prompt(self, path: str):
        """Called when user opens a password-protected folder in File Explorer."""
        wx.CallAfter(self.show_password_prompt_for_path, path)

    def on_explorer_auto_relock(self, path: str):
        """Called when a File Explorer window is closed."""
        wx.CallAfter(self.refresh_list)

    def show_password_prompt_for_path(self, path: str):
        """Displays password dialog on top of Windows Explorer."""
        with PasswordPromptDialog(self, target_path=path) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.refresh_list()
            else:
                # User membatalkan input password / gagal, tendang keluar dari folder
                explorer_watcher.force_navigate_away(path)
                
                # Beri jeda sedikit agar Explorer sempat pindah direktori sebelum flag dihapus
                # Jika tidak diberi jeda, watcher bisa keburu memanggil prompt ini lagi.
                wx.CallLater(500, explorer_watcher.clear_prompted_flag, path)

    # --- System Tray & Window State Handlers ---

    def on_hide_to_tray(self, event):
        """Hides the window to the System Tray."""
        self.Hide()
        speaker.speak(_("ANNOUNCE_MINIMIZED_TRAY"))

    def on_iconize(self, event):
        """When minimize button is pressed."""
        if event.IsIconized():
            self.Hide()
            speaker.speak(_("ANNOUNCE_MINIMIZED_TRAY"))
        event.Skip()

    def on_close_window(self, event):
        """Cleanup upon window closing."""
        explorer_watcher.stop()
        if hasattr(self, 'tray_icon') and self.tray_icon:
            if getattr(self.tray_icon, '_icon_set', False):
                try:
                    self.tray_icon.RemoveIcon()
                except Exception:
                    pass
            self.tray_icon.Destroy()
        self.Destroy()

    def on_toggle_explorer_integration(self, event):
        """Toggles Windows Explorer context menu integration (register/unregister)."""
        already_registered = acl_engine.is_context_menu_registered()
        if already_registered:
            ok, msg = acl_engine.register_explorer_context_menu(enable=False)
            if ok:
                speaker.speak(_("ANNOUNCE_CONTEXT_MENU_REMOVED",
                                default="Twinclers Guard context menu removed from Windows Explorer."))
                self.update_status_bar(_("ANNOUNCE_CONTEXT_MENU_REMOVED",
                                         default="Context menu removed."))
            else:
                speaker.speak(f"Error: {msg}")
        else:
            ok, msg = acl_engine.register_explorer_context_menu(enable=True)
            if ok:
                speaker.speak(_("ANNOUNCE_CONTEXT_MENU_REGISTERED",
                                default="Twinclers Guard context menu registered in Windows Explorer. Right-click any folder or file to access it."))
                self.update_status_bar(_("ANNOUNCE_CONTEXT_MENU_REGISTERED",
                                         default="Context menu registered."))
            else:
                speaker.speak(f"Error: {msg}")

    # --- Handlers Aksi ---

    def on_add_folder(self, event):
        self._process_add_item(initial_type="folder")

    def on_add_file(self, event):
        self._process_add_item(initial_type="file")

    def _process_add_item(self, initial_type: str):
        with AddItemDialog(self, initial_type=initial_type) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.selected_path
                mode = dlg.selected_mode
                auto_protect = dlg.auto_protect
                name = os.path.basename(path) or path

                # 1. Cek apakah ini AES-256 Vault lama
                if vault_mgr.has_encrypted_vault_files(path):
                    storage.add_item(path, mode="aes256_vault")
                    storage.update_item(path, status="protected")
                    speaker.speak(f"Auto-detected existing AES-256 Vault. {name} added and protected.")
                    self.refresh_list()
                    return

                # 2. Cek apakah folder ini sudah terproteksi oleh ACL Windows dari Twinclers sebelumnya
                acl_status = acl_engine.check_protection_status(path)
                if acl_status and acl_status.get("protected"):
                    detected_mode = acl_status.get("mode")
                    if detected_mode != "none":
                        storage.add_item(path, mode=detected_mode)
                        storage.update_item(path, status="protected")
                        speaker.speak(f"Auto-detected existing protection. {name} added as {detected_mode}.")
                        self.refresh_list()
                        return

                # 3. Jika folder/file baru dan tidak ada proteksi lama
                storage.add_item(path, mode=mode)
                if auto_protect:
                    if mode in ["instant_gate", "aes256_vault"] and dlg.password:
                        vault_mgr.set_password(path, dlg.password, mode=mode)
                        speaker.speak(_("ANNOUNCE_PROTECTED", mode=mode, name=name))
                    else:
                        ok, msg = acl_engine.protect(path, mode=mode, custom_rules=dlg.custom_rules)
                        if ok:
                            storage.update_item(path, status="protected")
                            speaker.speak(_("ANNOUNCE_PROTECTED", mode=mode, name=name))
                        else:
                            speaker.speak(f"Error: {msg}")
                else:
                    speaker.speak(f"{name} added to list.")

                self.refresh_list()

    def on_protect_selected(self, event):
        path = self.get_selected_item_path()
        if not path:
            speaker.speak(_("MSG_SELECT_ITEM_FIRST"))
            self.update_status_bar(_("MSG_SELECT_ITEM_FIRST"))
            return

        item = storage.get_item(path) or {}
        mode = item.get("mode", "anti_delete")
        name = os.path.basename(path) or path

        if mode in ["instant_gate", "aes256_vault"]:
            # Jika belum ada password, minta password baru
            if not item.get("password_hash"):
                with SetPasswordDialog(self, target_path=path, mode=mode) as dlg:
                    if dlg.ShowModal() == wx.ID_OK:
                        vault_mgr.set_password(path, dlg.password, mode=mode)
                        speaker.speak(_("ANNOUNCE_PROTECTED", mode=mode, name=name))
                    else:
                        return
            else:
                ok, msg = vault_mgr.lock_item(path)
                if not ok and "password required" in msg:
                    # Fallback jika memori RAM/DPAPI hilang (misal aplikasi baru saja direstart)
                    dlg = wx.PasswordEntryDialog(self, f"Session lost. Enter password to encrypt and lock {name}:", "Password Required")
                    if dlg.ShowModal() == wx.ID_OK:
                        ok, msg = vault_mgr.lock_item(path, password=dlg.GetValue())
                    dlg.Destroy()

                if ok:
                    speaker.speak(_("ANNOUNCE_PROTECTED", mode=mode, name=name))
                else:
                    speaker.speak(f"Error locking: {msg}")
            self.refresh_list()
        else:
            ok, msg = acl_engine.protect(path, mode=mode)
            if ok:
                storage.update_item(path, status="protected")
                self.refresh_list()
                speaker.speak(_("ANNOUNCE_PROTECTED", mode=mode, name=name))
                self.update_status_bar(_("STATUS_PROTECTED_MSG", path=path))
            else:
                speaker.speak(f"Error: {msg}")
                self.update_status_bar(f"Error: {msg}")

    def on_unprotect_selected(self, event):
        path = self.get_selected_item_path()
        if not path:
            speaker.speak(_("MSG_SELECT_ITEM_FIRST"))
            self.update_status_bar(_("MSG_SELECT_ITEM_FIRST"))
            return

        item = storage.get_item(path) or {}
        mode = item.get("mode", "anti_delete")
        name = os.path.basename(path) or path

        if mode in ["instant_gate", "aes256_vault"]:
            # Minta password untuk membuka
            with PasswordPromptDialog(self, target_path=path) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    self.refresh_list()
                    self.update_status_bar(_("STATUS_UNPROTECTED_MSG", path=path))
        else:
            ok, msg = acl_engine.unprotect(path)
            if ok:
                storage.update_item(path, status="unprotected")
                self.refresh_list()
                speaker.speak(_("ANNOUNCE_UNPROTECTED", name=name))
                self.update_status_bar(_("STATUS_UNPROTECTED_MSG", path=path))
            else:
                speaker.speak(f"Error: {msg}")
                self.update_status_bar(f"Error: {msg}")

    def on_protect_all(self, event):
        items = storage.get_all()
        if not items:
            speaker.speak(_("MSG_SELECT_ITEM_FIRST"))
            return
        success_count = 0
        for it in items:
            path = it["path"]
            mode = it.get("mode", "anti_delete")
            if mode not in ["instant_gate", "aes256_vault"]:
                ok, _ = acl_engine.protect(path, mode=mode)
                if ok:
                    storage.update_item(path, status="protected")
                    success_count += 1
            else:
                ok, msg = vault_mgr.lock_item(path)
                if not ok and "password required" in msg:
                    name = os.path.basename(path) or path
                    dlg = wx.PasswordEntryDialog(self, f"Session lost. Enter password to encrypt and lock {name}:", "Password Required")
                    if dlg.ShowModal() == wx.ID_OK:
                        ok, _ = vault_mgr.lock_item(path, password=dlg.GetValue())
                    dlg.Destroy()
                    
                if ok:
                    success_count += 1

        self.refresh_list()
        speaker.speak(_("ANNOUNCE_PROTECT_ALL", count=success_count))

    def on_unprotect_all(self, event):
        items = storage.get_all()
        if not items:
            speaker.speak(_("MSG_SELECT_ITEM_FIRST"))
            return
        
        dlg = wx.MessageDialog(
            self,
            _("MSG_CONFIRM_UNPROTECT_ALL"),
            "Confirm",
            wx.YES_NO | wx.ICON_QUESTION
        )
        if dlg.ShowModal() == wx.ID_YES:
            for it in items:
                mode = it.get("mode", "anti_delete")
                if mode not in ["instant_gate", "aes256_vault"]:
                    acl_engine.unprotect(it["path"])
                    storage.update_item(it["path"], status="unprotected")
            self.refresh_list()
            speaker.speak(_("ANNOUNCE_UNPROTECT_ALL"))
        dlg.Destroy()

    def on_test_delete(self, event):
        path = self.get_selected_item_path()
        if not path:
            speaker.speak(_("MSG_SELECT_ITEM_FIRST"))
            self.update_status_bar(_("MSG_SELECT_ITEM_FIRST"))
            return

        ok, msg = acl_engine.test_delete_protection(path)
        with TestResultDialog(self, success=ok, message=msg, path=path) as dlg:
            dlg.ShowModal()

    def on_change_mode(self, event):
        path = self.get_selected_item_path()
        if not path:
            speaker.speak(_("MSG_SELECT_ITEM_FIRST"))
            self.update_status_bar(_("MSG_SELECT_ITEM_FIRST"))
            return

        item = storage.get_item(path) or {}
        current_mode = item.get("mode", "anti_delete")

        with ChangeModeDialog(self, current_mode=current_mode, target_name=path) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_mode = dlg.selected_mode
                storage.update_item(path, mode=new_mode)
                
                if new_mode in ["instant_gate", "aes256_vault"] and dlg.password:
                    vault_mgr.set_password(path, dlg.password, mode=new_mode)
                elif item.get("status") == "protected":
                    acl_engine.protect(path, mode=new_mode, custom_rules=dlg.custom_rules)
                
                self.refresh_list()
                speaker.speak(_("ANNOUNCE_MODE_CHANGED", mode=new_mode))

    def on_remove_item(self, event):
        path = self.get_selected_item_path()
        if not path:
            return

        name = os.path.basename(path) or path
        dlg = wx.MessageDialog(
            self,
            _("MSG_CONFIRM_REMOVE", name=name),
            "Remove Item",
            wx.YES_NO | wx.ICON_QUESTION
        )
        if dlg.ShowModal() == wx.ID_YES:
            storage.remove_item(path)
            self.refresh_list()
            speaker.speak(_("ANNOUNCE_REMOVED", name=name))
        dlg.Destroy()

    def on_refresh(self, event):
        self.refresh_list()
        speaker.speak(_("ANNOUNCE_REFRESHED"))

    def on_help(self, event):
        dlg = HelpDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def on_about(self, event):
        wx.MessageBox(_("MSG_ABOUT_CONTENT"), _("MENU_ABOUT").replace("&", ""), wx.OK | wx.ICON_INFORMATION, self)
