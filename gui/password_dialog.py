"""
Password Entry & Setup Dialogs for Twinclers Guard.
Supports Instant Gate (0.01s) and AES-256 Military Vault modes with full NVDA accessibility.
"""

import os
import wx
from core.i18n import _
from core.vault_manager import vault_mgr
from core.nvda_speaker import speaker

class PasswordPromptDialog(wx.Dialog):
    """Password input dialog when opening a protected folder."""
    def __init__(self, parent, target_path: str):
        self.target_path = target_path
        self.target_name = os.path.basename(target_path) or target_path
        
        super().__init__(
            parent,
            title=_("PASSWORD_PROMPT_TITLE", name=self.target_name, default=f"Unlock {self.target_name}"),
            size=(440, 240),
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )
        self.entered_password = ""
        self.init_ui()
        self.CentreOnScreen()
        
        # NVDA announcement & Bring to front
        speaker.speak(_("ANNOUNCE_ENTER_PASSWORD", name=self.target_name, default=f"Folder {self.target_name} is password protected. Enter password to unlock."))
        self.Raise()
        self.txt_pwd.SetFocus()

    def init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Header Info
        lbl_info = wx.StaticText(
            self,
            label=_("PASSWORD_PROMPT_HEADER", name=self.target_name, default=f"Enter password to unlock:\n{self.target_path}")
        )
        sizer.Add(lbl_info, 0, wx.ALL, 12)

        # Password Input Row
        pwd_box = wx.BoxSizer(wx.VERTICAL)
        lbl_pwd = wx.StaticText(self, label=_("PASSWORD_LABEL", default="&Password:"))
        self.txt_pwd = wx.TextCtrl(self, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
        self.txt_pwd.SetName(_("PASSWORD_LABEL", default="Password"))
        
        pwd_box.Add(lbl_pwd, 0, wx.BOTTOM, 4)
        pwd_box.Add(self.txt_pwd, 0, wx.EXPAND)
        sizer.Add(pwd_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)

        # Show Password Checkbox
        self.chk_show = wx.CheckBox(self, label=_("SHOW_PASSWORD", default="&Show Password (Alt+S)"))
        self.chk_show.Bind(wx.EVT_CHECKBOX, self.on_toggle_show_pwd)
        sizer.Add(self.chk_show, 0, wx.ALL, 12)

        # Tombol Aksi
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        if btn_sizer:
            sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(sizer)

        # Bind events
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        self.txt_pwd.Bind(wx.EVT_TEXT_ENTER, self.on_ok)

    def on_toggle_show_pwd(self, event):
        """Toggles between masking the password and showing plain text."""
        current_val = self.txt_pwd.GetValue()
        pos = self.txt_pwd.GetInsertionPoint()
        
        # Buat style baru
        style = wx.TE_PROCESS_ENTER if self.chk_show.GetValue() else (wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
        
        # Recreate TextCtrl dengan style baru
        parent = self.txt_pwd.GetParent()
        sizer = self.txt_pwd.GetContainingSizer()
        
        sizer.Detach(self.txt_pwd)
        self.txt_pwd.Destroy()
        
        self.txt_pwd = wx.TextCtrl(parent, style=style, value=current_val)
        self.txt_pwd.SetName(_("PASSWORD_LABEL", default="Password"))
        self.txt_pwd.Bind(wx.EVT_TEXT_ENTER, self.on_ok)
        sizer.Add(self.txt_pwd, 0, wx.EXPAND)
        sizer.Layout()
        
        self.txt_pwd.SetInsertionPoint(pos)
        self.txt_pwd.SetFocus()

    def on_ok(self, event):
        pwd = self.txt_pwd.GetValue()
        if not pwd:
            speaker.speak(_("PASSWORD_EMPTY_MSG", default="Please enter a password."))
            self.txt_pwd.SetFocus()
            return

        ok, msg = vault_mgr.unlock_item(self.target_path, pwd)

        # VLN-04: Zero-fill password dari TextCtrl dan variabel lokal setelah digunakan
        self.txt_pwd.SetValue("")
        self.entered_password = ""

        if ok:
            speaker.speak(_("ANNOUNCE_UNLOCK_SUCCESS", name=self.target_name, default=f"Folder {self.target_name} unlocked successfully."))
            self.EndModal(wx.ID_OK)
        else:
            # VLN-09: Tampilkan pesan rate limit jika berlaku
            if "Try again in" in msg:
                speaker.speak(msg)
            else:
                speaker.speak(_("ANNOUNCE_WRONG_PASSWORD", default="Wrong password. Access denied."))
            self.txt_pwd.SelectAll()
            self.txt_pwd.SetFocus()


class SetPasswordDialog(wx.Dialog):
    """Dialog to set a new password for a folder."""
    def __init__(self, parent, target_path: str, mode: str = "instant_gate"):
        self.target_path = target_path
        self.mode = mode
        self.target_name = os.path.basename(target_path) or target_path
        self.password = ""

        super().__init__(
            parent,
            title=_("SET_PASSWORD_TITLE", name=self.target_name, default=f"Set Password for {self.target_name}"),
            size=(460, 310),
            style=wx.DEFAULT_DIALOG_STYLE
        )
        self.init_ui()
        self.CentreOnParent()

    def init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        mode_name = _("MODE_INSTANT_GATE", default="Instant Password Gate (0.01s)") if self.mode == "instant_gate" else _("MODE_AES256_VAULT", default="AES-256 Military Vault")
        lbl_info = wx.StaticText(
            self,
            label=_("SET_PASSWORD_INFO", name=self.target_name, mode=mode_name, default=f"Protecting {self.target_name} with {mode_name}.\nSet your master password:")
        )
        sizer.Add(lbl_info, 0, wx.ALL, 10)

        # Password 1
        lbl_p1 = wx.StaticText(self, label=_("ENTER_PASSWORD", default="&New Password:"))
        self.txt_p1 = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.txt_p1.SetName(_("ENTER_PASSWORD", default="New Password"))
        sizer.Add(lbl_p1, 0, wx.LEFT | wx.RIGHT, 10)
        sizer.Add(self.txt_p1, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Confirm Password
        lbl_p2 = wx.StaticText(self, label=_("CONFIRM_PASSWORD", default="&Confirm Password:"))
        self.txt_p2 = wx.TextCtrl(self, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
        self.txt_p2.SetName(_("CONFIRM_PASSWORD", default="Confirm Password"))
        sizer.Add(lbl_p2, 0, wx.LEFT | wx.RIGHT, 10)
        sizer.Add(self.txt_p2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        if btn_sizer:
            sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        self.txt_p2.Bind(wx.EVT_TEXT_ENTER, self.on_ok)
        self.txt_p1.SetFocus()

    def on_ok(self, event):
        p1 = self.txt_p1.GetValue()
        p2 = self.txt_p2.GetValue()

        if not p1:
            speaker.speak(_("PASSWORD_EMPTY_MSG", default="Password cannot be empty."))
            self.txt_p1.SetFocus()
            return

        if p1 != p2:
            speaker.speak(_("PASSWORD_MISMATCH_MSG", default="Passwords do not match. Please re-enter."))
            # VLN-04: Zero-fill both fields on mismatch
            self.txt_p1.SetValue("")
            self.txt_p2.SetValue("")
            self.txt_p1.SetFocus()
            return

        self.password = p1

        # VLN-04: Zero-fill confirm field — password is now in self.password only
        self.txt_p2.SetValue("")
        event.Skip()
