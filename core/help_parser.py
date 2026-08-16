"""
Help File Parser for Twinclers Guard.
Reads and parses text-based help files (such as help.txt / help_en.txt / help_id.txt)
based on topic markers (# Topic, ## Subtopic) into a Tree data structure for wx.TreeCtrl.
"""

import os
from typing import List, Dict, Optional

class HelpItem:
    def __init__(self, title: str, level: int = 1, content: str = ""):
        self.title = title.strip()
        self.level = level
        self.content = content.strip()
        self.children: List['HelpItem'] = []

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "level": self.level,
            "content": self.content,
            "children": [c.to_dict() for c in self.children]
        }

class HelpParser:
    @staticmethod
    def get_help_filepath(lang_code: str = "en") -> str:
        """Finds the help file path based on language or fallbacks to default."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 1. Cek di locales/help_{lang}.txt
        lang_file = os.path.join(base_dir, "locales", f"help_{lang_code}.txt")
        if os.path.exists(lang_file):
            return lang_file
            
        # 2. Cek di root help_{lang}.txt
        root_lang_file = os.path.join(base_dir, f"help_{lang_code}.txt")
        if os.path.exists(root_lang_file):
            return root_lang_file

        # 3. Fallback ke locales/help_en.txt
        default_file = os.path.join(base_dir, "locales", "help_en.txt")
        if os.path.exists(default_file):
            return default_file

        # 4. Fallback ke root help.txt
        root_file = os.path.join(base_dir, "help.txt")
        return root_file

    @classmethod
    def parse_file(cls, filepath: str) -> List[HelpItem]:
        """
        Parses a text file with heading formats (#, ##, ###) into a hierarchical tree structure.
        """
        if not os.path.exists(filepath):
            return []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError) as e:
            print(f"[HelpParser] Gagal membaca {filepath}: {e}")
            return []

        root_items: List[HelpItem] = []
        item_stack: List[HelpItem] = [] # Stack untuk melacak parent berdasarkan level
        current_content_lines: List[str] = []
        current_item: Optional[HelpItem] = None

        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()

            # Deteksi Header (#, ##, ###)
            if stripped.startswith("#"):
                # Hitung level heading
                level = 0
                for char in stripped:
                    if char == "#":
                        level += 1
                    else:
                        break
                
                # Judul setelah tanda #
                title = stripped[level:].strip()

                if current_item:
                    current_item.content = "\n".join(current_content_lines).strip()
                    current_content_lines = []

                new_item = HelpItem(title=title, level=level)

                # Atur relasi parent-child berdasarkan level
                while item_stack and item_stack[-1].level >= level:
                    item_stack.pop()

                if item_stack:
                    item_stack[-1].children.append(new_item)
                else:
                    root_items.append(new_item)

                item_stack.append(new_item)
                current_item = new_item
            else:
                # Konten baris teks
                if current_item is not None:
                    current_content_lines.append(line)

        # Simpan baris terakhir untuk item penutup
        if current_item:
            current_item.content = "\n".join(current_content_lines).strip()

        return root_items

    @classmethod
    def load_help_for_language(cls, lang_code: str = "en") -> List[HelpItem]:
        """Helper to directly load and parse help data for a specific language."""
        fpath = cls.get_help_filepath(lang_code)
        return cls.parse_file(fpath)
