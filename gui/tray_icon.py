"""
System Tray (TaskBar) Icon for Twinclers Guard.
Provides Minimize to Tray, Quick Actions Menu, and window restoration via keyboard shortcuts/NVDA.
"""

import wx
import wx.adv
from core.i18n import _
from core.storage import storage
from core.acl_manager import acl_engine
from core.nvda_speaker import speaker

class TwinclersTrayIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame
        self._icon_set = False
        
        # Buat icon shield bawaan (32x32) jika TaskBar tersedia
        if self.IsAvailable():
            try:
                icon = self.create_shield_icon()
                self.SetIcon(icon, _("APP_TITLE"))
                self._icon_set = True
            except Exception as e:
                print(f"[Tray] SetIcon skipped: {e}")

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_restore)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_restore)

    def create_shield_icon(self) -> wx.Icon:
        """Creates a clean and sharp shield bitmap for the tray icon."""
        bmp = wx.Bitmap(32, 32)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
        dc.Clear()

        # Gambar perisai (Shield)
        dc.SetBrush(wx.Brush(wx.Colour(30, 144, 255))) # Dodger Blue
        dc.SetPen(wx.Pen(wx.Colour(255, 255, 255), 2))
        
        # Polygon perisai
        points = [
            wx.Point(6, 4),
            wx.Point(26, 4),
            wx.Point(26, 18),
            wx.Point(16, 28),
            wx.Point(6, 18)
        ]
        dc.DrawPolygon(points)

        # Gambar gembok kecil di tengah
        dc.SetBrush(wx.Brush(wx.Colour(255, 255, 255)))
        dc.SetPen(wx.Pen(wx.Colour(255, 255, 255)))
        dc.DrawRectangle(11, 14, 10, 8)
        dc.DrawCircle(16, 12, 4)

        dc.SelectObject(wx.NullBitmap)
        
        icon = wx.Icon()
        icon.CopyFromBitmap(bmp)
        return icon

    def CreatePopupMenu(self):
        """Creates the Right-Click Menu for the Tray Icon."""
        menu = wx.Menu()

        m_show = menu.Append(wx.ID_ANY, _("MENU_TRAY_SHOW", default="&Show Twinclers Guard"))
        menu.AppendSeparator()

        m_prot_all = menu.Append(wx.ID_ANY, _("MENU_PROTECT_ALL"))
        m_unprot_all = menu.Append(wx.ID_ANY, _("MENU_UNPROTECT_ALL"))
        menu.AppendSeparator()

        m_exit = menu.Append(wx.ID_ANY, _("MENU_EXIT"))

        self.Bind(wx.EVT_MENU, self.on_restore, m_show)
        self.Bind(wx.EVT_MENU, self.on_protect_all, m_prot_all)
        self.Bind(wx.EVT_MENU, self.on_unprotect_all, m_unprot_all)
        self.Bind(wx.EVT_MENU, self.on_exit, m_exit)

        return menu

    def on_restore(self, event):
        """Restores and displays the application window."""
        if not self.frame.IsShown():
            self.frame.Show()
        self.frame.Iconize(False)
        self.frame.Raise()
        self.frame.SetFocus()
        speaker.speak(_("ANNOUNCE_RESTORED_TRAY", default="Twinclers Guard window restored."))

    def on_protect_all(self, event):
        items = storage.get_all()
        for it in items:
            acl_engine.protect(it["path"], mode=it.get("mode", "anti_delete"))
            storage.update_item(it["path"], status="protected")
        self.frame.refresh_list()
        speaker.speak(_("ANNOUNCE_PROTECT_ALL", count=len(items)))

    def on_unprotect_all(self, event):
        self.frame.on_unprotect_all(None)

    def on_exit(self, event):
        if self._icon_set:
            try:
                self.RemoveIcon()
            except Exception:
                pass
        self.frame.Destroy()
