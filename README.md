# Twinclers Guard

Twinclers Guard is a native Windows desktop security utility built with Python 3.13 and wxPython. It combines Windows NTFS Kernel Access Controls and Military-Grade AES-256-GCM Cryptographic Encryption to protect your folders and files from accidental deletion, unauthorized modification, or unauthorized viewing.

Designed with an NVDA First-Class Accessibility philosophy, official nvdaControllerClient.dll integration, Multi-language (i18n) support with English as Default, an Active Windows Explorer Watcher with Auto-Relock on Window Close, and an Interactive TreeView Help System (F1).

---

## 8 Security and Protection Modes

1. Anti-Accidental Delete (Default / Recommended):
   - Full freedom to read, open, edit, and create files.
   - Windows strictly blocks any delete command (Delete or Shift + Delete).
2. Instant Password Gate (0.01s Fast Lock):
   - Zero-delay instant locking/unlocking for large video, music, photo libraries, or working workspaces.
   - Auto-detects in Windows File Explorer -> Brings Password Prompt to front -> Auto-relocks when File Explorer is closed.
3. AES-256-GCM Military Vault (Encrypted):
   - True cryptographic encryption with AES-256-GCM + PBKDF2-HMAC-SHA256 (200,000 iterations).
   - Designed for sensitive source code, API keys, wallets, and secret documents.
   - Even Administrators, CMD, PowerShell, or forensic tools cannot read a single byte without the master password.
4. Anti-Rename and Move (+ Anti-Delete):
   - Prevents deletion and prevents accidental renaming or moving/cutting.
5. Append-Only Mode (Log Mode):
   - Allows creating new files, but prevents editing or deleting existing files.
6. Read-Only Mode (Total Freeze):
   - Read-only archive mode. Blocks modifying, creating, and deleting.
7. Full Lock Mode:
   - Complete access blackout until unlocked.
8. Custom Granular Rules:
   - Individually toggle specific NTFS permissions (Delete, Rename, Write, Create, Inheritance).

---

## Windows File Explorer Watcher and Smart Auto-Relock

1. Open This PC in Windows File Explorer and navigate to a password-protected folder.
2. Twinclers Guard detects this in the background and brings the Password Prompt directly to the foreground.
3. NVDA announces: "Folder [Name] is password protected. Enter password to unlock."
4. Type your password and press Enter.
5. The folder unlocks and File Explorer refreshes instantly.
6. When you close the folder or close File Explorer, Twinclers Guard automatically locks the folder in the background.

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| **Ctrl + O** | Add Folder to Monitored List |
| **Ctrl + Shift + O** | Add File to Monitored List |
| **Ctrl + P** | Protect / Lock Selected Item |
| **Ctrl + U** | Unprotect / Unlock Selected Item |
| **Ctrl + Shift + P** | Protect All Items |
| **Ctrl + Shift + U** | Unprotect All Items |
| **Ctrl + T** | Test Anti-Delete Protection |
| **Ctrl + M** | Change Security Mode |
| **Ctrl + H** | Hide / Minimize to System Tray |
| **Delete** | Remove Selected Item from Monitored List |
| **F5** | Refresh Protection Status from Disk |
| **F1** | Open Interactive Help Window |
| **Alt + F4** | Exit Application |

---

## How to Run

### Option 1: Double-click Batch Launcher
Run run.bat.

### Option 2: Run via Terminal
```powershell
python main.py
```
