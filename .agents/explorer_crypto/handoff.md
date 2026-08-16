# Crypto & Security Audit Handoff Report

## 1. Observation
Direct source code inspection across `core/`, `gui/`, and `main.py` revealed the following technical facts:

1. **Unauthenticated IPC Socket**:
   - `gui/main_window.py:91-109`: `s.bind(('127.0.0.1', 49152))` listens for raw TCP connections and receives JSON CLI commands without authentication tokens, PID verification, or access control.
   - `gui/main_window.py:134-152`: On receiving `--unprotect <path>`, it directly calls `self.on_unprotect_selected(None)`, unlocking non-password items immediately without user confirmation.

2. **AES-256 Vault False Relock**:
   - `core/vault_manager.py:187-193`: When `mode == "aes256_vault"` and `password is None`, `lock_item()` executes:
     `self.active_sessions.pop(norm_path, None)`
     `storage.update_item(norm_path, status="protected")`
     `return True, "Session cleared. Files remain decrypted until app provides password."`
   - `core/explorer_monitor.py:86-89`: When Explorer closes, `vault_mgr.lock_item(unlocked_path)` is called without a password. The speaker announces folder locked and the GUI marks it `[LOCKED]`, but the files remain raw unencrypted plaintext on disk.

3. **Storage HMAC Verification Bypass & Ignored Flags**:
   - `core/storage.py:85-96`: `stored_hmac = raw.pop("_hmac", None)`. If `_hmac` is missing, `if stored_hmac:` skips HMAC verification entirely.
   - `core/storage.py:93-103`: When `hmac.compare_digest` fails, `self._hmac_tampered = True` is set, but `self.data` and `self.settings` are still populated with tampered JSON. `storage.is_tampered()` is never checked elsewhere in the codebase.
   - `core/storage.py:19-35`: Machine HMAC key is read from `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`, which is world-readable by any non-admin process on Windows.

4. **In-Memory Buffering & Large File Crash Risk**:
   - `core/vault_crypto.py:122-130`, `170-175`: Entire files are read into RAM via `f.read()` and passed directly to `AESGCM.encrypt()` / `decrypt()`, creating high memory pressure on large files (>2GB) and risking `MemoryError` crashes during encryption.

5. **PowerShell Injection in SDDL Backup**:
   - `core/acl_manager.py:35-37`: `ps_script = f"(Get-Acl -LiteralPath '{norm_path}').GetSecurityDescriptorSddlForm('All')"` breaks when `norm_path` contains single quotes (`'`).

6. **Cryptographic Primitives & Constants**:
   - `core/vault_crypto.py:22-25`: `SALT_SIZE = 16`, `NONCE_SIZE = 12`, `KEY_SIZE = 32`, `ITERATIONS = 200_000` using PBKDF2-HMAC-SHA256 and AES-GCM.
   - Constant-time verification is correctly used at `core/vault_crypto.py:68` (`secrets.compare_digest`), `core/vault_crypto.py:92` (`secrets.compare_digest`), and `core/storage.py:93` (`hmac.compare_digest`).

---

## 2. Logic Chain
1. **From Observation 1**: Because `gui/main_window.py` exposes an open TCP port on localhost that executes unlock actions on receipt of `--unprotect`, any unprivileged process or background malware on the machine can bypass Twinclers Guard's ACL protections without user interaction (Critical vulnerability SEC-01).
2. **From Observation 2**: Because `core/vault_manager.py:187-193` marks an AES-256 folder as `status="protected"` when relocked without a password, automated relock in `core/explorer_monitor.py` falsely announces and displays the folder as locked while leaving plaintext files on disk (Critical vulnerability SEC-02).
3. **From Observation 3**: Because `core/storage.py` does not require `_hmac` presence and loads data even after tamper detection using a key known to all local processes, the database integrity mechanism can be easily defeated by local processes (High vulnerabilities SEC-03, SEC-04, SEC-05).
4. **From Observation 4**: Because `core/vault_crypto.py` lacks chunked streaming encryption, large file encryption will trigger unhandled out-of-memory errors on client systems (High vulnerability SEC-06).
5. **From Observation 5**: Because `core/acl_manager.py` interpolates unescaped path strings into PowerShell commands, paths with single quotes cause command parsing failure (High vulnerability SEC-07).

---

## 3. Caveats
- Windows dynamic runtime testing was limited by static code analysis in the environment.
- Analysis focused on cryptography, authentication, storage, and IPC. GUI layout accessibility (NVDA screen reader tags) was reviewed only where security flows intersected (password dialogs, speech announcements).

---

## 4. Conclusion
The cryptographic algorithms used in `core/vault_crypto.py` (AES-256-GCM, PBKDF2HMAC-SHA256, `secrets.token_bytes`) are solid standard primitives. However, the application suffers from two **Critical** architectural vulnerabilities:
1. An open unauthenticated local TCP IPC socket that permits unauthorized removal of ACL protections.
2. A flawed AES-256 auto-relock mechanism that presents plaintext files as protected.

In addition, storage HMAC verification and PowerShell command generation contain **High** severity flaws that require immediate remediation before release.

---

## 5. Verification Method
1. **IPC Exploitation Test**:
   ```powershell
   # Protect D:\TestFolder in Anti-Delete mode
   # In another PowerShell window:
   $c = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 49152)
   $w = New-Object System.IO.StreamWriter($c.GetStream())
   $w.Write('["--unprotect", "D:\\TestFolder"]')
   $w.Flush()
   $c.Close()
   # Observe that D:\TestFolder ACL is removed without authorization.
   ```
2. **AES Relock Plaintext Inspection**:
   - Decrypt an AES-256 vault folder in Twinclers Guard.
   - Close the Explorer window.
   - Inspect the filesystem: verify whether original unencrypted files remain in the folder while GUI reports locked.
3. **HMAC Stripping Verification**:
   - Remove `"_hmac"` from `%APPDATA%\TwinclersGuard\database.json`.
   - Run the app and verify that no error or tamper warning is raised.
