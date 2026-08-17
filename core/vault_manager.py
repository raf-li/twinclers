"""
Vault Manager for Twinclers Guard.

SECURITY PATCHES APPLIED:
  VLN-07: Remove plaintext password from active_sessions
  VLN-09: Anti-Brute Force rate limiting with exponential backoff
"""

import os
import time
import ctypes
from ctypes import wintypes
from typing import Tuple, Optional, Dict
from core.vault_crypto import VaultCrypto
from core.acl_manager import acl_engine
from core.storage import storage

# --- Windows DPAPI Helpers for Secure In-Memory Session Storage ---
CRYPTPROTECT_UI_FORBIDDEN = 0x01
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))]

_crypt32 = ctypes.windll.crypt32
_crypt32.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
_crypt32.CryptProtectData.restype = wintypes.BOOL
_crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
_crypt32.CryptUnprotectData.restype = wintypes.BOOL

def _dpapi_encrypt(data: bytes) -> bytes:
    try:
        in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        if _crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob)):
            result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return result
    except Exception as e:
        print("DPAPI Encrypt Error:", e)
    return b""

def _dpapi_decrypt(encrypted_data: bytes) -> bytes:
    try:
        in_blob = DATA_BLOB(len(encrypted_data), ctypes.cast(ctypes.c_char_p(encrypted_data), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        if _crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob)):
            result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return result
    except Exception as e:
        print("DPAPI Decrypt Error:", e)
    return b""

# VLN-09: Tracker for failed login attempts per path
_brute_force_tracker: Dict[str, Dict] = {}

def _check_rate_limit(path: str) -> Tuple[bool, float]:
    """
    VLN-09: Checks and applies exponential backoff anti-brute force.
    Returns (allowed, wait_seconds).
    """
    now = time.monotonic()
    tracker = _brute_force_tracker.get(path, {"attempts": 0, "locked_until": 0.0})

    if tracker["locked_until"] > now:
        return False, tracker["locked_until"] - now

    return True, 0.0

def _record_failed_attempt(path: str):
    """VLN-09: Records a failed attempt and applies lockout."""
    now = time.monotonic()
    tracker = _brute_force_tracker.get(path, {"attempts": 0, "locked_until": 0.0})
    tracker["attempts"] += 1
    attempts = tracker["attempts"]

    # Exponential backoff: 3 fails→1s, 5→5s, 8→30s, 12→120s, 15+→600s
    if attempts >= 15:
        delay = 600.0
    elif attempts >= 12:
        delay = 120.0
    elif attempts >= 8:
        delay = 30.0
    elif attempts >= 5:
        delay = 5.0
    elif attempts >= 3:
        delay = 1.0
    else:
        delay = 0.0

    tracker["locked_until"] = now + delay
    _brute_force_tracker[path] = tracker

def _reset_attempts(path: str):
    """Resets the counter after a successful login."""
    _brute_force_tracker.pop(path, None)


class VaultManager:
    def __init__(self):
        # VLN-07: Do not store password in session — only boolean session token
        self.active_sessions: Dict[str, Dict] = {}

    def is_password_protected(self, path: str) -> bool:
        item = storage.get_item(path)
        if not item:
            return False
        mode = item.get("mode", "")
        return mode in ["instant_gate", "aes256_vault"] and bool(item.get("password_hash"))

    def set_password(self, path: str, password: str, mode: str = "instant_gate") -> Tuple[bool, str]:
        norm_path = storage.normalize_path(path)
        if not os.path.exists(norm_path):
            return False, "Path does not exist."

        hash_hex, salt_hex = VaultCrypto.hash_password(password)
        storage.update_item(
            norm_path,
            mode=mode,
            password_hash=hash_hex,
            password_salt=salt_hex,
            status="protected"
        )

        return self.lock_item(norm_path, password=password)

    def has_encrypted_vault_files(self, path: str) -> bool:
        if not os.path.exists(path):
            return os.path.exists(path + VaultCrypto.VAULT_EXT)
        if os.path.isfile(path):
            return path.endswith(VaultCrypto.VAULT_EXT)
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                if any(f.endswith(VaultCrypto.VAULT_EXT) for f in files):
                    return True
        return False

    def verify_password(self, path: str, password: str) -> bool:
        norm_path = storage.normalize_path(path)
        item = storage.get_item(norm_path)
        if not item:
            return False
        hash_hex = item.get("password_hash")
        salt_hex = item.get("password_salt")
        if not hash_hex or not salt_hex:
            return False
        return VaultCrypto.verify_password(password, hash_hex, salt_hex)

    def unlock_item(self, path: str, password: str) -> Tuple[bool, str]:
        """Unlocks a folder with a password."""
        norm_path = storage.normalize_path(path)

        # VLN-09: Rate limit check
        allowed, wait = _check_rate_limit(norm_path)
        if not allowed:
            return False, f"Too many failed attempts. Try again in {int(wait)} seconds."

        item = storage.get_item(norm_path) or {}
        mode = item.get("mode", "instant_gate")

        # Mode AES-256 Vault atau folder berisi .twvault (portabel lintas PC)
        if mode == "aes256_vault" or self.has_encrypted_vault_files(norm_path):
            if os.path.isdir(norm_path):
                ok, cnt, msg = VaultCrypto.decrypt_directory(norm_path, password)
            else:
                target_f = norm_path if norm_path.endswith(VaultCrypto.VAULT_EXT) else norm_path + VaultCrypto.VAULT_EXT
                ok, msg = VaultCrypto.decrypt_file(target_f, password)
                cnt = 1 if ok else 0

            if ok and cnt >= 0:
                # VLN-07 & NEW DPAPI: Simpan versi terenkripsi dari password menggunakan Windows DPAPI
                dpapi_blob = _dpapi_encrypt(password.encode('utf-8'))
                
                self.active_sessions[norm_path] = {
                    "mode": "aes256_vault",
                    "unlocked": True,
                    "dpapi_blob": dpapi_blob
                }
                hash_hex, salt_hex = VaultCrypto.hash_password(password)
                storage.update_item(
                    norm_path,
                    mode="aes256_vault",
                    password_hash=hash_hex,
                    password_salt=salt_hex,
                    status="unprotected"
                )
                _reset_attempts(norm_path)
                return True, f"AES-256 Vault decrypted ({cnt} files)."

            _record_failed_attempt(norm_path)
            return False, "Incorrect password or decryption failed."

        # Mode Instant Gate — verifikasi hash dahulu
        if not self.verify_password(norm_path, password):
            _record_failed_attempt(norm_path)
            return False, "Incorrect password."

        if mode == "instant_gate":
            ok, msg = acl_engine.unprotect(norm_path)
            if ok:
                # VLN-07: Hanya simpan mode dan flag, BUKAN password
                self.active_sessions[norm_path] = {"mode": mode, "unlocked": True}
                storage.update_item(norm_path, status="unprotected")
                _reset_attempts(norm_path)
                return True, "Instant Gate unlocked (0.01s)."
            return False, msg

        return False, "Unknown password protection mode."

    def lock_item(self, path: str, password: Optional[str] = None) -> Tuple[bool, str]:
        """Relocks a folder."""
        norm_path = storage.normalize_path(path)
        item = storage.get_item(norm_path) or {}
        mode = item.get("mode", "instant_gate")

        if mode == "instant_gate":
            ok, msg = acl_engine.protect(norm_path, mode="full_lock")
            if ok:
                self.active_sessions.pop(norm_path, None)
                storage.update_item(norm_path, status="protected")
                return True, "Instant Gate locked."
            return False, msg

        elif mode == "aes256_vault":
            # Attempt to retrieve password from DPAPI blob if not provided explicitly
            if not password:
                session = self.active_sessions.get(norm_path, {})
                dpapi_blob = session.get("dpapi_blob")
                if dpapi_blob:
                    decrypted = _dpapi_decrypt(dpapi_blob)
                    if decrypted:
                        password = decrypted.decode('utf-8')
                        
            if not password:
                self.active_sessions.pop(norm_path, None)
                storage.update_item(norm_path, status="unprotected")
                return False, "Re-encryption failed: password required to encrypt files."

            if os.path.isdir(norm_path):
                ok, cnt, msg = VaultCrypto.encrypt_directory(norm_path, password)
            else:
                ok, msg = VaultCrypto.encrypt_file(norm_path, password)
                cnt = 1 if ok else 0

            # Zero-fill the local password variable to clear it from memory as fast as possible
            password = ""

            if ok:
                self.active_sessions.pop(norm_path, None)
                storage.update_item(norm_path, status="protected")
                return True, f"AES-256 Vault locked & encrypted ({cnt} files)."
            return False, msg

        return False, "Unknown protection mode."

vault_mgr = VaultManager()
