# Twinclers Guard — Comprehensive Cryptographic & Security Audit Report

**Date**: 2026-08-17  
**Auditor**: Teamwork Crypto Security Explorer  
**Target Codebase**: Twinclers Guard (`core/`, `gui/`, `main.py`)  
**Scope**: Cryptography implementations, Key Derivation Functions (KDF), AES encryption & AEAD integrity, secret storage & credential lifecycle, constant-time comparisons, IPC security, and Windows security controls.

---

## Executive Summary

The Twinclers Guard codebase implements security controls across two distinct models:
1. **Windows NTFS Access Control Lists (ACL)** via `icacls` (Anti-Delete, Anti-Rename, Read-Only, Full Lock, Instant Gate).
2. **Authenticated Symmetric Cryptography** via AES-256-GCM and PBKDF2-HMAC-SHA256 (`core/vault_crypto.py`).

While the cryptographic primitives selected (`AESGCM` and `PBKDF2HMAC` from Python's standard `cryptography` hazmat library) are modern and secure, critical security vulnerabilities exist in **inter-process communication (IPC) authorization**, **AES vault relocking logic**, **storage HMAC integrity verification**, **PowerShell command construction**, and **in-memory secret handling**.

---

## Vulnerability Findings Matrix

| ID | Title | Severity | Impacted File & Lines |
|---|---|---|---|
| **SEC-01** | Unauthenticated Local TCP IPC Allows Arbitrary Protection Bypass | **Critical** | `gui/main_window.py:91-109`, `113-154` |
| **SEC-02** | AES-256 Vault Silent Relock Failure Leaves Plaintext Exposed on Disk | **Critical** | `core/vault_manager.py:184-205`, `core/explorer_monitor.py:85-92` |
| **SEC-03** | HMAC Stripping / Downgrade Attack on `database.json` | **High** | `core/storage.py:84-96` |
| **SEC-04** | Tampered Storage Payload Loaded Despite Verification Failure | **High** | `core/storage.py:93-103` |
| **SEC-05** | Storage HMAC Key Derived from World-Readable Registry MachineGuid | **High** | `core/storage.py:19-35` |
| **SEC-06** | Entire File In-Memory Buffering Causes RAM Exhaustion / DoS on Large Files | **High** | `core/vault_crypto.py:122-130`, `170-175` |
| **SEC-07** | PowerShell Injection via Unsanitized Paths in SDDL Form Retrieval | **High** | `core/acl_manager.py:33-41` |
| **SEC-08** | Absence of Domain Separation between Password Hash and AES Key | **Medium** | `core/vault_crypto.py:75-84`, `97-105` |
| **SEC-09** | XOR-Derived Header Obfuscation Ineffective Against Identification | **Medium** | `core/vault_crypto.py:27-28`, `59-69`, `137`, `177-179` |
| **SEC-10** | 3-Pass DoD Wipe Ineffective on Modern Wear-Leveled Flash/SSD Storage | **Medium** | `core/vault_crypto.py:38-56` |
| **SEC-11** | False Assurance of In-Memory Secret Zeroization in CPython | **Medium** | `core/vault_crypto.py:31-36`, `81-83`, `127-129`, `gui/password_dialog.py:103-105` |
| **SEC-12** | Missing Associated Authenticated Data (AAD) Binding in AES-GCM | **Low** | `core/vault_crypto.py:130`, `182` |
| **SEC-13** | Non-Atomic Database Write Risks File Corruption on Abrupt Exit | **Low** | `core/storage.py:125-127` |

---

## Detailed Vulnerability Analysis & Remediation

---

### SEC-01: Unauthenticated Local TCP IPC Allows Arbitrary Protection Bypass
- **Severity**: **Critical**
- **File**: `gui/main_window.py` (lines 91–109, 113–154)
- **CWE**: CWE-306 (Missing Authentication for Critical Function), CWE-284 (Improper Access Control)

#### Technical Explanation
`MainWindow.start_ipc_server` opens a listening TCP socket on `127.0.0.1:49152` to support single-instance context menu arguments. When a connection is accepted, `s.recv(4096)` directly parses incoming JSON without validating any authentication token, session cookie, process owner, or integrity secret.

```python
# gui/main_window.py:91-109
def _listen():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', IPC_PORT))
        s.listen()
        ...
        conn, addr = s.accept()
        with conn:
            data = conn.recv(4096)
            if data:
                args_list = json.loads(data.decode('utf-8'))
                wx.CallAfter(self.process_ipc_args, args_list)
```

In `process_ipc_args` (lines 134–152), if `args.unprotect` is present:
```python
elif action == "unprotect":
    self.on_unprotect_selected(None)
```
For non-password protected modes (such as Anti-Delete, Anti-Rename, Read-Only, and Full Lock), `on_unprotect_selected` immediately executes `acl_engine.unprotect(target_path)` without user confirmation. Any unprivileged process, script, or malware running under the user's desktop session can connect to `localhost:49152`, send `["--unprotect", "C:\\ProtectedFolder"]`, and strip all folder protections instantly.

#### Remediation Steps
1. Replace raw unauthenticated TCP sockets with Windows Named Pipes configured with strict discretionary access control lists (DACLs) restricted to the current user SID, or generate a random session secret key stored in memory/DPAPI that must be presented in every IPC packet.
2. In `process_ipc_args`, require explicit user confirmation via dialog or UI prompt before modifying access control rules triggered from external CLI/IPC messages.

---

### SEC-02: AES-256 Vault Silent Relock Failure Leaves Plaintext Exposed on Disk
- **Severity**: **Critical**
- **File**: `core/vault_manager.py` (lines 184–205), `core/explorer_monitor.py` (lines 85–92)
- **CWE**: CWE-311 (Missing Encryption of Sensitive Data), CWE-390 (Detection of Error Condition Without Action)

#### Technical Explanation
When an AES-256 vault folder is unlocked, `VaultCrypto.decrypt_directory` decrypts all `.twvault` files into plaintext on disk. When Windows Explorer is subsequently closed, `ExplorerMonitor` detects the window closure and triggers auto-relock:

```python
# core/explorer_monitor.py:86-89
ok, msg = vault_mgr.lock_item(unlocked_path) # Called with password=None
if ok:
    name = os.path.basename(unlocked_path) or unlocked_path
    speaker.speak(f"Folder {name} has been automatically locked.")
```

Inside `VaultManager.lock_item`:
```python
# core/vault_manager.py:184-193
elif mode == "aes256_vault":
    if not password:
        self.active_sessions.pop(norm_path, None)
        storage.update_item(norm_path, status="protected")
        return True, "Session cleared. Files remain decrypted until app provides password."
```

Because `password` is `None` (intentionally removed from RAM in VLN-07), `lock_item` returns `True` and updates `database.json` to mark the folder `status="protected"`. The screen reader announces `"Folder ... has been automatically locked"`, and the GUI renders the folder as `[LOCKED]`. 

**In reality, all files remain completely unencrypted on disk.** The user is given a false sense of security, believing their data is encrypted when it is completely exposed to anyone inspecting the filesystem.

#### Remediation Steps
1. Differentiate between instant ACL locks and cryptographic vaults. If an AES vault cannot be re-encrypted due to lack of an in-memory key, mark the status as `"decrypted_unlocked"` or `"needs_reencryption"` rather than `"protected"`.
2. Provide a secure key caching mechanism in memory (e.g. an ephemeral session key wrapped in DPAPI or protected memory struct) during active sessions, or immediately prompt the user for the re-encryption password upon folder closure before setting status to protected.
3. If auto-relock cannot re-encrypt, do not return `True` to the caller, and speak an alert warning the user that files remain unencrypted.

---

### SEC-03: HMAC Stripping / Downgrade Attack on `database.json`
- **Severity**: **High**
- **File**: `core/storage.py` (lines 84–96)
- **CWE**: CWE-347 (Improper Verification of Cryptographic Signature), CWE-353 (Missing Support for Integrity Check)

#### Technical Explanation
`StorageManager.load()` verifies the integrity of `database.json` using an HMAC-SHA256 signature. However, the verification is wrapped in a conditional check on `stored_hmac`:

```python
# core/storage.py:84-96
stored_hmac = raw.pop("_hmac", None)
if stored_hmac:
    payload_str = json.dumps(
        {k: v for k, v in raw.items()},
        sort_keys=True, ensure_ascii=False
    )
    expected_hmac = _compute_hmac(payload_str, self._machine_key)
    if not hmac.compare_digest(stored_hmac, expected_hmac):
        print("[Storage] WARNING: database.json HMAC mismatch — possible tampering detected!")
        self._hmac_tampered = True
```

If an attacker opens `database.json` and deletes the `"_hmac"` field entirely, `stored_hmac` evaluates to `None`. The `if stored_hmac:` block is bypassed completely, `_hmac_tampered` remains `False`, and the modified configuration is loaded with zero integrity enforcement. When `storage.save()` is executed subsequently, a fresh valid HMAC is computed over the tampered data, legitimizing the modification.

#### Remediation Steps
1. Require `_hmac` to be strictly present in all production database loads. If `_hmac` is absent and the file is non-empty, treat it as tampered (`self._hmac_tampered = True`).
2. Reject loading unauthenticated files or create a clean backup and notify the user.

---

### SEC-04: Tampered Storage Payload Loaded Despite Verification Failure
- **Severity**: **High**
- **File**: `core/storage.py` (lines 93–103)
- **CWE**: CWE-390 (Detection of Error Condition Without Action), CWE-354 (Improper Validation of Integrity Check Value)

#### Technical Explanation
When the HMAC mismatch is detected:
```python
# core/storage.py:93-102
if not hmac.compare_digest(stored_hmac, expected_hmac):
    print("[Storage] WARNING: database.json HMAC mismatch — possible tampering detected!")
    self._hmac_tampered = True

if "_settings" in raw:
    self.settings = raw.get("_settings", {"language": "en"})
    self.data = {k: v for k, v in raw.items() if k != "_settings"}
```

Although `self._hmac_tampered` is flagged, the function continues parsing `raw` and populates `self.data` and `self.settings`. In the rest of the application (`main.py`, `MainWindow`), `storage.is_tampered()` is never checked. The application operates normally on the compromised data, rendering the HMAC check purely informational.

#### Remediation Steps
1. When HMAC verification fails, do not populate `self.data` with untrusted records.
2. In `MainWindow.__init__`, check `storage.is_tampered()` and display a fatal warning dialog to the user, offering recovery options or safe mode.

---

### SEC-05: Storage HMAC Key Derived from World-Readable Registry MachineGuid
- **Severity**: **High**
- **File**: `core/storage.py` (lines 19–35)
- **CWE**: CWE-321 (Use of Hard-coded Cryptographic Key), CWE-522 (Insufficiently Protected Credentials)

#### Technical Explanation
`_get_machine_guid()` retrieves the MachineGuid from `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`. 

```python
# core/storage.py:23-28
key = winreg.OpenKey(
    winreg.HKEY_LOCAL_MACHINE,
    r"SOFTWARE\Microsoft\Cryptography"
)
guid, _ = winreg.QueryValueEx(key, "MachineGuid")
```

On Windows, `HKLM\SOFTWARE\Microsoft\Cryptography` is readable by all standard, non-administrative user accounts (`Users: Read`). Any local process or script can read `MachineGuid`, compute `_compute_hmac(json_payload, machine_guid)`, and produce valid HMAC signatures for arbitrary modifications to `database.json`. The HMAC provides zero cryptographic protection against local tampering.

#### Remediation Steps
1. Replace MachineGuid with Windows Data Protection API (DPAPI) via `CryptProtectData` and `CryptUnprotectData`. DPAPI keys are dynamically derived from the logged-in user's Windows credentials and protected by the Local Security Authority (LSA).
2. Store an encrypted master signature token generated via DPAPI rather than plain registry keys.

---

### SEC-06: Entire File In-Memory Buffering Causes RAM Exhaustion / DoS on Large Files
- **Severity**: **High**
- **File**: `core/vault_crypto.py` (lines 122–130, 170–175)
- **CWE**: CWE-400 (Uncontrolled Resource Consumption), CWE-770 (Allocation of Resources Without Limits or Throttling)

#### Technical Explanation
In `VaultCrypto.encrypt_file` and `decrypt_file`:
```python
# core/vault_crypto.py:122-130
with open(filepath, 'rb') as f:
    data = f.read()
...
ciphertext = aesgcm.encrypt(nonce, data, None)
```

`f.read()` reads the entire file into memory as a single bytes object. During `aesgcm.encrypt()`, memory is duplicated for ciphertext and internal OpenSSL buffers. When encrypting large files (e.g. 2GB–10GB video or disk archives), the process exhausts available RAM, triggering Python `MemoryError` or terminating the process via OS OOM killer. If interrupted during `encrypt_directory`, this leaves the directory in an inconsistent, partially encrypted state.

#### Remediation Steps
1. Implement chunked streaming AEAD encryption (e.g. 64KB chunks with sequential 12-byte nonces or standard streaming AEAD constructions) for large files.
2. Add file size checks and safeguards to prevent loading multi-gigabyte files into memory synchronously.

---

### SEC-07: PowerShell Injection via Unsanitized Paths in SDDL Form Retrieval
- **Severity**: **High**
- **File**: `core/acl_manager.py` (lines 33–41)
- **CWE**: CWE-78 (Improper Neutralization of Special Elements used in an OS Command)

#### Technical Explanation
In `ACLManager.get_acl_sddl`:
```python
# core/acl_manager.py:35-37
norm_path = os.path.abspath(path)
ps_script = f"(Get-Acl -LiteralPath '{norm_path}').GetSecurityDescriptorSddlForm('All')"
code, stdout, _ = cls.run_command(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script])
```

The path is interpolated directly into single quotes in the PowerShell command string. If a folder or file path contains a single quote (e.g. `C:\Users\John\Bob's Documents`), the single quote breaks out of `-LiteralPath '...'`, causing a PowerShell syntax error and terminating SDDL backup. Furthermore, if a path contains crafted command injection payload syntax, it presents an arbitrary command execution vector.

#### Remediation Steps
1. Escape single quotes in `norm_path` by replacing `'` with `''` in PowerShell literals, or pass the path via environment variable or standard input.
2. Alternatively, retrieve SDDL natively in Python using `win32security.GetFileSecurity` and `win32security.ConvertSecurityDescriptorToStringSecurityDescriptor` to eliminate PowerShell subprocess overhead entirely.

---

### SEC-08: Absence of Domain Separation between Password Hash and AES Key
- **Severity**: **Medium**
- **File**: `core/vault_crypto.py` (lines 75–84, 97–105), `core/vault_manager.py` (lines 78–84)
- **CWE**: CWE-327 (Use of a Broken or Risky Cryptographic Algorithm)

#### Technical Explanation
`VaultCrypto.hash_password` and `VaultCrypto._derive_aes_key` utilize identical PBKDF2-HMAC-SHA256 configurations (SHA-256, 32-byte output, 200,000 iterations). 

```python
# hash_password:
kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=cls.KEY_SIZE, salt=salt, iterations=cls.ITERATIONS)
key_ba = bytearray(kdf.derive(password.encode('utf-8')))

# _derive_aes_key:
kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=cls.KEY_SIZE, salt=salt, iterations=cls.ITERATIONS)
return bytearray(kdf.derive(password.encode('utf-8')))
```

If the verification hash salt and the encryption salt ever collide or are reused, the stored verification hash in `database.json` becomes the identical AES key used to decrypt files. Furthermore, storing password hashes in `database.json` for AES-256 Vault items exposes an offline dictionary attack target on the machine.

#### Remediation Steps
1. Implement domain separation strings by prepending distinct purpose prefixes (e.g. `salt = b"auth:" + raw_salt` vs `salt = b"aes_enc:" + raw_salt`), or use HKDF expansion with distinct `info` parameters.
2. Modernize the KDF to Argon2id (`argon2-cffi`) for memory-hard resistance against GPU-accelerated brute force.

---

### SEC-09: XOR-Derived Header Obfuscation Ineffective Against Identification
- **Severity**: **Medium**
- **File**: `core/vault_crypto.py` (lines 27–28, 59–69, 137, 177–179)
- **CWE**: CWE-656 (Reliance on Security Through Obscurity)

#### Technical Explanation
VLN-06 attempts to hide fixed magic headers by XORing `b"TW1"` with the first 3 bytes of the salt:
```python
@classmethod
def _make_header(cls, salt: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(cls._HEADER_PREFIX, salt[:3]))
```

Because `salt` is stored in plaintext immediately following the 3-byte header, an external scanner can compute `header[0] ^ salt[0]`, `header[1] ^ salt[1]`, `header[2] ^ salt[2]` and determine with 100% certainty if it equals `b"TW1"`. This provides zero anti-forensic security. 

Additionally, performing a 3-byte header check before GCM verification provides no cryptographic authenticity guarantee; GCM's 16-byte authentication tag already verifies ciphertext integrity.

#### Remediation Steps
1. Remove artificial XOR obfuscation. Use standard structured binary headers containing format version, KDF algorithm identifier, iteration count, salt, and nonce.
2. Rely strictly on AES-GCM tag verification for integrity validation.

---

### SEC-10: 3-Pass DoD Wipe Ineffective on Modern Wear-Leveled Flash/SSD Storage
- **Severity**: **Medium**
- **File**: `core/vault_crypto.py` (lines 38–56)
- **CWE**: CWE-459 (Incomplete Cleanup)

#### Technical Explanation
`_secure_delete` performs 3 overwrite passes with `secrets.token_bytes(size)` followed by `os.fsync` before calling `os.remove`. 
On modern solid-state drives (SSDs, NVMe) and flash media, the Flash Translation Layer (FTL) uses wear leveling and reallocates write blocks across NAND flash chips. Overwriting a file in-place through the OS filesystem writes to new physical NAND blocks rather than the existing physical cells holding original plaintext data. Furthermore, generating `3 * size` cryptographically secure random bytes on large files blocks the UI thread and incurs high write amplification.

#### Remediation Steps
1. Clarify that software in-place overwriting does not guarantee physical sanitization on SSDs.
2. For secure file removal, perform a single-pass zero/random fill with standard chunk sizes before unlinking, and advise users that whole-disk encryption (BitLocker) is required for hardware-level data-at-rest protection.

---

### SEC-11: False Assurance of In-Memory Secret Zeroization in CPython
- **Severity**: **Medium**
- **File**: `core/vault_crypto.py` (lines 31–36, 81–83, 127–129), `gui/password_dialog.py` (lines 103–105)
- **CWE**: CWE-244 (Improper Clearing of Heap Memory Containing Sensitive Data)

#### Technical Explanation
The codebase attempts to zeroize keys using `ctypes.memset` on `bytearray`:
```python
@staticmethod
def _zero_bytes(data: bytearray):
    if data:
        ctypes.memset((ctypes.c_char * len(data)).from_buffer(data), 0, len(data))
```

However:
1. `password.encode('utf-8')` creates immutable `bytes` objects in CPython heap memory that cannot be zeroized.
2. `aesgcm = AESGCM(bytes(key_ba))` casts the bytearray to immutable `bytes` and copies the key into OpenSSL internal C structs.
3. In `gui/password_dialog.py`, `self.txt_pwd.SetValue("")` and `self.entered_password = ""` rebind string references, but the underlying immutable CPython string objects remain in memory until GC collection and arena recycling.

#### Remediation Steps
1. Avoid false claims of DoD/military RAM zeroization in documentation.
2. Use `SecureString` or memory-locked buffers (`VirtualLock` on Windows) if strict in-memory security is mandated, or minimize the lifetime of secret variables.

---

### SEC-12: Missing Associated Authenticated Data (AAD) Binding in AES-GCM
- **Severity**: **Low**
- **File**: `core/vault_crypto.py` (lines 130, 182)
- **CWE**: CWE-353 (Missing Support for Integrity Check)

#### Technical Explanation
`AESGCM.encrypt(nonce, data, None)` and `AESGCM.decrypt(nonce, ciphertext, None)` pass `associated_data=None`. The ciphertext is not cryptographically bound to its file name, relative path, or header metadata. An attacker with filesystem access can rename or move a `.twvault` file, and `decrypt_file` will decrypt it into the new location without detecting the relocation.

#### Remediation Steps
1. Pass normalized file metadata (e.g. relative path, version header) into `associated_data` during both encryption and decryption to cryptographically bind ciphertext to its path.

---

### SEC-13: Non-Atomic Database Write Risks File Corruption on Abrupt Exit
- **Severity**: **Low**
- **File**: `core/storage.py` (lines 125–127)
- **CWE**: CWE-362 (Concurrent Execution using Shared Resource with Improper Synchronization)

#### Technical Explanation
`StorageManager.save()` writes directly to `self.db_path` using `open(self.db_path, 'w')`:
```python
with open(self.db_path, 'w', encoding='utf-8') as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)
```

If the system experiences a sudden power loss, OS crash, or termination mid-write, `database.json` can be left truncated (0 bytes or partial JSON), causing catastrophic loss of protected item lists on subsequent application startup.

#### Remediation Steps
1. Apply the atomic write pattern: write to a temporary file in the same directory using `tempfile.mkstemp`, flush and fsync, then call `os.replace(tmp_path, self.db_path)`.

---

## Verification & Independent Proof Steps

1. **Verify SEC-01 (Unauthenticated IPC Access)**:
   - Run Twinclers Guard.
   - Protect a test folder in Anti-Delete mode: `d:\test_prot`.
   - From another terminal, execute a standard TCP client sending JSON:
     ```powershell
     $client = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 49152)
     $stream = $client.GetStream()
     $writer = New-Object System.IO.StreamWriter($stream)
     $writer.Write('["--unprotect", "d:\\test_prot"]')
     $writer.Flush()
     $client.Close()
     ```
   - Observe that `d:\test_prot` is immediately unprotected without any password or user confirmation prompt.

2. **Verify SEC-02 (AES Relock Silent Plaintext Exposure)**:
   - Encrypt a folder in AES-256 Vault mode.
   - Unlock the folder via password prompt. Verify files are decrypted.
   - Close Windows Explorer.
   - Check the physical files on disk: observe they are still raw plaintext files, while GUI and speaker claim the folder is locked.

3. **Verify SEC-03 (HMAC Stripping)**:
   - Open `%APPDATA%\TwinclersGuard\database.json`.
   - Delete the `"_hmac"` property and change a setting or status.
   - Start Twinclers Guard.
   - Observe that the modified database loads successfully with no warnings (`_hmac_tampered` remains `False`).

4. **Verify SEC-07 (PowerShell Single Quote Injection)**:
   - Create a folder named `D:\Test'Folder`.
   - Attempt to call `ACLManager.get_acl_sddl("D:\\Test'Folder")`.
   - Observe syntax failure in PowerShell subprocess output.

---

## Conclusion & Architecture Roadmap

The cryptographic engine in `core/vault_crypto.py` correctly adopts AES-256-GCM authenticated encryption and PBKDF2-SHA256. However, systemic authorization flaws in the IPC layer (SEC-01), flawed state synchronization in AES vault relocking (SEC-02), and weak integrity verification in `core/storage.py` (SEC-03, SEC-04, SEC-05) represent critical attack vectors that must be remediated prior to production release.
