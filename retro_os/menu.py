"""Retro Serial Hub flyout/accordion menu."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from .shortcuts import ShortcutsManager


class OSFlyoutMenu:
    """Flyout menu where only the selected category is expanded."""

    SECTIONS: List[Tuple[str, str, List[Tuple[str, str, str]]]] = [
        (
            "Communications",
            "1",
            [
                ("A", "Bulletin Boards", "bbs"),
                ("B", "Telnet Terminal", "telnet"),
                ("C", "Web Browser", "browser"),
                ("D", "FTP Client", "ftp"),
                ("E", "Electronic Mail", "mail"),
            ],
        ),
        (
            "Host Connectivity",
            "2",
            [
                ("A", "Host Applications", "apps"),
                ("B", "Launch Host App", "launch"),
                ("C", "Keyboard Bridge", "keyboard"),
                ("D", "COM Port Bridge", "com_bridge"),
                ("E", "Host Terminal / Prompt", "host_terminal"),
                ("F", "System Monitor & Media", "host_media"),
            ],
        ),
        (
            "Files & Media",
            "3",
            [
                ("A", "File Transfers", "files"),
                ("B", "Document Viewer", "view"),
                ("C", "Text Library", "textlib"),
                ("D", "ASCII Image Viewer", "ascii_viewer"),
            ],
        ),
        (
            "Games",
            "4",
            [
                ("A", "Minesweeper", "mines"),
                ("B", "Solitaire", "solitaire"),
                ("C", "WarGames (W.O.P.R.)", "wargames"),
            ],
        ),
        (
            "Accessories",
            "5",
            [
                ("A", "Notepad (Notes)", "notes"),
                ("B", "Calculator", "calc"),
                ("C", "Live Weather & News", "weather_news"),
                ("D", "AI Assistant", "ai"),
                ("E", "Host Printing", "print"),
            ],
        ),
        (
            "System",
            "6",
            [
                ("A", "Command Shell (CLI)", "cli"),
                ("B", "Task Scheduler", "scheduler"),
                ("C", "Terminal Settings", "terminal_settings"),
                ("D", "Keyboard Profiles", "kb"),
                ("E", "Help & User Guide", "help_menu"),
                ("F", "Welcome Banner", "welcome_banner"),
                ("G", "Disconnect", "disconnect"),
            ],
        ),
    ]

    def __init__(
        self,
        initial_section: Optional[Any] = None,
        shortcuts_manager: Optional[ShortcutsManager] = None,
    ):
        if shortcuts_manager is None:
            try:
                self.shortcuts_manager = ShortcutsManager()
            except Exception:
                self.shortcuts_manager = None
        else:
            self.shortcuts_manager = shortcuts_manager

        if initial_section is not None:
            if isinstance(initial_section, str):
                self.select_section(initial_section)
            else:
                self.active_section = initial_section
        elif self.shortcuts_manager and self.shortcuts_manager.has_shortcuts():
            self.active_section = "shortcuts"
        else:
            self.active_section = 0

    @property
    def active_section_idx(self) -> int:
        if self.active_section == "shortcuts":
            return -1
        return int(self.active_section)

    @active_section_idx.setter
    def active_section_idx(self, val: int):
        self.active_section = val

    @property
    def active_section_name(self) -> str:
        if self.active_section == "shortcuts":
            return "Shortcuts"
        if isinstance(self.active_section, int) and 0 <= self.active_section < len(self.SECTIONS):
            return self.SECTIONS[self.active_section][0]
        return "Accessories"

    def auto_flyout_if_shortcuts(self) -> bool:
        """Expand Shortcuts section if shortcuts are populated."""
        if self.shortcuts_manager and self.shortcuts_manager.has_shortcuts():
            self.active_section = "shortcuts"
            return True
        return False

    def get_shortcuts_items(self) -> List[Tuple[str, str, str]]:
        items = []
        if self.shortcuts_manager:
            for idx, sc in enumerate(self.shortcuts_manager.list_shortcuts()):
                letter = chr(ord("A") + idx)
                items.append((
                    letter,
                    f"{sc['name']} ({sc['command']})",
                    f"shortcut_run:{sc['command']}",
                ))
        items.append(("+", "Add Shortcut", "shortcut_add"))
        if self.shortcuts_manager and self.shortcuts_manager.has_shortcuts():
            items.append(("-", "Remove Shortcut", "shortcut_del"))
        return items

    def select_section(self, selector: str) -> bool:
        """Select active section by number (0-6, S) or name (case-insensitive)."""
        s = selector.strip().upper()
        if s in ("0", "S", "SHORTCUT", "SHORTCUTS"):
            self.active_section = "shortcuts"
            return True
        if s in ("BRIDGING", "BRIDGE", "CONNECTIVITY", "HOST"):
            for idx, (name, _, _) in enumerate(self.SECTIONS):
                if "CONNECTIVITY" in name.upper() or "BRIDGE" in name.upper():
                    self.active_section = idx
                    return True
        for idx, (name, num, _) in enumerate(self.SECTIONS):
            u_name = name.upper()
            if (
                s == num
                or s == u_name
                or (len(s) >= 3 and u_name.startswith(s))
                or (len(s) >= 4 and s in u_name)
            ):
                self.active_section = idx
                return True
        return False

    def get_active_items(self, is_remote: bool = False):
        """Return the items of the currently expanded section."""
        if self.active_section == "shortcuts":
            return self.get_shortcuts_items()
        idx = self.active_section if isinstance(self.active_section, int) else 0
        if not (0 <= idx < len(self.SECTIONS)):
            idx = 0
        items = self.SECTIONS[idx][2]
        if not is_remote and self.active_section_name == "System":
            return [it for it in items if it[2] != "disconnect"]
        return items

    def get_action_for_key(self, key: str, is_remote: bool = False):
        """Find the action string for a key in the active section."""
        k = key.strip().upper()
        if self.active_section == "shortcuts":
            if k in ("+", "ADD", "NEW", "N"):
                return "shortcut_add"
            if k in ("-", "DEL", "DELETE", "REMOVE", "R"):
                return "shortcut_del"

        for item_key, _, action in self.get_active_items(is_remote=is_remote):
            if k == item_key.upper():
                return action
        return None

    def render(
        self,
        columns: int = 80,
        translate_ansi: bool = False,
        welcome_banner: str = "Retro Serial Hub",
        version: str = "1.0",
        is_remote: bool = False,
        status: str = "",
    ) -> str:
        """Render the flyout menu where only the selected section is expanded."""
        lines = []
        if columns == 40:
            lines.append(welcome_banner[:40])
            lines.append(f"v{version}, copyright (c) 2025-2026")
            lines.append("")
        else:
            lines.append("\r\n" + welcome_banner)
            lines.append(f"v{version}, copyright (c) 2025-2026\r\n")

        # Shortcuts section (Section 0)
        indent = "    " if columns == 40 else "      "
        if self.active_section == "shortcuts":
            lines.append("[0] > SHORTCUTS <")
            if not self.shortcuts_manager or not self.shortcuts_manager.has_shortcuts():
                lines.append(f"{indent}(No shortcuts configured yet)")
                lines.append(f"{indent}+] Add Shortcut")
            else:
                for item_key, label, action in self.get_active_items(is_remote=is_remote):
                    display_label = label
                    prefix_len = len(indent) + len(item_key) + 2
                    if prefix_len + len(display_label) > columns - 1:
                        max_label = (columns - 1) - prefix_len - 3
                        if max_label > 5:
                            display_label = display_label[:max_label] + "..."
                    lines.append(f"{indent}{item_key}] {display_label}")
        else:
            lines.append("[0]   SHORTCUTS")

        # Core sections (Sections 1-6)
        for idx, (name, num, _) in enumerate(self.SECTIONS):
            if self.active_section == idx:
                lines.append(f"[{num}] > {name.upper()} <")
                for item_key, label, action in self.get_active_items(is_remote=is_remote):
                    display_label = label
                    if action == "columns":
                        target_cols = 40 if columns == 80 else 80
                        display_label = (
                            f"Switch to {target_cols} Cols"
                            if columns == 40
                            else f"Switch to {target_cols} Columns"
                        )
                    elif action == "translate_ansi":
                        if columns == 40:
                            display_label = (
                                "ANSI: Turn Off"
                                if translate_ansi
                                else "ANSI: Turn On"
                            )
                        else:
                            display_label = (
                                "Turn ANSI Translation Off"
                                if translate_ansi
                                else "Turn ANSI Translation On"
                            )
                    lines.append(f"{indent}{item_key}] {display_label}")
            else:
                lines.append(f"[{num}]   {name.upper()}")

        if status:
            lines.append("")
            lines.append(status)

        lines.append("Type ATM to return to this menu.")
        num_sections = len(self.SECTIONS)
        if columns == 80:
            lines.append("")
            prompt = f"Select [1-{num_sections}] for section, [A-G] for item, or command (CLI/ATM): "
        else:
            prompt = f"[0-{num_sections}] Sec, [A-G] Item, or CLI: "

        return "\r\n".join(lines) + "\r\n" + prompt
