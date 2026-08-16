# Code Hygiene & Anti-AI Rules Audit Report

Audit target: Twinclers Guard (`core/`, `gui/`, `libs/`, `locales/`, `build_scripts/`, `main.py`)
Standards: `D:/Twinclers/.agents/rules/agent_rules.md`
Date: 2026-08-17

---

## Executive Summary

An audit of the 16 Python source files and associated build assets in Twinclers Guard identified 38 distinct code hygiene and anti-AI rule violations:
- **Blind Defensive Programming (Broad `except Exception: pass`)**: 11 occurrences across `core/nvda_speaker.py`, `core/explorer_monitor.py`, `core/vault_crypto.py`, `main.py`, and `gui/tray_icon.py`.
- **Logic Duplication & SSOT Violations**: 4 occurrences, including a security bypass where `gui/tray_icon.py` duplicated batch protection without checking vault modes, and schema duplication in `core/storage.py`.
- **Over-Engineering & Boilerplate**: 4 occurrences of Java-style pseudo-classes holding only static methods (`ACLManager`, `VaultCrypto`, `HelpParser`) and unused methods (`HelpItem.to_dict`).
- **Redundant Docstrings (Tautological Docstrings)**: 28 occurrences across `gui/main_window.py`, `gui/dialogs.py`, `core/i18n.py`, `core/vault_manager.py`, and `main.py`.
- **Over-Commenting (WHAT instead of WHY)**: 45+ occurrences of decorative section dividers, obvious syntactic narration, and repetitive fix annotations.
- **Generic & Abbreviated Variable Names**: 35+ occurrences of lazy names (`it`, `dlg`, `ok, msg`, `p1, p2`, `s1..s5`, `c`, `w`, `p`, `trans`).
- **Idiomatic Coding Violations & Functional Bugs**: 2 occurrences, including C-style indexing loops and a functional mismatch bug in `gui/main_window.py:select_path_in_list` querying status column instead of path column.

---

## Detailed Audit Findings by File

### 1. `main.py`

#### Finding 1.1: Silent Failure in IPC Client via Blind Exception Suppression
- **File & Lines**: `main.py:121-128`
- **Severity**: Medium
- **Rule Broken**: Blind Defensive Programming (`agent_rules.md:29`)
- **Observation**:
  ```python
  try:
      with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
          s.settimeout(2)
          s.connect(('127.0.0.1', 49152))
          s.sendall(json.dumps(sys.argv[1:]).encode('utf-8'))
  except OSError:
      pass
  ```
- **Rationale**: If `wx.SingleInstanceChecker` detects an existing instance due to a stale OS lock, but the existing process has crashed or failed to bind port 49152, `connect()` fails with `ConnectionRefusedError`. Swallowing this with `pass` silently drops user CLI / context menu commands.
- **Refactoring**:
  ```python
  try:
      with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ipc_client:
          ipc_client.settimeout(2.0)
          ipc_client.connect(('127.0.0.1', 49152))
          ipc_client.sendall(json.dumps(sys.argv[1:]).encode('utf-8'))
  except ConnectionRefusedError:
      # Previous instance terminated unexpectedly; proceed to run GUI directly
      run_gui(app=app, cli_args=sys.argv[1:])
  except OSError as socket_error:
      sys.stderr.write(f"[IPC] Failed to forward arguments: {socket_error}\n")
  ```

#### Finding 1.2: Redundant Docstring and Decorative Banner Comments
- **File & Lines**: `main.py:29`, `main.py:94`, `main.py:100`, `main.py:109`, `main.py:130`
- **Severity**: Low
- **Rule Broken**: Redundant Docstrings (`agent_rules.md:30-32`) & Over-commenting (`agent_rules.md:24-26`)
- **Observation**:
  - Line 29: `def run_gui(app=None, cli_args=None): """Runs the native wxPython graphical user interface."""`
  - Lines 94, 100, 109, 130: `# --- Uninstaller Mode ---`, `# --- Pure CLI Mode ---`, `# --- Single Instance & IPC ---`, `# --- Main Instance ---`
- **Rationale**: The docstring merely restates the function signature. Decorative ASCII banners add noise without explaining design context.
- **Refactoring**: Remove tautological docstring and decorative headers.

#### Finding 1.3: Abbreviated Variable Names
- **File & Lines**: `main.py:104`, `main.py:122`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names (`agent_rules.md:27`)
- **Observation**: `for it in items:`, `with socket.socket(...) as s:`
- **Refactoring**: Use `for item in items:` and `with socket.socket(...) as ipc_client:`.

---

### 2. `core/__init__.py` and `gui/__init__.py`

#### Finding 2.1: Obvious Syntax Explanation Comments
- **File & Lines**: `core/__init__.py:1` and `gui/__init__.py:1`
- **Severity**: Low
- **Rule Broken**: Over-commenting (`agent_rules.md:24-26`)
- **Observation**: `# core package` and `# gui package`
- **Rationale**: Restates basic Python syntax.
- **Refactoring**: Remove comments; leave package files clean.

---

### 3. `core/acl_manager.py`

#### Finding 3.1: Java-Style Class Wrapper for Stateless Methods (Over-Engineering)
- **File & Lines**: `core/acl_manager.py:11-307`
- **Severity**: Medium
- **Rule Broken**: Over-Engineering & Boilerplate (`agent_rules.md:28`)
- **Observation**:
  ```python
  class ACLManager:
      SID_EVERYONE = "*S-1-1-0"
      @staticmethod
      def run_command(cmd_list: list) -> Tuple[int, str, str]: ...
      @classmethod
      def get_acl_sddl(cls, path: str) -> Optional[str]: ...
      # 10 consecutive @classmethod / @staticmethod declarations
  acl_engine = ACLManager()
  ```
- **Rationale**: `ACLManager` maintains zero instance state. Wrapping free functions in a class full of `@classmethod` decorators and then instantiating a dummy instance `acl_engine = ACLManager()` introduces unnecessary abstraction overhead.
- **Refactoring**: Use module-level functions with `SID_EVERYONE = "*S-1-1-0"` as a module constant.

#### Finding 3.2: Single-Letter and Numbered Variable Names
- **File & Lines**: `core/acl_manager.py:162-163`, `core/acl_manager.py:259-276`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names (`agent_rules.md:27`)
- **Observation**: `code1, _, _ = cls.run_command(...)`, `code2, _, _ = ...`, and `s1 = ...`, `s2 = ...`, `s3 = ...`, `s4 = ...`, `s5 = ...`
- **Rationale**: Lazy numbered variable names reduce readability.
- **Refactoring**:
  ```python
  submenus = [
      ("01_Protect", "&Protect with Twinclers Guard", f'{cmd_prefix} --protect "%1"'),
      ("02_Unprotect", "&Unprotect (Remove Protection)", f'{cmd_prefix} --unprotect "%1"'),
      ("03_Sep", "-", None),
      ("04_Add", "&Add to Twinclers Guard List", f'{cmd_prefix} --add "%1"'),
      ("05_Open", "&Open Twinclers Guard", f'{cmd_prefix}')
  ]
  for sub_key, label, command in submenus:
      key_path = rf"{base}\shell\{sub_key}"
      _reg_add(key_path, "", label)
      if command:
          _reg_add(rf"{key_path}\command", "", command)
  ```

#### Finding 3.3: PowerShell Command Injection / Escaping Vulnerability
- **File & Lines**: `core/acl_manager.py:36`
- **Severity**: High
- **Rule Broken**: Idiomatic / Secure Coding Practices
- **Observation**:
  ```python
  ps_script = f"(Get-Acl -LiteralPath '{norm_path}').GetSecurityDescriptorSddlForm('All')"
  ```
- **Rationale**: Direct string formatting inside single quotes will fail or execute arbitrary PowerShell code if `norm_path` contains single quotes (e.g. `D:\User's Files\Project`).
- **Refactoring**:
  ```python
  escaped_path = norm_path.replace("'", "''")
  ps_script = f"(Get-Acl -LiteralPath '{escaped_path}').GetSecurityDescriptorSddlForm('All')"
  ```

#### Finding 3.4: Over-Commenting of Standard Business Logic
- **File & Lines**: `core/acl_manager.py:12`, `59`, `96`, `99`, `105`, `112`, `118`, `124`, `130`, `302`
- **Severity**: Low
- **Rule Broken**: Over-commenting (`agent_rules.md:24-26`)
- **Observation**: `# Cek tipe deny`, `# Kunci total akses`, `# Aturan custom sesuai checkbox`, `# Hapus dulu Deny lama jika ada sebelum menerapkan yang baru`.
- **Refactoring**: Remove comments explaining obvious conditionals.

---

### 4. `core/explorer_monitor.py`

#### Finding 4.1: Systematic Silent Exception Suppression in Monitor Loop and COM
- **File & Lines**: `core/explorer_monitor.py:64-67`, `core/explorer_monitor.py:110-111`
- **Severity**: High
- **Rule Broken**: Blind Defensive Programming (`agent_rules.md:29`)
- **Observation**:
  ```python
  # Lines 64-67:
  except Exception:
      pass
  except Exception:
      pass

  # Lines 110-111:
  except Exception as e:
      pass
  ```
- **Rationale**: Bare `except Exception: pass` hides COM crashes, attribute errors, and threading deadlocks.
- **Refactoring**: Catch specific COM exceptions (`pythoncom.com_error`, `AttributeError`, `OSError`) and log errors to diagnostic output when unexpected errors occur.

#### Finding 4.2: Generic Single-Letter Loop Variables
- **File & Lines**: `core/explorer_monitor.py:56`, `core/explorer_monitor.py:80`, `core/explorer_monitor.py:86`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names (`agent_rules.md:27`)
- **Observation**: `for w in windows:`, `p == unlocked_path or p.startswith(...)`, `ok, msg = vault_mgr.lock_item(...)`
- **Refactoring**: Rename to `for window in windows:`, `open_path`, and `is_locked, lock_message`.

#### Finding 4.3: Redundant Docstrings and Step Narration
- **File & Lines**: `core/explorer_monitor.py:29`, `37`, `41`, `46`, `75`, `78`, `85`, `94`, `102`
- **Severity**: Low
- **Rule Broken**: Redundant Docstrings & Over-commenting (`agent_rules.md:24,30`)
- **Observation**: `"""Starts the background monitoring thread."""`, `"""Stops the monitoring thread."""`, `# 1. Cek folder yang sedang aktif di-unlock...`, `# Jendela Explorer sudah ditutup! Auto Relock!`.
- **Refactoring**: Remove trivial docstrings and narrative comments.

---

### 5. `core/help_parser.py`

#### Finding 5.1: Dead Code / Unused Method & Static Class Wrapper
- **File & Lines**: `core/help_parser.py:17-23`, `core/help_parser.py:25-50`
- **Severity**: Medium
- **Rule Broken**: Over-Engineering & Boilerplate (`agent_rules.md:28`)
- **Observation**:
  ```python
  def to_dict(self) -> Dict:
      return {
          "title": self.title,
          "level": self.level,
          "content": self.content,
          "children": [c.to_dict() for c in self.children]
      }
  ```
- **Rationale**: `to_dict` is never called anywhere in the codebase. `HelpParser` contains only static methods.
- **Refactoring**: Remove unused `to_dict` and convert `HelpParser` to module functions.

#### Finding 5.2: Non-Idiomatic Character Iteration
- **File & Lines**: `core/help_parser.py:77-82`
- **Severity**: Low
- **Rule Broken**: Idiomatic Language Rules (`agent_rules.md:33`)
- **Observation**:
  ```python
  level = 0
  for char in stripped:
      if char == "#":
          level += 1
      else:
          break
  ```
- **Refactoring**:
  ```python
  level = len(stripped) - len(stripped.lstrip('#'))
  ```

---

### 6. `core/i18n.py`

#### Finding 6.1: Generic Variable Names and Redundant Docstrings
- **File & Lines**: `core/i18n.py:20`, `24`, `27`, `35`, `37`, `45`, `52`, `56`, `65-72`, `87`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names, Redundant Docstrings & Over-commenting (`agent_rules.md:24,27,30`)
- **Observation**: `fname`, `fpath`, `trans`, `cb in self.callbacks`, `lambda x: (0 if x[0] == "en" else 1, x[1])`, `"""Global helper for text translation."""`, `# 1. Cari di bahasa aktif`.
- **Refactoring**:
  ```python
  def get_available_languages(self) -> List[Tuple[str, str]]:
      raw_languages = [
          (lang_code, trans_map.get("LANGUAGE_NAME", lang_code.upper()))
          for lang_code, trans_map in self.translations.items()
      ]
      if not raw_languages:
          return [("en", "English"), ("id", "Bahasa Indonesia")]
      return sorted(raw_languages, key=lambda item: (0 if item[0] == "en" else 1, item[1]))
  ```

---

### 7. `core/nvda_speaker.py`

#### Finding 7.1: Pervasive Blind Error Suppression Across All 10 TTS Functions
- **File & Lines**: `core/nvda_speaker.py:33-34`, `49-51`, `60-61`, `69-70`, `88-89`, `101-102`, `111-112`, `121-122`, `129-130`, `137-138`
- **Severity**: High
- **Rule Broken**: Blind Defensive Programming (`agent_rules.md:29`)
- **Observation**: Every method catches `Exception` and executes `pass`.
- **Rationale**: Complete error silencing conceals missing DLL dependencies, invalid ctypes pointer arguments, and COM dispatch failures.
- **Refactoring**: Catch specific exceptions (`OSError`, `ctypes.ArgumentError`, `AttributeError`, `win32com.client.com_error`) and log failures when TTS backend initialization fails.

#### Finding 7.2: Generic Return and Helper Variables
- **File & Lines**: `core/nvda_speaker.py:58`, `core/nvda_speaker.py:96`, `core/nvda_speaker.py:107`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names (`agent_rules.md:27`)
- **Observation**: `res = self._nvda_dll.nvdaController_testIfRunning()`, `res = self._nvda_dll.nvdaController_speakText(text)`, `ao = ...`
- **Refactoring**: Rename to `is_running_status`, `speak_return_code`, `auto_output`.

---

### 8. `core/storage.py`

#### Finding 8.1: Schema Dictionary Duplication (DRY Violation) & Unused Imports
- **File & Lines**: `core/storage.py:13-14`, `core/storage.py:158-167`, `core/storage.py:182-191`
- **Severity**: Medium
- **Rule Broken**: Core DRY Principles (`agent_rules.md:41-49`) & Dead imports
- **Observation**:
  - `import ctypes` and `import ctypes.wintypes` are imported but never referenced in `storage.py`.
  - The dictionary schema structure for a monitored item is duplicated verbatim in `add_item` and `update_item`:
  ```python
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
  ```
- **Rationale**: Schema drift occurs when fields are added to one location but missed in the other.
- **Refactoring**: Remove unused imports and centralize item creation into a single helper:
  ```python
  def _build_item_record(path: str, mode: str = "anti_delete", status: str = "unprotected") -> Dict[str, any]:
      norm_path = os.path.abspath(os.path.normpath(path))
      now_timestamp = datetime.now().isoformat()
      return {
          "path": norm_path,
          "type": "folder" if os.path.isdir(norm_path) else "file",
          "status": status,
          "mode": mode,
          "date_added": now_timestamp,
          "last_updated": now_timestamp,
          "original_acl_sddl": None,
          "note": ""
      }
  ```

---

### 9. `core/vault_crypto.py`

#### Finding 9.1: Broad Exception Suppression Swallowing Decryption Errors & Unused Import
- **File & Lines**: `core/vault_crypto.py:15`, `core/vault_crypto.py:50-56`, `147-148`, `155-156`, `194-195`, `201-202`, `206-207`
- **Severity**: High
- **Rule Broken**: Blind Defensive Programming (`agent_rules.md:29`) & Dead imports
- **Observation**:
  - Line 15: `import shutil` is never used.
  - Lines 206-207: `except Exception: return False, "Incorrect password or corrupted file."`
- **Rationale**: Catching `Exception` indiscriminately mislabels OS I/O errors, disk full errors, and memory errors as wrong passwords.
- **Refactoring**: Remove `import shutil`. Handle `cryptography.exceptions.InvalidTag` specifically for password/integrity failures, and handle `OSError` for filesystem failures.

#### Finding 9.2: Stateless Class Packaging & Generic Variable Names
- **File & Lines**: `core/vault_crypto.py:21-263`, `62`, `133`, `187`, `225`, `231-232`, `250`, `255-256`
- **Severity**: Low
- **Rule Broken**: Over-Engineering & Generic Variable Names (`agent_rules.md:27,28`)
- **Observation**: `VaultCrypto` class has only `@staticmethod` and `@classmethod`. Variables named `a, b`, `tmp_fd, tmp_path`, `fname`, `fpath`, `ok, msg`.
- **Refactoring**: Use descriptive names `byte_a, byte_b`, `temp_fd, temp_filepath`, `filename`, `file_path`, `is_success, status_msg`.

---

### 10. `core/vault_manager.py`

#### Finding 10.1: Repetitive Fix Annotations and Narrative Comments
- **File & Lines**: `core/vault_manager.py:16`, `39`, `63`, `123`, `133`, `137`, `153`, `161`, `185-189`
- **Severity**: Low
- **Rule Broken**: Over-commenting (`agent_rules.md:24-26`)
- **Observation**: `# VLN-07: TIDAK simpan password — hanya session flag`, `# password intentionally NOT stored`, `# VLN-07: Hanya simpan mode dan flag, BUKAN password`.
- **Refactoring**: Remove repetitive commentary.

#### Finding 10.2: Generic and Abbreviated Variable Names
- **File & Lines**: `core/vault_manager.py:96`, `116`, `126`, `128`, `129`, `159`, `177`, `195`, `197`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names (`agent_rules.md:27`)
- **Observation**: `f in files`, `allowed, wait`, `ok, cnt, msg`, `target_f`.
- **Refactoring**: Rename to `filename in files`, `is_allowed, wait_seconds`, `is_decrypted, decrypted_count, status_message`, `vault_target_path`.

---

### 11. `gui/dialogs.py`

#### Finding 11.1: Mode Definition Duplication Across Dialogs (DRY Violation)
- **File & Lines**: `gui/dialogs.py:130-149` and `gui/dialogs.py:237-268`
- **Severity**: Medium
- **Rule Broken**: Core DRY Principles (`agent_rules.md:41-49`)
- **Observation**:
  - `AddItemDialog` and `ChangeModeDialog` both declare `self.mode_keys = ["anti_delete", "instant_gate", ...]` and identical lists of translated choice keys.
- **Rationale**: Modifying or adding a security mode requires editing multiple GUI classes.
- **Refactoring**: Define `SECURITY_MODES` in a single shared configuration constant.

#### Finding 11.2: Lazy Variable Names Across All Dialogs
- **File & Lines**: `gui/dialogs.py:173`, `177`, `195`, `210`, `218`, `280`, `294`, `299`, `306`, `348-350`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names (`agent_rules.md:27`)
- **Observation**: `dlg` repeated 7 times, `idx`, `m_id`, `res_box`, `txt_res`.
- **Refactoring**: Use descriptive names `dir_dialog`, `file_dialog`, `password_dialog`, `selected_index`, `mode_key`, `result_box`, `result_text_ctrl`.

---

### 12. `gui/help_dialog.py`

#### Finding 12.1: Generic Variable Names and Basic Layout Comments
- **File & Lines**: `gui/help_dialog.py:26`, `29`, `35`, `42`, `45`, `58`, `73`, `85`, `88`, `91`, `94`, `108`, `111`, `131`, `133`, `143`
- **Severity**: Low
- **Rule Broken**: Over-commenting, Redundant Docstrings & Generic Variable Names (`agent_rules.md:24,27,30`)
- **Observation**: `# 1. KIRI: TreeCtrl...`, `# 2. KANAN: TextCtrl...`, `data`, `text`, `key`.
- **Refactoring**: Remove layout comments and use descriptive variable names.

---

### 13. `gui/main_window.py`

#### Finding 13.1: Non-Idiomatic C-Style Loops, Duplication & Functional Column Index Bug
- **File & Lines**: `gui/main_window.py:164-169`, `gui/main_window.py:173-178`
- **Severity**: High
- **Rule Broken**: Idiomatic Language Rules (`agent_rules.md:33`), Zero Copy-Paste (`agent_rules.md:47`) & Functional Bug
- **Observation**:
  ```python
  for i in range(self.list_ctrl.GetItemCount()):
      item_path = self.list_ctrl.GetItemText(i, 2)
      if item_path.lower() == path.lower():
          self.list_ctrl.Select(i)
          self.list_ctrl.EnsureVisible(i)
          return
  # ... storage.add_item ...
  for i in range(self.list_ctrl.GetItemCount()):
      item_path = self.list_ctrl.GetItemText(i, 2)
      if item_path.lower() == path.lower():
          self.list_ctrl.Select(i)
          self.list_ctrl.EnsureVisible(i)
          return
  ```
- **Rationale**:
  1. The C-style loop `for i in range(...)` is duplicated twice.
  2. `GetItemText(i, 2)` queries column 2 (Protection Status), whereas column 0 is Path. Comparing Protection Status to target path never matches, causing IPC path selection to fail.
- **Refactoring**:
  ```python
  def _find_item_index_by_path(self, target_path: str) -> Optional[int]:
      target_norm = storage.normalize_path(target_path).lower()
      for row_index in range(self.list_ctrl.GetItemCount()):
          row_path = self.list_ctrl.GetItemText(row_index, 0)
          if storage.normalize_path(row_path).lower() == target_norm:
              return row_index
      return None

  def select_path_in_list(self, path: str):
      found_index = self._find_item_index_by_path(path)
      if found_index is None:
          storage.add_item(path, mode="anti_delete")
          self.refresh_list()
          found_index = self._find_item_index_by_path(path)
      if found_index is not None:
          self.list_ctrl.Select(found_index)
          self.list_ctrl.EnsureVisible(found_index)
  ```

#### Finding 13.2: 22 Tautological Docstrings Repeating Function Signatures
- **File & Lines**: `gui/main_window.py:114`, `163`, `181`, `253`, `272`, `302`, `311`, `319`, `327`, `334`, `380`, `387`, `398`, `412`, `420`, `440`, `444`, `448`, `458`, `463`, `470`, `482`
- **Severity**: Medium
- **Rule Broken**: Redundant Docstrings (`agent_rules.md:30-32`)
- **Observation**:
  - `"""Handles keyboard keys on ListCtrl."""`
  - `"""Right-click menu / context menu key (AppsKey / Shift+F10)."""`
  - `"""Called when user opens a password-protected folder in File Explorer."""`
  - `"""Called when a File Explorer window is closed."""`
  - `"""Displays password dialog on top of Windows Explorer."""`
  - `"""Hides the window to the System Tray."""`
  - `"""When minimize button is pressed."""`
  - `"""Cleanup upon window closing."""`
- **Rationale**: Clutters the code with zero informational value.
- **Refactoring**: Remove tautological docstrings.

#### Finding 13.3: Blind Exception Suppression in IPC Thread and Tray Cleanup
- **File & Lines**: `gui/main_window.py:107-108`, `gui/main_window.py:476-477`
- **Severity**: Medium
- **Rule Broken**: Blind Defensive Programming (`agent_rules.md:29`)
- **Observation**: `except Exception: pass`
- **Refactoring**: Handle `socket.error`, `json.JSONDecodeError`, and `wx.PyDeadObjectError` specifically.

#### Finding 13.4: Generic Variable Names
- **File & Lines**: `gui/main_window.py:98`, `101`, `110`, `216`, `239`, `268`, `330`, `349`, `366`, `375`, `381`, `388`, `413`, `449`, `485`, `494`, `512`, `529`, `555`, `565`, `588`, `593`, `609`, `613`, `630`, `637`, `653`, `655`, `667`, `686`, `703`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names (`agent_rules.md:27`)
- **Observation**: `conn, addr`, `data`, `t`, `it`, `prot_cnt`, `idx`, `dlg` (repeated across 10 methods).
- **Refactoring**: Use semantic names (`ipc_conn, client_addr`, `payload_bytes`, `ipc_thread`, `item`, `protected_count`, `item_index`, `dialog_instance`).

---

### 14. `gui/password_dialog.py`

#### Finding 14.1: Lazy Numbered Variable Names and Obvious UI Comments
- **File & Lines**: `gui/password_dialog.py:13`, `28`, `36`, `43`, `53`, `58`, `65`, `70`, `74`, `77`, `94`, `100`, `102`, `110`, `120`, `146-154`, `170-171`, `180`, `188`
- **Severity**: Low
- **Rule Broken**: Generic Variable Names, Redundant Docstrings & Over-commenting (`agent_rules.md:24,27,30`)
- **Observation**: `pwd`, `ok, msg`, `lbl_p1`, `self.txt_p1`, `lbl_p2`, `self.txt_p2`, `p1`, `p2`, `# Password 1`, `# Confirm Password`.
- **Refactoring**: Rename to `entered_password`, `is_unlocked, unlock_status`, `lbl_new_password`, `self.txt_new_password`, `lbl_confirm_password`, `self.txt_confirm_password`, `new_password`, `confirm_password`.

---

### 15. `gui/tray_icon.py`

#### Finding 15.1: Logic Duplication & Security Bypass in Tray Actions (Critical DRY Violation)
- **File & Lines**: `gui/tray_icon.py:94-108`
- **Severity**: High
- **Rule Broken**: Core DRY Principles (`agent_rules.md:41-49`) & Single Source of Truth
- **Observation**:
  ```python
  def on_protect_all(self, event):
      items = storage.get_all()
      for it in items:
          acl_engine.protect(it["path"], mode=it.get("mode", "anti_delete"))
          storage.update_item(it["path"], status="protected")
      self.frame.refresh_list()
      speaker.speak(_("ANNOUNCE_PROTECT_ALL", count=len(items)))

  def on_unprotect_all(self, event):
      items = storage.get_all()
      for it in items:
          acl_engine.unprotect(it["path"])
          storage.update_item(it["path"], status="unprotected")
      self.frame.refresh_list()
      speaker.speak(_("ANNOUNCE_UNPROTECT_ALL"))
  ```
- **Rationale**: `tray_icon.py` duplicates `on_protect_all` and `on_unprotect_all` from `main_window.py`. The tray implementation omits vault mode checks, applying raw `acl_engine.protect`/`unprotect` to AES vaults and Instant Gate items without password verification, corrupting state and bypassing security.
- **Refactoring**: Eliminate duplicated logic and delegate directly to `MainWindow`:
  ```python
  def on_protect_all(self, event):
      self.frame.on_protect_all(event)

  def on_unprotect_all(self, event):
      self.frame.on_unprotect_all(event)
  ```

#### Finding 15.2: Blind Exception Suppression in Tray Icon Removal
- **File & Lines**: `gui/tray_icon.py:25-26`, `gui/tray_icon.py:114-115`
- **Severity**: Low
- **Rule Broken**: Blind Defensive Programming (`agent_rules.md:29`)
- **Observation**: `except Exception as e: print(...)` and `except Exception: pass`
- **Refactoring**: Catch `wx.PyDeadObjectError` or `OSError` explicitly.

---

### 16. Repository Root & Miscellaneous Files

#### Finding 16.1: Orphaned Scratch File at Repository Root
- **File & Lines**: `scratch_wiki.txt:1`
- **Severity**: Low
- **Rule Broken**: Repository Hygiene
- **Observation**: `scratch_wiki.txt` is an empty 0-byte file left in the repository root.
- **Refactoring**: Delete the file.

---

## Remediation Roadmap

| Target File | Primary Actions | Expected Outcome |
| :--- | :--- | :--- |
| `gui/tray_icon.py` | Delegate `on_protect_all` and `on_unprotect_all` to `MainWindow` | Fixes critical security bypass & enforces SSOT |
| `gui/main_window.py` | Fix column index 2 -> 0 bug in `select_path_in_list`; remove 22 redundant docstrings; clean generic variable names | Fixes IPC selection bug & cleans codebase |
| `core/acl_manager.py` | Fix PowerShell single quote escaping; refactor registry loop; clean syntax comments | Eliminates command injection risk & cleans up code |
| `core/nvda_speaker.py` | Replace 10 `except Exception: pass` blocks with specific exceptions and diagnostics | Restores error visibility for TTS subsystem |
| `core/storage.py` | Extract `_build_item_record` helper; remove dead imports (`ctypes`, `ctypes.wintypes`) | Enforces schema DRY & removes dead imports |
| `core/vault_crypto.py` | Remove unused `import shutil`; distinguish `InvalidTag` from `OSError` | Prevents masking filesystem errors as bad passwords |
| `core/help_parser.py` | Remove dead `to_dict` method; replace manual `#` counting loop with idiomatic string method | Simplifies parser |
| `gui/dialogs.py` | Centralize `SECURITY_MODES` constant; clean repetitive `dlg` variables | Enforces DRY mode definitions across GUI |
| `scratch_wiki.txt` | Delete empty file | Clean repository |
