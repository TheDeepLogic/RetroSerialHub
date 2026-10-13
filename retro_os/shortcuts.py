"""User shortcuts manager for Retro Serial OS."""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List, Optional


class ShortcutsManager:
    """Manages custom user shortcuts to actions/commands with arguments."""

    def __init__(self, storage_path: pathlib.Path | str | None = None):
        if storage_path is None:
            self.storage_path = pathlib.Path(__file__).parent.parent / "user_shortcuts.json"
        else:
            self.storage_path = pathlib.Path(storage_path)
        self.shortcuts: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> List[Dict[str, Any]]:
        """Load shortcuts from JSON storage file."""
        if not self.storage_path.exists():
            self.shortcuts = []
            return self.shortcuts
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    cleaned = []
                    for idx, s in enumerate(data, 1):
                        if isinstance(s, dict) and "name" in s and "command" in s:
                            cleaned.append({
                                "id": idx,
                                "name": str(s["name"]),
                                "command": str(s["command"]),
                            })
                    self.shortcuts = cleaned
                else:
                    self.shortcuts = []
        except Exception:
            self.shortcuts = []
        return self.shortcuts

    def save(self) -> bool:
        """Persist shortcuts to JSON storage file."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.shortcuts, f, indent=2)
            return True
        except Exception:
            return False

    def list_shortcuts(self) -> List[Dict[str, Any]]:
        """Return all user shortcuts."""
        return list(self.shortcuts)

    def has_shortcuts(self) -> bool:
        """Return True if at least one shortcut exists."""
        return len(self.shortcuts) > 0

    def add_shortcut(self, name: str, command: str) -> Dict[str, Any]:
        """Add a new shortcut and save to disk."""
        name = name.strip()
        command = command.strip()
        shortcut = {
            "id": len(self.shortcuts) + 1,
            "name": name,
            "command": command,
        }
        self.shortcuts.append(shortcut)
        self.save()
        return shortcut

    def delete_shortcut(self, identifier: int | str) -> bool:
        """Delete a shortcut by 1-based index, letter ('A', 'B'), or name."""
        if not self.shortcuts:
            return False

        # Try numeric index (1-based)
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            idx = int(identifier) - 1
            if 0 <= idx < len(self.shortcuts):
                self.shortcuts.pop(idx)
                for i, s in enumerate(self.shortcuts, 1):
                    s["id"] = i
                self.save()
                return True

        # Try single letter (e.g. 'A', 'B' corresponding to index)
        if isinstance(identifier, str) and len(identifier) == 1 and identifier.isalpha():
            idx = ord(identifier.upper()) - ord("A")
            if 0 <= idx < len(self.shortcuts):
                self.shortcuts.pop(idx)
                for i, s in enumerate(self.shortcuts, 1):
                    s["id"] = i
                self.save()
                return True

        # Try name match
        if isinstance(identifier, str):
            target = identifier.strip().lower()
            for idx, s in enumerate(self.shortcuts):
                if s.get("name", "").strip().lower() == target:
                    self.shortcuts.pop(idx)
                    for i, rem in enumerate(self.shortcuts, 1):
                        rem["id"] = i
                    self.save()
                    return True

        return False

    def get_shortcut(self, identifier: int | str) -> Optional[Dict[str, Any]]:
        """Get a shortcut by index, letter, or name."""
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            idx = int(identifier) - 1
            if 0 <= idx < len(self.shortcuts):
                return self.shortcuts[idx]

        if isinstance(identifier, str) and len(identifier) == 1 and identifier.isalpha():
            idx = ord(identifier.upper()) - ord("A")
            if 0 <= idx < len(self.shortcuts):
                return self.shortcuts[idx]

        if isinstance(identifier, str):
            target = identifier.strip().lower()
            for s in self.shortcuts:
                if s.get("name", "").strip().lower() == target:
                    return s

        return None
