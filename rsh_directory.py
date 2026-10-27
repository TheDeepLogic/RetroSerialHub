"""Persistent BBS directory storage."""

from rsh_storage import settings_dir, settings_path
import json
from pathlib import Path


BBS_DIRECTORY_FILE = settings_path("bbs_directory.json")


def validate_entries(entries):
    if not isinstance(entries, list):
        raise ValueError("BBS directory must contain a list of entries.")

    validated = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"BBS directory entry {index} must be an object.")
        name = entry.get("name")
        host = entry.get("host")
        port = entry.get("port")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"BBS directory entry {index} has no name.")
        if not isinstance(host, str) or not host.strip():
            raise ValueError(f"BBS directory entry {index} has no host.")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"BBS directory entry {index} has an invalid port.")
        validated.append(
            {"name": name.strip(), "host": host.strip(), "port": port}
        )
    return validated


def load_directory(path=BBS_DIRECTORY_FILE):
    """Load the structured JSON directory, seeded by the shared settings store."""
    path = Path(path)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as directory_file:
                entries = json.load(directory_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise OSError(f"Could not load BBS directory {path}: {exc}") from exc
        return validate_entries(entries)

    raise ValueError('BBS directory is missing; restore settings/defaults/bbs_directory.json.')


def save_directory(entries, path=BBS_DIRECTORY_FILE):
    """Atomically save the complete BBS directory."""
    validated = validate_entries(entries)
    path = Path(path)
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as directory_file:
            json.dump(validated, directory_file, indent=2)
            directory_file.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        try:
            if temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass
        raise OSError(f"Could not save BBS directory {path}: {exc}") from exc
