"""Load and persist the hub's configurable welcome banner."""

import json
import os
from pathlib import Path
import tempfile


MAX_BANNER_LENGTH = 80


def validate_banner(value):
    banner = value.strip()
    if not banner:
        raise ValueError("The welcome banner cannot be empty.")
    if len(banner) > MAX_BANNER_LENGTH:
        raise ValueError(
            "The welcome banner must be no more than %d characters."
            % MAX_BANNER_LENGTH
        )
    if any(ord(character) < 32 or ord(character) > 126 for character in banner):
        raise ValueError("Use printable ASCII characters only.")
    return banner


def load_banner(configured_banner, path):
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as banner_file:
            saved = json.load(banner_file)
    except FileNotFoundError:
        return configured_banner

    if not isinstance(saved, dict) or not isinstance(saved.get("banner"), str):
        raise ValueError("Saved welcome banner file has an invalid format.")
    return validate_banner(saved["banner"])


def save_banner(path, banner):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as banner_file:
            temporary_path = Path(banner_file.name)
            json.dump({"banner": validate_banner(banner)}, banner_file, indent=2)
            banner_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def reset_banner(path):
    Path(path).unlink(missing_ok=True)
