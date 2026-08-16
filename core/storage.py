"""
Storage manager for Twinclers Guard.

SECURITY PATCHES APPLIED:
  VLN-03: HMAC-SHA256 signature on database.json using Windows Machine GUID
  VLN-10: Restrict database.json file permissions to current user only
"""

import os
import json
import hmac
import hashlib
import ctypes
import ctypes.wintypes
from datetime import datetime
from typing import List, Dict, Optional


import ctypes
from ctypes import wintypes
import secrets

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

crypt32 = ctypes.windll.crypt32
kernel32 = ctypes.windll.kernel32

def dpapi_encrypt(data: bytes) -> bytes:
    in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    if not crypt32.CryptProtectData(ctypes.byref(in_blob), "TwinclersKey", None, None, None, 0, ctypes.byref(out_blob)):
        raise OSError("CryptProtectData failed")
    result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    kernel32.LocalFree(out_blob.pbData)
    return result

def dpapi_decrypt(cipher_bytes: bytes) -> bytes:
    in_blob = DATA_BLOB(len(cipher_bytes), ctypes.cast(ctypes.create_string_buffer(cipher_bytes), ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise OSError("CryptUnprotectData failed")
    result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    kernel32.LocalFree(out_blob.pbData)
    return result

def _get_or_create_secure_key(db_path: str) -> bytes:
    """Retrieves or creates a DPAPI-protected HMAC key."""
    key_path = db_path + ".key"
    try:
        with open(key_path, 'rb') as f:
            return dpapi_decrypt(f.read())
    except (OSError, Exception):
        new_key = secrets.token_bytes(32)
        try:
            with open(key_path, 'wb') as f:
                f.write(dpapi_encrypt(new_key))
        except OSError:
            pass
        return new_key


def _compute_hmac(payload_str: str, machine_key: bytes) -> str:
    """Computes HMAC-SHA256 from a JSON payload string."""
    return hmac.new(machine_key, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()


def _restrict_file_permissions(filepath: str):
    """
    VLN-10: Restrict database.json file permissions to current user only.
    Uses icacls via shell.
    """
    try:
        username = os.getenv('USERNAME', '')
        if username:
            import subprocess
            # Reset inheritance lalu set hanya current user yang punya akses
            subprocess.run(
                ['icacls', filepath, '/inheritance:r', '/grant:r', f'{username}:F'],
                capture_output=True, check=False
            )
    except OSError:
        pass


class StorageManager:
    def __init__(self, custom_path: Optional[str] = None):
        if custom_path:
            self.db_path = custom_path
        else:
            appdata = os.getenv('APPDATA') or os.path.expanduser('~')
            data_dir = os.path.join(appdata, 'TwinclersGuard')
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, 'database.json')

        self.data: Dict[str, Dict] = {}
        self.settings: Dict[str, any] = {"language": "en"}
        self._machine_key = _get_or_create_secure_key(self.db_path)
        self._hmac_tampered = False
        self.load()

    def load(self):
        """Loads database from JSON file with enforced HMAC verification."""
        if not os.path.exists(self.db_path):
            self.data, self.settings = {}, {"language": "en"}
            return

        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)

            if not isinstance(raw, dict):
                raise ValueError("Invalid database format")

            stored_hmac = raw.pop("_hmac", None)
            if not stored_hmac and len(raw) > 0:
                self._hmac_tampered = True
                raise ValueError("HMAC signature missing")

            payload_str = json.dumps({k: v for k, v in raw.items()}, sort_keys=True, ensure_ascii=False)
            expected_hmac = _compute_hmac(payload_str, self._machine_key)
            
            if not hmac.compare_digest(stored_hmac, expected_hmac):
                self._hmac_tampered = True
                raise ValueError("HMAC verification failed")

            self.settings = raw.get("_settings", {"language": "en"})
            self.data = {k: v for k, v in raw.items() if k != "_settings"}
            
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"[Storage] Tampering or corruption detected: {e}")
            self.data, self.settings = {}, {"language": "en"}
            # Jika corrupt/tampered, kita bisa backup file-nya
            try:
                import shutil
                shutil.copy(self.db_path, self.db_path + ".corrupted")
            except OSError:
                pass

    def save(self):
        """Saves database to JSON file atomically with HMAC signature."""
        try:
            payload = dict(self.data)
            payload["_settings"] = self.settings

            payload_str = json.dumps(
                {k: v for k, v in payload.items()},
                sort_keys=True, ensure_ascii=False
            )
            payload["_hmac"] = _compute_hmac(payload_str, self._machine_key)

            import tempfile
            tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self.db_path))
            try:
                with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.db_path)
            except OSError:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            _restrict_file_permissions(self.db_path)

        except OSError as e:
            print(f"[Storage] Error saving database: {e}")

    def is_tampered(self) -> bool:
        """VLN-03: Returns True if HMAC does not match upon loading."""
        return self._hmac_tampered

    def get_language(self) -> str:
        return self.settings.get("language", "en")

    def set_language(self, lang_code: str):
        self.settings["language"] = lang_code
        self.save()

    def normalize_path(self, path: str) -> str:
        return os.path.abspath(os.path.normpath(path))

    def get_all(self) -> List[Dict]:
        return list(self.data.values())

    def get_item(self, path: str) -> Optional[Dict]:
        norm_path = self.normalize_path(path)
        return self.data.get(norm_path)

    def add_item(self, path: str, mode: str = "anti_delete") -> Dict:
        norm_path = self.normalize_path(path)
        is_dir = os.path.isdir(norm_path)
        item = {
            "path": norm_path,
            "type": "folder" if is_dir else "file",
            "status": "unprotected",
            "mode": mode,
            "date_added": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "original_acl_sddl": None,
            "note": ""
        }
        self.data[norm_path] = item
        self.save()
        return item

    def update_item(self, path: str, **kwargs) -> Optional[Dict]:
        norm_path = self.normalize_path(path)
        if norm_path in self.data:
            self.data[norm_path].update(kwargs)
            self.data[norm_path]["last_updated"] = datetime.now().isoformat()
            self.save()
            return self.data[norm_path]
        else:
            # Buat entry baru jika belum ada (untuk portabel vault)
            is_dir = os.path.isdir(norm_path)
            item = {
                "path": norm_path,
                "type": "folder" if is_dir else "file",
                "status": "unprotected",
                "mode": "anti_delete",
                "date_added": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "original_acl_sddl": None,
                "note": ""
            }
            item.update(kwargs)
            self.data[norm_path] = item
            self.save()
            return item

    def remove_item(self, path: str) -> bool:
        norm_path = self.normalize_path(path)
        if norm_path in self.data:
            del self.data[norm_path]
            self.save()
            return True
        return False


# Global storage instance
storage = StorageManager()
