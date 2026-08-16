"""
Help Window & Interactive Documentation for Twinclers Guard (F1).
Reads and parses external help files (help_en.txt / help_id.txt / help.txt)
using a TreeView on the left and a Text Reader on the right.
Supports multi-language and is 100% NVDA screen reader friendly.
"""

import wx
from core.i18n import _, i18n
from core.help_parser import HelpParser, HelpItem
from core.nvda_speaker import speaker

class HelpDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title=_("HELP_WINDOW_TITLE"),
            size=(840, 560),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX
        )

        self._topic_map = {}
        self.init_ui()
        self.CentreOnParent()

        # Keyboard shortcuts (Esc to close)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        
        # Announcement
        speaker.speak(_("HELP_WINDOW_INSTRUCTION"))

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Instruksi singkat di atas
        header_lbl = wx.StaticText(
            self,
            label=_("HELP_WINDOW_INSTRUCTION")
        )
        main_sizer.Add(header_lbl, 0, wx.ALL | wx.EXPAND, 8)

        # Split area / Sizer horizontal
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 1. KIRI: TreeCtrl untuk kategori bantuan
        tree_panel = wx.Panel(self)
        tree_box = wx.StaticBoxSizer(wx.VERTICAL, tree_panel, _("HELP_TREEVIEW_LABEL"))
        
        self.tree = wx.TreeCtrl(
            tree_box.GetStaticBox(),
            style=wx.TR_DEFAULT_STYLE | wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_SINGLE
        )
        self.tree.SetName(_("HELP_TREEVIEW_LABEL"))
        tree_box.Add(self.tree, 1, wx.EXPAND | wx.ALL, 4)
        tree_panel.SetSizer(tree_box)
        content_sizer.Add(tree_panel, 1, wx.EXPAND | wx.RIGHT, 4)

        # 2. KANAN: TextCtrl untuk pembaca isi
        reader_panel = wx.Panel(self)
        reader_box = wx.StaticBoxSizer(wx.VERTICAL, reader_panel, _("HELP_READER_LABEL"))
        
        self.text_reader = wx.TextCtrl(
            reader_box.GetStaticBox(),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        self.text_reader.SetName(_("HELP_READER_LABEL"))
        reader_box.Add(self.text_reader, 1, wx.EXPAND | wx.ALL, 4)
        reader_panel.SetSizer(reader_box)
        content_sizer.Add(reader_panel, 2, wx.EXPAND | wx.LEFT, 4)

        main_sizer.Add(content_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # Bottom Action Bar (Tombol Tutup)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        
        self.btn_close = wx.Button(self, wx.ID_CLOSE, _("HELP_BTN_CLOSE"))
        self.btn_close.Bind(wx.EVT_BUTTON, self.on_close)
        btn_sizer.Add(self.btn_close, 0, wx.ALL, 8)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.TOP, 4)

        self.SetSizer(main_sizer)

        # Populate tree from external parsed text file
        self.populate_tree()

        # Bind events
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_tree_selection_changed)

        # Set initial focus to tree
        self.tree.SetFocus()

    def _add_help_node_recursive(self, parent_id, help_item: HelpItem, first_selectable: list):
        node_id = self.tree.AppendItem(parent_id, help_item.title)
        self.tree.SetItemData(node_id, (help_item.title, help_item.content))
        
        if not first_selectable:
            first_selectable.append(node_id)

        for child in help_item.children:
            self._add_help_node_recursive(node_id, child, first_selectable)
            
        if help_item.children:
            self.tree.Expand(node_id)

    def populate_tree(self):
        """Loads help topic structure from the help_{lang}.txt file using HelpParser."""
        self.tree.DeleteAllItems()

        # Muat daftar HelpItem dari file teks berdasarkan bahasa aktif
        help_items = HelpParser.load_help_for_language(i18n.current_lang)

        root_label = "Documentation" if i18n.current_lang == "en" else "Semua Topik Bantuan"
        root_id = self.tree.AddRoot(root_label)
        self.tree.SetItemData(root_id, (root_label, "Select any topic from the list to view its documentation."))
        first_selectable = []

        for item in help_items:
            self._add_help_node_recursive(root_id, item, first_selectable)

        self.tree.Expand(root_id)
        if first_selectable:
            self.tree.SelectItem(first_selectable[0])

    def on_tree_selection_changed(self, event):
        item_id = event.GetItem()
        if not item_id.IsOk():
            return

        data = self.tree.GetItemData(item_id)
        if data and isinstance(data, (tuple, list)):
            title, text = data
            self.text_reader.SetValue(text or title)
            self.text_reader.SetInsertionPoint(0)
        else:
            item_text = self.tree.GetItemText(item_id)
            self.text_reader.SetValue(f"Select a topic under {item_text}." if i18n.current_lang == "en" else f"Silakan pilih sub-topik di bawah {item_text}.")

        event.Skip()

    def on_char_hook(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def on_close(self, event):
        self.Close()
