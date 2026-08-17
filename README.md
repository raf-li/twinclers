# Twinclers Guard

[![Build Status](https://github.com/raf-li/twinclers/actions/workflows/build.yml/badge.svg)](https://github.com/raf-li/twinclers/actions)

Twinclers Guard is a Windows desktop application that protects files and folders using NTFS access controls and AES-256-GCM encryption. It integrates directly with the NVDA screen reader for accessibility.

## Download & Install

Download the installer (`TwinclersGuardSetup.exe`) from the [Releases](https://github.com/raf-li/twinclers/releases/latest) page. Run the setup file to install.

## Protection Modes

1. **Anti-Delete (Default):** Prevents file deletion while allowing normal read and write access.
2. **Instant Password Gate:** Locks folders instantly using NTFS ACLs.
3. **AES-256 Vault:** Encrypts files using AES-256-GCM. Uses Windows DPAPI to secure the master password in memory.
4. **Anti-Rename and Move:** Stops files from being renamed or moved. Deletion is also blocked.
5. **Append-Only:** Allows creating new files but denies modifications to existing ones.
6. **Read-Only:** Denies write access to prevent any modifications or deletions.
7. **Full Lock:** Denies all access to the item.
8. **Custom:** Toggle specific NTFS permissions manually.

## Auto-Relock

If you open a protected folder in Windows File Explorer, Twinclers Guard displays a password prompt. After you unlock it, the app monitors the active window. When you close the folder or navigate away, the folder is automatically locked again.

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + O` | Add Folder |
| `Ctrl + Shift + O` | Add File |
| `Ctrl + P` | Lock Selected Item |
| `Ctrl + U` | Unlock Selected Item |
| `Ctrl + Shift + P` | Lock All Items |
| `Ctrl + Shift + U` | Unlock All Items |
| `Ctrl + T` | Test Anti-Delete Protection |
| `Ctrl + M` | Change Security Mode |
| `Ctrl + H` | Minimize to Tray |
| `Delete` | Remove Selected Item |
| `F5` | Refresh Status |
| `F1` | Help Menu |
| `Alt + F4` | Exit |

---
Compiled with Nuitka using Python and wxPython.
