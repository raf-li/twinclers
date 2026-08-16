"""
Dialogs collection for Twinclers Guard: Add item, Change Mode, Custom ACL, Test Result, About.
Supports Anti-Delete, Instant Password Gate (0.01s), AES-256 Vault, Anti-Rename, Append-Only, Read-Only, Full Lock, and Custom Granular modes.
100% NVDA screen reader friendly and keyboard navigable.
"""

import os
import wx
from core.i18n import _
from core.nvda_speaker import speaker
from gui.password_dialog import SetPasswordDialog

class CustomACLDialog(wx.Dialog):
    """Dialog to configure granular NTFS ACL permissions."""
    def __init__(self, parent, target_name=""):
        name_only = os.path.basename(target_name) or target_name
        super().__init__(
            parent,
            title=_("DIALOG_CUSTOM_TITLE", name=name_only, default=f"Custom ACL Rules - {name_only}"),
            size=(520, 360),
            style=wx.DEFAULT_DIALOG_STYLE
        )
        self.rules = {
            "deny_delete": True,
            "deny_rename": False,
            "deny_write": False,
            "deny_create": False,
            "recursive": True
        }
        self.init_ui()
        self.CentreOnParent()

    def init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        lbl = wx.StaticText(self, label=_("DIALOG_CUSTOM_INSTRUCTION", default="Select specific Windows NTFS permissions to restrict:"))
        sizer.Add(lbl, 0, wx.ALL, 10)

        box = wx.StaticBoxSizer(wx.VERTICAL, self, _("DIALOG_CUSTOM_BOX", default="&Permission Restrictions (Deny Rules)"))
        st_box = box.GetStaticBox()

        self.chk_delete = wx.CheckBox(st_box, label=_("RULE_DENY_DELETE", default="&Deny Deletion of Files & Folders (Prevent Delete)"))
        self.chk_delete.SetValue(True)

        self.chk_rename = wx.CheckBox(st_box, label=_("RULE_DENY_RENAME", default="Deny &Renaming and Moving (Prevent Rename/Move)"))
        self.chk_write = wx.CheckBox(st_box, label=_("RULE_DENY_WRITE", default="Deny &Modifying Existing Files (Prevent Edit)"))
        self.chk_create = wx.CheckBox(st_box, label=_("RULE_DENY_CREATE", default="Deny &Creating New Files/Folders (Prevent Create)"))

        self.chk_inherit = wx.CheckBox(st_box, label=_("RULE_INHERITANCE", default="&Apply recursively to all subfolders & files (Inheritance)"))
        self.chk_inherit.SetValue(True)

        box.Add(self.chk_delete, 0, wx.ALL, 6)
        box.Add(self.chk_rename, 0, wx.ALL, 6)
        box.Add(self.chk_write, 0, wx.ALL, 6)
        box.Add(self.chk_create, 0, wx.ALL, 6)
        box.Add(wx.StaticLine(st_box), 0, wx.EXPAND | wx.ALL, 6)
        box.Add(self.chk_inherit, 0, wx.ALL, 6)

        sizer.Add(box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        if btn_sizer:
            sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(sizer)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def on_ok(self, event):
        self.rules = {
            "deny_delete": self.chk_delete.GetValue(),
            "deny_rename": self.chk_rename.GetValue(),
            "deny_write": self.chk_write.GetValue(),
            "deny_create": self.chk_create.GetValue(),
            "recursive": self.chk_inherit.GetValue()
        }
        event.Skip()


class AddItemDialog(wx.Dialog):
    """Dialog to add a folder or file to the protection list."""
    def __init__(self, parent, initial_type="folder"):
        super().__init__(
            parent,
            title=_("DIALOG_ADD_TITLE"),
            size=(580, 440),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.item_type = initial_type
        self.selected_path = ""
        self.selected_mode = "anti_delete"
        self.custom_rules = None
        self.password = None
        self.auto_protect = True

        self.init_ui()
        self.CentreOnParent()

    def init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Radio Tipe Item
        type_box = wx.StaticBoxSizer(wx.HORIZONTAL, self, _("DIALOG_ADD_TARGET_TYPE"))
        self.radio_folder = wx.RadioButton(type_box.GetStaticBox(), label=_("DIALOG_ADD_RADIO_FOLDER"), style=wx.RB_GROUP)
        self.radio_file = wx.RadioButton(type_box.GetStaticBox(), label=_("DIALOG_ADD_RADIO_FILE"))
        if self.item_type == "folder":
            self.radio_folder.SetValue(True)
        else:
            self.radio_file.SetValue(True)

        type_box.Add(self.radio_folder, 0, wx.ALL, 6)
        type_box.Add(self.radio_file, 0, wx.ALL, 6)
        sizer.Add(type_box, 0, wx.EXPAND | wx.ALL, 8)

        # Path input + Browse Button
        path_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("DIALOG_ADD_PATH_LOCATION"))
        path_row = wx.BoxSizer(wx.HORIZONTAL)
        
        self.txt_path = wx.TextCtrl(path_box.GetStaticBox())
        self.txt_path.SetName(_("DIALOG_ADD_INPUT_NAME"))
        self.btn_browse = wx.Button(path_box.GetStaticBox(), label=_("DIALOG_ADD_BTN_BROWSE"))
        self.btn_browse.Bind(wx.EVT_BUTTON, self.on_browse)

        path_row.Add(self.txt_path, 1, wx.EXPAND | wx.RIGHT, 6)
        path_row.Add(self.btn_browse, 0)
        path_box.Add(path_row, 0, wx.EXPAND | wx.ALL, 4)
        sizer.Add(path_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # Pilihan Mode Proteksi
        mode_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("DIALOG_ADD_MODE_BOX"))
        self.mode_keys = [
            "anti_delete",
            "instant_gate",
            "aes256_vault",
            "anti_rename_delete",
            "append_only",
            "read_only",
            "full_lock",
            "custom"
        ]
        self.mode_choices = wx.Choice(mode_box.GetStaticBox(), choices=[
            _("MODE_ANTI_DELETE"),
            _("MODE_INSTANT_GATE"),
            _("MODE_AES256_VAULT"),
            _("MODE_ANTI_RENAME"),
            _("MODE_APPEND_ONLY"),
            _("MODE_READ_ONLY"),
            _("MODE_FULL_LOCK"),
            _("MODE_CUSTOM")
        ])
        self.mode_choices.SetSelection(0)
        self.mode_choices.SetName(_("DIALOG_ADD_MODE_BOX"))
        mode_box.Add(self.mode_choices, 0, wx.EXPAND | wx.ALL, 4)
        sizer.Add(mode_box, 0, wx.EXPAND | wx.ALL, 8)

        # Checkbox: Langsung kunci sekarang
        self.chk_auto_protect = wx.CheckBox(self, label=_("DIALOG_ADD_AUTO_PROTECT"))
        self.chk_auto_protect.SetValue(True)
        sizer.Add(self.chk_auto_protect, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        # Tombol Aksi
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        if btn_sizer:
            sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(sizer)

        # Bind OK button validation
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        self.txt_path.SetFocus()

    def on_browse(self, event):
        if self.radio_folder.GetValue():
            with wx.DirDialog(self, _("MENU_ADD_FOLDER").replace("&", "").split("\t")[0], style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    self.txt_path.SetValue(dlg.GetPath())
        else:
            with wx.FileDialog(self, _("MENU_ADD_FILE").replace("&", "").split("\t")[0], style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    self.txt_path.SetValue(dlg.GetPath())

    def on_ok(self, event):
        path = self.txt_path.GetValue().strip()
        if not path:
            speaker.speak(_("DIALOG_ADD_EMPTY_PATH"))
            self.txt_path.SetFocus()
            return

        if not os.path.exists(path):
            speaker.speak(_("DIALOG_ADD_INVALID_PATH", path=path))
            self.txt_path.SetFocus()
            return

        self.selected_path = os.path.abspath(path)
        self.item_type = "folder" if self.radio_folder.GetValue() else "file"
        idx = self.mode_choices.GetSelection()
        self.selected_mode = self.mode_keys[idx] if idx >= 0 else "anti_delete"
        self.auto_protect = self.chk_auto_protect.GetValue()
        
        # Cek jika folder sudah berisi file .twvault (Vault yang dipindahkan dari PC lain)
        from core.vault_manager import vault_mgr
        if vault_mgr.has_encrypted_vault_files(self.selected_path):
            self.selected_mode = "aes256_vault"
            self.auto_protect = False # Sudah terenkripsi
            event.Skip()
            return

        # Jika mode Password (Instant Gate / AES-256 Vault), minta password baru
        if self.selected_mode in ["instant_gate", "aes256_vault"]:
            with SetPasswordDialog(self, target_path=self.selected_path, mode=self.selected_mode) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    self.password = dlg.password
                else:
                    return

        # Jika mode Custom, buka konfigurasi dialog custom
        elif self.selected_mode == "custom":
            with CustomACLDialog(self, target_name=self.selected_path) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    self.custom_rules = dlg.rules
                else:
                    return

        event.Skip()


class ChangeModeDialog(wx.Dialog):
    """Dialog to change the protection mode of an existing item."""
    def __init__(self, parent, current_mode="anti_delete", target_name=""):
        name_only = os.path.basename(target_name) or target_name
        super().__init__(
            parent,
            title=_("DIALOG_CHG_TITLE", name=name_only),
            size=(520, 380),
            style=wx.DEFAULT_DIALOG_STYLE
        )
        self.target_name = target_name
        self.mode_keys = [
            "anti_delete",
            "instant_gate",
            "aes256_vault",
            "anti_rename_delete",
            "append_only",
            "read_only",
            "full_lock",
            "custom"
        ]
        self.selected_mode = current_mode
        self.custom_rules = None
        self.password = None
        self.init_ui(current_mode)
        self.CentreOnParent()

    def init_ui(self, current_mode):
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(self, label=_("DIALOG_CHG_LABEL"))
        sizer.Add(lbl, 0, wx.ALL, 10)

        choices = [
            _("MODE_ANTI_DELETE"),
            _("MODE_INSTANT_GATE"),
            _("MODE_AES256_VAULT"),
            _("MODE_ANTI_RENAME"),
            _("MODE_APPEND_ONLY"),
            _("MODE_READ_ONLY"),
            _("MODE_FULL_LOCK"),
            _("MODE_CUSTOM")
        ]

        self.radio_box = wx.RadioBox(
            self,
            label=_("DIALOG_CHG_BOX"),
            choices=choices,
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS
        )
        
        # Set selection
        for i, m_id in enumerate(self.mode_keys):
            if m_id == current_mode:
                self.radio_box.SetSelection(i)
                break

        sizer.Add(self.radio_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        if btn_sizer:
            sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(sizer)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def on_ok(self, event):
        idx = self.radio_box.GetSelection()
        self.selected_mode = self.mode_keys[idx]
        
        if self.selected_mode in ["instant_gate", "aes256_vault"]:
            with SetPasswordDialog(self, target_path=self.target_name, mode=self.selected_mode) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    self.password = dlg.password
                else:
                    return

        elif self.selected_mode == "custom":
            with CustomACLDialog(self, target_name=self.target_name) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    self.custom_rules = dlg.rules
                else:
                    return

        event.Skip()


class TestResultDialog(wx.Dialog):
    """Dialog to display the deletion protection test result."""
    def __init__(self, parent, success: bool, message: str, path: str):
        super().__init__(
            parent,
            title=_("DIALOG_TEST_TITLE"),
            size=(580, 320),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.success = success
        self.message = message
        self.path = path

        self.init_ui()
        self.CentreOnParent()

        # Announce to NVDA
        status_text = "Pass: " if success else "Warning: "
        speaker.speak(f"{status_text}{message}")

    def init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        status_title = _("DIALOG_TEST_SUCCESS_HEADER") if self.success else _("DIALOG_TEST_FAIL_HEADER")
        lbl_status = wx.StaticText(self, label=status_title)
        font = lbl_status.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        lbl_status.SetFont(font)
        sizer.Add(lbl_status, 0, wx.ALL, 10)

        lbl_path = wx.StaticText(self, label=_("DIALOG_TEST_TARGET", path=self.path))
        sizer.Add(lbl_path, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        res_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("DIALOG_TEST_DETAILS_BOX"))
        txt_res = wx.TextCtrl(res_box.GetStaticBox(), value=self.message, style=wx.TE_MULTILINE | wx.TE_READONLY)
        txt_res.SetName(_("DIALOG_TEST_DETAILS_BOX"))
        res_box.Add(txt_res, 1, wx.EXPAND | wx.ALL, 4)
        sizer.Add(res_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK)
        if btn_sizer:
            sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
