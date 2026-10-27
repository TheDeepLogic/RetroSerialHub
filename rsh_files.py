"""
rsh_files.py

Pluggable Files module for RETRO_SERIAL_HUB.

Interface:
- create_session(ser, use_ansi=True, files=None, transfer_mode='XMODEM') -> session
- handle_input(session, line_str, ser, use_ansi=True) -> (consumed:bool, action_or_new_mode)

Actions returned for core to execute:
- 'XMODEM_SEND:<absolute-path>'
- 'YMODEM_SEND:<absolute-path>'
- 'ASCII_SEND:<absolute-path>'
- 'RECEIVE_XMODEM:<dest_filename>'  (core should call xmodem_receive and save into files dir)
- 'SET_TRANSFER_MODE:<mode>' (updates transfer mode and re-renders)
- 'MENU' (return to main menu)

Session is a dict containing at least 'files' (list) and 'transfer_mode'.
"""

from textwrap import shorten
import os
from contextlib import nullcontext
import time
import pathlib
import textwrap
from rsh_terminal import clear_terminal_screen, format_numbered_list, terminal_columns

# XMODEM / YMODEM constants
SOH = 0x01  # 128-byte blocks
STX = 0x02  # 1024‑byte block (YMODEM)
EOT = 0x04
ACK = 0x06
NAK = 0x15
CAN = 0x18


def _write(ser, s):
    ser.write(s.encode('ascii', errors='ignore'))


def _root_directories():
    if os.name == "nt":
        drives = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = pathlib.Path(f"{letter}:\\")
            if drive.is_dir():
                drives.append(drive)
        return drives
    return [pathlib.Path("/")]


def _refresh_entries(sess):
    current_dir = sess["current_dir"]
    try:
        directories = sorted(
            (path for path in current_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name.lower(),
        )
        files = sorted(
            (path for path in current_dir.iterdir() if path.is_file()),
            key=lambda path: path.name.lower(),
        )
    except OSError as exc:
        sess["entries"] = []
        sess["files"] = []
        sess["notice"] = f"Cannot list {current_dir}: {exc}"
        return

    sess["entries"] = [("directory", path) for path in directories]
    sess["entries"].extend(("file", path) for path in files)
    sess["files"] = [path.name for path in files]
    sess["notice"] = None


def create_session(
    ser,
    use_ansi=True,
    files=None,
    transfer_mode='XMODEM',
    base_dir=None,
    current_dir=None,
    root_mode=False,
):
    home_dir = pathlib.Path(base_dir).expanduser().resolve() if base_dir else pathlib.Path.cwd()
    start_dir = pathlib.Path(current_dir).expanduser() if current_dir else home_dir
    sess = {
        'submode': 'FILES_MENU',
        'files': [],
        'entries': [],
        'transfer_mode': transfer_mode,
        'base_dir': home_dir,
        'home_dir': home_dir,
        'current_dir': start_dir,
        'root_mode': root_mode,
        'use_ansi': use_ansi,
        'notice': None,
    }
    if root_mode:
        sess["entries"] = [("directory", path) for path in _root_directories()]
    else:
        _refresh_entries(sess)
    _render_menu(ser, sess)
    return sess


def _render_menu(ser, sess):
    clear_terminal_screen(ser, sess.get('use_ansi', True))
    _write(ser, f"\r\nFile Transfer Menu (Current mode: {sess['transfer_mode']})\r\n\r\n")
    columns = terminal_columns(ser)
    if sess.get("root_mode"):
        heading = "Available drives:" if os.name == "nt" else "Filesystem root:"
        _write(ser, heading + "\r\n")
    else:
        _write(
            ser,
            textwrap.shorten(
                f"Directory: {sess['current_dir']}",
                width=37 if columns == 40 else 76,
                placeholder="...",
            )
            + "\r\n",
        )

    display_entries = []
    for kind, path in sess.get("entries", []):
        prefix = "[DIR] " if kind == "directory" else "      "
        name = path.name or str(path).rstrip("\\/") or path.anchor
        display_entries.append(
            shorten(
                prefix + name,
                width=34 if columns == 80 else 35,
                placeholder="...",
            )
        )
    for line in format_numbered_list(display_entries, columns):
        _write(ser, line + "\r\n")

    if sess.get("notice"):
        _write(ser, f"\r\n{sess['notice']}\r\n")
    if sess.get("root_mode"):
        controls = "Enter number to open drive, H=Home, Q=Quit"
    else:
        controls = (
            "Enter number to open directory or transfer file, "
            "D=Drives/Root, B=Parent, H=Home, "
            "or type a directory path to jump there; U=Upload, "
            "X=XMODEM, Y=YMODEM, A=ASCII, Q=Quit"
        )
    _write(ser, "\r\n" + controls + "\r\n")
    _write(ser, "Command: ")


def handle_input(sess, line_str, ser, use_ansi=True):
    txt = line_str.strip()
    # Submode handling: FILES_MENU or UPLOAD_PROMPT
    sub = sess.get('submode', 'FILES_MENU')
    if sub == 'UPLOAD_PROMPT':
        # treat this line as the filename to save into base_dir
        fname = pathlib.Path(txt).name
        if not fname:
            _write(ser, "Filename: ")
            return True, None
        base = sess.get('base_dir')
        if not base:
            _write(ser, "\r\n*** No base directory configured for uploads. ***\r\n")
            sess['submode'] = 'FILES_MENU'
            _render_menu(ser, sess)
            return True, None
        dest = sess["current_dir"] / fname
        try:
            # perform receive according to transfer mode (currently XMODEM only)
            mode = sess.get('transfer_mode', 'XMODEM')
            if mode in ('XMODEM', 'X'):
                xmodem_receive(ser, str(dest))
            else:
                # fallback to xmodem_receive for unknown modes
                xmodem_receive(ser, str(dest))
        except Exception as e:
            _write(ser, f"\r\n*** Upload error: {e} ***\r\n")
        # refresh file list and return to menu
        _refresh_entries(sess)
        sess['submode'] = 'FILES_MENU'
        _render_menu(ser, sess)
        return True, None

    if txt == '':
        _render_menu(ser, sess)
        return True, None
    upper = txt.upper()
    if upper == 'Q':
        return True, 'MENU'
    if upper == 'H':
        sess["current_dir"] = sess["home_dir"]
        sess["root_mode"] = False
        _refresh_entries(sess)
        _render_menu(ser, sess)
        return True, None
    if upper == 'D':
        sess["root_mode"] = True
        sess["entries"] = [
            ("directory", path) for path in _root_directories()
        ]
        sess["notice"] = None
        _render_menu(ser, sess)
        return True, None
    if upper == 'B':
        if sess.get("root_mode"):
            sess["root_mode"] = False
            sess["current_dir"] = sess["home_dir"]
        else:
            current_dir = sess["current_dir"]
            parent = current_dir.parent
            if parent == current_dir:
                sess["root_mode"] = True
                sess["entries"] = [
                    ("directory", path) for path in _root_directories()
                ]
                _render_menu(ser, sess)
                return True, None
            sess["current_dir"] = parent
        _refresh_entries(sess)
        _render_menu(ser, sess)
        return True, None
    if upper == 'U':
        # Module handles upload prompting and receive directly
        sess['submode'] = 'UPLOAD_PROMPT'
        _write(ser, "\r\nEnter filename to save as: ")
        return True, None
    if upper == 'Y':
        sess['transfer_mode'] = 'YMODEM'
        _render_menu(ser, sess)
        return True, None
    if upper == 'X':
        sess['transfer_mode'] = 'XMODEM'
        _render_menu(ser, sess)
        return True, None
    if upper == 'A':
        sess['transfer_mode'] = 'ASCII'
        _render_menu(ser, sess)
        return True, None

    # Numeric selection opens a directory or transfers the selected file.
    try:
        num = int(txt)
        entries = sess.get("entries", [])
        if 1 <= num <= len(entries):
            kind, path = entries[num - 1]
            if kind == "directory":
                sess["current_dir"] = path
                sess["root_mode"] = False
                _refresh_entries(sess)
                _render_menu(ser, sess)
                return True, None
            mode = sess.get('transfer_mode', 'XMODEM')
            if mode == 'XMODEM':
                        return True, f'XMODEM_SEND:{path}'
            if mode == 'YMODEM':
                        return True, f'YMODEM_SEND:{path}'
            if mode == 'ASCII':
                        # prefer module to actually perform ASCII send
                        return True, f'ASCII_SEND:{path}'
        else:
            _write(ser, "Invalid file number\r\n")
            _write(ser, "Command: ")
            return True, None
    except ValueError:
        try:
            target_dir = pathlib.Path(txt).expanduser().resolve(strict=True)
            if not target_dir.is_dir():
                raise NotADirectoryError(f"Not a directory: {target_dir}")
        except (OSError, RuntimeError, ValueError) as exc:
            _write(ser, f"\r\nCannot open directory: {exc}\r\n")
            _write(ser, "Command: ")
            return True, None
        sess["current_dir"] = target_dir
        sess["root_mode"] = False
        _refresh_entries(sess)
        _render_menu(ser, sess)
        return True, None


def xmodem_send(ser, file_path, ser_name_for_user=None):
    from rsh_transfer import xsend
    _write(ser, f"\r\nXMODEM SEND: {pathlib.Path(file_path).name}\r\nWaiting for receiver...\r\n")
    try:
        total = xsend(ser, file_path)
        _write(ser, f"\r\nTransfer complete: {total} bytes.\r\n")
    except (OSError, ValueError) as exc:
        _write(ser, f"\r\nTransfer stopped: {exc}\r\n")


def xmodem_receive(ser, dest_path, exact_size=None):
    from rsh_transfer import xreceive
    _write(ser, f"\r\nXMODEM RECEIVE: {pathlib.Path(dest_path).name}\r\n")
    try:
        total = xreceive(ser, dest_path, exact_size)
        _write(ser, f"\r\nUpload complete: {total} bytes.\r\n")
        if exact_size is None:
            _write(ser, "XMODEM has no file length; final block padding is preserved.\r\n")
    except (OSError, ValueError) as exc:
        _write(ser, f"\r\nTransfer stopped: {exc}\r\nIncomplete data remains in a .part file.\r\n")


def ymodem_send(ser, file_path):
    from rsh_transfer import ysend
    _write(ser, f"\r\nYMODEM SEND: {pathlib.Path(file_path).name}\r\nWaiting for receiver...\r\n")
    try:
        total = ysend(ser, file_path)
        _write(ser, f"\r\nTransfer complete: {total} bytes.\r\n")
    except (OSError, ValueError) as exc:
        _write(ser, f"\r\nTransfer stopped: {exc}\r\n")


def ascii_send(ser, file_path):
    """Simple ASCII send: stream the file, converting LF->CRLF and notify when done."""
    fname = os.path.basename(file_path)
    _write(ser, f"\r\nASCII SEND: {fname}\r\n")
    try:
        service = getattr(ser, '_rsh_services', None)
        with service.transfer() if service else nullcontext():
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    # Keep asynchronous messages out of the captured text file.
                    ser.write(line.rstrip('\n').replace('\n', '\r\n').encode('ascii', errors='ignore'))
                    ser.write(b"\r\n")
        _write(ser, "\r\nASCII transfer complete.\r\n")
    except Exception as e:
        _write(ser, f"\r\nASCII send error: {e}\r\n")
