"""Interactive FTP/explicit-FTPS directory browsing and downloads."""

import ftplib
import json
import os
import posixpath
import tempfile
from pathlib import Path

from rsh_terminal import clear_terminal_screen


DEFAULT_BOOKMARKS_PATH = Path(__file__).resolve().parent / "ftp_bookmarks.json"


def _write(ser, text):
    ser.write(text.encode("ascii", errors="replace"))


def _safe_remote_name(name):
    if not isinstance(name, str) or not name or name in (".", ".."):
        raise ValueError("The server returned an invalid file name.")
    if (
        "/" in name
        or "\\" in name
        or any(ord(char) < 32 for char in name)
        or any(char in '<>:"|?*' for char in name)
    ):
        raise ValueError("The server returned an unsafe file name.")
    return name


def _validate_port(text):
    try:
        port = int(text)
    except ValueError as exc:
        raise ValueError("Port must be from 1 to 65535.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Port must be from 1 to 65535.")
    return port


def _render_listing(ser, session, use_ansi=True, notice=None):
    clear_terminal_screen(ser, use_ansi)
    if notice:
        _write(ser, f"\r\n{notice}\r\n")
    _write(
        ser,
        f"\r\nFTP directory: {session['host']}"
        f"{session['cwd']}\r\n\r\n",
    )
    if not session["entries"]:
        _write(ser, "(No files or directories listed.)\r\n")
    for index, entry in enumerate(session["entries"], start=1):
        marker = "/" if entry["is_dir"] else ""
        size_text = "" if entry["is_dir"] else f" ({entry['size']} bytes)"
        _write(
            ser,
            f"{index:2d}] {entry['name']}{marker}{size_text}\r\n",
        )
    _write(
        ser,
        "\r\nEnter a file number to download, C<number> to open a directory, "
        "U to go up, R to refresh, A to bookmark, M to open bookmarks, "
        "or Q to disconnect.\r\n",
    )
    _write(ser, "Command: ")


def _render_bookmarks(ser, session, use_ansi=True, notice=None):
    clear_terminal_screen(ser, use_ansi)
    if notice:
        _write(ser, f"\r\n{notice}\r\n")
    _write(ser, "\r\nFTP Bookmarks\r\n\r\n")
    if not session["bookmarks"]:
        _write(ser, "No FTP bookmarks saved.\r\n")
    for index, bookmark in enumerate(session["bookmarks"], start=1):
        scheme = "FTPS" if bookmark["secure"] else "FTP"
        _write(
            ser,
            f"{index:2d}] {bookmark['name'][:24]:<24} "
            f"{scheme} {bookmark['host']}:{bookmark['port']}\r\n",
        )
    _write(ser, "\r\nEnter a number to open, D<number> to delete, or Q to return.\r\n")
    _write(ser, "Command: ")


def _validate_bookmarks(bookmarks):
    if not isinstance(bookmarks, list):
        raise ValueError("FTP bookmarks must contain a list.")
    validated = []
    for index, bookmark in enumerate(bookmarks, start=1):
        if not isinstance(bookmark, dict):
            raise ValueError(f"FTP bookmark {index} must be an object.")
        name = bookmark.get("name")
        host = bookmark.get("host")
        port = bookmark.get("port")
        secure = bookmark.get("secure")
        username = bookmark.get("username", "anonymous")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"FTP bookmark {index} has no name.")
        if (
            not isinstance(host, str)
            or not host.strip()
            or any(char.isspace() or ord(char) < 32 for char in host)
        ):
            raise ValueError(f"FTP bookmark {index} has an invalid host.")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"FTP bookmark {index} has an invalid port.")
        if not isinstance(secure, bool):
            raise ValueError(f"FTP bookmark {index} has an invalid security setting.")
        if not isinstance(username, str) or not username:
            raise ValueError(f"FTP bookmark {index} has an invalid username.")
        validated.append(
            {
                "name": name.strip(),
                "host": host.strip(),
                "port": port,
                "secure": secure,
                "username": username,
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
        raise OSError(f"Could not load FTP bookmarks from {path}: {exc}") from exc


def _save_bookmarks(session, bookmarks):
    bookmarks = _validate_bookmarks(bookmarks)
    path = session["bookmarks_path"]
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as bookmark_file:
            temporary_path = Path(bookmark_file.name)
            json.dump(bookmarks, bookmark_file, indent=2)
            bookmark_file.write("\n")
        os.replace(temporary_path, path)
    except OSError as exc:
        try:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass
        raise OSError(f"Could not save FTP bookmarks to {path}: {exc}") from exc


def _list_entries(session):
    ftp = session["ftp"]
    entries = []
    try:
        for name, facts in ftp.mlsd():
            if name in (".", ".."):
                continue
            kind = facts.get("type", "file")
            if kind in ("cdir", "pdir"):
                continue
            try:
                name = _safe_remote_name(name)
            except ValueError:
                continue
            entries.append(
                {
                    "name": name,
                    "is_dir": kind == "dir",
                    "size": facts.get("size", "?"),
                }
            )
    except (
        ftplib.error_perm,
        ftplib.error_reply,
        AttributeError,
        NotImplementedError,
    ):
        names = ftp.nlst()
        for remote_name in names:
            name = posixpath.basename(remote_name.rstrip("/"))
            if not name or name in (".", ".."):
                continue
            try:
                name = _safe_remote_name(name)
            except ValueError:
                continue
            entries.append({"name": name, "is_dir": False, "size": "?"})
    return sorted(entries, key=lambda entry: (not entry["is_dir"], entry["name"].lower()))


def _refresh(session, ser, use_ansi=True, notice=None):
    session["entries"] = _list_entries(session)
    _render_listing(ser, session, use_ansi, notice)


def create_session(ser, use_ansi=True, bookmarks_path=None):
    bookmark_path = (
        Path(bookmarks_path)
        if bookmarks_path is not None
        else DEFAULT_BOOKMARKS_PATH
    )
    session = {
        "ftp": None,
        "host": "",
        "port": 21,
        "cwd": "/",
        "entries": [],
        "submode": "START",
        "secure": False,
        "username": "",
        "password": "",
        "download_name": "",
        "download_mode": "",
        "transfer_mode": "",
        "target_dir": None,
        "bookmarks": _load_bookmarks(bookmark_path),
        "bookmarks_path": bookmark_path,
    }
    clear_terminal_screen(ser, use_ansi)
    _write(ser, "\r\nFTP / Explicit FTPS\r\n")
    _write(
        ser,
        "Enter a host, M to open FTP bookmarks, or Q for the main menu.\r\n",
    )
    _write(ser, "Host or command: ")
    return session


def _disconnect(session):
    ftp = session.get("ftp")
    session["ftp"] = None
    if ftp is not None:
        try:
            ftp.quit()
        except (OSError, EOFError, ftplib.Error):
            try:
                ftp.close()
            except OSError:
                pass


def close_session(session):
    """Close the active FTP control connection."""
    _disconnect(session)


def connect(session, ser, use_ansi=True):
    ftp = ftplib.FTP_TLS() if session["secure"] else ftplib.FTP()
    try:
        ftp.connect(session["host"], session["port"], timeout=20)
        ftp.login(session["username"], session["password"])
        session["password"] = ""
        if session["secure"]:
            ftp.prot_p()
        ftp.set_pasv(True)
        session["ftp"] = ftp
        session["cwd"] = ftp.pwd()
        _refresh(session, ser, use_ansi, "Connected.")
    except (OSError, EOFError, ftplib.Error):
        session["password"] = ""
        try:
            ftp.close()
        except OSError:
            pass
        raise


def _begin_connection(session, ser, use_ansi=True):
    session["submode"] = "PORT"
    _write(ser, "\r\nPort (Enter for 21): ")


def _connect_saved_bookmark(session, bookmark, ser):
    session.update(
        {
            "host": bookmark["host"],
            "port": bookmark["port"],
            "secure": bookmark["secure"],
            "username": bookmark["username"],
            "password": "",
            "submode": "PASSWORD",
        }
    )
    _write(
        ser,
        f"\r\nPassword for {bookmark['username']}@{bookmark['host']} "
        "(Enter if not required): ",
    )


def _save_current_bookmark(session, name):
    name = name.strip() or session["host"]
    bookmark = {
        "name": name,
        "host": session["host"],
        "port": session["port"],
        "secure": session["secure"],
        "username": session["username"] or "anonymous",
    }
    updated = session["bookmarks"] + [bookmark]
    _save_bookmarks(session, updated)
    session["bookmarks"] = updated


def download_to_path(session, remote_name, destination):
    """Download the selected remote file to a local path."""
    remote_name = _safe_remote_name(remote_name)
    destination = Path(destination)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".part",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as target:
            session["ftp"].retrbinary(
                f"RETR {remote_name}", target.write
            )
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return destination


def handle_input(session, line_str, ser, use_ansi=True):
    """Handle FTP prompts and listing commands; return (consumed, action)."""
    text = line_str.strip()
    state = session["submode"]

    if state == "START":
        upper = text.upper()
        if upper == "Q":
            return True, "MENU"
        if upper == "M":
            session["submode"] = "BOOKMARKS"
            _render_bookmarks(ser, session, use_ansi)
            return True, None
        if (
            not text
            or len(text) > 253
            or any(char.isspace() or ord(char) < 32 for char in text)
        ):
            _write(ser, "Enter a host, M for bookmarks, or Q: ")
            return True, None
        session["host"] = text
        _begin_connection(session, ser, use_ansi)
        return True, None

    if state == "BOOKMARKS":
        upper = text.upper()
        if upper == "Q":
            session["submode"] = "START"
            _write(
                ser,
                "\r\nEnter a host, M for bookmarks, or Q for main menu.\r\n"
                "Host or command: ",
            )
            return True, None
        if upper == "A":
            session["submode"] = "START"
            _write(ser, "\r\nHost or IP address: ")
            return True, None
        if upper.startswith("D"):
            try:
                index = int(text[1:].strip()) - 1
                if not 0 <= index < len(session["bookmarks"]):
                    raise ValueError
            except ValueError:
                _render_bookmarks(
                    ser, session, use_ansi, "Enter D followed by a valid bookmark number."
                )
                return True, None
            updated = session["bookmarks"][:]
            del updated[index]
            try:
                _save_bookmarks(session, updated)
            except OSError as exc:
                _render_bookmarks(ser, session, use_ansi, f"Could not delete bookmark: {exc}")
            else:
                session["bookmarks"] = updated
                _render_bookmarks(ser, session, use_ansi, "Bookmark deleted.")
            return True, None
        try:
            index = int(text) - 1
            if not 0 <= index < len(session["bookmarks"]):
                raise ValueError
        except ValueError:
            _render_bookmarks(ser, session, use_ansi, "Enter a number, D<number>, or Q.")
            return True, None
        if session.get("ftp") is not None:
            _disconnect(session)
        _connect_saved_bookmark(session, session["bookmarks"][index], ser)
        return True, None

    if state == "HOST":
        if (
            not text
            or len(text) > 253
            or any(char.isspace() or ord(char) < 32 for char in text)
        ):
            _write(ser, "Enter a valid hostname or IP address: ")
            return True, None
        session["host"] = text
        _begin_connection(session, ser, use_ansi)
        return True, None

    if state == "PORT":
        try:
            session["port"] = 21 if not text else _validate_port(text)
        except ValueError as exc:
            _write(ser, f"{exc}\r\nPort (Enter for 21): ")
            return True, None
        session["submode"] = "SECURE"
        _write(ser, "\r\nUse explicit FTPS? (Y/N): ")
        return True, None

    if state == "SECURE":
        if text.upper() not in ("Y", "N"):
            _write(ser, "Enter Y or N: ")
            return True, None
        session["secure"] = text.upper() == "Y"
        session["submode"] = "USERNAME"
        _write(ser, "\r\nUsername (Enter for anonymous): ")
        return True, None

    if state == "USERNAME":
        if any(ord(char) < 32 for char in text):
            _write(ser, "Username cannot contain control characters: ")
            return True, None
        session["username"] = text or "anonymous"
        session["submode"] = "PASSWORD"
        _write(ser, "\r\nPassword (Enter if not required): ")
        return True, None

    if state == "PASSWORD":
        if any(ord(char) < 32 for char in text):
            _write(ser, "Password cannot contain control characters: ")
            return True, None
        session["password"] = text
        try:
            connect(session, ser, use_ansi)
        except (OSError, EOFError, ftplib.Error) as exc:
            _write(ser, f"\r\n*** FTP connection failed: {exc} ***\r\n")
            session["submode"] = "HOST"
            _write(ser, "Host or IP address: ")
            return True, None
        session["submode"] = "LISTING"
        return True, None

    if state == "DOWNLOAD_MODE":
        upper = text.upper()
        if upper not in ("H", "D"):
            _write(ser, "Choose H or D: ")
            return True, None
        session["download_mode"] = upper
        if upper == "H":
            return True, ("DOWNLOAD_TO_HOST", session["download_name"])
        session["submode"] = "TRANSFER_MODE"
        _write(ser, "\r\nTransfer protocol: X=XMODEM, Y=YMODEM, A=ASCII: ")
        return True, None

    if state == "TRANSFER_MODE":
        mode = text.upper()
        if mode not in ("X", "Y", "A"):
            _write(ser, "Choose X, Y, or A: ")
            return True, None
        session["transfer_mode"] = {
            "X": "XMODEM_SEND",
            "Y": "YMODEM_SEND",
            "A": "ASCII_SEND",
        }[mode]
        return True, (
            "DOWNLOAD_TO_SERIAL",
            session["download_name"],
            session["transfer_mode"],
        )

    if state == "SAVE_BOOKMARK":
        try:
            _save_current_bookmark(session, text)
        except (OSError, ValueError) as exc:
            session["submode"] = "LISTING"
            _render_listing(
                ser, session, use_ansi, f"Could not save FTP bookmark: {exc}"
            )
        else:
            session["submode"] = "LISTING"
            _render_listing(ser, session, use_ansi, "FTP bookmark saved.")
        return True, None

    if state == "LISTING":
        upper = text.upper()
        if upper in ("Q", "ATM"):
            _disconnect(session)
            return True, "MENU"
        if upper == "M":
            _disconnect(session)
            session["submode"] = "BOOKMARKS"
            _render_bookmarks(ser, session, use_ansi)
            return True, None
        if upper == "A":
            session["submode"] = "SAVE_BOOKMARK"
            _write(ser, "\r\nBookmark name (Enter uses hostname): ")
            return True, None
        if upper == "R":
            _refresh(session, ser, use_ansi)
            return True, None
        if upper == "U":
            try:
                session["ftp"].cwd("..")
                session["cwd"] = session["ftp"].pwd()
                _refresh(session, ser, use_ansi)
            except (OSError, EOFError, ftplib.Error) as exc:
                _render_listing(ser, session, use_ansi, f"Could not change directory: {exc}")
            return True, None
        if upper.startswith("C") and upper[1:].isdigit():
            index = int(upper[1:]) - 1
            if not 0 <= index < len(session["entries"]):
                _render_listing(ser, session, use_ansi, "Invalid entry number.")
                return True, None
            entry = session["entries"][index]
            if not entry["is_dir"]:
                _render_listing(ser, session, use_ansi, "That entry is not a directory.")
                return True, None
            try:
                session["ftp"].cwd(entry["name"])
                session["cwd"] = session["ftp"].pwd()
                _refresh(session, ser, use_ansi)
            except (OSError, EOFError, ftplib.Error) as exc:
                _render_listing(ser, session, use_ansi, f"Could not open directory: {exc}")
            return True, None
        if text.isdigit():
            index = int(text) - 1
            if not 0 <= index < len(session["entries"]):
                _render_listing(ser, session, use_ansi, "Invalid file number.")
                return True, None
            entry = session["entries"][index]
            if entry["is_dir"]:
                _render_listing(ser, session, use_ansi, "Use C<number> to open a directory.")
                return True, None
            session["download_name"] = entry["name"]
            session["submode"] = "DOWNLOAD_MODE"
            _write(
                ser,
                f"\r\nDownload {entry['name']} to [H]ost storage or "
                "[D]irectly to this terminal? ",
            )
            return True, None
        _render_listing(ser, session, use_ansi, "Invalid command.")
        return True, None

    raise RuntimeError(f"Unknown FTP menu state: {state}")


def download_finished(session, ser, use_ansi=True, notice=None):
    """Return to the FTP directory after completing or cancelling a download."""
    session["submode"] = "LISTING"
    session["download_name"] = ""
    try:
        _refresh(session, ser, use_ansi, notice)
    except (OSError, EOFError, ftplib.Error) as exc:
        _write(ser, f"\r\n*** FTP directory refresh failed: {exc} ***\r\n")
