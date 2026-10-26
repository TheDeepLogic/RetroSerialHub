"""Retro Serial Hub flyout/accordion menu."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from .shortcuts import ShortcutsManager
from rsh_console import VERSION


class OSFlyoutMenu:
    """Flyout menu where only the selected category is expanded."""

    from .menu_data import SECTIONS

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

        self.shortcuts_page = 0
        self.section_page = 0
        self.page_capacity = 8
        self.shortcut_capacity = 8
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
            all_shortcuts = self.shortcuts_manager.list_shortcuts()
            self.shortcuts_page = min(self.shortcuts_page,max(0,(len(all_shortcuts)-1)//self.shortcut_capacity))
            for idx, sc in enumerate(all_shortcuts[self.shortcuts_page*self.shortcut_capacity:(self.shortcuts_page+1)*self.shortcut_capacity]):
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
        """Select active section by number (0-7, S) or name (case-insensitive)."""
        s = selector.strip().upper()
        self.section_page = 0
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
            items = [it for it in items if it[2] != "disconnect"]
        start = self.section_page*self.page_capacity
        return items[start:start+self.page_capacity]

    def get_action_for_key(self, key: str, is_remote: bool = False):
        """Find the action string for a key in the active section."""
        k = key.strip().upper()
        if self.active_section != 'shortcuts' and k in ('>','<'):
            items=self.SECTIONS[self.active_section][2]
            if not is_remote and self.active_section_name == 'System':
                items=[item for item in items if item[2] != 'disconnect']
            count = len(items)
            self.section_page = (self.section_page+(1 if k == '>' else -1)) % max(1,(count+self.page_capacity-1)//self.page_capacity)
            return 'shortcut_page'
        if self.active_section == "shortcuts":
            if k in ('>','<'):
                total = len(self.shortcuts_manager.list_shortcuts()) if self.shortcuts_manager else 0
                self.shortcuts_page = (self.shortcuts_page + (1 if k == '>' else -1)) % max(1,(total+self.shortcut_capacity-1)//self.shortcut_capacity)
                return 'shortcut_page'
            if k in ("+", "ADD", "NEW", "N"):
                return "shortcut_add"
            if k in ("-", "DEL", "DELETE", "REMOVE", "R"):
                return "shortcut_del"

        for item_key, _, action in self.get_active_items(is_remote=is_remote):
            if k == item_key.upper():
                return action
        return None

    def render(
        self, columns=80, translate_ansi=False, welcome_banner='Retro Serial Hub',
        version=VERSION, is_remote=False, status='', rows=24,
    ):
        """Anchor the footer to the configured last row, without cursor addressing."""
        if not isinstance(rows,int) or not 16 <= rows <= 100:
            raise ValueError('Terminal height must be 16-100 rows.')
        columns = 40 if columns == 40 else 80
        width = columns-1  # Avoid auto-wrap in the rightmost terminal cell.
        footer_height = 4
        header = [welcome_banner[:width], f'v{version}, copyright (c) 2025-2026', '']
        base_height = len(header)+len(self.SECTIONS)+1+footer_height
        available_actions=rows-base_height
        self.page_capacity = max(1,min(8,available_actions))
        self.shortcut_capacity = max(1,min(8,rows-base_height-1))
        if self.active_section != 'shortcuts':
            items=self.SECTIONS[self.active_section][2]
            if not is_remote and self.active_section_name == 'System':
                items=[item for item in items if item[2] != 'disconnect']
            self.section_page=min(self.section_page,max(0,(len(items)-1)//self.page_capacity))
        indent = '    ' if columns == 40 else '      '
        lines = list(header)
        if self.active_section == 'shortcuts':
            lines.append('[0] > SHORTCUTS <')
            if not self.shortcuts_manager or not self.shortcuts_manager.has_shortcuts():
                lines.extend([indent+'(No shortcuts configured yet)',indent+'+] Add Shortcut'] if available_actions >= 2 else [indent+'(empty) +] Add Shortcut'])
            else:
                for key,label,action in self.get_shortcuts_items():
                    if key not in ('+','-'):
                        prefix=indent+key+'] '
                        available=width-len(prefix)
                        if len(label)>available:
                            label=label[:max(0,available-3)]+'...'
                        lines.append(prefix+label)
                if available_actions >= 2:
                    lines.append(indent+'+] Add Shortcut  -] Remove Shortcut')
        else:
            lines.append('[0]   SHORTCUTS')
        for index,(title,number,items) in enumerate(self.SECTIONS):
            if self.active_section == index:
                lines.append(f'[{number}] > {title.upper()} <')
                for key,label,action in self.get_active_items(is_remote=is_remote):
                    if action == 'columns':
                        label=f'Switch to {40 if columns == 80 else 80} Columns'
                    elif action == 'translate_ansi':
                        label='ANSI: Turn Off' if translate_ansi else 'ANSI: Turn On'
                    lines.append((indent+key+'] '+label)[:width])
            else:
                lines.append(f'[{number}]   {title.upper()}')
        if self.active_section == 'shortcuts':
            paged=self.shortcuts_manager and len(self.shortcuts_manager.list_shortcuts())>self.shortcut_capacity
        else:
            items=self.SECTIONS[self.active_section][2]
            if not is_remote and self.active_section_name == 'System':
                items=[item for item in items if item[2] != 'disconnect']
            paged=len(items)>self.page_capacity
        prompt=(f'Select [1-{len(self.SECTIONS)}] for section, [A-H] for item, or command (CLI/ATM): '
                if columns == 80 else f'[0-{len(self.SECTIONS)}] Sec, [A-H] Item, or CLI: ')
        if self.active_section == 'shortcuts' and available_actions < 2:
            prompt='A-H Item +/- Edit 0-7 Sec CLI/ATM: '
        if paged:
            prompt='A-H Item </> Page +/- Edit 0-7 Sec: ' if self.active_section == 'shortcuts' else 'A-H Item </> Page 0-7 Sec CLI/ATM: '
        # All footer fields occupy exactly one row; incoming notices are queued by the session.
        status_line=' '.join(status.splitlines())[:width]
        footer=[status_line,'Type ATM to return to this menu.']
        footer.append('')
        footer.append(prompt[:width])
        body_height=rows-len(footer)
        if len(lines)>body_height:
            raise ValueError('Menu body exceeds the configured height.')
        lines.extend(['']*(body_height-len(lines)))
        return '\r\n'.join(lines+footer)
