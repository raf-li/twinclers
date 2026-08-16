"""
Windows NTFS ACL (Access Control List) Protection Engine for Twinclers Guard.
Supports Anti-Delete, Anti-Rename & Move, Append-Only (Log Mode), Read-Only, Full Lock, and Custom Granular modes.
"""

import os
import sys
import subprocess
from typing import Tuple, Optional, Dict

class ACLManager:
    # Use BUILTIN\Users (S-1-5-32-545) instead of Everyone to prevent blocking SYSTEM and Defender (SEC-09)
    SID_USERS = "*S-1-5-32-545"

    @staticmethod
    def run_command(cmd_list: list) -> Tuple[int, str, str]:
        """Safely executes a subprocess command without opening a separate CMD window."""
        try:
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                creationflags=0x08000000 # CREATE_NO_WINDOW
            )
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr
        except OSError as e:
            return 1, "", str(e)

    @classmethod
    def get_acl_sddl(cls, path: str) -> Optional[str]:
        """Retrieves the current SDDL string / permission backup."""
        norm_path = os.path.abspath(path)
        # SEC-07: Sanitize single quotes to prevent PowerShell injection
        safe_path = norm_path.replace("'", "''")
        ps_script = f"(Get-Acl -LiteralPath '{safe_path}').GetSecurityDescriptorSddlForm('All')"
        code, stdout, _ = cls.run_command(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script])
        if code == 0 and stdout.strip():
            return stdout.strip()
        return None

    @classmethod
    def check_protection_status(cls, path: str) -> Dict[str, any]:
        """
        Checks whether the current path has Deny Delete / Deny Access rules applied.
        """
        norm_path = os.path.abspath(path)
        if not os.path.exists(norm_path):
            return {"exists": False, "protected": False, "mode": "none", "details": "Path tidak ditemukan"}

        code, stdout, _ = cls.run_command(["icacls", norm_path])
        if code != 0:
            return {"exists": True, "protected": False, "mode": "none", "details": "Gagal membaca ACL"}

        stdout_lower = stdout.lower()
        is_protected = False
        mode = "none"

        # Cek tipe deny
        if ":(denied)" in stdout_lower or ":(deny)" in stdout_lower or "(n)" in stdout_lower or "(de,dc)" in stdout_lower or "(de)" in stdout_lower or "(f)" in stdout_lower:
            is_protected = True
            if "(f)" in stdout_lower:
                mode = "full_lock"
            elif "(wd," in stdout_lower or "(wd)" in stdout_lower:
                if "(ad)" in stdout_lower:
                    mode = "read_only"
                else:
                    mode = "append_only"
            elif "(wa" in stdout_lower or "(wea" in stdout_lower:
                mode = "anti_rename_delete"
            else:
                mode = "anti_delete"

        return {
            "exists": True,
            "protected": is_protected,
            "mode": mode,
            "details": stdout.strip()
        }

    @classmethod
    def protect(cls, path: str, mode: str = "anti_delete", custom_rules: Dict = None) -> Tuple[bool, str]:
        """
        Applies ACL protection rules to a folder or file.
        
        :param path: Target path (folder or file)
        :param mode: 'anti_delete', 'anti_rename_delete', 'append_only', 'read_only', 'full_lock', 'custom'
        :param custom_rules: Dict containing boolean flags if mode == 'custom'
        """
        norm_path = os.path.abspath(path)
        if not os.path.exists(norm_path):
            return False, f"Path not found: {norm_path}"

        is_dir = os.path.isdir(norm_path)

        # Hapus dulu Deny lama jika ada sebelum menerapkan yang baru
        cls.unprotect(norm_path, silent=True)

        if mode == "anti_delete":
            # Mencegah hapus folder & file di dalamnya, bebas baca/tulis/tambah
            perm = f"{cls.SID_USERS}:(OI)(CI)(DE,DC)" if is_dir else f"{cls.SID_USERS}:(DE)"
            code, stdout, stderr = cls.run_command(["icacls", norm_path, "/deny", perm])
            return (code == 0), (stderr or stdout or "Success")

        elif mode == "anti_rename_delete":
            # Mencegah hapus DAN mencegah ganti nama (rename) / pindah lokasi
            perm = f"{cls.SID_USERS}:(OI)(CI)(DE,DC,WA,WEA)" if is_dir else f"{cls.SID_USERS}:(DE,WA,WEA)"
            code, stdout, stderr = cls.run_command(["icacls", norm_path, "/deny", perm])
            return (code == 0), (stderr or stdout or "Success")

        elif mode == "append_only":
            # Mode Log: File lama dilarang diedit & dilarang dihapus, tapi user BISA menambah file baru
            perm = f"{cls.SID_USERS}:(OI)(CI)(WD,DE,DC)" if is_dir else f"{cls.SID_USERS}:(WD,DE)"
            code, stdout, stderr = cls.run_command(["icacls", norm_path, "/deny", perm])
            return (code == 0), (stderr or stdout or "Success")

        elif mode == "read_only":
            # Mencegah modifikasi isi file, penambahan file, dan penghapusan
            perm = f"{cls.SID_USERS}:(OI)(CI)(DE,DC,WD,AD,WA,WEA)" if is_dir else f"{cls.SID_USERS}:(DE,WD,AD,WA,WEA)"
            code, stdout, stderr = cls.run_command(["icacls", norm_path, "/deny", perm])
            return (code == 0), (stderr or stdout or "Success")

        elif mode == "full_lock":
            # Kunci total akses
            perm = f"{cls.SID_USERS}:(OI)(CI)(F)" if is_dir else f"{cls.SID_USERS}:(F)"
            code, stdout, stderr = cls.run_command(["icacls", norm_path, "/deny", perm])
            return (code == 0), (stderr or stdout or "Success")

        elif mode == "custom" and custom_rules:
            # Aturan custom sesuai checkbox
            deny_flags = []
            if custom_rules.get("deny_delete", True):
                deny_flags.extend(["DE", "DC"] if is_dir else ["DE"])
            if custom_rules.get("deny_rename", False):
                deny_flags.extend(["WA", "WEA"])
            if custom_rules.get("deny_write", False):
                deny_flags.append("WD")
            if custom_rules.get("deny_create", False):
                deny_flags.append("AD")
            if custom_rules.get("deny_full", False):
                deny_flags = ["F"]

            if not deny_flags:
                deny_flags = ["DE"]

            flag_str = ",".join(list(dict.fromkeys(deny_flags)))
            inherit = "(OI)(CI)" if is_dir and custom_rules.get("recursive", True) else ""
            perm = f"{cls.SID_USERS}:{inherit}({flag_str})"
            
            code, stdout, stderr = cls.run_command(["icacls", norm_path, "/deny", perm])
            return (code == 0), (stderr or stdout or "Success")

        return False, f"Unknown protection mode: {mode}"

    @classmethod
    def unprotect(cls, path: str, silent: bool = False) -> Tuple[bool, str]:
        """Removes ACL protection by deleting Deny rules."""
        norm_path = os.path.abspath(path)
        if not os.path.exists(norm_path):
            return False, f"Path not found: {norm_path}"

        code1, _, _ = cls.run_command(["icacls", norm_path, "/remove:d", cls.SID_USERS])
        code2, _, _ = cls.run_command(["icacls", norm_path, "/remove:d", "Users"])
        code3, _, _ = cls.run_command(["icacls", norm_path, "/remove:d", "Everyone"])

        if code1 == 0 or code2 == 0 or code3 == 0:
            return True, "Protection unlocked successfully."
        return False, "Failed to unlock or folder was not locked."

    @classmethod
    def test_delete_protection(cls, path: str) -> Tuple[bool, str]:
        """Tests if the Anti-Delete protection is active and working correctly."""
        norm_path = os.path.abspath(path)
        if not os.path.exists(norm_path):
            return False, "Path not found for testing."

        if os.path.isdir(norm_path):
            test_file = os.path.join(norm_path, ".twinclers_protection_test.tmp")
            try:
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write("Twinclers Guard Protection Test")
            except PermissionError:
                status = cls.check_protection_status(norm_path)
                if status["protected"]:
                    return True, f"Protection is ACTIVE ({status['mode'].upper()}): Windows denied file creation/modification."
                return False, "Permission error while creating test file (not locked by Twinclers Guard)."
            except OSError as e:
                return False, f"Error creating test file: {e}"

            delete_blocked = False
            try:
                os.remove(test_file)
            except PermissionError:
                delete_blocked = True
            except OSError:
                delete_blocked = True

            try:
                cls.run_command(["icacls", test_file, "/grant", f"{cls.SID_EVERYONE}:(F)"])
                if os.path.exists(test_file):
                    os.remove(test_file)
            except OSError:
                pass

            if delete_blocked:
                return True, "TEST PASSED: Windows successfully REJECTED the delete command (Access is Denied)! The folder is 100% safe from Delete / Shift+Delete."
            else:
                return False, "TEST FAILED: The test file was deleted. Protection is not active."

        else:
            status = cls.check_protection_status(norm_path)
            if status["protected"]:
                return True, f"TEST PASSED: File is protected in {status['mode'].upper()} mode. Windows will reject deletion."
            return False, "File is currently unprotected."

    @classmethod
    def is_context_menu_registered(cls) -> bool:
        """Checks if the context menu is already registered in the Registry."""
        reg_base = r"HKCU\Software\Classes\Directory\shell\TwinclersGuard"
        code, stdout, _ = cls.run_command(["reg", "query", reg_base])
        return code == 0 and "TwinclersGuard" in (stdout or "")

    @classmethod
    def _get_executable_cmd(cls) -> str:
        """Gets the application execution path (source or compiled EXE)."""
        is_compiled = getattr(sys, 'frozen', False) or not sys.executable.lower().endswith("python.exe")
        if is_compiled:
            return rf'"{sys.executable}"'
        python_exe = sys.executable
        pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw_exe):
            pythonw_exe = python_exe
        main_script = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"))
        return rf'"{pythonw_exe}" "{main_script}"'

    @classmethod
    def register_explorer_context_menu(cls, enable: bool = True) -> Tuple[bool, str]:
        """
        Adds or removes the Windows Explorer right-click integration (Context Menu).
        """
        cmd_prefix = cls._get_executable_cmd()

        base_dir  = r"HKCU\Software\Classes\Directory\shell\TwinclersGuard"
        base_file = r"HKCU\Software\Classes\*\shell\TwinclersGuard"

        def _reg_add(key, value_name, value):
            args = ["reg", "add", key, "/f"]
            if value_name:
                args += ["/v", value_name, "/d", value]
            else:
                args += ["/ve", "/d", value]
            cls.run_command(args)

        def _build_submenu(base: str):
            # JANGAN set nilai default (ve) pada base key, karena itu merusak cascade di Explorer!
            _reg_add(base, "MUIVerb",     "Twinclers Guard")
            _reg_add(base, "SubCommands", "")
            _reg_add(base, "Icon",        r"C:\Windows\System32\shell32.dll,167")

            s1 = rf"{base}\shell\01_Protect"
            _reg_add(s1, "", "&Protect with Twinclers Guard")
            _reg_add(rf"{s1}\command", "", rf'{cmd_prefix} --protect "%1"')

            s2 = rf"{base}\shell\02_Unprotect"
            _reg_add(s2, "", "&Unprotect (Remove Protection)")
            _reg_add(rf"{s2}\command", "", rf'{cmd_prefix} --unprotect "%1"')

            s3 = rf"{base}\shell\03_Sep"
            _reg_add(s3, "", "-")

            s4 = rf"{base}\shell\04_Add"
            _reg_add(s4, "", "&Add to Twinclers Guard List")
            _reg_add(rf"{s4}\command", "", rf'{cmd_prefix} --add "%1"')

            s5 = rf"{base}\shell\05_Open"
            _reg_add(s5, "", "&Open Twinclers Guard")
            _reg_add(rf"{s5}\command", "", rf'{cmd_prefix}')

        if enable:
            _build_submenu(base_dir)
            _build_submenu(base_file)
            return True, "Windows Explorer context menu registered with 4 submenu entries."
        else:
            cls.run_command(["reg", "delete", base_dir,  "/f"])
            cls.run_command(["reg", "delete", base_file, "/f"])
            return True, "Windows Explorer context menu removed."

    @classmethod
    def repair_context_menu(cls) -> bool:
        """
        Self-healing: Checks if the EXE path in the context menu matches the current application location.
        If not (e.g., user moved the .exe to another folder), automatically repair it.
        """
        if not cls.is_context_menu_registered():
            return False
            
        expected_cmd = cls._get_executable_cmd()

        reg_path = r"HKCU\Software\Classes\Directory\shell\TwinclersGuard\shell\05_Open\command"
        code, stdout, _ = cls.run_command(["reg", "query", reg_path, "/ve"])
        if code == 0:
            if expected_cmd not in stdout:
                # Path berubah! (Stale entry). Lakukan registrasi ulang (Repair)
                cls.register_explorer_context_menu(enable=True)
                return True
        return False

acl_engine = ACLManager()

