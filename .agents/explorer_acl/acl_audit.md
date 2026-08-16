# Technical Security & Windows ACL Audit Report: Twinclers Guard

## 1. Executive Summary
This report provides a deep technical analysis of Windows NTFS ACL enforcement, system calls, privilege boundaries, process communication, and file security mechanisms in the Twinclers Guard codebase.

The audit identified critical and high-severity security issues across multiple modules, including unauthenticated local IPC socket execution, arbitrary PowerShell command injection in SDDL retrieval, unencrypted file exposure during AES-256 vault auto-relock, ACL inheritance bypasses, hardlink/reparse point data destruction risks during file wiping, and password gate bypasses in system tray handlers.

---

## 2. Comprehensive Findings

### 2.1 Critical Severity

#### SEC-ACL-01: Remote / Local Command Execution via PowerShell String Interpolation in SDDL Retrieval
- **Target File**: `D:/Twinclers/core/acl_manager.py` (Lines 33–40)
- **Component**: `ACLManager.get_acl_sddl(path)`
- **Severity**: **Critical**
- **Vulnerability Description**:
  The `get_acl_sddl` method constructs a PowerShell command using direct f-string interpolation:
  ```python
  norm_path = os.path.abspath(path)
  ps_script = f"(Get-Acl -LiteralPath '{norm_path}').GetSecurityDescriptorSddlForm('All')"
  code, stdout, _ = cls.run_command(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script])
  ```
  Because `norm_path` is enclosed in single quotes inside `ps_script` without escaping or parameterization, any file or directory path containing single quotes and command separators (e.g., `test'; Start-Process calc.exe; '` or `C:\folder' -and $true; iex(...)`) breaks out of the string literal. When `powershell.exe` executes `-Command`, it evaluates the injected PowerShell payload with the privileges of the active user.
- **Impact**: Arbitrary command execution under the user's execution context when inspecting or backing up ACLs on maliciously named paths.
- **Remediation**:
  Replace external PowerShell invocation with native Win32 APIs via `ctypes` (`advapi32.GetNamedSecurityInfoW` and `advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW`) or `win32security`. If PowerShell must remain as a fallback, pass parameters through script arguments rather than string interpolation:
  ```python
  import ctypes
  from ctypes import wintypes

  # Native Win32 API implementation using advapi32
  advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
  kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

  # SE_FILE_OBJECT = 1
  # OWNER_SECURITY_INFORMATION | GROUP_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION | SACL_SECURITY_INFORMATION = 0xF
  ```

---

#### SEC-ACL-02: Unauthenticated Local TCP Socket Allowing Arbitrary Command Triggering (Port 49152)
- **Target File**: `D:/Twinclers/main.py` (Lines 118–128) & `D:/Twinclers/gui/main_window.py` (Lines 85–161)
- **Component**: IPC Server & Single Instance Handler
- **Severity**: **Critical**
- **Vulnerability Description**:
  The application creates a TCP server listening on `127.0.0.1:49152` without authentication, HMAC handshake, or access tokens.
  When data arrives:
  ```python
  args_list = json.loads(data.decode('utf-8'))
  wx.CallAfter(self.process_ipc_args, args_list)
  ```
  `process_ipc_args` parses arguments such as `--protect`, `--unprotect`, `--add`, and `--mode`.
  Any local process running under any user account (or low-integrity sandbox on the system) can connect to `127.0.0.1:49152` and send crafted JSON payloads.
- **Impact**:
  - Denial of Service: An attacker can send `["--protect", "C:\\Users\\<Target>\\Documents", "--mode", "full_lock"]` to lock user folders with `Deny Everyone (F)`.
  - State Tampering: An attacker can flood the monitored database list or invoke unprotect triggers.
- **Remediation**:
  1. Replace the TCP socket with a Windows Named Pipe (`\\.\pipe\TwinclersGuard_<UserSID>`) secured with a DACL allowing only the current user SID.
  2. If maintaining a socket, generate a cryptographically random 256-bit authentication token on startup, store it in memory/restricted user directory, and require the token in every IPC request header.

---

#### SEC-ACL-03: AES-256 Vault Auto-Relock False Protection (Plaintext File Exposure)
- **Target File**: `D:/Twinclers/core/vault_manager.py` (Lines 184–193), `D:/Twinclers/core/explorer_monitor.py` (Lines 85–92), `D:/Twinclers/gui/main_window.py` (Lines 551–564)
- **Component**: `VaultManager.lock_item()` & `ExplorerMonitor._monitor_loop()`
- **Severity**: **Critical**
- **Vulnerability Description**:
  When `lock_item` is called without providing a password for `aes256_vault` (e.g. during Explorer auto-relock or when locking from the UI):
  ```python
  elif mode == "aes256_vault":
      if not password:
          self.active_sessions.pop(norm_path, None)
          storage.update_item(norm_path, status="protected")
          return True, "Session cleared. Files remain decrypted until app provides password."
  ```
  The function clears the session and sets `status="protected"` in `database.json`, but does NOT re-encrypt the files on disk!
  The GUI list updates to show the folder as `Locked / Protected`, and NVDA speaks `Folder has been automatically locked`.
  However, all files in the directory remain unencrypted plaintext files on disk indefinitely.
- **Impact**: Complete confidentiality failure. Users believe their sensitive files are encrypted and safe, while any attacker with filesystem access can read the files.
- **Remediation**:
  - Do NOT mark status as `protected` when re-encryption does not occur. Set status to `unprotected` or `needs_relock_password`.
  - Prompt the user with a mandatory password dialog when relocking, OR securely retain a session key in memory using Windows `CryptProtectMemory` during the active unlocked session to enable automatic re-encryption on Explorer close.

---

### 2.2 High Severity

#### SEC-ACL-04: Owner Privilege Retention (WRITE_DAC / WRITE_OWNER Bypass)
- **Target File**: `D:/Twinclers/core/acl_manager.py` (Lines 82–154)
- **Component**: `ACLManager.protect()`
- **Severity**: **High**
- **Vulnerability Description**:
  Under the Windows NT security architecture, the Creator/Owner of an NTFS object always retains implicit `READ_CONTROL` and `WRITE_DAC` permissions.
  When `ACLManager.protect` applies a Deny ACE for `*S-1-1-0` (Everyone), the owner of the folder or file can override or remove the Deny rule at any time by calling `icacls <path> /grant %USERNAME%:F` or `icacls <path> /remove:d *S-1-1-0` directly in CMD/PowerShell without administrator privileges and without knowing the Twinclers Guard master password.
- **Impact**: Standard users who own files can bypass all NTFS ACL deny rules (anti-delete, read-only, instant gate) without application authorization.
- **Remediation**:
  - For enterprise / administrative protection, provide an option to change object ownership to `BUILTIN\Administrators` or `NT AUTHORITY\SYSTEM` and strip `WRITE_DAC` from standard users.
  - Document in the security specification that NTFS ACL Deny rules are protection guards against accidental actions and unprivileged standard tools, while cryptographic secrecy requires `aes256_vault` mode.

---

#### SEC-ACL-05: Deny Everyone (F) Blocks SYSTEM Services, Antivirus Scanners, and OS Backups
- **Target File**: `D:/Twinclers/core/acl_manager.py` (Lines 123–127)
- **Component**: `ACLManager.protect(..., mode="full_lock")`
- **Severity**: **High**
- **Vulnerability Description**:
  Applying `*S-1-1-0:(OI)(CI)(F)` denies Full Control to the `Everyone` group.
  In Windows, `Everyone` includes `NT AUTHORITY\SYSTEM`, `BUILTIN\Administrators`, `LOCAL SERVICE`, and security services.
  Consequently:
  1. Windows Defender and 3rd party antivirus engines cannot scan files in the locked folder.
  2. Volume Shadow Copy (VSS) and system backup services fail when attempting to read the directory.
  3. If database metadata is lost or corrupted, even an Administrator cannot open or manage the directory without taking ownership (`takeown /f`) and rebuilding the ACL.
- **Impact**: System backup failures, antivirus blind spots, and administrative lockout risks.
- **Remediation**:
  Apply Deny ACEs targeting `BUILTIN\Users` (`S-1-5-32-545`) or the specific user SID, while explicitly ensuring Allow ACEs remain intact for `NT AUTHORITY\SYSTEM` (`S-1-5-18`) and `BUILTIN\Administrators` (`S-1-5-32-544`).

---

#### SEC-ACL-06: Hardlink and Reparse Point (Symlink) Target Destruction in `_secure_delete`
- **Target File**: `D:/Twinclers/core/vault_crypto.py` (Lines 38–57)
- **Component**: `VaultCrypto._secure_delete(filepath)`
- **Severity**: **High**
- **Vulnerability Description**:
  `_secure_delete` opens `filepath` in `'r+b'` mode and writes 3 passes of random bytes before unlinking:
  ```python
  with open(filepath, 'r+b') as f:
      for _ in range(3):
          f.seek(0)
          f.write(secrets.token_bytes(size))
          f.flush()
          os.fsync(f.fileno())
  ```
  If `filepath` is an NTFS Hardlink pointing to another user file or system file, overwriting the file data destroys the contents of all linked paths.
  If `filepath` is a junction or symlink, opening it with `'r+b'` opens the target file across the link and overwrites its contents.
  Additionally, if `filepath` has a read-only attribute or is locked by another handle, `open('r+b')` raises `PermissionError` which is caught by `except OSError: pass`. The subsequent `os.remove` fails silently, leaving the plaintext file on disk alongside the encrypted `.twvault` file.
- **Impact**: Data loss on linked files, silent failure to wipe original files after encryption.
- **Remediation**:
  1. Inspect file attributes before opening. If `os.path.islink(filepath)` or `GetFileAttributes` indicates `FILE_ATTRIBUTE_REPARSE_POINT`, remove the symlink/reparse point without writing into target data.
  2. Check hardlink count via `GetFileInformationByHandle` (`nNumberOfLinks`). If `nNumberOfLinks > 1`, do not overwrite in place; unlink directly.
  3. Verify file deletion. If `_secure_delete` or `os.remove` fails, raise an exception, delete the `.twvault` file, and inform the user.

---

#### SEC-ACL-07: Unrestricted Tray Icon `on_unprotect_all` Password Bypass
- **Target File**: `D:/Twinclers/gui/tray_icon.py` (Lines 102–109)
- **Component**: `TwinclersTrayIcon.on_unprotect_all()`
- **Severity**: **High**
- **Vulnerability Description**:
  In `gui/tray_icon.py`:
  ```python
  def on_unprotect_all(self, event):
      items = storage.get_all()
      for it in items:
          acl_engine.unprotect(it["path"])
          storage.update_item(it["path"], status="unprotected")
      self.frame.refresh_list()
      speaker.speak(_("ANNOUNCE_UNPROTECT_ALL"))
  ```
  The tray icon context menu exposes an "Unprotect All" option that directly executes `acl_engine.unprotect()` on all monitored paths without password prompt, confirmation modal, or verification of protection mode.
- **Impact**: Anyone with access to the system tray can unprotect all items with two mouse clicks, bypassing password verification.
- **Remediation**:
  Forward the tray menu event to `MainWindow.on_unprotect_all()`, which enforces confirmation and skips password-gated vault folders.

---

#### SEC-ACL-08: TOCTOU and Monitoring Blind Spots in Explorer Watcher
- **Target File**: `D:/Twinclers/core/explorer_monitor.py` (Lines 45–114)
- **Component**: `ExplorerMonitor._monitor_loop()`
- **Severity**: **High**
- **Vulnerability Description**:
  The `ExplorerMonitor` uses a 0.2-second polling loop against COM `Shell.Application.Windows()`.
  This approach has two major security gaps:
  1. **Time-of-Check to Time-of-Use (TOCTOU)**: There is a ~200ms latency window between when an Explorer window navigates to a folder and when the password dialog modal is displayed.
  2. **Process Blind Spot**: `Shell.Application` only tracks GUI Explorer windows. It has zero visibility into accesses originating from CMD, PowerShell, WSL, 3rd-party file managers (Total Commander, 7-Zip, Far Manager), or background scripts.
  3. **Global Permission Dropping**: In `instant_gate` mode, unlocking a folder removes the NTFS Deny ACE globally. While Explorer is browsing the folder, all processes on the system gain full access.
- **Impact**: Protection is bypassed by non-Explorer tools, and brief race windows exist during window opening.
- **Remediation**:
  Clarify in the user documentation that `instant_gate` is an access helper for Explorer workflows, and `aes256_vault` must be used when cryptographic confidentiality against other processes is required.

---

### 2.3 Medium Severity

#### SEC-ACL-09: Unbounded In-Memory File Reads Causing Memory Exhaustion (DoS)
- **Target File**: `D:/Twinclers/core/vault_crypto.py` (Lines 122–124, 170–175)
- **Component**: `VaultCrypto.encrypt_file()` & `VaultCrypto.decrypt_file()`
- **Severity**: **Medium**
- **Vulnerability Description**:
  The cryptographic routines load entire files into memory in a single step:
  ```python
  with open(filepath, 'rb') as f:
      data = f.read()
  ```
  Encrypting or decrypting large files (e.g., ISO images, virtual disks, database dumps exceeding available RAM) causes a `MemoryError` crash, aborts the operation mid-transaction, and leaves temporary files in the directory.
- **Impact**: Denial of service and application crashes when handling large files.
- **Remediation**:
  Implement chunked AEAD processing (e.g., 64KB / 1MB stream chunks with chunk counters in AAD) or use cryptographic streaming envelopes.

---

#### SEC-ACL-10: Insecure Storage HMAC Key from World-Readable MachineGuid
- **Target File**: `D:/Twinclers/core/storage.py` (Lines 19–35, 77–96)
- **Component**: `_get_machine_guid()` & `_compute_hmac()`
- **Severity**: **Medium**
- **Vulnerability Description**:
  The database HMAC signature is calculated using `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`.
  This registry key is readable by every non-elevated user on the system. Any local script or user can read `MachineGuid`, modify `database.json` (altering mode, paths, or password hashes), and compute a valid HMAC signature.
- **Impact**: Database integrity protection can be forged by any local user.
- **Remediation**:
  Use Windows DPAPI (`CryptProtectData` / `CryptUnprotectData` via `ctypes.windll.crypt32`) to encrypt the database or generate a user-bound master secret.

---

#### SEC-ACL-11: Brittle Substring Matching in `check_protection_status`
- **Target File**: `D:/Twinclers/core/acl_manager.py` (Lines 59–73)
- **Component**: `ACLManager.check_protection_status()`
- **Severity**: **Medium**
- **Vulnerability Description**:
  The method parses raw text from `icacls` using substring checks:
  `if ":(denied)" in stdout_lower or "(de,dc)" in stdout_lower or "(f)" in stdout_lower:`
  If a folder path or account name contains `(f)` or `(de)` (e.g. `D:\Data (Full)\...`), this logic misidentifies the protection mode.
- **Impact**: Incorrect UI status indicators and faulty protection logic branch execution.
- **Remediation**:
  Use structured Win32 security APIs (`GetNamedSecurityInfoW`) to inspect ACE masks directly.

---

#### SEC-ACL-12: Uninstaller Does Not Unlock Protected Folders
- **Target File**: `D:/Twinclers/build_scripts/setup.iss` (Line 24) & `D:/Twinclers/main.py` (Lines 96–98)
- **Component**: Inno Setup Uninstall Handler
- **Severity**: **Medium**
- **Vulnerability Description**:
  When the application is uninstalled with `--uninstall-cleanup`, only the context menu registry keys are removed. Monitored folders locked with `full_lock` or `anti_delete` are not unlocked.
  After uninstallation, users find their folders locked by `Deny Everyone` with no Twinclers Guard GUI available to unlock them.
- **Impact**: User data remains locked and inaccessible after uninstalling.
- **Remediation**:
  Add an uninstallation routine that enumerates `storage.get_all()` and removes Deny ACEs, or prompts the user before removing application binaries.

---

#### SEC-ACL-13: Inconsistent Tray Icon `on_protect_all` Mode Execution
- **Target File**: `D:/Twinclers/gui/tray_icon.py` (Lines 94–101)
- **Component**: `TwinclersTrayIcon.on_protect_all()`
- **Severity**: **Medium**
- **Vulnerability Description**:
  `TwinclersTrayIcon.on_protect_all` invokes `acl_engine.protect(it["path"], mode=it.get("mode", "anti_delete"))` for all items and sets `status="protected"` without checking if the mode is `aes256_vault`.
  `acl_engine.protect` returns an error for `aes256_vault`, but storage still marks the item as protected.
- **Impact**: Inconsistent database state and false protection indicator in the UI.
- **Remediation**:
  Standardize `on_protect_all` handling through `MainWindow` or `VaultManager`.

---

### 2.4 Low Severity

#### SEC-ACL-14: Non-Atomic Database File Save
- **Target File**: `D:/Twinclers/core/storage.py` (Lines 125–130)
- **Component**: `StorageManager.save()`
- **Severity**: **Low**
- **Vulnerability Description**:
  `save()` opens `self.db_path` directly with `'w'`. If the process crashes or loses power during `json.dump`, `database.json` is corrupted or truncated to zero bytes.
- **Impact**: Loss of monitored path configurations on sudden termination.
- **Remediation**:
  Write to a temporary file (`database.json.tmp`) and use `os.replace()` for atomic commit.

#### SEC-ACL-15: Missing Quotes Around Username in `_restrict_file_permissions`
- **Target File**: `D:/Twinclers/core/storage.py` (Lines 42–58)
- **Component**: `_restrict_file_permissions()`
- **Severity**: **Low**
- **Vulnerability Description**:
  `subprocess.run(['icacls', filepath, '/inheritance:r', '/grant:r', f'{username}:F'])` fails when `username` contains whitespace.
- **Impact**: ACL restriction fails silently for users with space-separated account names.
- **Remediation**:
  Enclose username in quotes or resolve to User SID (`*S-1-5-...`).

---

## 3. Summary Classification Table

| ID | Module | Severity | Vulnerability Summary |
|---|---|---|---|
| SEC-ACL-01 | `core/acl_manager.py:33-40` | **Critical** | PowerShell string interpolation command injection in SDDL retrieval |
| SEC-ACL-02 | `main.py:118-128`, `gui/main_window.py:85-161` | **Critical** | Unauthenticated local TCP IPC socket allowing arbitrary action execution |
| SEC-ACL-03 | `core/vault_manager.py:184-193`, `core/explorer_monitor.py:85-92` | **Critical** | AES-256 vault auto-relock marks status as locked while files remain plaintext |
| SEC-ACL-04 | `core/acl_manager.py:82-154` | **High** | Object Owner retains implicit `WRITE_DAC`, bypassing NTFS Deny ACEs |
| SEC-ACL-05 | `core/acl_manager.py:123-127` | **High** | `Deny Everyone (F)` blocks SYSTEM, Windows Defender, and OS backups |
| SEC-ACL-06 | `core/vault_crypto.py:38-57` | **High** | Hardlink/Reparse Point target destruction & silent wipe failure in `_secure_delete` |
| SEC-ACL-07 | `gui/tray_icon.py:102-109` | **High** | System Tray "Unprotect All" unprotects items without password verification |
| SEC-ACL-08 | `core/explorer_monitor.py:45-114` | **High** | Explorer active window monitor TOCTOU race condition and process blind spots |
| SEC-ACL-09 | `core/vault_crypto.py:122-124` | **Medium** | Unbounded in-memory file reading causes MemoryError DoS on large files |
| SEC-ACL-10 | `core/storage.py:19-35` | **Medium** | MachineGuid is world-readable, allowing local forgery of HMAC signatures |
| SEC-ACL-11 | `core/acl_manager.py:59-73` | **Medium** | Brittle substring matching in `check_protection_status` produces false results |
| SEC-ACL-12 | `build_scripts/setup.iss:24`, `main.py:96-98` | **Medium** | Uninstaller cleanup leaves folders permanently locked |
| SEC-ACL-13 | `gui/tray_icon.py:94-101` | **Medium** | Tray `on_protect_all` records false success for `aes256_vault` mode |
| SEC-ACL-14 | `core/storage.py:125-130` | **Low** | Direct non-atomic file writing to `database.json` risks truncation |
| SEC-ACL-15 | `core/storage.py:42-58` | **Low** | Unquoted username in `_restrict_file_permissions` breaks for accounts with spaces |
