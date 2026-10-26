"""Per-session keyboard shortcut profiles stored as JSON."""

from __future__ import annotations
from rsh_storage import settings_dir, settings_path

import json
import pathlib
import threading


DEFAULT_PROFILES = {
    "default": {"CTRL+W": "WIN"},
    "apple2": {"CTRL+W": "WIN"},
}


class KeyboardProfiles:
    def __init__(self, path=None):
        self.path = pathlib.Path(path) if path else settings_path("keyboard_profiles.json")
        self._lock = threading.RLock()
        self._profiles = self._load()

    def _load(self):
        if not self.path.exists():
            return {name: dict(mappings) for name, mappings in DEFAULT_PROFILES.items()}
        try:
            profiles = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OSError(f"Could not load keyboard profiles from {self.path}: {exc}") from exc
        if not isinstance(profiles, dict) or any(
            not isinstance(name, str)
            or not isinstance(mappings, dict)
            or any(not isinstance(key, str) or not isinstance(action, str) for key, action in mappings.items())
            for name, mappings in profiles.items()
        ):
            raise ValueError(f"Invalid keyboard profile data in {self.path}.")
        return profiles

    @property
    def names(self):
        with self._lock:
            return tuple(sorted(self._profiles))

    def get(self, name):
        with self._lock:
            try:
                return dict(self._profiles[name])
            except KeyError as exc:
                raise LookupError(f"Keyboard profile not found: {name}") from exc

    def set_mapping(self, profile, key, action):
        key = key.upper()
        action = action.upper()
        if not key.startswith("CTRL+") or len(key) != 6 or not key[-1].isalpha():
            raise ValueError("Key must be a control shortcut such as CTRL+W.")
        if not action or any(part not in {"WIN", "CTRL", "ALT", "SHIFT", "R", "A", "TAB", "ENTER"} for part in action.split("+")):
            raise ValueError("Action must contain supported keys/modifiers (for example WIN+R).")
        with self._lock:
            if profile not in self._profiles:
                raise LookupError(f"Keyboard profile not found: {profile}")
            updated = {name: dict(mappings) for name, mappings in self._profiles.items()}
            updated[profile][key] = action
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(self.path.name + ".tmp")
            try:
                temporary.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
                temporary.replace(self.path)
            except OSError as exc:
                temporary.unlink(missing_ok=True)
                raise OSError(f"Could not save keyboard profiles to {self.path}: {exc}") from exc
            self._profiles = updated
            return dict(updated[profile])
