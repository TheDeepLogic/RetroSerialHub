"""Direct TCP terminal connections and saved Telnet destinations."""

from rsh_storage import settings_dir, settings_path
import json
from pathlib import Path

from rsh_terminal import clear_terminal_screen, terminal_columns


TELNET_BOOKMARKS_FILE = settings_path("telnet_bookmarks.json")


def _write(ser, text):
    ser.write(text.encode("ascii", errors="replace"))


def _validate_host(host):
    host = host.strip()
    if (
        not host
        or any(character.isspace() or ord(character) < 32 for character in host)
        or len(host) > 253
    ):
        raise ValueError("Enter a valid hostname or IP address.")
    return host


def _validate_port(port_text):
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("Port must be a number from 1 to 65535.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Port must be a number from 1 to 65535.")
    return port


def _validate_bookmarks(bookmarks):
    if not isinstance(bookmarks, list):
        raise ValueError("Telnet bookmarks must contain a list.")
    validated = []
    for index, bookmark in enumerate(bookmarks, start=1):
        if not isinstance(bookmark, dict):
            raise ValueError(f"Telnet bookmark {index} must be an object.")
        name = bookmark.get("name")
        host = bookmark.get("host")
        port = bookmark.get("port")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Telnet bookmark {index} has no name.")
        if not isinstance(host, str):
            raise ValueError(f"Telnet bookmark {index} has no host.")
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"Telnet bookmark {index} has an invalid port.")
        validated.append(
            {
                "name": name.strip(),
                "host": _validate_host(host),
                "port": _validate_port(str(port)),
            }
        )
    return validated


def _load_bookmarks(path):
    path = Path(path)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as bookmark_file:
            return _validate_bookmarks(json.load(bookmark_file))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise OSError(f"Could not load Telnet bookmarks from {path}: {exc}") from exc


def _save_bookmarks(bookmarks, path):
    path = Path(path)
    temporary_path = path.with_name(path.name + ".tmp")
    validated = _validate_bookmarks(bookmarks)
    try:
        with temporary_path.open("w", encoding="utf-8") as bookmark_file:
            json.dump(validated, bookmark_file, indent=2)
            bookmark_file.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        try:
            if temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass
        raise OSError(f"Could not save Telnet bookmarks to {path}: {exc}") from exc


def _render_menu(ser, session, use_ansi):
    clear_terminal_screen(ser, use_ansi)
    _write(ser, "\r\nTelnet destinations\r\n\r\n")
    for index, bookmark in enumerate(session["bookmarks"], start=1):
        if terminal_columns(ser) == 40:
            _write(ser, f"{index:2d}] {bookmark['name'][:35]}\r\n")
            _write(ser, f"    {bookmark['host'][:27]}:{bookmark['port']}\r\n")
        else:
            _write(
                ser,
                f"{index:2d}] {bookmark['name']} - "
                f"{bookmark['host']}:{bookmark['port']}\r\n",
            )
    _write(
        ser,
        "\r\nEnter a number to connect, A to enter an address, "
        "D to delete a Telnet bookmark, or Q for the main menu.\r\n",
    )
    _write(ser, "Command: ")


def create_session(ser, use_ansi=True, bookmarks_path=TELNET_BOOKMARKS_FILE):
    session = {
        "bookmarks": _load_bookmarks(bookmarks_path),
        "bookmarks_path": Path(bookmarks_path),
        "submode": "MENU",
        "new_host": "",
        "new_port": None,
        "new_name": "",
        "delete_index": None,
    }
    _render_menu(ser, session, use_ansi)
    return session


def _connect_action(host, port):
    return "CONNECT", host, port


def handle_input(
    session,
    line_str,
    ser,
    use_ansi=True,
    add_bbs_entry=None,
):
    """Handle Telnet destination menu and return (consumed, action)."""
    text = line_str.strip()
    state = session["submode"]

    if state == "MENU":
        if not text:
            _render_menu(ser, session, use_ansi)
            return True, None
        upper = text.upper()
        if upper == "Q":
            return True, "MENU"
        if upper == "A":
            session["submode"] = "HOST"
            _write(ser, "\r\nHost or IP address: ")
            return True, None
        if upper == "D":
            session["submode"] = "DELETE"
            _write(ser, "\r\nBookmark number to delete: ")
            return True, None
        if text.isdigit():
            index = int(text) - 1
            if 0 <= index < len(session["bookmarks"]):
                bookmark = session["bookmarks"][index]
                return True, _connect_action(bookmark["host"], bookmark["port"])
        _write(ser, "\r\nInvalid command.\r\n")
        _render_menu(ser, session, use_ansi)
        return True, None

    if state == "HOST":
        try:
            session["new_host"] = _validate_host(text)
        except ValueError as exc:
            _write(ser, f"\r\n{exc}\r\nHost or IP address: ")
            return True, None
        session["submode"] = "PORT"
        _write(ser, "\r\nPort (1-65535): ")
        return True, None

    if state == "PORT":
        try:
            session["new_port"] = _validate_port(text)
        except ValueError as exc:
            _write(ser, f"\r\n{exc}\r\nPort (1-65535): ")
            return True, None
        session["submode"] = "NAME"
        _write(ser, "\r\nBookmark name (Enter for host:port): ")
        return True, None

    if state == "NAME":
        session["new_name"] = text or (
            f"{session['new_host']}:{session['new_port']}"
        )
        session["submode"] = "SAVE"
        _write(
            ser,
            "\r\nSave to [T]elnet bookmarks, [B]ulletin Boards, or [N]one? ",
        )
        return True, None

    if state == "SAVE":
        upper = text.upper()
        host = session["new_host"]
        port = session["new_port"]
        name = session["new_name"]
        if upper == "T":
            session["bookmarks"].append(
                {"name": name, "host": host, "port": port}
            )
            _save_bookmarks(session["bookmarks"], session["bookmarks_path"])
        elif upper == "B":
            if add_bbs_entry is None:
                raise RuntimeError("BBS directory saving is unavailable.")
            add_bbs_entry(name, host, port)
        elif upper != "N":
            _write(ser, "Choose T, B, or N: ")
            return True, None
        session["submode"] = "MENU"
        session["new_host"] = ""
        session["new_port"] = None
        session["new_name"] = ""
        return True, _connect_action(host, port)

    if state == "DELETE":
        if not text.isdigit():
            _write(ser, "Enter a bookmark number: ")
            return True, None
        index = int(text) - 1
        if not 0 <= index < len(session["bookmarks"]):
            _write(ser, "Invalid bookmark number. Enter a bookmark number: ")
            return True, None
        del session["bookmarks"][index]
        _save_bookmarks(session["bookmarks"], session["bookmarks_path"])
        session["submode"] = "MENU"
        _write(ser, "\r\nTelnet bookmark deleted.\r\n")
        _render_menu(ser, session, use_ansi)
        return True, None

    raise RuntimeError(f"Unknown Telnet menu state: {state}")


def show_menu(ser, session, use_ansi=True):
    session["submode"] = "MENU"
    _render_menu(ser, session, use_ansi)
