"""
Internationalization (i18n) Module for Twinclers Guard.
Supports multi-language with English (en) as default, and can be switched to Indonesian (id) or other languages.
"""

import os
import json
from typing import Dict, List, Tuple, Callable

class I18nManager:
    def __init__(self, default_lang: str = "en"):
        self.current_lang = default_lang
        self.locales_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")
        self.translations: Dict[str, Dict[str, str]] = {}
        self.callbacks: List[Callable[[str], None]] = []
        
        self.load_all_translations()

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
