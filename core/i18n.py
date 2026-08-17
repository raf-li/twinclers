"""
Internationalization (i18n) Module for Twinclers Guard.
Supports multi-language with English (en) as default, and can be switched to Indonesian (id) or other languages.
"""

import os
import json
import shutil
import urllib.request
import urllib.error
import threading
from typing import Dict, List, Tuple, Callable

class I18nManager:
    def __init__(self, default_lang: str = "en"):
        self.current_lang = default_lang
        
        # Setup AppData locales directory
        appdata = os.getenv('APPDATA') or os.path.expanduser('~')
        self.appdata_dir = os.path.join(appdata, 'TwinclersGuard')
        self.locales_dir = os.path.join(self.appdata_dir, 'locales')
        
        # Original bundled locales
        self.bundled_locales_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")
        
        self.translations: Dict[str, Dict[str, str]] = {}
        self.callbacks: List[Callable[[str], None]] = []
        
        self._ensure_locales_dir()
        self.load_all_translations()
        
    def _ensure_locales_dir(self):
        """Creates the AppData locales dir and copies bundled locales if missing."""
        os.makedirs(self.locales_dir, exist_ok=True)
        if os.path.exists(self.bundled_locales_dir):
            for fname in os.listdir(self.bundled_locales_dir):
                if fname.endswith(".json") or fname.endswith(".txt"):
                    bundled_path = os.path.join(self.bundled_locales_dir, fname)
                    appdata_path = os.path.join(self.locales_dir, fname)
                    # Copy if not exists in AppData
                    if not os.path.exists(appdata_path):
                        try:
                            shutil.copy2(bundled_path, appdata_path)
                        except Exception:
                            pass
    def load_all_translations(self):
        """Loads all language JSON files from the locales/ directory."""
        if not os.path.exists(self.locales_dir):
            return

        for fname in os.listdir(self.locales_dir):
            if fname.endswith(".json"):
                lang_code = fname[:-5]
                fpath = os.path.join(self.locales_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        self.translations[lang_code] = json.load(f)
                except (OSError, json.JSONDecodeError) as e:
                    print(f"[i18n] Error loading {fname}: {e}")

    def sync_locales_from_github_background(self):
        """Spawns a background thread to download new locales from GitHub."""
        t = threading.Thread(target=self._sync_locales, daemon=True)
        t.start()

    def _sync_locales(self):
        """Downloads updated locale files from GitHub API (OTA Updates)."""
        api_url = "https://api.github.com/repos/raf-li/twinclers/contents/locales"
        try:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'TwinclersGuard-I18n'})
            with urllib.request.urlopen(req, timeout=10) as response:
                files_metadata = json.loads(response.read().decode('utf-8'))
                
            updated = False
            for file_info in files_metadata:
                fname = file_info.get("name", "")
                download_url = file_info.get("download_url")
                if not download_url:
                    continue
                    
                if fname.endswith(".json") or fname.endswith(".txt"):
                    local_path = os.path.join(self.locales_dir, fname)
                    
                    # Download the file to a temporary buffer
                    dl_req = urllib.request.Request(download_url, headers={'User-Agent': 'TwinclersGuard-I18n'})
                    with urllib.request.urlopen(dl_req, timeout=10) as dl_res:
                        content = dl_res.read()
                        
                    # Check if file changed or is new
                    is_new_or_changed = True
                    if os.path.exists(local_path):
                        with open(local_path, "rb") as f:
                            local_content = f.read()
                        if local_content == content:
                            is_new_or_changed = False
                            
                    if is_new_or_changed:
                        with open(local_path, "wb") as f:
                            f.write(content)
                        updated = True
                        
            # If we updated any JSON file, reload translations in memory
            if updated:
                self.load_all_translations()
        except Exception as e:
            print(f"[i18n] Sync error: {e}")
        
    def get_available_languages(self) -> List[Tuple[str, str]]:
        """Returns a list of available languages (code, display name)."""
        languages = []
        for code, trans in self.translations.items():
            display_name = trans.get("LANGUAGE_NAME", code.upper())
            languages.append((code, display_name))
            
        if not languages:
            return [("en", "English"), ("id", "Bahasa Indonesia")]
            
        # Urutkan dengan 'en' di urutan pertama
        languages.sort(key=lambda x: (0 if x[0] == "en" else 1, x[1]))
        return languages

    def set_language(self, lang_code: str):
        """Changes the active application language and invokes observer callbacks."""
        if lang_code in self.translations or lang_code in ["en", "id"]:
            self.current_lang = lang_code
            for cb in self.callbacks:
                cb(lang_code)

    def add_language_change_listener(self, callback: Callable[[str], None]):
        """Registers a listener for language change events."""
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def t(self, key: str, default: str = None, **kwargs) -> str:
        """
        Retrieves translated text based on a key.
        Fallback: Active Language -> English (en) -> Default Value -> Key.
        """
        # 1. Cari di bahasa aktif
        text = self.translations.get(self.current_lang, {}).get(key)
        
        # 2. Fallback ke English jika tidak ditemukan
        if text is None and self.current_lang != "en":
            text = self.translations.get("en", {}).get(key)
            
        # 3. Fallback ke default argumen atau key
        if text is None:
            text = default if default is not None else key

        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError, IndexError):
                return text
        return text

# Global singleton
i18n = I18nManager(default_lang="en")

def _(key: str, default: str = None, **kwargs) -> str:
    """Global helper for text translation."""
    return i18n.t(key, default, **kwargs)
