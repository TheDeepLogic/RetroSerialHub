#!/usr/bin/env python3
# Copyright (c) 2025-2026 Aaron Smith.
"""
LogicNet Multi-port Serial <-> TCP bridge with BBS-style menus.

Features per serial port:
- Main menu (ATM to return from anywhere)
- Bulletin Boards directory with ADTnn dialing and ATH hangup
- Telnet direct connections and bookmarks
- File Transfers: two-column file list, select number to XMODEM-send
- Text Library: list *.txt files, view with pagination
- Web Browser: browse paginated text pages and follow numbered links
- Keyboard Bridge: inject serial input into a focused host application

Each configured COM port is opened (if available) and runs its own
independent bridge loop. If a port isn't present, it's skipped.

UX Design:
- Menu layout supports 40- and 80-column terminal profiles
- ATM cancels any active BBS connection and returns to main menu
"""

import serial, socket, select, threading, time, os, sys, pathlib, importlib, tempfile, json, platform, re
from rsh_terminal import (
    AnsiToTextTranslator,
    clear_terminal_screen,
    configure_screen_clearing,
    format_numbered_list,
    terminal_columns,
)
from rsh_welcome import load_banner, reset_banner, save_banner, validate_banner
from rsh_console import ConsoleDashboard, VERSION
from rsh_access import TelnetAccess
from rsh_host import HostTerminal

# Import configuration from config.py
try:
    import config as _config
    from config import (
        SERIAL_CONFIGS,
        BBSS,
        IPS,
        PORTS,
        EIGHTBITS,
        SEVENBITS,
        PARITY_NONE,
        STOPBITS_ONE,
        WELCOME_BANNER as CONFIG_WELCOME_BANNER,
    )
    from rsh_directory import load_directory, save_directory
    from rsh_server import SocketTerminal
except ImportError:
    print("ERROR: config.py not found. Please ensure config.py exists in the same directory.")
    print("See config.py for configuration examples.")
    sys.exit(1)
TELNET_SERVER_CONFIGS = getattr(_config, "TELNET_SERVER_CONFIGS", {})

try:
    _bbs_entries = load_directory(BBSS, IPS, PORTS)
except (OSError, ValueError) as exc:
    print(f"ERROR: Could not load BBS directory: {exc}")
    sys.exit(1)
BBSS[:] = [entry["name"] for entry in _bbs_entries]
IPS[:] = [entry["host"] for entry in _bbs_entries]
PORTS[:] = [entry["port"] for entry in _bbs_entries]

# Global registry: map port name -> {'thread': thread_name, 'serial': Serial()}
ACTIVE_PORTS = {}
ACTIVE_REMOTE_CLIENTS = set()
ACTIVE_REMOTE_CLIENTS_LOCK = threading.Lock()
ACTIVE_TERMINALS = set()
ACTIVE_TERMINALS_LOCK = threading.Lock()
CONSOLE = None
TELNET_ACCESS = None
# Ports that have been surrendered/taken over by a COM-bridge request. Worker threads should stop retrying if their port is surrendered.
SURRENDERED_PORTS = set()

def register_active_terminal(terminal):
    if not hasattr(terminal, "_terminal_name"):
        profile = getattr(terminal, "_profile_name", "Terminal")
        address = getattr(terminal, "_remote_address", None)
        terminal._terminal_name = f"{profile}@{address[0]}" if address else profile
    with ACTIVE_TERMINALS_LOCK:
        ACTIVE_TERMINALS.add(terminal)

def unregister_active_terminal(terminal):
    with ACTIVE_TERMINALS_LOCK:
        ACTIVE_TERMINALS.discard(terminal)

def broadcast_to_terminals(text):
    """Send text in real-time to all connected serial and TCP terminals."""
    with ACTIVE_TERMINALS_LOCK:
        terminals = list(ACTIVE_TERMINALS)
    for term in terminals:
        try:
            write(term, text)
        except Exception:
            pass

def broadcast_scheduler_event(task, output):
    """Broadcast a scheduled task result to all connected terminals in real time."""
    task_name = task.get("name", "Task")
    show_output = task.get("show_output", True)
    cmd = task.get("command", "")
    notice = f"\r\n\r\n*** [SCHEDULED EVENT: {task_name.upper()}] ***\r\n"
    if show_output and output and str(output).strip():
        notice += f"{str(output).strip()}\r\n"
    else:
        notice += f"Executed: {cmd}\r\n"
    notice += "*** [END EVENT] ***\r\n\r\n"
    broadcast_to_terminals(notice)

HUB_TOOL_ALIASES = {
    "CALENDAR": "calendar", "CAL": "calendar",
    "CONVERT": "convert", "UNITS": "convert",
    "CONTACTS": "contacts", "ADDRESSBOOK": "contacts",
    "FILEMAN": "fileman", "FM": "fileman",
    "ARCHIVE": "archive", "ZIP": "archive",
    "AUDIO": "audio", "PLAYER": "audio",
}

MAIN_MENU_ACTIONS = {
    "1": "bbs",
    "2": "browser",
    "3": "telnet",
    "4": "notes",
    "5": "com_bridge",
    "6": "keyboard",
    "7": "files",
    "8": "text",
    "9": "ftp",
    "10": "ai",
    "11": "wargames",
    "12": "translate_ansi",
    "13": "columns",
    "14": "welcome_banner",
}
RETRO_OS_MENU_ACTIONS = {
    "calendar": "calendar",
    "convert": "convert",
    "contacts": "contacts",
    "fileman": "fileman",
    "archive": "archive",
    "audio": "audio",
    "bbs": "bbs",
    "browser": "browser",
    "telnet": "telnet",
    "terminals": "terminals",
    "notes": "notes",
    "files": "files",
    "textlib": "text",
    "ftp": "ftp",
    "ai": "ai",
    "wargames": "wargames",
    "keyboard": "keyboard",
    "com_bridge": "com_bridge",
    "calc": "calc",
    "mail": "mail",
    "mailto": "mailto",
    "apps": "apps",
    "launch": "launch",
    "view": "view",
    "games": "games",
    "wordguess": "wordguess",
    "trek": "trek",
    "mines": "mines",
    "solitaire": "solitaire",
    "wumpus": "wumpus",
    "help_menu": "help_menu",
    "ascii_viewer": "ascii_viewer",
    "print": "print",
    "kb": "kb",
    "cli": "cli",
    "scheduler": "scheduler",
    "host_terminal": "host_terminal",
    "host_media": "host_media",
    "sysinfo": "sysinfo",
    "weather_news": "weather_news",
    "terminal_settings": "terminal_settings",
    "host_settings": "host_settings",
}

# ---------------- Paths ----------------
BASE_DIR = pathlib.Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "files"
TEXT_DIR  = BASE_DIR / "text"
NOTES_DIR = BASE_DIR / "notes"
WELCOME_BANNER_FILE = BASE_DIR / "welcome_banner.json"
TELNET_ALLOWLIST_FILE = BASE_DIR / "telnet_allowlist.json"
COLUMN_SETTINGS_FILE = BASE_DIR / "terminal_columns.json"
ANSI_TRANSLATION_SETTINGS_FILE = BASE_DIR / "terminal_ansi_translation.json"
HOST_SETTINGS_FILE = BASE_DIR / "host_settings.json"
FILES_DIR.mkdir(exist_ok=True)
TEXT_DIR.mkdir(exist_ok=True)
NOTES_DIR.mkdir(exist_ok=True)

def load_column_preferences(path):
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as settings_file:
            preferences = json.load(settings_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise OSError(f"Could not load terminal column settings from {path}: {exc}") from exc
    if not isinstance(preferences, dict) or any(
        not isinstance(name, str) or value not in (40, 80)
        for name, value in preferences.items()
    ):
        raise ValueError(f"Invalid terminal column settings in {path}.")
    return preferences


def save_column_preference(path, preferences, name, columns):
    if columns not in (40, 80):
        raise ValueError("Terminal columns must be 40 or 80.")
    updated_preferences = dict(preferences)
    updated_preferences[name] = columns
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as settings_file:
            json.dump(updated_preferences, settings_file, indent=2)
            settings_file.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise OSError(f"Could not save terminal column settings to {path}: {exc}") from exc
    return updated_preferences


def load_ansi_translation_preferences(path):
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as settings_file:
            preferences = json.load(settings_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise OSError(
            f"Could not load ANSI translation settings from {path}: {exc}"
        ) from exc
    if not isinstance(preferences, dict) or any(
        not isinstance(name, str) or not isinstance(value, bool)
        for name, value in preferences.items()
    ):
        raise ValueError(f"Invalid ANSI translation settings in {path}."        )
    return preferences


def save_ansi_translation_preference(path, preferences, name, enabled):
    if not isinstance(enabled, bool):
        raise ValueError("ANSI translation preference must be a boolean.")
    updated_preferences = dict(preferences)
    updated_preferences[name] = enabled
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as settings_file:
            json.dump(updated_preferences, settings_file, indent=2)
            settings_file.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise OSError(
            f"Could not save ANSI translation settings to {path}: {exc}"
        ) from exc
    return updated_preferences


def load_host_settings(path):
    if not path.exists():
        return {"keyboard_exit_binding": "CTRL+X"}
    try:
        with path.open("r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise OSError(f"Could not load host settings from {path}: {exc}") from exc
    binding = settings.get("keyboard_exit_binding") if isinstance(settings, dict) else None
    if not isinstance(binding, str) or not re.fullmatch(r"CTRL\+[A-Z]", binding.upper()):
        raise ValueError(f"Invalid keyboard exit binding in {path}.")
    settings = dict(settings)
    settings["keyboard_exit_binding"] = binding.upper()
    return settings


def save_host_settings(path, settings):
    binding = settings.get("keyboard_exit_binding") if isinstance(settings, dict) else None
    if not isinstance(binding, str) or not re.fullmatch(r"CTRL\+[A-Z]", binding.upper()):
        raise ValueError("Keyboard exit binding must be CTRL+A through CTRL+Z.")
    updated = dict(settings)
    updated["keyboard_exit_binding"] = binding.upper()
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as settings_file:
            json.dump(updated, settings_file, indent=2)
            settings_file.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise OSError(f"Could not save host settings to {path}: {exc}") from exc
    return updated


try:
    COLUMN_PREFERENCES = load_column_preferences(COLUMN_SETTINGS_FILE)
except (OSError, ValueError) as exc:
    print(f"Terminal column settings error: {exc}. Using config.py values.")
    COLUMN_PREFERENCES = {}
COLUMN_PREFERENCES_LOCK = threading.Lock()
for _profile_name, _columns in COLUMN_PREFERENCES.items():
    if _profile_name in SERIAL_CONFIGS:
        SERIAL_CONFIGS[_profile_name]["columns"] = _columns

try:
    ANSI_TRANSLATION_PREFERENCES = load_ansi_translation_preferences(
        ANSI_TRANSLATION_SETTINGS_FILE
    )
except (OSError, ValueError) as exc:
    print(f"ANSI translation settings error: {exc}. Using config.py values.")
    ANSI_TRANSLATION_PREFERENCES = {}
ANSI_TRANSLATION_PREFERENCES_LOCK = threading.Lock()
for _profile_name, _enabled in ANSI_TRANSLATION_PREFERENCES.items():
    if _profile_name in SERIAL_CONFIGS:
        SERIAL_CONFIGS[_profile_name]["translate_ansi"] = _enabled

try:
    WELCOME_BANNER = load_banner(CONFIG_WELCOME_BANNER, WELCOME_BANNER_FILE)
except (OSError, ValueError) as exc:
    print(f"Welcome banner override error: {exc}. Using config.py value.")
    WELCOME_BANNER = CONFIG_WELCOME_BANNER

try:
    HOST_SETTINGS = load_host_settings(HOST_SETTINGS_FILE)
except (OSError, ValueError) as exc:
    print(f"Host settings error: {exc}. Using default settings.")
    HOST_SETTINGS = {"keyboard_exit_binding": "CTRL+X"}
HOST_SETTINGS_LOCK = threading.Lock()

# ---------------- UI helpers ----------------
def clear_screen(ser, use_ansi=True):
    clear_terminal_screen(ser, use_ansi)

def write(ser, s):
    if not isinstance(s, str):
        s = str(s)
    if getattr(ser, "_rsh_caps_only", None) is True:
        s = s.upper()
    if '\n' in s:
        s = s.replace('\r\n', '\n').replace('\n', '\r\n')
    pace = getattr(ser, "_rsh_pace_delay", 0.0)
    data = s.encode('ascii', errors='ignore')
    if isinstance(pace, (int, float)) and pace > 0.0:
        for b in data:
            ser.write(bytes((b,)))
            time.sleep(pace)
    else:
        ser.write(data)

def write_bytes(ser, b):
    ser.write(b)


def update_command_input(buffer, data):
    """Append printable input and apply destructive backspaces."""
    for byte in data:
        if byte in (8, 127):
            buffer = buffer[:-1]
        elif byte in (10, 13) or byte >= 32:
            buffer += bytes((byte,))
    return buffer


def wait_for_key(ser, quit_msg=False):
    if quit_msg:
        write(ser, "\r\nPress any key to continue (Q to quit)...\r\n")
    else:
        write(ser, "\r\nPress any key to continue...\r\n")
    while True:
        if ser.in_waiting:
            ch = ser.read(1)
            try:
                return ch.decode(errors="ignore").upper()
            except Exception:
                return ""
        time.sleep(0.05)


def read_input_line(ser):
    """Read a line of interactive terminal input with echo and backspace."""
    buf = b""
    while True:
        if ser.in_waiting:
            ch = ser.read(1)
            if not ch:
                if getattr(ser, "_eof", False):
                    return ""
                continue
            if ch in (b"\r", b"\n"):
                write(ser, "\r\n")
                break
            if ch in (b"\x03", b"\x1b", b"\x18"):
                write(ser, "^C\r\n")
                return ""
            if ch in (b"\x08", b"\x7f"):
                if buf:
                    buf = buf[:-1]
                    ser.write(b"\x08 \x08")
            elif ch[0] >= 32:
                buf += ch
                ser.write(ch)
        time.sleep(0.02)
    return buf.decode(errors="ignore").strip()

def paginate_lines(ser, lines, page_lines=22, quit_msg=False):
    count = 0
    for ln in lines:
        write(ser, ln + "\r\n")
        count += 1
        if count >= page_lines:
            key = wait_for_key(ser, quit_msg=quit_msg)
            if key == "Q":
                return "QUIT"
            count = 0
    # Only pause at EOF if the caller asked for a quit prompt
    if quit_msg:
        key = wait_for_key(ser, quit_msg=quit_msg)
        if key == "Q":
            return "QUIT"
    return "DONE"

def two_column_list(items, left_pad=38, columns=80):
    return format_numbered_list(items, columns, left_pad)


def configured_columns(name, cfg):
    columns = cfg.get("columns", 80)
    if columns not in (40, 80):
        console_log(f"{name}: invalid terminal columns {columns!r}; using 80.", level="yellow")
        return 80
    return columns


def console_log(message, level="info"):
    if CONSOLE is None:
        print(message)
    else:
        CONSOLE.log(message, level=level)


def get_terminal_client_id(ser, default_name=None):
    cid = getattr(ser, "_client_id", None)
    if cid is not None:
        return cid
    if default_name:
        return f"serial:{default_name}"
    return id(ser)


def set_terminal_activity(ser, action, user_label=None, default_name=None):
    if CONSOLE:
        cid = get_terminal_client_id(ser, default_name)
        if user_label is None:
            pname = getattr(ser, "_profile_name", default_name)
            if not isinstance(ser, SocketTerminal) and pname:
                user_label = pname
        CONSOLE.set_user_activity(cid, action, user_label=user_label)


def clear_terminal_activity(ser, default_name=None):
    if CONSOLE:
        cid = get_terminal_client_id(ser, default_name)
        CONSOLE.clear_user_activity(cid)


def get_active_connection_counts():
    """Return the number of open serial ports and connected remote clients."""
    with ACTIVE_REMOTE_CLIENTS_LOCK:
        remote_count = len(ACTIVE_REMOTE_CLIENTS)
    return len(ACTIVE_PORTS), remote_count


def show_main_menu(ser, use_ansi=True, auto_flyout=True):
    if getattr(ser, "_rsh_menu_style", "flyout") == "legacy":
        return show_legacy_main_menu(ser, use_ansi)
    columns = terminal_columns(ser)
    remote_client = isinstance(ser, SocketTerminal)
    clear_screen(ser, use_ansi)
    from retro_os.menu import OSFlyoutMenu
    from retro_os.shortcuts import ShortcutsManager
    if not hasattr(ser, "_rsh_shortcuts_manager"):
        ser._rsh_shortcuts_manager = ShortcutsManager(BASE_DIR / "user_shortcuts.json")
    if not hasattr(ser, "_rsh_flyout_menu"):
        ser._rsh_flyout_menu = OSFlyoutMenu(shortcuts_manager=ser._rsh_shortcuts_manager)
    else:
        if getattr(ser._rsh_flyout_menu, "shortcuts_manager", None):
            ser._rsh_flyout_menu.shortcuts_manager.load()
        if auto_flyout and getattr(ser._rsh_flyout_menu, "auto_flyout_if_shortcuts", None):
            ser._rsh_flyout_menu.auto_flyout_if_shortcuts()

    flyout = ser._rsh_flyout_menu
    sec_idx = getattr(flyout, "active_section_idx", 0) if flyout else 0
    # Flyout indices are zero-based; dashboard section labels are 1-based.
    # Opening a serial port only means the host can listen on it. Do not show
    # an idle machine as browsing the menu until it has sent us input.
    if getattr(ser, "_rsh_input_seen", isinstance(ser, SocketTerminal)):
        set_terminal_activity(ser, f"section:{sec_idx + 1}")
    else:
        clear_terminal_activity(ser)

    serial_count, remote_count = get_active_connection_counts()
    if columns == 40:
        status = (
            f"{time.strftime('%H:%M')} | Serial {serial_count} "
            f"Telnet {remote_count}"
        )
    else:
        status = (
            f"Status: {time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Serial ports: {serial_count} | Telnet clients: {remote_count}"
        )

    output = ser._rsh_flyout_menu.render(
        columns=columns,
        translate_ansi=getattr(ser, "_rsh_translate_ansi", False),
        welcome_banner=WELCOME_BANNER,
        version=VERSION,
        is_remote=remote_client,
        status=status + ("\r\n" + ser._rsh_reminder_notice if getattr(ser, "_rsh_reminder_notice", "") else ""),
    )
    write(ser, output)
    ser._rsh_reminder_notice = ""


def show_legacy_main_menu(ser, use_ansi=True):
    set_terminal_activity(ser, "section:0")
    columns = terminal_columns(ser)
    remote_client = isinstance(ser, SocketTerminal)
    clear_screen(ser, use_ansi)
    banner_prefix = "\r\n" if columns == 80 else ""
    version_spacing = "\r\n\r\n"
    write(ser, banner_prefix + WELCOME_BANNER + "\r\n")
    write(ser, f"v{VERSION}, copyright (c) 2025-2026" + version_spacing)
    if getattr(ser, "_rsh_reminder_notice", ""):
        write(ser, ser._rsh_reminder_notice + "\r\n")
        ser._rsh_reminder_notice = ""
    options = {
        "Accessories": [
            ("1", "Bulletin Boards"),
            ("2", "Web Browser"),
            ("3", "Telnet"),
            ("4", "Notes"),
        ],
        "Bridging": [("5", "COM Port"), ("6", "Keyboard")],
        "Files": [
            ("7", "File Transfers"),
            ("8", "Text Library"),
            ("9", "FTP"),
        ],
        "Various": [("10", "AI Assistant"), ("11", "Wargames")],
        "System": [
            (
                "12",
                (
                    "ANSI: Turn Off"
                    if getattr(ser, "_rsh_translate_ansi", False)
                    else "ANSI: Turn On"
                )
                if columns == 40
                else (
                    "Turn ANSI Translation Off"
                    if getattr(ser, "_rsh_translate_ansi", False)
                    else "Turn ANSI Translation On"
                ),
            ),
            (
                "13",
                f"Switch to {120 - columns} Columns",
            ),
            ("14", "Welcome Banner"),
        ],
    }
    if remote_client:
        options["System"].append(("15", "Disconnect"))

    if columns == 80:
        left_groups = ("Accessories", "Bridging", "Files")
        right_groups = ("Various", "System")
        left_lines = _format_menu_groups(left_groups, options, 39)
        right_lines = _format_menu_groups(right_groups, options, 39)
        for index in range(max(len(left_lines), len(right_lines))):
            left_line = left_lines[index] if index < len(left_lines) else ""
            right_line = right_lines[index] if index < len(right_lines) else ""
            write(ser, f"{left_line:<40}{right_line}\r\n")
    else:
        for group_index, group in enumerate(
            ("Accessories", "Bridging", "Files", "Various", "System")
        ):
            group_spacing = "\r\n" if group_index else ""
            write(ser, f"{group_spacing}[ {group} ]\r\n")
            entries = [
                f"{number:>2}] "
                f"{120 - columns} Columns"
                if number == "13"
                else f"{number:>2}] {label[:14]}"
                for number, label in options[group]
            ]
            for index in range(0, len(entries), 2):
                left = entries[index]
                right = entries[index + 1] if index + 1 < len(entries) else ""
                write(ser, f"{left:<19}{right}\r\n")

    serial_count, remote_count = get_active_connection_counts()
    if columns == 40:
        status = (
            f"{time.strftime('%H:%M')} | Serial {serial_count} "
            f"Telnet {remote_count}"
        )
    else:
        status = (
            f"Status: {time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Serial ports: {serial_count} | Telnet clients: {remote_count}"
        )
    write(ser, "\r\n" + status + "\r\n")
    write(ser, "Type ATM to return to this menu.\r\n")
    if columns == 80:
        write(ser, "\r\n")
    write(ser, "Command: ")


def _format_menu_groups(group_names, options, width):
    lines = []
    for group in group_names:
        lines.append(f"[ {group} ]")
        lines.extend(
            f"{number:>2}] {label}"[:width]
            for number, label in options[group]
        )
        lines.append("")
    while lines and not lines[-1]:
        lines.pop()
    return lines

def show_notes_menu(ser, notes, use_ansi=True):
    clear_screen(ser, use_ansi)
    write(ser, "\r\nNotes:\r\n\r\n")
    display_names = [truncate_name(f) for f in notes]
    for line in two_column_list(
        display_names, left_pad=38, columns=terminal_columns(ser)
    ):
        write(ser, line + "\r\n")
    write(ser, "\r\nEnter number to read, C=Create, D=Delete, Q=Quit\r\n")
    write(ser, "Command: ")

## BBS menu rendering has been moved into the pluggable module `rsh_bbs`.
## The legacy `show_bbs_menu` implementation was removed so the BBS UI
## can be fully controlled from `rsh_bbs.py` and edited without touching
## the core hub.

## File menu rendering is handled by rsh_files.py

def show_text_menu(ser, files, use_ansi=True):
    clear_screen(ser, use_ansi)
    write(ser, "Text library:\r\n\r\n")
    display_names = [truncate_name(f) for f in files]
    for line in two_column_list(
        display_names, left_pad=38, columns=terminal_columns(ser)
    ):
        write(ser, line + "\r\n")
    write(ser, "\r\nEnter the number to read the file. Enter Q to return to the main menu.\r\n")
    write(ser, "Command: ")


def show_bbs_menu(ser, use_ansi=True):
    """Delegate BBS menu rendering to rsh_bbs module if available.

    This keeps existing call sites working while moving presentation
    into the pluggable module.
    """
    try:
        importlib.invalidate_caches()
        bm = importlib.import_module('rsh_bbs')
        importlib.reload(bm)
        # let the module render the menu; it accepts BBSS/IPS/PORTS
        bm.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
    except Exception as e:
        write(ser, f"\r\n*** BBS render error: {e} ***\r\n")
        show_main_menu(ser, use_ansi)

def truncate_name(name, max_len=34):
    # 34 chars + "NN] " keeps within 38-char left column comfortably
    return (name[:max_len] + "…") if len(name) > max_len else name

# ---------------- Networking (BBS dialing) ----------------

def connect_bbs(index, ser):
    host, port = IPS[index], PORTS[index]
    return connect_host(host, port, ser)


def connect_host(host, port, ser):
    """Open a TCP connection to the requested host and port."""
    try:
        s = socket.create_connection((host, port), timeout=10)
        s.settimeout(None)
        write(ser, "\r\nCONNECT\r\n")
        return s
    except Exception:
        write(ser, f"\r\n*** Unable to connect to {host}:{port} ***\r\n")
        write(ser, "NO CARRIER\r\n")
        wait_for_key(ser)
        return None


def add_bbs_entry(name, host, port):
    """Add an entry to the persisted BBS directory transactionally."""
    snapshot = (list(BBSS), list(IPS), list(PORTS))
    BBSS.append(name)
    IPS.append(host)
    PORTS.append(port)
    entries = [
        {"name": entry_name, "host": entry_host, "port": entry_port}
        for entry_name, entry_host, entry_port in zip(BBSS, IPS, PORTS)
    ]
    try:
        save_directory(entries)
    except (OSError, ValueError):
        BBSS[:], IPS[:], PORTS[:] = snapshot
        raise


# File transfer functionality is handled by rsh_files.py

# ---------------- Per-port bridge loop ----------------
def port_worker(name, cfg):
    """Worker thread for each serial port. Only retries if a port was once open and then lost."""
    while True:
        try:
            columns = configured_columns(name, cfg)
            ser = serial.Serial(
                port=cfg["port"],
                baudrate=cfg["baud"],
                bytesize=cfg.get("bytesize", EIGHTBITS),
                parity=cfg.get("parity", PARITY_NONE),
                stopbits=cfg.get("stopbits", STOPBITS_ONE),
                xonxoff=cfg.get("xonxoff", False),
                rtscts=cfg.get("rtscts", False),
                timeout=0
            )
            configure_screen_clearing(
                ser,
                translate_ansi=cfg.get("translate_ansi", False),
                clear_sequence=cfg.get("ansi_clear_sequence", b"\x0c"),
                columns=columns,
            )
            if CONSOLE:
                CONSOLE.update_profile(name, serial="OPEN")
            ser._client_id = f"serial:{name}"
            ser._profile_name = name
            # Register active port
            try:
                ACTIVE_PORTS[cfg['port'].upper()] = {'thread': name, 'serial': ser}
            except Exception:
                pass
            # Run bridge loop until it throws (e.g. port disappears)
            try:
                bridge_loop(
                    name,
                    ser,
                    cfg.get("ansi", True),
                    translate_ansi=cfg.get("translate_ansi", False),
                    ansi_clear_sequence=cfg.get("ansi_clear_sequence", b"\x0c"),
                    ansi_home_clears_screen=cfg.get("ansi_home_clears_screen", False),
                )
            finally:
                unregister_active_terminal(ser)
                clear_terminal_activity(ser, default_name=name)
            # When bridge_loop exits normally, unregister
            try:
                ACTIVE_PORTS.pop(cfg['port'].upper(), None)
            except Exception:
                pass
            if CONSOLE:
                CONSOLE.update_profile(name, serial="RETRY")
        except serial.SerialException as e:
            try:
                ACTIVE_PORTS.pop(cfg["port"].upper(), None)
            except Exception:
                pass
            # If the port was never present at startup, bail out permanently
            if "FileNotFoundError" in str(e) or "cannot find the file" in str(e):
                if CONSOLE:
                    CONSOLE.update_profile(name, serial="MISSING")
                else:
                    console_log(f"{name}: serial port {cfg['port']} is not present.")
                return
            else:
                # If this port was surrendered for COM bridge takeover, wait until it's returned
                if cfg['port'].upper() in SURRENDERED_PORTS:
                    if CONSOLE:
                        CONSOLE.update_profile(name, serial="BRIDGED")
                    console_log(
                        f"{name}: serial port {cfg['port']} is in use by COM Bridge; waiting for it to return.",
                        level="yellow",
                    )
                    # ensure it's unregistered
                    ACTIVE_PORTS.pop(cfg['port'].upper(), None)
                    # Block here until the surrender is cleared
                    while cfg['port'].upper() in SURRENDERED_PORTS:
                        time.sleep(1)
                    console_log(f"{name}: serial port {cfg['port']} returned; retrying.")
                    time.sleep(1)
                    continue
                if CONSOLE:
                    CONSOLE.update_profile(name, serial="RETRY")
                console_log(
                    f"{name}: serial error on {cfg['port']}: {e}; retrying in 5 seconds.",
                    level="red",
                )
                time.sleep(5)
                continue
        except Exception as e:
            try:
                ACTIVE_PORTS.pop(cfg["port"].upper(), None)
            except Exception:
                pass
            if CONSOLE:
                CONSOLE.update_profile(name, serial="ERROR")
            console_log(
                f"{name}: unexpected serial worker error: {e}; retrying in 5 seconds.",
                level="red",
            )
            time.sleep(5)
            continue


def remote_client_worker(name, cfg, client_socket, address):
    """Run one remote client through the same terminal menu as a serial port."""
    terminal = SocketTerminal(client_socket)
    columns = configured_columns(name, cfg)
    client_id = id(client_socket)
    terminal._client_id = client_id
    terminal._profile_name = name
    terminal._remote_address = address
    terminal._terminal_name = f"{name}@{address[0]}"
    with ACTIVE_REMOTE_CLIENTS_LOCK:
        ACTIVE_REMOTE_CLIENTS.add(client_id)
    if CONSOLE:
        CONSOLE.add_client(client_id, name, address)
    try:
        configure_screen_clearing(
            terminal,
            translate_ansi=cfg.get("translate_ansi", False),
            clear_sequence=cfg.get("ansi_clear_sequence", b"\x0c"),
            columns=columns,
        )
        try:
            bridge_loop(
                name,
                terminal,
                cfg.get("ansi", True),
                translate_ansi=cfg.get("translate_ansi", False),
                ansi_clear_sequence=cfg.get("ansi_clear_sequence", b"\x0c"),
                ansi_home_clears_screen=cfg.get("ansi_home_clears_screen", False),
            )
        finally:
            unregister_active_terminal(terminal)
            clear_terminal_activity(terminal, default_name=name)
    except (OSError, ConnectionError) as exc:
        console_log(
            f"{name}: remote client {address[0]}:{address[1]} disconnected: {exc}",
            level="yellow",
        )
    except Exception as exc:
        console_log(
            f"{name}: remote session error for {address[0]}:{address[1]}: {exc}",
            level="red",
        )
    finally:
        with ACTIVE_REMOTE_CLIENTS_LOCK:
            ACTIVE_REMOTE_CLIENTS.discard(client_id)
        if CONSOLE:
            CONSOLE.remove_client(client_id)
        clear_terminal_activity(terminal, default_name=name)
        terminal.close()


def start_remote_client(name, cfg, client_socket, address):
    """Called by the access gate only after the source IP is approved."""
    threading.Thread(
        target=remote_client_worker,
        args=(name, cfg, client_socket, address),
        name=f"{name}-remote-{address[0]}", daemon=True,
    ).start()


def host_console_worker(terminal):
    """Use the full terminal CLI/menu flow for the local dashboard keyboard."""
    try:
        bridge_loop("Host", terminal, use_ansi=False)
    finally:
        unregister_active_terminal(terminal)
        clear_terminal_activity(terminal, default_name="Host")


def local_ipv4_addresses():
    """Return distinct non-loopback IPv4 addresses available on this host."""
    addresses = set()
    try:
        addresses.update(
            info[4][0]
            for info in socket.getaddrinfo(
                socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM
            )
            if not info[4][0].startswith("127.")
        )
    except socket.gaierror as exc:
        console_log(
            f"Could not resolve this computer's hostname for LAN address discovery: {exc}",
            level="yellow",
        )

    # A UDP connect selects the default route without sending any network data.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route_socket:
            route_socket.connect(("192.0.2.1", 9))
            address = route_socket.getsockname()[0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError as exc:
        console_log(
            f"Could not detect the default LAN interface address: {exc}",
            level="yellow",
        )

    return sorted(addresses)


def telnet_server_worker(name, cfg, server_cfg):
    """Accept remote terminal connections for one configured machine profile."""
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        if CONSOLE:
            CONSOLE.update_profile(name, tcp="ERROR")
        console_log(
            f"{name}: invalid TCP server port {port!r}; expected an integer from 1 to 65535.",
            level="red",
        )
        return

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
            listener.listen()
            if CONSOLE:
                CONSOLE.update_profile(name, tcp="LISTENING")
            while True:
                client_socket, address = listener.accept()
                if TELNET_ACCESS is None:
                    client_socket.close()
                    console_log(f"{name}: refused Telnet connection; access gate is not initialized.", level="red")
                    continue
                TELNET_ACCESS.accept(name, cfg, client_socket, address)
    except (OSError, TypeError) as exc:
        if CONSOLE:
            CONSOLE.update_profile(name, tcp="ERROR")
        console_log(
            f"{name}: could not start TCP terminal server on {host}:{port}: {exc}",
            level="red",
        )


def bridge_loop(
    name,
    ser,
    use_ansi,
    translate_ansi=False,
    ansi_clear_sequence=b"\x0c",
    ansi_home_clears_screen=False,
):
    global ANSI_TRANSLATION_PREFERENCES, COLUMN_PREFERENCES
    from retro_os.runtime import create_runtime
    from retro_os.core import Session

    ser._profile_name = getattr(ser, "_profile_name", name)
    if not hasattr(ser, "_client_id"):
        if isinstance(ser, SocketTerminal):
            ser._client_id = id(getattr(ser, "socket", ser))
        else:
            ser._client_id = f"serial:{name}"
    ser._rsh_translate_ansi = bool(translate_ansi)
    ser._rsh_menu_style = getattr(ser, "_rsh_menu_style", "flyout")
    from retro_os.menu import OSFlyoutMenu
    from retro_os.shortcuts import ShortcutsManager
    if not hasattr(ser, "_rsh_shortcuts_manager"):
        ser._rsh_shortcuts_manager = ShortcutsManager(BASE_DIR / "user_shortcuts.json")
    shortcuts_mgr = ser._rsh_shortcuts_manager
    if not hasattr(ser, "_rsh_flyout_menu"):
        ser._rsh_flyout_menu = OSFlyoutMenu(shortcuts_manager=shortcuts_mgr)
    else:
        ser._rsh_flyout_menu.shortcuts_manager = shortcuts_mgr
    tcp_sock = None
    # For COM Port Bridge mode: separate serial to bridge
    bridge_serial = None
    pending_bridge = None
    input_buffer = b""
    mode = "MENU"  # MENU, TELNET, BBS, FILES, TEXT, BROWSER
    retro_session = Session(
        client_type="host" if getattr(ser, "_rsh_host_console", False) is True else "telnet" if isinstance(ser, SocketTerminal) else "serial",
        cols=terminal_columns(ser),
        user="Host" if getattr(ser, "_rsh_host_console", False) is True else getattr(ser, "_terminal_name", name),
    )
    shell_requested_module = []

    def activate_retro_module(module_name):
        shell_requested_module.append(module_name)

    register_active_terminal(ser)
    retro_session, event_bus, host_env, retro_shell, _module_loader = create_runtime(
        {
            "notes": NOTES_DIR,
            "text": TEXT_DIR,
            "files": FILES_DIR,
            "bookmarks": BASE_DIR / "browser_bookmarks.json",
            "mail": BASE_DIR / "mail",
            "tasks": BASE_DIR / "scheduled_tasks.json",
            "shortcuts": BASE_DIR / "user_shortcuts.json",
        },
        session=retro_session,
        activate_module=activate_retro_module,
        profiles_path=BASE_DIR / "keyboard_profiles.json",
        shortcuts_path=BASE_DIR / "user_shortcuts.json",
    )
    host_env.shortcuts_manager = shortcuts_mgr
    if getattr(ser, "_rsh_host_console", False) is True:
        retro_shell.register_command("help", lambda _args: retro_shell.help() + "\nHost controls: allow <#>, deny <#>, pending, clear. ATM opens menus. PgUp/PgDn scroll output; Up/Down recall commands.")
    if hasattr(host_env, "scheduler") and host_env.scheduler:
        host_env.scheduler.broadcaster = broadcast_scheduler_event
    from retro_os.toolkit import CalendarTool, start_calendar_reminders
    calendar_tool = getattr(host_env, "calendar_tool", None)
    if isinstance(calendar_tool, CalendarTool):
        try:
            ser._rsh_reminder_notice = calendar_tool.connection_reminders()
            start_calendar_reminders(calendar_tool, broadcast_to_terminals)
        except (OSError, ValueError, KeyError) as exc:
            console_log(f"Calendar reminders could not load: {exc}", level="yellow")

    def render_shell_result(result):
        from retro_os.viewer import paginate_text

        text = str(result)
        if getattr(ser, "_rsh_host_console", False) is True:
            for output_line in text.splitlines():
                write(ser, output_line + "\r\n")
            return
        cols = getattr(retro_session, "cols", terminal_columns(ser))
        rows = getattr(retro_session, "rows", 24)
        pages = paginate_text(text, cols, page_lines=max(1, rows - 2))

        page_index = 0
        while page_index < len(pages):
            for output_line in pages[page_index]:
                write(ser, output_line + "\r\n")
            if page_index + 1 < len(pages):
                prompt = f"-- More [{page_index + 1}/{len(pages)}] (Space/Enter=Next, Q=Quit, A-Z=Skip) --"
                write(ser, prompt)
                ch = ""
                while True:
                    if ser.in_waiting:
                        raw = ser.read(1)
                        try:
                            ch = raw.decode(errors="ignore").upper()
                        except Exception:
                            ch = ""
                        break
                    time.sleep(0.05)
                write(ser, "\r\n")
                if ch in ("Q", "\x1b", "\x18", "\x03"):
                    break
                if "A" <= ch <= "Z" and ch != "Q":
                    target_page = None
                    for p_idx in range(len(pages)):
                        for line in pages[p_idx]:
                            stripped = line.strip()
                            if stripped and stripped[0].upper() == ch:
                                target_page = p_idx
                                break
                        if target_page is not None:
                            break
                    if target_page is not None:
                        page_index = target_page
                        continue
                    else:
                        write(ser, f"(No entries starting with '{ch}')\r\n")
            page_index += 1

    def shortcut_mappings():
        return host_env.keyboard_profiles.get(retro_session.kb_profile)

    def publish_shortcut(shortcut, action):
        event_bus.publish(
            "kb.shortcut",
            {"session": retro_session, "shortcut": shortcut, "action": action},
        )

    def on_send_keys_event(evt):
        if not isinstance(evt, dict):
            return
        target_session = evt.get("session")
        if target_session is not None and target_session != retro_session:
            return
        raw_text = evt.get("text", "")
        if not raw_text:
            return
        from retro_os.runtime import parse_and_chunk_keystrokes
        actions = parse_and_chunk_keystrokes(raw_text)
        for act, val in actions:
            if act == "wait":
                time.sleep(val)
            elif act == "send":
                if tcp_sock:
                    try:
                        tcp_sock.sendall(val)
                    except Exception:
                        pass
                elif bridge_session and bridge_module:
                    bs = bridge_session.get("bridge_serial") if isinstance(bridge_session, dict) else None
                    if bs:
                        try:
                            bs.write(val)
                        except Exception:
                            pass
                else:
                    try:
                        ser.write(val)
                    except Exception:
                        pass

    event_bus.subscribe("session.send_keys", on_send_keys_event)

    def on_terminals_list(evt):
        if isinstance(evt, dict):
            with ACTIVE_TERMINALS_LOCK:
                terminals = list(ACTIVE_TERMINALS)
            evt["names"] = [
                getattr(term, "_terminal_name", getattr(term, "_profile_name", "Terminal"))
                for term in terminals
            ]

    event_bus.subscribe("terminals.list", on_terminals_list)

    def on_notify_event(evt):
        if not isinstance(evt, dict):
            return
        sender = evt.get("sender") or "Host"
        msg = evt.get("message", "")
        target = evt.get("target")
        if target and msg:
            with ACTIVE_TERMINALS_LOCK:
                terminals = list(ACTIVE_TERMINALS)
            matches = [
                term for term in terminals
                if target.casefold() in {
                    str(getattr(term, "_terminal_name", "")).casefold(),
                    str(getattr(term, "_profile_name", "")).casefold(),
                }
            ]
            for term in matches:
                try:
                    write(term, f"\r\n*** [MESSAGE from {sender}] {msg} ***\r\n")
                    evt["delivered"] = True
                except Exception:
                    pass
            return
        # Avoid double-broadcast if sent from automated scheduler task
        if msg and evt.get("session") is not None:
            broadcast_to_terminals(f"\r\n*** [ALERT from {sender}] {msg} ***\r\n")

    event_bus.subscribe("notify", on_notify_event)

    def run_mail_menu():
        while True:
            try:
                mgr = host_env.mail_manager
                cur_mode = mgr.get_mode() if mgr else "hub"
            except Exception:
                cur_mode = "hub"
            mode_desc = "Hub Mailbox (Inter-Terminal)" if cur_mode == "hub" else "Internet Email (IMAP/SMTP)"

            write(ser, f"\r\n--- ELECTRONIC MAIL [{mode_desc}] ---\r\n")
            write(ser, "[1] View Inbox\r\n")
            write(ser, "[2] Read Message\r\n")
            write(ser, "[3] Compose & Send Message\r\n")
            write(ser, "[4] Toggle Mail Mode (Hub Mail <-> Internet)\r\n")
            write(ser, "[5] Configure Internet Mail (Host Desktop GUI)\r\n")
            write(ser, "[6] Open Mailto Link on Host PC\r\n")
            write(ser, "[7] Delete Message\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                write(ser, "\r\n")
                try:
                    res = retro_shell.execute("mail inbox")
                    render_shell_result(res)
                except Exception as exc:
                    write(ser, f"Mail error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "2":
                write(ser, "\r\nMessage ID or Number (Q to cancel): ")
                mid = read_input_line(ser).strip()
                if mid and mid.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"mail read {mid}")
                        render_shell_result(res)
                    except Exception as exc:
                        write(ser, f"Mail error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "3":
                if cur_mode == "internet":
                    write(ser, "\r\nTo (recipient email address, Q to cancel): ")
                    to_addr = read_input_line(ser).strip()
                    if not to_addr or to_addr.upper() == "Q":
                        continue
                else:
                    write(ser, "\r\nRecipient or Machine (leave blank for All, Q to cancel): ")
                    to_addr = read_input_line(ser).strip()
                    if to_addr.upper() == "Q":
                        continue
                    if not to_addr:
                        to_addr = "All"
                write(ser, "Subject: ")
                subj = read_input_line(ser).strip()
                write(ser, "Body: ")
                body = read_input_line(ser).strip()
                try:
                    res = retro_shell.execute(f"mail send {to_addr} {subj} | {body}")
                    write(ser, f"\r\n{res}\r\n")
                except Exception as exc:
                    write(ser, f"Mail error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "4":
                try:
                    res = retro_shell.execute("mail mode")
                    write(ser, f"\r\n{res}\r\n")
                except Exception as exc:
                    write(ser, f"Mail error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "5":
                write(ser, "\r\nOpening configuration window on host desktop...\r\n")
                try:
                    res = retro_shell.execute("mail popup")
                    write(ser, f"{res}\r\n")
                except Exception as exc:
                    write(ser, f"Mail error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "6":
                write(ser, "\r\nEnter email address (Q to cancel): ")
                addr = read_input_line(ser).strip()
                if addr and addr.upper() != "Q":
                    write(ser, "Subject (optional): ")
                    subj = read_input_line(ser).strip()
                    try:
                        cmd = f"mail mailto {addr} {subj}" if subj else f"mail mailto {addr}"
                        res = retro_shell.execute(cmd)
                        write(ser, f"\r\n{res}\r\n")
                    except Exception as exc:
                        write(ser, f"Mail error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "7":
                write(ser, "\r\nMessage ID or Number to delete (Q to cancel): ")
                mid = read_input_line(ser).strip()
                if mid and mid.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"mail delete {mid}")
                        write(ser, f"\r\n{res}\r\n")
                    except Exception as exc:
                        write(ser, f"Mail error: {exc}\r\n")
                    wait_for_key(ser)

    def run_minesweeper_session():
        write(ser, "\r\n--- MINESWEEPER ---\r\n")
        res = retro_shell.execute("mines")
        write(ser, res + "\r\n")
        while True:
            write(ser, "\r\nMines [R/F row col, N=new, Q=quit]> ")
            cmd = read_input_line(ser).strip()
            if not cmd or cmd.upper() in ("Q", "QUIT", "EXIT"):
                break
            if cmd.upper() in ("NEW", "RESTART"):
                res = retro_shell.execute("mines new")
                write(ser, "\r\n" + res + "\r\n")
            else:
                clean_cmd = cmd
                if clean_cmd.lower().startswith("minesweeper "):
                    clean_cmd = clean_cmd[12:].strip()
                elif clean_cmd.lower().startswith("mines "):
                    clean_cmd = clean_cmd[6:].strip()
                res = retro_shell.execute(f"mines {clean_cmd}")
                write(ser, "\r\n" + res + "\r\n")
                if "Game over" in res or "You win" in res:
                    write(ser, "Press any key to continue...\r\n")
                    wait_for_key(ser)
                    break

    def run_solitaire_session():
        write(ser, "\r\n--- SOLITAIRE ---\r\n")
        res = retro_shell.execute("solitaire")
        write(ser, res + "\r\n")
        while True:
            write(ser, "\r\nSolitaire [D=draw, M=move, A=auto, N=new, Q=quit]> ")
            cmd = read_input_line(ser).strip()
            if not cmd or cmd.upper() in ("Q", "QUIT", "EXIT"):
                break
            if cmd.upper() in ("NEW", "RESTART"):
                res = retro_shell.execute("solitaire new")
                write(ser, "\r\n" + res + "\r\n")
            else:
                clean_cmd = cmd
                if clean_cmd.lower().startswith("solitaire "):
                    clean_cmd = clean_cmd[10:].strip()
                elif clean_cmd.lower().startswith("sol "):
                    clean_cmd = clean_cmd[4:].strip()
                res = retro_shell.execute(f"solitaire {clean_cmd}")
                write(ser, "\r\n" + res + "\r\n")
                if "You win" in res:
                    write(ser, "Press any key to continue...\r\n")
                    wait_for_key(ser)
                    break

    def run_wumpus_session():
        write(ser, "\r\n--- HUNT THE WUMPUS ---\r\n")
        write(ser, retro_shell.execute("games wumpus new") + "\r\n")
        while True:
            write(ser, "\r\nWumpus [M room, S rooms, N=new, Q=quit]> ")
            cmd = read_input_line(ser).strip()
            if not cmd or cmd.upper() in ("Q", "QUIT", "EXIT"):
                retro_shell.execute("games wumpus quit")
                break
            if cmd.upper() in ("NEW", "RESTART"):
                res = retro_shell.execute("games wumpus new")
            else:
                res = retro_shell.execute("games wumpus " + cmd)
            write(ser, "\r\n" + str(res) + "\r\n")
            if "Game over" in res or "YOU WIN" in res:
                write(ser, "Press any key to continue...\r\n")
                wait_for_key(ser)
                break

    def run_lander_session():
        write(ser, "\r\n--- LUNAR LANDER ---\r\n")
        write(ser, retro_shell.execute("games lander new") + "\r\n")
        while True:
            write(ser, "\r\nLander [B 0-4, I=status, N=new, Q=quit]> ")
            cmd = read_input_line(ser).strip()
            if not cmd or cmd.upper() in ("Q", "QUIT", "EXIT"):
                retro_shell.execute("games lander quit")
                break
            if cmd.upper() in ("NEW", "RESTART"):
                res = retro_shell.execute("games lander new")
            elif cmd.lower().startswith("lander "):
                res = retro_shell.execute("games " + cmd)
            else:
                res = retro_shell.execute("games lander " + cmd)
            write(ser, "\r\n" + str(res) + "\r\n")
            if "Touchdown!" in res or "CRASH!" in res:
                write(ser, "Press any key to continue...\r\n")
                wait_for_key(ser)
                break

    def run_card_or_code_game(game_name, title, prompt, end_markers):
        command = "blackjack" if game_name == "blackjack" else "mastermind"
        write(ser, f"\r\n--- {title} ---\r\n")
        write(ser, retro_shell.execute(f"games {command} new") + "\r\n")
        while True:
            write(ser, f"\r\n{prompt}")
            cmd = read_input_line(ser).strip()
            if not cmd or cmd.upper() in ("Q", "QUIT", "EXIT"):
                retro_shell.execute(f"games {command} quit")
                break
            if cmd.upper() in ("NEW", "RESTART"):
                res = retro_shell.execute(f"games {command} new")
            else:
                res = retro_shell.execute(f"games {command} {cmd}")
            write(ser, "\r\n" + str(res) + "\r\n")
            if any(marker in res for marker in end_markers):
                write(ser, "Press any key to continue...\r\n")
                wait_for_key(ser)
                break

    def run_word_guess_session():
        write(ser, "\r\n--- WORD GUESS ---\r\n")
        write(ser, retro_shell.execute("games wordguess new") + "\r\n")
        while True:
            write(ser, "\r\nWord [five letters, N=new, Q=quit]> ")
            cmd = read_input_line(ser).strip()
            if not cmd or cmd.upper() in ("Q", "QUIT", "EXIT"):
                retro_shell.execute("games wordguess quit")
                break
            res = retro_shell.execute(
                "games wordguess new" if cmd.upper() in ("N", "NEW", "RESTART")
                else f"games wordguess {cmd}"
            )
            write(ser, "\r\n" + str(res) + "\r\n")
            if "YOU WIN!" in res or "No guesses left." in res:
                write(ser, "Press any key to continue...\r\n")
                wait_for_key(ser)
                break

    def run_trek_session():
        write(ser, "\r\n--- STAR TREK ---\r\n")
        write(ser, retro_shell.execute("games trek new") + "\r\n")
        while True:
            write(ser, "\r\nTrek [command, N=new, Q=quit]> ")
            cmd = read_input_line(ser).strip()
            if not cmd or cmd.upper() in ("Q", "QUIT", "EXIT"):
                retro_shell.execute("games trek quit")
                break
            if cmd.upper() in ("N", "NEW", "RESTART"):
                res = retro_shell.execute("games trek new")
            else:
                res = retro_shell.execute(f"games trek {cmd}")
            res = str(res)
            write(ser, "\r\n" + res + "\r\n")
            lower = res.lower()
            if "victory!" in lower or "destroyed!" in lower or "mission time expired" in lower:
                write(ser, "Press any key to continue...\r\n")
                wait_for_key(ser)
                break

    def run_games_menu():
        while True:
            write(ser, "\r\n--- RETRO GAMES ---\r\n")
            write(ser, "[1] Minesweeper\r\n")
            write(ser, "[2] Solitaire\r\n")
            write(ser, "[3] Lunar Lander\r\n")
            write(ser, "[4] Hunt the Wumpus\r\n")
            write(ser, "[5] Blackjack\r\n")
            write(ser, "[6] Mastermind\r\n")
            write(ser, "[7] Word Guess\r\n")
            write(ser, "[8] Star Trek\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                return None
            elif choice in ("3", "L", "LANDER", "LUNAR LANDER"):
                run_lander_session()
            elif choice in ("1", "M", "MINES", "MINESWEEPER"):
                run_minesweeper_session()
            elif choice in ("2", "S", "SOL", "SOLITAIRE"):
                run_solitaire_session()
            elif choice in ("4", "WUMPUS", "HUNT"):
                run_wumpus_session()
            elif choice in ("5", "BLACKJACK", "21"):
                run_card_or_code_game("blackjack", "BLACKJACK", "Blackjack [H=hit, S=stand, N=new, Q=quit]> ", ("You win!", "Dealer wins.", "Push.", "Bust!", "BLACKJACK!"))
            elif choice in ("6", "MASTERMIND", "CODEBREAKER"):
                run_card_or_code_game("mastermind", "MASTERMIND", "Mastermind [G 1234=guess, N=new, Q=quit]> ", ("YOU WIN!", "Out of guesses."))
            elif choice in ("7", "WORD", "WORDGUESS", "WORDLE"):
                run_word_guess_session()
            elif choice in ("8", "TREK", "STAR TREK", "STARTREK"):
                run_trek_session()

    def run_help_menu():
        from retro_os.help_data import get_help_topics, get_topic_content
        topics = get_help_topics()
        while True:
            write(ser, "\r\n--- RETRO SERIAL HUB HELP & USER GUIDE ---\r\n")
            for tid, title in topics:
                write(ser, f"[{tid}] {title}\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Select topic (1-9, or Q): ")
            choice = read_input_line(ser).strip()
            if not choice or choice.upper() in ("Q", "QUIT", "EXIT", "0"):
                break
            content = get_topic_content(choice)
            write(ser, "\r\n")
            render_shell_result(content)
            wait_for_key(ser)

    def run_tool_menu(tool):
        import shlex
        from retro_os.modules.toolkit import TOOL_MENUS
        from retro_os.core import Shell

        title, initial, choices = TOOL_MENUS[tool]
        clear_screen(ser, use_ansi)
        write(ser, f"\r\n--- {title} ---\r\n")
        render_shell_result(retro_shell.execute(f"{tool} {initial}"))
        while True:
            write(ser, f"\r\n--- {title} ---\r\n")
            for index, (label, _, _) in enumerate(choices, 1):
                write(ser, f"[{index}] {label}\r\n")
            write(ser, "[Q] Return to Main Menu\r\nChoice (or command): ")
            choice = read_input_line(ser).strip()
            if not choice or choice.upper() in ("Q", "QUIT", "EXIT", "ATM"):
                return False
            if choice.isdigit() and 1 <= int(choice) <= len(choices):
                _, fixed, prompts = choices[int(choice) - 1]
                arguments = list(fixed)
                cancelled = False
                for prompt in prompts:
                    write(ser, prompt + " (Enter cancels): ")
                    value = read_input_line(ser).strip()
                    if not value:
                        cancelled = True
                        break
                    arguments.append(value)
                if cancelled:
                    continue
            else:
                try:
                    arguments = Shell.split_line(choice)
                except ValueError as exc:
                    write(ser, f"\r\n{exc}\r\n")
                    continue
                if arguments and HUB_TOOL_ALIASES.get(arguments[0].upper()) == tool:
                    arguments = arguments[1:]
            result = retro_shell.execute(shlex.join([tool, *arguments]))
            render_shell_result(result)
            if shell_requested_module:
                handled = handle_shell_action(shell_requested_module.pop())
                if handled:
                    return True

    def run_calc_session():
        write(ser, "\r\n--- RETRO CALCULATOR ---\r\n")
        write(ser, "Enter expressions (e.g. 15 * 24, sqrt(144), 0x1F + 10).\r\n")
        write(ser, "Type 'q' or 'exit' to return to Main Menu.\r\n")
        while True:
            write(ser, "Calc> ")
            expr = read_input_line(ser).strip()
            if not expr or expr.upper() in ("Q", "QUIT", "EXIT"):
                break
            try:
                res = retro_shell.execute(f"calc {expr}")
                write(ser, f"Result: {res}\r\n")
            except Exception as exc:
                write(ser, f"Error: {exc}\r\n")

    def run_logo_session():
        from retro_os.logo import LogoInterpreter

        logo = LogoInterpreter(graphics=True)
        write(ser, "\r\n--- LOGO ---\r\n")
        write(ser, "Terminal Logo interpreter. Drawing commands report position and heading.\r\n")
        write(ser, "Type HELP for commands; type BYE to return to the hub.\r\n")
        write(ser, logo.help_text() + "\r\n")
        while not logo.done:
            write(ser, logo.prompt)
            command = read_input_line(ser).strip()
            if not command:
                continue
            response = logo.execute(command)
            if response:
                write(ser, response.replace("\n", "\r\n") + "\r\n")

    def run_keyboard_profiles_menu():
        while True:
            prof = getattr(retro_session, "kb_profile", "default")
            write(ser, f"\r\n--- KEYBOARD BRIDGE PROFILES ---\r\n")
            write(ser, f"Active Profile: {prof}\r\n")
            write(ser, "[1] List Available Profiles\r\n")
            write(ser, "[2] Switch Active Profile\r\n")
            write(ser, "[3] Map Key to Shortcut\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                write(ser, "\r\n")
                try:
                    res = retro_shell.execute("kb profiles")
                    render_shell_result(res)
                except Exception as exc:
                    write(ser, f"KB profile error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "2":
                write(ser, "\r\nProfile name to activate (Q to cancel): ")
                pname = read_input_line(ser).strip()
                if pname and pname.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"kb profile {pname}")
                        write(ser, f"{res}\r\n")
                    except Exception as exc:
                        write(ser, f"KB profile error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "3":
                write(ser, "\r\nKey to map (e.g. CTRL+W, Q to cancel): ")
                k = read_input_line(ser).strip()
                if not k or k.upper() == "Q":
                    continue
                write(ser, "Host action/shortcut (e.g. WIN or WIN+R): ")
                a = read_input_line(ser).strip()
                if a:
                    try:
                        res = retro_shell.execute(f"kb map {k} {a}")
                        write(ser, f"{res}\r\n")
                    except Exception as exc:
                        write(ser, f"KB map error: {exc}\r\n")
                    wait_for_key(ser)

    def run_document_viewer_menu():
        while True:
            write(ser, "\r\n--- DOCUMENT VIEWER ---\r\n")
            write(ser, "Formats: PDF, DOCX, XLSX, CSV, TXT, MD, HTML, Web URLs\r\n")
            write(ser, "[1] Browse Local Files (files/ and text/)\r\n")
            write(ser, "[2] Enter Local File Path\r\n")
            write(ser, "[3] Download and View from Internet (URL)\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                found_files = []
                for p in [FILES_DIR, TEXT_DIR]:
                    if p.exists() and p.is_dir():
                        for item in sorted(p.iterdir()):
                            if item.is_file() and not item.name.startswith("."):
                                found_files.append(item)
                if not found_files:
                    write(ser, "\r\nNo files found in files/ or text/ directories.\r\n")
                    wait_for_key(ser)
                    continue
                write(ser, "\r\nAvailable Files:\r\n")
                for idx, fpath in enumerate(found_files, 1):
                    write(ser, f"[{idx}] {fpath.name} ({fpath.parent.name}/)\r\n")
                write(ser, "Select file number (Q to cancel): ")
                f_idx = read_input_line(ser).strip()
                if not f_idx or f_idx.upper() == "Q":
                    continue
                try:
                    chosen = found_files[int(f_idx) - 1]
                    write(ser, f"\r\nLoading {chosen.name}...\r\n")
                    res = retro_shell.execute(f'view "{chosen}"')
                    render_shell_result(res)
                except (ValueError, IndexError):
                    write(ser, "Invalid file selection.\r\n")
                except Exception as exc:
                    write(ser, f"Viewer error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "2":
                write(ser, "\r\nEnter local file path (Q to cancel): ")
                fpath_input = read_input_line(ser).strip()
                if fpath_input and fpath_input.upper() != "Q":
                    try:
                        clean_path = fpath_input.strip("'\"")
                        res = retro_shell.execute(f'view "{clean_path}"')
                        render_shell_result(res)
                    except Exception as exc:
                        write(ser, f"Viewer error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "3":
                write(ser, "\r\nEnter URL to download and view (e.g. https://wttr.in/Austin?format=3, Q to cancel):\r\nURL: ")
                url_input = read_input_line(ser).strip()
                if url_input and url_input.upper() != "Q":
                    write(ser, f"\r\nDownloading and extracting {url_input}...\r\n")
                    try:
                        clean_url = url_input.strip("'\"")
                        res = retro_shell.execute(f'view "{clean_url}"')
                        render_shell_result(res)
                    except Exception as exc:
                        write(ser, f"Download/viewer error: {exc}\r\n")
                    wait_for_key(ser)

    def run_keyboard_bridge_session(target_app=None, app_args=None):
        if target_app:
            write(ser, f"\r\nLaunching {target_app} on host...\r\n")
            try:
                host_env.launch_app(target_app, app_args or [], interactive=False)
            except Exception as exc:
                write(ser, f"*** Failed to launch app: {exc} ***\r\n")
                wait_for_key(ser)
                return
            time.sleep(0.5)

        try:
            keyboard_module = importlib.import_module("rsh_keyboard")
            kb = keyboard_module.KeyboardBridge(
                shortcut_mappings=shortcut_mappings,
                on_shortcut=publish_shortcut,
                exit_byte=ord(HOST_SETTINGS["keyboard_exit_binding"][-1]) - 64,
            )
        except Exception as e:
            write(ser, f"\r\n*** Keyboard Bridge unavailable: {e} ***\r\n")
            wait_for_key(ser)
            return

        clear_screen(ser, use_ansi)
        if target_app:
            write(ser, f"--- KEYBOARD BRIDGE: {target_app} ---\r\n")
        else:
            write(ser, "--- KEYBOARD BRIDGE ACTIVE ---\r\n")
        write(ser, "Characters typed on the retro terminal are sent to the active host window.\r\n")
        write(ser, "Enter, Tab, Backspace and configured shortcuts (e.g. CTRL+W -> WIN) are supported.\r\n")
        write(
            ser,
            f"Press {HOST_SETTINGS['keyboard_exit_binding']} to exit and return to Retro Serial Hub.\r\n",
        )
        write(ser, "----------------------------------------------------------------------\r\n\r\n")

        while True:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                if not data and isinstance(ser, SocketTerminal):
                    break
                kb._shortcut_mappings = shortcut_mappings
                kb._on_shortcut = publish_shortcut
                try:
                    if kb.feed(data):
                        break
                except Exception as exc:
                    write(ser, f"\r\n[Keyboard injection error: {exc}]\r\n")
            time.sleep(0.01)

        write(ser, "\r\n*** Keyboard Bridge closed. Returning to Retro Serial Hub. ***\r\n")
        time.sleep(0.3)

    def run_interactive_app(target_app, app_args=None, local_echo=True, crlf_mode=True, work_dir=None):
        if host_env.is_gui_app(target_app):
            write(ser, f"\r\nNotice: '{target_app}' is a GUI application (no text console stream).\r\n")
            write(ser, "Starting Keyboard Bridge so you can type into the application window...\r\n")
            time.sleep(0.5)
            run_keyboard_bridge_session(target_app, app_args)
            return

        write(ser, f"\r\nStarting console terminal session for {target_app}...\r\n")
        try:
            proc = host_env.launch_app(target_app, app_args or [], interactive=True, cwd=work_dir)
        except Exception as exc:
            write(ser, f"*** Failed to launch console app: {exc} ***\r\n")
            wait_for_key(ser)
            return

        if not hasattr(proc, "stdin") or proc.stdin is None:
            run_keyboard_bridge_session(target_app, app_args)
            return

        clear_screen(ser, use_ansi)
        write(ser, f"--- Host Terminal: {target_app} ---\r\n")
        echo_str = "ON" if local_echo else "OFF"
        crlf_str = "CRLF" if crlf_mode else "LF"
        write(ser, f"Streaming I/O (Echo: {echo_str}, Translation: {crlf_str}).\r\n")
        write(ser, "Type host commands. Press Ctrl+X to exit terminal.\r\n")
        write(ser, "--------------------------------------------------------\r\n\r\n")

        stop_event = threading.Event()

        def stdout_reader():
            last_was_cr = False
            while not stop_event.is_set():
                try:
                    chunk = proc.stdout.read(256)
                    if not chunk:
                        break
                    out = bytearray()
                    for b in chunk:
                        if b == 10:  # \n
                            if not last_was_cr:
                                out.extend(b"\r\n")
                            else:
                                out.append(10)
                            last_was_cr = False
                        elif b == 13:  # \r
                            out.append(13)
                            last_was_cr = True
                        else:
                            out.append(b)
                            last_was_cr = False
                    ser.write(bytes(out))
                except Exception:
                    break

        reader_thread = threading.Thread(target=stdout_reader, daemon=True)
        reader_thread.start()

        try:
            while True:
                if proc.poll() is not None:
                    time.sleep(0.2)
                    break
                if ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    if not data and isinstance(ser, SocketTerminal):
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        break
                    if b"\x18" in data:  # Ctrl+X
                        write(ser, "\r\n*** Console session terminated by user (Ctrl+X). ***\r\n")
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        break
                    # Local echo for retro serial terminal
                    if local_echo:
                        for b in data:
                            if b in (8, 127):
                                ser.write(b"\x08 \x08")
                            elif b in (10, 13):
                                ser.write(b"\r\n")
                            elif b >= 32:
                                ser.write(bytes((b,)))
                    if crlf_mode:
                        normalized = (
                            data.replace(b"\r\n", b"\n")
                            .replace(b"\r", b"\n")
                            .replace(b"\n", b"\r\n")
                        )
                    else:
                        normalized = data.replace(b"\r", b"\n")
                    try:
                        proc.stdin.write(normalized)
                        proc.stdin.flush()
                    except Exception:
                        break
                time.sleep(0.01)
        finally:
            stop_event.set()
            try:
                proc.stdin.close()
            except Exception:
                pass
            reader_thread.join(timeout=1.0)
            try:
                proc.stdout.close()
            except Exception:
                pass
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            exit_code = proc.poll()
            write(ser, f"\r\n[Process finished (exit code {exit_code})]\r\n")
            wait_for_key(ser)

    def launch_with_keyboard_bridge(target_app, app_args=None):
        run_keyboard_bridge_session(target_app, app_args)

    def prompt_and_launch_app(app_name):
        is_gui = host_env.is_gui_app(app_name)
        write(ser, f"\r\nSelect Launch Mode for '{app_name}':\r\n")
        if is_gui:
            write(ser, "  [1] Keyboard Bridge (launch & type into host window) [Default]\r\n")
            write(ser, "  [2] Background (run on host without terminal interaction)\r\n")
            write(ser, "Choice [1-2, default=1]: ")
            l_mode = read_input_line(ser).strip()
            if l_mode in ("2", "B", "BG", "BACKGROUND"):
                try:
                    res = retro_shell.execute(f"launch -b {app_name}")
                    write(ser, f"\r\n{res}\r\n")
                except Exception as exc:
                    write(ser, f"Launch error: {exc}\r\n")
                wait_for_key(ser)
            else:
                run_keyboard_bridge_session(app_name)
        else:
            write(ser, "  [1] Console Terminal (stream app output to terminal) [Default]\r\n")
            write(ser, "  [2] Keyboard Bridge (launch & type into host window)\r\n")
            write(ser, "  [3] Background (run on host without terminal interaction)\r\n")
            write(ser, "Choice [1-3, default=1]: ")
            l_mode = read_input_line(ser).strip()
            if l_mode in ("2", "K", "KEYBOARD"):
                run_keyboard_bridge_session(app_name)
            elif l_mode in ("3", "B", "BG", "BACKGROUND"):
                try:
                    res = retro_shell.execute(f"launch -b {app_name}")
                    write(ser, f"\r\n{res}\r\n")
                except Exception as exc:
                    write(ser, f"Launch error: {exc}\r\n")
                wait_for_key(ser)
            else:
                run_interactive_app(app_name)

    def run_apps_menu(launch_first=False):
        if launch_first:
            write(ser, "\r\nApplication name or path to launch (Q to cancel): ")
            app_to_launch = read_input_line(ser).strip()
            if app_to_launch and app_to_launch.upper() != "Q":
                prompt_and_launch_app(app_to_launch)
            return

        while True:
            write(ser, "\r\n--- HOST APPLICATIONS ---\r\n")
            write(ser, "[1] List All Applications (A-Z Paginated)\r\n")
            write(ser, "[2] Search Applications by Name\r\n")
            write(ser, "[3] Launch Application\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                write(ser, "\r\n")
                try:
                    res = retro_shell.execute("apps")
                    render_shell_result(res)
                except Exception as exc:
                    write(ser, f"Apps error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "2":
                write(ser, "\r\nSearch term or letter (Q to cancel): ")
                term = read_input_line(ser).strip()
                if term and term.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"apps {term}")
                        render_shell_result(res)
                    except Exception as exc:
                        write(ser, f"Apps error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "3":
                write(ser, "\r\nApplication name to launch (Q to cancel): ")
                app_name = read_input_line(ser).strip()
                if app_name and app_name.upper() != "Q":
                    prompt_and_launch_app(app_name)

    def run_host_terminal_menu(initial_cmd=None):
        import platform
        shell_info = host_env.get_host_shell()
        target_shell = shell_info["default_shell"]
        target_args = list(shell_info["default_args"])
        target_name = shell_info["default_name"]
        alt_shell = shell_info.get("alt_shell")
        alt_args = list(shell_info.get("alt_args", []))
        alt_name = shell_info.get("alt_name", "Alternative Shell")
        system_name = shell_info.get("system", platform.system())

        if initial_cmd:
            parts = initial_cmd.strip().split()
            if len(parts) > 1 and parts[0].upper() in ("CMD", "TERMINAL", "HOSTCMD", "HOSTSH", "PROMPT"):
                sub = parts[1].lower()
                if sub in ("powershell", "ps") and alt_shell:
                    run_interactive_app(alt_shell, alt_args + parts[2:], local_echo=False)
                    return
                elif sub in ("cmd", "cmd.exe"):
                    run_interactive_app("cmd.exe", ["/q"] + parts[2:], local_echo=True)
                    return
                else:
                    run_interactive_app(parts[1], parts[2:], local_echo=True)
                    return

        local_echo = True
        crlf_mode = True
        current_workdir = None

        while True:
            clear_screen(ser, use_ansi)
            write(ser, "========================================\r\n")
            write(ser, "   Host Terminal / Command Prompt\r\n")
            write(ser, "========================================\r\n")
            write(ser, f"Host OS : {system_name} ({platform.machine()})\r\n")
            write(ser, f"Target  : {target_name}\r\n")
            echo_status = "ON" if local_echo else "OFF"
            crlf_status = "CRLF" if crlf_mode else "LF"
            write(ser, f"Settings: Echo: {echo_status} | Translation: {crlf_status}\r\n\r\n")

            write(ser, "  [1] Quick Launch (Default Shell) [Enter]\r\n")
            if alt_shell:
                write(ser, f"  [2] Switch Shell ({alt_name})\r\n")
            else:
                write(ser, "  [2] Switch Shell\r\n")
            write(ser, f"  [3] Toggle Local Echo ({echo_status})\r\n")
            write(ser, f"  [4] Toggle Line Translation ({crlf_status})\r\n")
            write(ser, "  [5] Custom Command / Shell\r\n")
            write(ser, "  [Q] Return to Main Menu\r\n\r\n")
            write(ser, "Choice [1-5, Enter=Quick Launch]: ")

            choice = read_input_line(ser).strip()
            if not choice or choice in ("1", "L", "LAUNCH", "QUICK", "START"):
                run_interactive_app(
                    target_shell,
                    target_args,
                    local_echo=local_echo,
                    crlf_mode=crlf_mode,
                    work_dir=current_workdir,
                )
                break
            elif choice in ("2", "SWITCH", "SHELL"):
                if alt_shell and target_shell == shell_info["default_shell"]:
                    target_shell = alt_shell
                    target_args = list(alt_args)
                    target_name = alt_name
                    if "powershell" in target_shell.lower():
                        local_echo = False
                else:
                    target_shell = shell_info["default_shell"]
                    target_args = list(shell_info["default_args"])
                    target_name = shell_info["default_name"]
                    local_echo = True
                continue
            elif choice in ("3", "ECHO"):
                local_echo = not local_echo
                continue
            elif choice in ("4", "CRLF", "TRANSLATE"):
                crlf_mode = not crlf_mode
                continue
            elif choice in ("5", "CUSTOM", "CMD"):
                write(ser, "\r\nEnter custom command or shell (Q to cancel): ")
                custom_cmd = read_input_line(ser).strip()
                if custom_cmd and custom_cmd.upper() != "Q":
                    c_parts = custom_cmd.split()
                    c_app = c_parts[0]
                    c_args = c_parts[1:]
                    run_interactive_app(
                        c_app,
                        c_args,
                        local_echo=local_echo,
                        crlf_mode=crlf_mode,
                        work_dir=current_workdir,
                    )
                    break
                continue
            elif choice.upper() in ("Q", "QUIT", "EXIT", "MENU", "0"):
                break

    def run_print_menu():
        while True:
            write(ser, "\r\n--- HOST PRINTING ---\r\n")
            write(ser, "[1] Print Text Message\r\n")
            write(ser, "[2] Print File from Disk\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                write(ser, "\r\nText to print on host printer (Q to cancel): ")
                txt = read_input_line(ser).strip()
                if txt and txt.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"print {txt}")
                        write(ser, f"\r\n{res}\r\n")
                    except Exception as exc:
                        write(ser, f"Print error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "2":
                write(ser, "\r\nPath of file to print (Q to cancel): ")
                fpath = read_input_line(ser).strip()
                if fpath and fpath.upper() != "Q":
                    try:
                        clean_path = fpath.strip("'\"")
                        res = retro_shell.execute(f'print "{clean_path}"')
                        write(ser, f"\r\n{res}\r\n")
                    except Exception as exc:
                        write(ser, f"Print error: {exc}\r\n")
                    wait_for_key(ser)

    def run_connected_terminals_menu():
        while True:
            with ACTIVE_TERMINALS_LOCK:
                terminals = sorted(
                    list(ACTIVE_TERMINALS),
                    key=lambda term: str(getattr(term, "_terminal_name", getattr(term, "_profile_name", "Terminal"))).casefold(),
                )
            write(ser, "\r\n--- CONNECTED TERMINALS ---\r\n")
            if not terminals:
                write(ser, "No terminals are connected.\r\n")
                wait_for_key(ser)
                return
            for index, terminal in enumerate(terminals, 1):
                label = getattr(terminal, "_terminal_name", getattr(terminal, "_profile_name", "Terminal"))
                write(ser, f"[{index}] {label}\r\n")
            write(ser, "\r\nSelect a terminal number, R=Refresh, Q=Return: ")
            choice = read_input_line(ser).strip().upper()
            if choice in ("", "Q", "QUIT", "EXIT"):
                return
            if choice in ("R", "REFRESH"):
                continue
            try:
                index = int(choice) - 1
                target = terminals[index]
            except (ValueError, IndexError):
                write(ser, "Invalid terminal selection.\r\n")
                continue

            target_name = getattr(target, "_terminal_name", getattr(target, "_profile_name", "Terminal"))
            sender_name = getattr(ser, "_profile_name", name)
            write(ser, f"\r\n{target_name}\r\n[M] Send message  [F] Send file  [R] Return\r\nChoice: ")
            action = read_input_line(ser).strip().upper()
            if action in ("R", "RETURN", "Q"):
                continue
            if action in ("M", "MESSAGE"):
                write(ser, "Message (Q to cancel): ")
                message = read_input_line(ser).strip()
                if message and message.upper() != "Q":
                    try:
                        write(target, f"\r\n*** [MESSAGE from {sender_name}] {message} ***\r\n")
                        write(ser, f"Message sent to {target_name}.\r\n")
                    except Exception as exc:
                        write(ser, f"Message failed: {exc}\r\n")
                continue
            if action in ("F", "FILE"):
                write(ser, "File path or file name from files/ (Q to cancel): ")
                raw_path = read_input_line(ser).strip().strip("'\"")
                if not raw_path or raw_path.upper() == "Q":
                    continue
                file_path = pathlib.Path(raw_path).expanduser()
                if not file_path.is_absolute():
                    file_path = FILES_DIR / file_path
                if not file_path.is_file():
                    write(ser, f"File not found: {file_path}\r\n")
                    wait_for_key(ser)
                    continue
                try:
                    fm = importlib.import_module("rsh_files")
                    write(target, f"\r\n*** Incoming text file from {sender_name}: {file_path.name} ***\r\n")
                    fm.ascii_send(target, str(file_path))
                    write(ser, f"\r\nSent {file_path.name} to {target_name} as ASCII text.\r\n")
                except Exception as exc:
                    write(ser, f"File delivery failed: {exc}\r\n")
                wait_for_key(ser)
                continue
            write(ser, "Choose M, F, or R.\r\n")

    def run_ascii_viewer_menu():
        while True:
            write(ser, "\r\n--- ASCII IMAGE VIEWER ---\r\n")
            write(ser, "Preview images as terminal ASCII art\r\n")
            write(ser, "[1] Browse Files Directory for Images\r\n")
            write(ser, "[2] Enter Image Path Directly\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                img_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
                images = []
                if FILES_DIR.exists() and FILES_DIR.is_dir():
                    for item in sorted(FILES_DIR.iterdir()):
                        if item.is_file() and item.suffix.lower() in img_exts:
                            images.append(item)
                if not images:
                    write(ser, "\r\nNo image files found in files/ directory.\r\n")
                    wait_for_key(ser)
                    continue
                write(ser, "\r\nAvailable Images:\r\n")
                for idx, img in enumerate(images, 1):
                    write(ser, f"[{idx}] {img.name}\r\n")
                write(ser, "Select image number (Q to cancel): ")
                sel = read_input_line(ser).strip()
                if not sel or sel.upper() == "Q":
                    continue
                try:
                    chosen = images[int(sel) - 1]
                    write(ser, f"\r\nRendering {chosen.name}...\r\n")
                    res = retro_shell.execute(f'ascii "{chosen}"')
                    render_shell_result(res)
                except (ValueError, IndexError):
                    write(ser, "Invalid image selection.\r\n")
                except Exception as exc:
                    write(ser, f"ASCII viewer error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "2":
                write(ser, "\r\nEnter image path (Q to cancel): ")
                ipath = read_input_line(ser).strip()
                if ipath and ipath.upper() != "Q":
                    try:
                        clean_ipath = ipath.strip("'\"")
                        res = retro_shell.execute(f'ascii "{clean_ipath}"')
                        render_shell_result(res)
                    except Exception as exc:
                        write(ser, f"ASCII viewer error: {exc}\r\n")
                    wait_for_key(ser)

    def run_scheduler_menu():
        sched = getattr(host_env, "scheduler", None)
        while True:
            write(ser, "\r\n--- TASK SCHEDULER ---\r\n")
            write(ser, "[1] List Scheduled Tasks\r\n")
            write(ser, "[2] Add New Scheduled Task\r\n")
            write(ser, "[3] Run Task Now\r\n")
            write(ser, "[4] Toggle Task (Enable/Disable)\r\n")
            write(ser, "[5] Delete Scheduled Task\r\n")
            write(ser, "[6] View Available Modules & Usage\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                write(ser, "\r\n")
                try:
                    res = retro_shell.execute("schedule list")
                    render_shell_result(res)
                except Exception as exc:
                    write(ser, f"Scheduler error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "2":
                write(ser, "\r\n--- ADD SCHEDULED TASK ---\r\n")
                write(ser, "Task Name (e.g. Morning News, Q to cancel): ")
                t_name = read_input_line(ser).strip()
                if not t_name or t_name.upper() == "Q":
                    continue
                write(ser, "Command (e.g. 'news : weather Austin : broadcast Good Morning', or 'help'): ")
                t_cmd = read_input_line(ser).strip()
                if not t_cmd or t_cmd.upper() == "Q":
                    continue
                if t_cmd.lower() in ("help", "modules"):
                    res = retro_shell.execute("schedule modules")
                    render_shell_result(res)
                    write(ser, "Enter command to schedule (chain with ' : '): ")
                    t_cmd = read_input_line(ser).strip()
                    if not t_cmd or t_cmd.upper() == "Q":
                        continue
                raw_segments = [c.strip() for c in re.split(r"\s+:\s+|\s*;\s*", t_cmd) if c.strip()]
                norm_segments = []
                for seg in raw_segments:
                    if seg.startswith(("http://", "https://")):
                        norm_segments.append(f"view {seg}")
                    else:
                        norm_segments.append(seg)
                t_cmd = " : ".join(norm_segments)
                write(ser, "Schedule Frequency:\r\n")
                write(ser, "  [1] Interval (every X minutes)\r\n")
                write(ser, "  [2] Hourly (every hour at specified minute)\r\n")
                write(ser, "  [3] Daily (every day at specified time)\r\n")
                write(ser, "  [4] Weekly (on day of week at specified time)\r\n")
                write(ser, "  [5] Monthly (on day of month at specified time)\r\n")
                write(ser, "Choice [1-5]: ")
                freq_choice = read_input_line(ser).strip()
                freq_map = {"1": "interval", "2": "hourly", "3": "daily", "4": "weekly", "5": "monthly"}
                freq = freq_map.get(freq_choice, "interval")
                interval_mins = 60
                run_time = "08:00"
                dow = None
                dom = None
                if freq == "interval":
                    write(ser, "Every how many minutes? [default 15]: ")
                    mins_str = read_input_line(ser).strip()
                    try:
                        interval_mins = int(mins_str) if mins_str else 15
                    except ValueError:
                        interval_mins = 15
                elif freq == "hourly":
                    write(ser, "At minute of each hour (0-59) [default 0]: ")
                    min_str = read_input_line(ser).strip()
                    run_time = f":{int(min_str):02d}" if min_str and min_str.isdigit() else ":00"
                elif freq == "daily":
                    write(ser, "Run time (HH:MM 24-hr) [default 08:00]: ")
                    t_str = read_input_line(ser).strip()
                    run_time = t_str if t_str else "08:00"
                elif freq == "weekly":
                    write(ser, "Day of week (mon/tue/wed/thu/fri/sat/sun) [default mon]: ")
                    dow_str = read_input_line(ser).strip().lower()
                    dow = dow_str if dow_str in ("mon", "tue", "wed", "thu", "fri", "sat", "sun") else "mon"
                    write(ser, "Run time (HH:MM 24-hr) [default 08:00]: ")
                    t_str = read_input_line(ser).strip()
                    run_time = t_str if t_str else "08:00"
                elif freq == "monthly":
                    write(ser, "Day of month (1-31) [default 1]: ")
                    dom_str = read_input_line(ser).strip()
                    try:
                        dom = int(dom_str) if dom_str else 1
                    except ValueError:
                        dom = 1
                    write(ser, "Run time (HH:MM 24-hr) [default 08:00]: ")
                    t_str = read_input_line(ser).strip()
                    run_time = t_str if t_str else "08:00"

                write(ser, "Broadcast output to all connected terminals? (Y/N) [default Y]: ")
                bcast_input = read_input_line(ser).strip().upper()
                bcast = False if bcast_input in ("N", "NO") else True

                try:
                    if sched:
                        task = sched.add_task(
                            name=t_name,
                            command=t_cmd,
                            frequency=freq,
                            interval_minutes=interval_mins,
                            run_time=run_time,
                            day_of_week=dow,
                            day_of_month=dom,
                            show_output=True,
                            broadcast=bcast,
                        )
                        write(ser, f"\r\nTask '{task['name']}' added! ID: {task['id']}, Next run: {task['next_run']}\r\n")
                    else:
                        write(ser, "\r\nScheduler service not initialized.\r\n")
                except Exception as exc:
                    write(ser, f"\r\nError adding task: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "3":
                write(ser, "\r\nTask ID to run immediately (Q to cancel): ")
                tid = read_input_line(ser).strip()
                if tid and tid.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"schedule run {tid}")
                        render_shell_result(res)
                    except Exception as exc:
                        write(ser, f"Error running task: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "4":
                write(ser, "\r\nTask ID to toggle enabled/disabled (Q to cancel): ")
                tid = read_input_line(ser).strip()
                if tid and tid.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"schedule toggle {tid}")
                        write(ser, f"\r\n{res}\r\n")
                    except Exception as exc:
                        write(ser, f"Error toggling task: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "5":
                write(ser, "\r\nTask ID to delete (Q to cancel): ")
                tid = read_input_line(ser).strip()
                if tid and tid.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"schedule delete {tid}")
                        write(ser, f"\r\n{res}\r\n")
                    except Exception as exc:
                        write(ser, f"Error deleting task: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "6":
                write(ser, "\r\n")
                try:
                    res = retro_shell.execute("schedule modules")
                    render_shell_result(res)
                    write(ser, "\r\nView detailed info for a module (name or Enter to skip): ")
                    mod_name = read_input_line(ser).strip()
                    if mod_name:
                        info_res = retro_shell.execute(f"schedule info {mod_name}")
                        render_shell_result(info_res)
                except Exception as exc:
                    write(ser, f"Error viewing modules: {exc}\r\n")
                wait_for_key(ser)

    def run_sysinfo_display(realtime=True, clear_on_update=True, interval=2.0, max_iterations=None):
        cols = terminal_columns(ser)
        if not realtime:
            try:
                res = retro_shell.execute("sysinfo")
                render_shell_result(res)
            except Exception as exc:
                write(ser, f"System info error: {exc}\r\n")
            write(ser, "\r\nPress any key to return...\r\n")
            wait_for_key(ser)
            return

        clear_active = clear_on_update
        rate = max(1.0, float(interval))
        paused = False
        iteration = 0

        while True:
            iteration += 1
            if clear_active:
                clear_screen(ser, use_ansi)
            else:
                write(ser, "\r\n")

            try:
                content = host_env.format_sysinfo(cols=cols)
            except Exception:
                try:
                    content = retro_shell.execute("sysinfo")
                except Exception as exc:
                    content = f"System info error: {exc}"

            for line in str(content).splitlines():
                write(ser, line + "\r\n")

            status_note = "PAUSED (Snapshot)" if paused else f"Live ({rate:g}s)"
            clr_note = "ON" if clear_active else "OFF"
            if cols == 40:
                write(ser, f"[{status_note}] Clr:{clr_note}\r\n")
                write(ser, "[Q]Exit [C]Clr [+/-]Rate [S]Pause\r\n")
            else:
                write(ser, f"\r\n--- [{status_note}]  Clear Screen: {clr_note}  |  Refresh Rate: {rate:g}s ---\r\n")
                write(ser, "Commands: [Q] Return  |  [C] Toggle Clear Screen  |  [+/-] Rate  |  [S] Pause/Resume  |  [Space] Refresh\r\n")

            if not hasattr(ser, "in_waiting") or (max_iterations is not None and iteration >= max_iterations):
                break

            start_t = time.time()
            while True:
                if ser.in_waiting:
                    raw = ser.read(1)
                    try:
                        ch = raw.decode(errors="ignore").upper()
                    except Exception:
                        ch = ""
                    if not ch and getattr(ser, "_eof", False):
                        return
                    if ch in ("Q", "\x1b", "\x03", "\x18"):
                        return
                    elif ch == "C":
                        clear_active = not clear_active
                        break
                    elif ch in ("+", "="):
                        rate = max(1.0, rate - 1.0)
                        break
                    elif ch in ("-", "_"):
                        rate = min(10.0, rate + 1.0)
                        break
                    elif ch in ("S", "P"):
                        paused = not paused
                        break
                    elif ch in (" ", "R"):
                        break

                if paused:
                    time.sleep(0.05)
                    continue

                if time.time() - start_t >= rate:
                    break
                time.sleep(0.05)

    def run_host_media_menu():
        while True:
            write(ser, "\r\n--- SYSTEM MONITOR & MEDIA ---\r\n")
            write(ser, "[1] Host System Monitor (Real-Time Live)\r\n")
            write(ser, "[2] View Host Clipboard\r\n")
            write(ser, "[3] Set Host Clipboard\r\n")
            write(ser, "[4] Media: Play / Pause\r\n")
            write(ser, "[5] Media: Next Track\r\n")
            write(ser, "[6] Media: Previous Track\r\n")
            write(ser, "[7] Media: Stop\r\n")
            write(ser, "[8] Volume Up\r\n")
            write(ser, "[9] Volume Down\r\n")
            write(ser, "[0] Volume Mute Toggle\r\n")
            write(ser, "[S] System Status Snapshot (Single View)\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT"):
                break
            elif choice in ("1", "LIVE", "MONITOR"):
                run_sysinfo_display(realtime=True)
            elif choice in ("S", "SNAP", "SNAPSHOT", "STATUS"):
                run_sysinfo_display(realtime=False)
            elif choice == "2":
                try:
                    res = retro_shell.execute("clip")
                    render_shell_result(res)
                except Exception as exc:
                    write(ser, f"Clipboard error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "3":
                write(ser, "\r\nEnter text to copy to host clipboard (Q to cancel): ")
                clip_text = read_input_line(ser).strip()
                if clip_text and clip_text.upper() != "Q":
                    try:
                        res = retro_shell.execute(f"clip {clip_text}")
                        write(ser, f"\r\n{res}\r\n")
                    except Exception as exc:
                        write(ser, f"Clipboard error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "4":
                res = retro_shell.execute("media play")
                write(ser, f"\r\n{res}\r\n")
                time.sleep(0.3)
            elif choice == "5":
                res = retro_shell.execute("media next")
                write(ser, f"\r\n{res}\r\n")
                time.sleep(0.3)
            elif choice == "6":
                res = retro_shell.execute("media prev")
                write(ser, f"\r\n{res}\r\n")
                time.sleep(0.3)
            elif choice == "7":
                res = retro_shell.execute("media stop")
                write(ser, f"\r\n{res}\r\n")
                time.sleep(0.3)
            elif choice == "8":
                res = retro_shell.execute("vol up")
                write(ser, f"\r\n{res}\r\n")
                time.sleep(0.3)
            elif choice == "9":
                res = retro_shell.execute("vol down")
                write(ser, f"\r\n{res}\r\n")
                time.sleep(0.3)
            elif choice == "0":
                res = retro_shell.execute("vol mute")
                write(ser, f"\r\n{res}\r\n")
                time.sleep(0.3)

    def run_weather_news_menu():
        def show_news_interactive(source, label):
            write(ser, f"\r\nFetching {label} headlines...\r\n")
            try:
                from retro_os.news import fetch_news_items, format_article
                items = fetch_news_items(source, count=6)
                if not items:
                    write(ser, f"No articles found for {label}.\r\n")
                    wait_for_key(ser)
                    return

                while True:
                    src_display = items[0].get("source", label)
                    lines = [f"--- {src_display} Headlines ---"]
                    for it in items:
                        lines.append(f"[{it['index']}] {it['title']}")
                    render_shell_result("\n".join(lines))

                    write(ser, f"\r\nEnter article number to read (1-{len(items)}), or Q to return: ")
                    art_choice = read_input_line(ser).strip().upper()
                    if not art_choice or art_choice in ("Q", "QUIT", "EXIT", "0"):
                        break
                    if art_choice.isdigit() and 1 <= int(art_choice) <= len(items):
                        item = items[int(art_choice) - 1]
                        art_display = format_article(item)
                        render_shell_result(art_display)

                        if item.get("link"):
                            write(ser, "[F] Fetch Full Webpage | [Q/Enter] Back to Headlines\r\nAction: ")
                            sub_choice = read_input_line(ser).strip().upper()
                            if sub_choice == "F":
                                write(ser, f"\r\nFetching full web article from {item['link']}...\r\n")
                                try:
                                    from retro_os.viewer import extract_text_from_url
                                    full_text = extract_text_from_url(item["link"])
                                    render_shell_result(full_text)
                                except Exception as exc:
                                    write(ser, f"\r\nCould not fetch full article: {exc}\r\n")
                                wait_for_key(ser)
                    else:
                        write(ser, f"\r\nInvalid choice. Please enter a number 1-{len(items)}.\r\n")
                        time.sleep(1)
            except Exception as exc:
                write(ser, f"News error: {exc}\r\n")
                wait_for_key(ser)

        while True:
            write(ser, "\r\n--- WEATHER & NEWS ---\r\n")
            write(ser, "[1] Morning / Desk Briefing\r\n")
            write(ser, "[2] Live Weather Forecast (Auto Location)\r\n")
            write(ser, "[3] Live Weather (Specify City / Zip)\r\n")
            write(ser, "[4] NPR News Headlines\r\n")
            write(ser, "[5] Hacker News Headlines\r\n")
            write(ser, "[6] BBC News Headlines\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                write(ser, "\r\nGenerating briefing...\r\n")
                try:
                    res = retro_shell.execute("briefing")
                    render_shell_result(res)
                    from retro_os.news import get_cached_news_items, format_article
                    items = get_cached_news_items()
                    if items:
                        write(ser, f"\r\nEnter article number to read (1-{len(items)}), or Enter to return: ")
                        art_choice = read_input_line(ser).strip().upper()
                        if art_choice.isdigit() and 1 <= int(art_choice) <= len(items):
                            item = items[int(art_choice) - 1]
                            art_display = format_article(item)
                            render_shell_result(art_display)
                            if item.get("link"):
                                write(ser, "[F] Fetch Full Webpage | [Q/Enter] Continue\r\nAction: ")
                                sub_choice = read_input_line(ser).strip().upper()
                                if sub_choice == "F":
                                    write(ser, f"\r\nFetching full web article from {item['link']}...\r\n")
                                    try:
                                        from retro_os.viewer import extract_text_from_url
                                        full_text = extract_text_from_url(item["link"])
                                        render_shell_result(full_text)
                                    except Exception as exc:
                                        write(ser, f"\r\nCould not fetch full article: {exc}\r\n")
                                    wait_for_key(ser)
                            else:
                                wait_for_key(ser)
                except Exception as exc:
                    write(ser, f"Briefing error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "2":
                write(ser, "\r\nFetching weather...\r\n")
                try:
                    res = retro_shell.execute("weather")
                    render_shell_result(res)
                except Exception as exc:
                    write(ser, f"Weather error: {exc}\r\n")
                wait_for_key(ser)
            elif choice == "3":
                write(ser, "\r\nEnter city or zip code (e.g. Austin, 90210, London; Q to cancel): ")
                loc = read_input_line(ser).strip()
                if loc and loc.upper() != "Q":
                    write(ser, f"\r\nFetching weather for {loc}...\r\n")
                    try:
                        res = retro_shell.execute(f"weather {loc}")
                        render_shell_result(res)
                    except Exception as exc:
                        write(ser, f"Weather error: {exc}\r\n")
                    wait_for_key(ser)
            elif choice == "4":
                show_news_interactive("npr", "NPR")
            elif choice == "5":
                show_news_interactive("hn", "Hacker News")
            elif choice == "6":
                show_news_interactive("bbc", "BBC")

    def run_terminal_settings_menu():
        nonlocal use_ansi
        while True:
            cur_cols = terminal_columns(ser)
            cur_caps = getattr(ser, "_rsh_caps_only", None) is True
            cur_pace = getattr(ser, "_rsh_pace_delay", 0.0)
            if not isinstance(cur_pace, (int, float)):
                cur_pace = 0.0
            cur_ansi = getattr(ser, "_rsh_translate_ansi", use_ansi)
            if not isinstance(cur_ansi, bool):
                cur_ansi = bool(use_ansi)
            pace_ms = int(cur_pace * 1000)

            write(ser, "\r\n--- TERMINAL HARDWARE SETTINGS ---\r\n")
            write(ser, f"Screen Width:    {cur_cols} columns\r\n")
            write(ser, f"Caps-Only Mode:  {'ON (Apple II / PET)' if cur_caps else 'OFF (Standard ASCII)'}\r\n")
            write(ser, f"Serial Pacing:   {pace_ms} ms/char ({'None' if pace_ms == 0 else 'Throttled'})\r\n")
            write(ser, f"ANSI Code Strip: {'ON (Filter color codes)' if cur_ansi else 'OFF (Pass-through)'}\r\n")
            write(ser, "----------------------------------\r\n")
            write(ser, "[1] Toggle Screen Width (40 / 80 cols)\r\n")
            write(ser, "[2] Toggle Caps-Only Mode (Uppercase)\r\n")
            write(ser, "[3] Adjust Serial Pacing Delay\r\n")
            write(ser, "[4] Toggle ANSI Code Filter\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                break
            elif choice == "1":
                new_cols = 40 if cur_cols == 80 else 80
                try:
                    with COLUMN_PREFERENCES_LOCK:
                        save_column_preference(
                            COLUMN_SETTINGS_FILE,
                            COLUMN_PREFERENCES,
                            name,
                            new_cols,
                        )
                except Exception:
                    pass
                if name in SERIAL_CONFIGS:
                    SERIAL_CONFIGS[name]["columns"] = new_cols
                ser._rsh_columns = new_cols
                retro_session.cols = new_cols
                if inbound_translator:
                    inbound_translator.columns = new_cols
                write(ser, f"\r\nTerminal width set to {new_cols} columns.\r\n")
                wait_for_key(ser)
            elif choice == "2":
                new_caps = not cur_caps
                ser._rsh_caps_only = new_caps
                retro_session.caps_only = new_caps
                write(ser, f"\r\nCaps-Only mode set to {'ON' if new_caps else 'OFF'}.\r\n")
                wait_for_key(ser)
            elif choice == "3":
                write(ser, f"\r\nCurrent pacing: {pace_ms} ms/char.\r\n")
                write(ser, "Pacing adds a slight delay after each character to prevent buffer overruns on vintage UARTs.\r\n")
                write(ser, "Enter delay in milliseconds (0=off, 2=low, 5=medium, Q to cancel): ")
                p_str = read_input_line(ser).strip()
                if p_str and p_str.upper() != "Q":
                    try:
                        ms = max(0.0, float(p_str))
                        sec = ms / 1000.0
                        ser._rsh_pace_delay = sec
                        retro_session.pace_delay = sec
                        write(ser, f"Pacing set to {int(ms)} ms/character.\r\n")
                    except ValueError:
                        write(ser, "Invalid pacing delay.\r\n")
                    wait_for_key(ser)
            elif choice == "4":
                new_ansi = not cur_ansi
                try:
                    with ANSI_TRANSLATION_PREFERENCES_LOCK:
                        save_ansi_translation_preference(
                            ANSI_TRANSLATION_SETTINGS_FILE,
                            ANSI_TRANSLATION_PREFERENCES,
                            name,
                            new_ansi,
                        )
                except Exception:
                    pass
                if name in SERIAL_CONFIGS:
                    SERIAL_CONFIGS[name]["translate_ansi"] = new_ansi
                ser._rsh_translate_ansi = new_ansi
                use_ansi = new_ansi
                write(ser, f"\r\nANSI translation set to {'ON' if new_ansi else 'OFF'}.\r\n")
                wait_for_key(ser)

    def run_host_settings_menu():
        global HOST_SETTINGS
        while True:
            with HOST_SETTINGS_LOCK:
                current_binding = HOST_SETTINGS["keyboard_exit_binding"]
            write(ser, "\r\n--- HOST SETTINGS ---\r\n")
            write(ser, f"Keyboard Bridge Exit Binding: {current_binding}\r\n")
            write(ser, "[1] Change Exit Binding (Ctrl+A through Ctrl+Z)\r\n")
            write(ser, "[2] Restore Default (Ctrl+X)\r\n")
            write(ser, "[Q] Return to Main Menu\r\n")
            write(ser, "Choice: ")
            choice = read_input_line(ser).strip().upper()
            if not choice or choice in ("Q", "QUIT", "EXIT", "0"):
                return
            if choice == "1":
                write(ser, "Enter exit binding (CTRL+A through CTRL+Z, Q to cancel): ")
                binding = read_input_line(ser).strip().upper()
                if binding == "Q":
                    continue
            elif choice == "2":
                binding = "CTRL+X"
            else:
                continue

            try:
                with HOST_SETTINGS_LOCK:
                    updated_settings = dict(HOST_SETTINGS)
                    updated_settings["keyboard_exit_binding"] = binding
                    HOST_SETTINGS = save_host_settings(HOST_SETTINGS_FILE, updated_settings)
                write(ser, f"\r\nKeyboard Bridge exit binding set to {binding}.\r\n")
            except (OSError, ValueError) as exc:
                write(ser, f"\r\nCould not update Host Settings: {exc}\r\n")
            wait_for_key(ser)

    def handle_shell_action(requested_module):
        nonlocal mode, tcp_sock, use_ansi
        if isinstance(requested_module, tuple):
            act = requested_module[0]
            if act in ("bbs_connect", "telnet_connect"):
                connect_type, host, port = requested_module
                write(ser, f"\r\nConnecting to {host}:{port}...\r\n")
                tcp_sock = connect_host(host, int(port), ser)
                if tcp_sock:
                    mode = "BBS" if connect_type == "bbs_connect" else "TELNET"
                    if inbound_translator:
                        inbound_translator.reset()
                    return True
                else:
                    write(ser, f"Failed to connect to {host}:{port}.\r\n")
                    return False
            elif act in ("app_interactive", "host_terminal"):
                _, target, app_args = requested_module
                echo_opt = False if "powershell" in str(target).lower() else True
                run_interactive_app(target, app_args, local_echo=echo_opt)
                return False
            elif act == "app_keyboard":
                _, target, app_args = requested_module
                launch_with_keyboard_bridge(target, app_args)
                return False
            elif act == "file_transfer":
                _, transfer_action, fname = requested_module
                try:
                    importlib.invalidate_caches()
                    fm = importlib.import_module("rsh_files")
                    importlib.reload(fm)
                    fpath = pathlib.Path(fname)
                    if not fpath.is_absolute():
                        fpath = FILES_DIR / fname
                    if transfer_action == "XMODEM_SEND":
                        if not fpath.exists():
                            write(ser, f"\r\nFile not found: {fpath}\r\n")
                        else:
                            fm.xmodem_send(ser, str(fpath), fpath.name)
                    elif transfer_action == "YMODEM_SEND":
                        if not fpath.exists():
                            write(ser, f"\r\nFile not found: {fpath}\r\n")
                        else:
                            fm.ymodem_send(ser, str(fpath))
                    elif transfer_action == "ASCII_SEND":
                        if not fpath.exists():
                            write(ser, f"\r\nFile not found: {fpath}\r\n")
                        else:
                            fm.ascii_send(ser, str(fpath))
                    elif transfer_action == "XMODEM_RECV":
                        dest = FILES_DIR / fpath.name
                        fm.xmodem_receive(ser, str(dest))
                except Exception as exc:
                    write(ser, f"\r\nFile transfer error: {exc}\r\n")
                return False
            elif act == "set_caps":
                ser._rsh_caps_only = requested_module[1]
                retro_session.caps_only = requested_module[1]
                return False
            elif act == "set_pace":
                ser._rsh_pace_delay = requested_module[1]
                retro_session.pace_delay = requested_module[1]
                return False
            elif act == "set_columns":
                new_cols = requested_module[1]
                try:
                    with COLUMN_PREFERENCES_LOCK:
                        save_column_preference(
                            COLUMN_SETTINGS_FILE,
                            COLUMN_PREFERENCES,
                            name,
                            new_cols,
                        )
                except Exception:
                    pass
                if name in SERIAL_CONFIGS:
                    SERIAL_CONFIGS[name]["columns"] = new_cols
                ser._rsh_columns = new_cols
                retro_session.cols = new_cols
                if inbound_translator:
                    inbound_translator.columns = new_cols
                return False
            elif act == "set_ansi":
                new_ansi = requested_module[1]
                try:
                    with ANSI_TRANSLATION_PREFERENCES_LOCK:
                        save_ansi_translation_preference(
                            ANSI_TRANSLATION_SETTINGS_FILE,
                            ANSI_TRANSLATION_PREFERENCES,
                            name,
                            new_ansi,
                        )
                except Exception:
                    pass
                if name in SERIAL_CONFIGS:
                    SERIAL_CONFIGS[name]["translate_ansi"] = new_ansi
                ser._rsh_translate_ansi = new_ansi
                use_ansi = new_ansi
                return False
            elif act == "sysinfo_live":
                run_sysinfo_display(realtime=True)
                return False
        return None
    # dynamic module handles (loaded on demand)
    wargames_module = None
    wargames_session = None
    # BBS module handles
    bbs_module = None
    bbs_session = None
    telnet_module = None
    telnet_session = None
    ftp_module = None
    ftp_session = None
    # AI module handles
    ai_module = None
    ai_session = None
    # Bridge runtime session (created when COM bridge opens)
    bridge_session = None
    # Text module handles
    text_module = None
    text_session = None
    # Browser module handles
    browser_module = None
    browser_session = None
    keyboard_bridge = None
    # Notes module handles
    notes_module = None
    notes_session = None
    note_buffer = []
    pending_delete = None
    # buffer to assemble a single input line while connected to a remote BBS
    bbs_line_buffer = b""
    inbound_translator = (
        AnsiToTextTranslator(
            clear_sequence=ansi_clear_sequence,
            columns=terminal_columns(ser),
            clear_on_home=ansi_home_clears_screen,
        )
        if translate_ansi else None
    )

    # Pre-compute files lists
    notes_list = sorted([p.name for p in NOTES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
    text_list  = sorted([p.name for p in TEXT_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])

    def refresh_notes_session(notice=None):
        nonlocal notes_list, notes_session
        notes_list = sorted(
            p.name
            for p in NOTES_DIR.iterdir()
            if p.is_file() and p.suffix.lower() == ".txt"
        )
        notes_session = notes_module.create_session(
            ser,
            use_ansi,
            notes=notes_list,
            base_dir=NOTES_DIR,
            notice=notice,
        )

    # dynamic module handles for menus loaded on demand
    wargames_module = None
    wargames_session = None
    files_module = None
    files_session = None

    def run_add_shortcut_flow():
        write(ser, "\r\n--- ADD SHORTCUT ---\r\n")
        write(ser, "Enter a short label/name (Q to cancel): ")
        name = read_input_line(ser).strip()
        if not name or name.upper() in ("Q", "QUIT", "CANCEL"):
            write(ser, "Cancelled.\r\n")
            wait_for_key(ser)
            return
        write(ser, "\r\nEnter command and arguments.\r\n")
        write(ser, "Examples: 'view https://news.ycombinator.com', 'calc 50*12',\r\n")
        write(ser, "          'games mines 9 9 10', 'mail inbox', 'launch notepad.exe'\r\n")
        write(ser, "Command: ")
        cmd = read_input_line(ser).strip()
        if not cmd or cmd.upper() in ("Q", "QUIT", "CANCEL"):
            write(ser, "Cancelled.\r\n")
            wait_for_key(ser)
            return
        sc = shortcuts_mgr.add_shortcut(name, cmd)
        write(ser, f"\r\nShortcut '{sc['name']}' added!\r\n")
        wait_for_key(ser)

    def run_remove_shortcut_flow():
        write(ser, "\r\n--- REMOVE SHORTCUT ---\r\n")
        shortcuts = shortcuts_mgr.list_shortcuts()
        if not shortcuts:
            write(ser, "No shortcuts configured to remove.\r\n")
            wait_for_key(ser)
            return
        for idx, sc in enumerate(shortcuts):
            letter = chr(ord("A") + idx)
            write(ser, f"[{letter}] {sc['name']}: {sc['command']}\r\n")
        write(ser, "\r\nEnter letter or number to remove (Q to cancel): ")
        choice = read_input_line(ser).strip().upper()
        if not choice or choice in ("Q", "QUIT", "CANCEL"):
            write(ser, "Cancelled.\r\n")
            wait_for_key(ser)
            return
        if shortcuts_mgr.delete_shortcut(choice):
            write(ser, "Shortcut removed.\r\n")
        else:
            write(ser, "Shortcut not found.\r\n")
        wait_for_key(ser)

    def return_to_connection_menu():
        nonlocal mode, bbs_session
        try:
            if mode == "TELNET" and telnet_module and telnet_session:
                telnet_module.show_menu(ser, telnet_session, use_ansi)
            elif bbs_module:
                bbs_session = bbs_module.create_session(
                    ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS
                )
            else:
                show_bbs_menu(ser, use_ansi)
        except Exception as exc:
            write(ser, f"\r\n*** Could not display connection menu: {exc} ***\r\n")
            mode = "MENU"
            show_main_menu(ser, use_ansi)

    if getattr(ser, "_rsh_host_console", False) is True:
        mode = "CLI"
        retro_session.active_module = "shell"
        set_terminal_activity(ser, "cli", user_label="Host")
        write(ser, "\r\nHost Retro Serial Hub CLI. Type help for commands or ATM for menus.\r\ncli> ")
    else:
        show_main_menu(ser, use_ansi)

    while True:
        # serial, network, or local host input
        if getattr(ser, "_rsh_host_console", False) is True:
            ser.secret_input = mode == "FTP" and ftp_session is not None and ftp_session.get("submode") == "PASSWORD"
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            if not data and isinstance(ser, SocketTerminal):
                console_log(f"{name}: remote terminal disconnected.", level="yellow")
                retro_session.state = "disconnected"
                event_bus.publish("session.disconnected", retro_session)
                return

            if data:
                first_input = not getattr(ser, "_rsh_input_seen", False)
                ser._rsh_input_seen = True
                if first_input and CONSOLE and not isinstance(ser, SocketTerminal):
                    CONSOLE.update_profile(name, terminal="ACTIVE")
                if first_input and mode == "MENU":
                    if not isinstance(ser, SocketTerminal) and isinstance(calendar_tool, CalendarTool):
                        try:
                            ser._rsh_reminder_notice = calendar_tool.connection_reminders()
                        except (OSError, ValueError, KeyError):
                            pass
                    flyout = getattr(ser, "_rsh_flyout_menu", None)
                    section = getattr(flyout, "active_section_idx", 0)
                    set_terminal_activity(
                        ser, f"section:{section + 1}", default_name=name
                    )

            if mode == "KEYBOARD":
                try:
                    keyboard_bridge._shortcut_mappings = shortcut_mappings
                    keyboard_bridge._on_shortcut = publish_shortcut
                    if keyboard_bridge.feed(data):
                        keyboard_bridge = None
                        mode = "MENU"
                        write(ser, "\r\nKeyboard Bridge closed.\r\n")
                        show_main_menu(ser, use_ansi)
                except Exception as e:
                    keyboard_bridge = None
                    mode = "MENU"
                    write(ser, f"\r\n*** Keyboard Bridge error: {e} ***\r\n")
                    show_main_menu(ser, use_ansi)
                continue

            # Echo in command-mode only (i.e., not while transparent BBS session)
            suppress_ftp_password_echo = (
                mode == "FTP"
                and ftp_session is not None
                and ftp_session.get("submode") == "PASSWORD"
            )
            if (
                (mode not in ("BBS", "TELNET") or not tcp_sock)
                and not suppress_ftp_password_echo
            ):
                echoed_data = data.replace(b"\x08", b"\x08 \x08")
                echoed_data = echoed_data.replace(b"\x7f", b"\x08 \x08")
                ser.write(echoed_data)

            # If we're in COMBRIDGE, delegate raw bytes to the bridge module so
            # it can forward characters immediately (per-character live mode).
            try:
                if mode == "COMBRIDGE" and bridge_module and bridge_session is not None:
                    try:
                        handled = False
                        if hasattr(bridge_module, 'handle_raw_input'):
                            handled = bridge_module.handle_raw_input(bridge_session, data)
                        # If module reports failure, close the bridge and return to menu
                        if not handled:
                            write(ser, "\r\n*** COM bridge write failed ***\r\n")
                            try:
                                # attempt to let module clean up; if not, try to close underlying serial
                                bs = bridge_session.get('bridge_serial') if isinstance(bridge_session, dict) else None
                                if bs:
                                    try:
                                        bs.close()
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            bridge_session = None
                            mode = "MENU"
                            show_main_menu(ser, use_ansi)
                    except Exception as e:
                        write(ser, f"\r\n*** Bridge module error: {e} ***\r\n")
                        wait_for_key(ser)
                        bridge_session = None
                        mode = "MENU"
                        show_main_menu(ser, use_ansi)
                    # raw bytes handled by bridge module; skip menu parsing for these bytes
                    continue
            except Exception:
                pass

            # Forward raw input while connected to a BBS or direct Telnet host.
            # to the TCP socket and assemble a small line buffer so we can still
            # detect an 'ATH' hangup when the user presses Enter.
            if mode in ("BBS", "TELNET") and tcp_sock:
                try:
                    tcp_sock.sendall(data)
                except Exception:
                    write(ser, "\r\n*** Connection to remote lost ***\r\n")
                    try:
                        tcp_sock.close()
                    except Exception:
                        pass
                    tcp_sock = None
                    tcp_sock = None
                    return_to_connection_menu()
                    continue

                # Accumulate characters until a CR/LF so we can detect local ATH hangup.
                for byte in data:
                    if byte in (10, 13):  # LF or CR
                        if bbs_line_buffer:
                            try:
                                s = bbs_line_buffer.decode(errors='ignore').strip().upper()
                            except Exception:
                                s = ""
                            if s == 'ATH':
                                # local hangup request
                                write(ser, "\r\nDisconnecting...\r\n")
                                try:
                                    tcp_sock.close()
                                except Exception:
                                    pass
                                tcp_sock = None
                                return_to_connection_menu()
                                bbs_line_buffer = b""
                                break
                            bbs_line_buffer = b""
                        else:
                            # ignore stray CR/LF
                            pass
                    else:
                        bbs_line_buffer += bytes((byte,))
                # We've forwarded the bytes and handled any ATH; do not run menu parsing on them
                continue

            # otherwise normal command-mode buffering
            input_buffer = update_command_input(input_buffer, data)

            # parse lines
            while b"\r" in input_buffer or b"\n" in input_buffer:
                for sep in (b"\r", b"\n"):
                    if sep in input_buffer:
                        raw_line, _, rest = input_buffer.partition(sep)
                        input_buffer = rest.lstrip(b"\r\n")
                        break
                else:
                    break

                line_str = raw_line.decode(errors='ignore').strip()
                upper = line_str.upper()

                # Global ATM: return to menu, drop any BBS connection
                if upper == "ATM":
                    if tcp_sock:
                        write(ser, "\r\nDisconnecting...\r\n")
                        tcp_sock.close()
                        tcp_sock = None
                    if mode == "FTP" and ftp_module and ftp_session:
                        ftp_module.close_session(ftp_session)
                    # If a COM bridge is active, close it too (ask module or close underlying serial)
                    if bridge_session:
                        try:
                            if bridge_module and hasattr(bridge_module, 'close_bridge_session'):
                                try:
                                    bridge_module.close_bridge_session(bridge_session)
                                except Exception:
                                    pass
                            else:
                                bs = bridge_session.get('bridge_serial') if isinstance(bridge_session, dict) else None
                                if bs:
                                    try:
                                        bs.close()
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        bridge_session = None
                    # If our own serial was surrendered, stop processing and exit
                    if ser.port and ser.port.upper() in SURRENDERED_PORTS:
                        write(ser, "\r\nThis session's COM port was surrendered to a bridge. Exiting session.\r\n")
                        try:
                            ser.close()
                        except Exception:
                            pass
                        return
                    mode = "MENU"
                    retro_session.active_module = None
                    show_main_menu(ser, use_ansi)
                    continue

                menu_action = None
                if mode == "MENU" and upper in ("CLI", "SHELL", "OS"):
                    mode = "CLI"
                    retro_session.cols = terminal_columns(ser)
                    retro_session.active_module = "shell"
                    set_terminal_activity(ser, "cli", default_name=name)
                    write(ser, "\r\nRetro Serial Hub CLI. Type 'help' for commands, 'exit' for menu.\r\ncli> ")
                    continue

                if mode in ("SHELL", "CLI"):
                    write(ser, "\r\n")
                    if upper in ("EXIT", "QUIT", "MENU"):
                        mode = "MENU"
                        retro_session.active_module = None
                        show_main_menu(ser, use_ansi)
                        continue
                    if line_str:
                        try:
                            response = retro_shell.execute(line_str)
                        except Exception as exc:
                            response = f"Command failed: {exc}"
                        if response:
                            render_shell_result(response)
                    if shell_requested_module:
                        requested_module = shell_requested_module.pop()
                        handled = handle_shell_action(requested_module)
                        if handled:
                            continue
                        elif handled is False:
                            write(ser, "cli> ")
                            continue
                        else:
                            retro_session.active_module = requested_module
                            mode = "MENU"
                            menu_action = requested_module
                    else:
                        write(ser, "cli> ")
                        continue

                if (
                    mode == "MENU"
                    and upper == "15"
                    and isinstance(ser, SocketTerminal)
                ):
                    write(ser, "\r\nDisconnecting from Retro Serial Hub.\r\n")
                    retro_session.state = "disconnected"
                    event_bus.publish("session.disconnected", retro_session)
                    return

                if mode == "WELCOME_BANNER":
                    global WELCOME_BANNER
                    if not line_str:
                        try:
                            reset_banner(WELCOME_BANNER_FILE)
                        except OSError as exc:
                            write(ser, f"\r\n*** Could not reset banner: {exc} ***\r\n")
                        else:
                            WELCOME_BANNER = CONFIG_WELCOME_BANNER
                            write(ser, "\r\nWelcome banner reset to config.py value.\r\n")
                    else:
                        try:
                            new_banner = validate_banner(line_str)
                            save_banner(WELCOME_BANNER_FILE, new_banner)
                        except (OSError, ValueError) as exc:
                            write(ser, f"\r\n*** Could not change banner: {exc} ***\r\n")
                            write(ser, "Enter a banner (1-80 printable ASCII characters): ")
                            continue
                        WELCOME_BANNER = new_banner
                        write(ser, "\r\nWelcome banner saved.\r\n")
                    mode = "MENU"
                    show_main_menu(ser, use_ansi)
                    continue

                if mode == "MENU":
                    if menu_action is None:
                        if not line_str:
                            show_main_menu(ser, use_ansi)
                            continue

                        if getattr(ser, "_rsh_menu_style", "flyout") != "legacy":
                            flyout = getattr(ser, "_rsh_flyout_menu", None)
                            if flyout is None:
                                from retro_os.menu import OSFlyoutMenu
                                ser._rsh_flyout_menu = OSFlyoutMenu(shortcuts_manager=shortcuts_mgr)
                                flyout = ser._rsh_flyout_menu

                            # Check section switch (0-5 or section name)
                            if flyout.select_section(upper):
                                show_main_menu(ser, use_ansi, auto_flyout=False)
                                continue

                            # Check item key (A-F, +) in active section
                            menu_action = flyout.get_action_for_key(
                                upper, is_remote=isinstance(ser, SocketTerminal)
                            )

                        # Direct command strings
                        if menu_action is None:
                            if HUB_TOOL_ALIASES.get(upper.split()[0]):
                                menu_action = HUB_TOOL_ALIASES[upper.split()[0]]
                            elif upper in ("CLI", "SHELL", "OS"):
                                menu_action = "cli"
                            elif upper in ("SHORTCUT", "SHORTCUTS") or upper.startswith("SHORTCUT ") or upper.startswith("SHORTCUTS "):
                                if upper in ("SHORTCUT", "SHORTCUTS"):
                                    flyout = getattr(ser, "_rsh_flyout_menu", None)
                                    if flyout:
                                        flyout.select_section("0")
                                        show_main_menu(ser, use_ansi, auto_flyout=False)
                                        continue
                                else:
                                    try:
                                        response = retro_shell.execute(line_str)
                                        render_shell_result(response)
                                    except Exception as exc:
                                        write(ser, f"Shortcut error: {exc}\r\n")
                                    wait_for_key(ser)
                                    show_main_menu(ser, use_ansi)
                                    continue
                            elif upper in ("+", "ADD"):
                                menu_action = "shortcut_add"
                            elif upper in ("-", "DEL", "DELETE"):
                                menu_action = "shortcut_del"
                            elif upper in ("BBS", "BOARDS"):
                                menu_action = "bbs"
                            elif upper in ("BROWSER", "WEB"):
                                menu_action = "browser"
                            elif upper in ("TELNET",):
                                menu_action = "telnet"
                            elif upper in ("TERMINALS", "CONNECTED TERMINALS"):
                                menu_action = "terminals"
                            elif upper in ("NOTES", "NOTE"):
                                menu_action = "notes"
                            elif upper in ("CALC", "CALCULATOR") or upper.startswith("CALC "):
                                menu_action = "calc"
                            elif upper == "LOGO":
                                menu_action = "logo"
                            elif upper in ("MAIL", "EMAIL") or upper.startswith("MAIL "):
                                menu_action = "mail"
                            elif upper in ("APPS", "APPLICATIONS") or upper.startswith("APPS "):
                                menu_action = "apps"
                            elif upper == "LAUNCH" or upper.startswith("LAUNCH "):
                                menu_action = "launch"
                            elif upper in ("TERMINAL", "CMD", "PROMPT", "HOSTCMD", "HOSTSH") or upper.startswith("TERMINAL ") or upper.startswith("CMD ") or upper.startswith("HOSTCMD ") or upper.startswith("HOSTSH "):
                                menu_action = "host_terminal"
                            elif upper in ("KEYBOARD",):
                                menu_action = "keyboard"
                            elif upper in ("KB",) or upper.startswith("KB "):
                                menu_action = "kb"
                            elif upper in ("COMBRIDGE", "BRIDGE", "COM"):
                                menu_action = "com_bridge"
                            elif upper in ("FILES", "FILE"):
                                menu_action = "files"
                            elif upper in ("TEXT", "TEXTLIB", "LIBRARY"):
                                menu_action = "text"
                            elif upper == "VIEW" or upper.startswith("VIEW "):
                                menu_action = "view"
                            elif upper in ("FTP",):
                                menu_action = "ftp"
                            elif upper in ("AI", "CHAT"):
                                menu_action = "ai"
                            elif upper in ("MINES", "MINESWEEPER") or upper.startswith("MINES "):
                                menu_action = "mines"
                            elif upper in ("SOLITAIRE", "SOL") or upper.startswith("SOLITAIRE ") or upper.startswith("SOL "):
                                menu_action = "solitaire"
                            elif upper in ("GAMES", "GAME"):
                                menu_action = "games"
                            elif upper in ("WORD", "WORDGUESS", "WORDLE"):
                                menu_action = "wordguess"
                            elif upper in ("TREK", "STAR TREK", "STARTREK"):
                                menu_action = "trek"
                            elif upper in ("HELP", "MAN", "GUIDE", "?") or upper.startswith("HELP "):
                                menu_action = "help_menu"
                            elif upper in ("MAILTO",) or upper.startswith("MAILTO "):
                                menu_action = "mailto"
                            elif upper in ("ASCII", "ASCII_VIEWER"):
                                menu_action = "ascii_viewer"
                            elif upper in ("PRINT", "PRINTER"):
                                menu_action = "print"
                            elif upper in ("SYS", "SYSINFO", "TOP") or upper.startswith("SYSINFO "):
                                menu_action = "sysinfo"
                            elif upper in ("CLIP", "PASTE", "COPY", "MEDIA", "VOL", "VOLUME") or upper.startswith("CLIP ") or upper.startswith("COPY ") or upper.startswith("MEDIA ") or upper.startswith("VOL "):
                                menu_action = "host_media"
                            elif upper in ("WEATHER", "NEWS", "BRIEFING") or upper.startswith("WEATHER ") or upper.startswith("NEWS ") or upper.startswith("BRIEFING "):
                                menu_action = "weather_news"
                            elif upper in ("TERMINAL_SETTINGS", "SETTINGS", "CAPS", "PACE") or upper.startswith("CAPS ") or upper.startswith("PACE "):
                                menu_action = "terminal_settings"
                            elif upper in ("HOST_SETTINGS", "HOST SETTINGS"):
                                menu_action = "host_settings"
                            elif upper.startswith("XSEND ") or upper.startswith("YSEND ") or upper.startswith("ASEND ") or upper.startswith("XRECV ") or upper == "XRECV":
                                menu_action = "direct_transfer"
                            elif upper in ("SCHEDULE", "SCHEDULER", "TASKS", "CRON") or upper.startswith("SCHEDULE ") or upper.startswith("SCHEDULER "):
                                menu_action = "scheduler"
                            elif upper in ("FETCH", "DOWNLOAD") or upper.startswith("FETCH ") or upper.startswith("DOWNLOAD "):
                                menu_action = "fetch"
                            elif upper in ("WARGAMES",):
                                menu_action = "wargames"
                            elif upper in ("WUMPUS", "HUNT"):
                                menu_action = "wumpus"
                            elif upper in ("COLUMNS", "WIDTH"):
                                menu_action = "columns"
                            elif upper in ("ANSI",):
                                menu_action = "translate_ansi"
                            elif upper in ("BANNER",):
                                menu_action = "welcome_banner"
                            elif upper in ("DISCONNECT", "QUIT", "15") and isinstance(ser, SocketTerminal):
                                menu_action = "disconnect"
                            else:
                                menu_action = MAIN_MENU_ACTIONS.get(upper)

                    if menu_action is not None:
                        set_terminal_activity(ser, menu_action, default_name=name)

                    if menu_action in HUB_TOOL_ALIASES.values():
                        parts = line_str.split(maxsplit=1) if line_str else []
                        if len(parts) > 1 and HUB_TOOL_ALIASES.get(parts[0].upper()) == menu_action:
                            render_shell_result(retro_shell.execute(line_str))
                            if shell_requested_module and handle_shell_action(shell_requested_module.pop()):
                                continue
                            wait_for_key(ser)
                        elif run_tool_menu(menu_action):
                            continue
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "columns":
                        new_columns = 40 if terminal_columns(ser) == 80 else 80
                        try:
                            with COLUMN_PREFERENCES_LOCK:
                                COLUMN_PREFERENCES = save_column_preference(
                                    COLUMN_SETTINGS_FILE,
                                    COLUMN_PREFERENCES,
                                    name,
                                    new_columns,
                                )
                            SERIAL_CONFIGS[name]["columns"] = new_columns
                            ser._rsh_columns = new_columns
                            retro_session.cols = new_columns
                            if inbound_translator:
                                inbound_translator.columns = new_columns
                        except (OSError, ValueError) as exc:
                            write(ser, f"\r\n*** Could not save display width: {exc} ***\r\n")
                            show_main_menu(ser, use_ansi)
                            continue
                        write(ser, f"\r\nTerminal width saved: {new_columns} columns.\r\n")
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "translate_ansi":
                        new_translate_ansi = not bool(
                            getattr(ser, "_rsh_translate_ansi", translate_ansi)
                        )
                        try:
                            with ANSI_TRANSLATION_PREFERENCES_LOCK:
                                ANSI_TRANSLATION_PREFERENCES = (
                                    save_ansi_translation_preference(
                                        ANSI_TRANSLATION_SETTINGS_FILE,
                                        ANSI_TRANSLATION_PREFERENCES,
                                        name,
                                        new_translate_ansi,
                                    )
                                )
                            SERIAL_CONFIGS[name]["translate_ansi"] = (
                                new_translate_ansi
                            )
                            ser._rsh_translate_ansi = new_translate_ansi
                            translate_ansi = new_translate_ansi
                            inbound_translator = (
                                AnsiToTextTranslator(
                                    clear_sequence=ansi_clear_sequence,
                                    columns=terminal_columns(ser),
                                    clear_on_home=ansi_home_clears_screen,
                                )
                                if new_translate_ansi
                                else None
                            )
                        except (OSError, ValueError) as exc:
                            write(
                                ser,
                                f"\r\n*** Could not save ANSI translation setting: {exc} ***\r\n",
                            )
                            show_main_menu(ser, use_ansi)
                            continue
                        state = "enabled" if new_translate_ansi else "disabled"
                        write(ser, f"\r\nANSI translation {state} for {name}.\r\n")
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "bbs":
                        # Load BBS module on demand so it can be edited without restarting the hub
                        try:
                            importlib.invalidate_caches()
                            bm = importlib.import_module('rsh_bbs')
                            importlib.reload(bm)
                            bbs_module = bm
                            # create a fresh session and render the menu via module
                            try:
                                bbs_session = bm.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
                            except AttributeError:
                                # backward compat: some older modules might expose enter()
                                bbs_session = bm.enter(ser, use_ansi)
                        except Exception as e:
                            write(ser, f"\r\n*** BBS module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "BBS"
                    elif menu_action == "telnet":
                        try:
                            importlib.invalidate_caches()
                            telnet_module = importlib.import_module("rsh_telnet")
                            importlib.reload(telnet_module)
                            telnet_session = telnet_module.create_session(
                                ser, use_ansi
                            )
                        except Exception as exc:
                            write(
                                ser,
                                f"\r\n*** Telnet module load error: {exc} ***\r\n",
                            )
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "TELNET"
                    elif menu_action == "terminals":
                        run_connected_terminals_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "ftp":
                        try:
                            importlib.invalidate_caches()
                            ftp_module = importlib.import_module("rsh_ftp")
                            importlib.reload(ftp_module)
                            ftp_session = ftp_module.create_session(ser, use_ansi)
                        except Exception as exc:
                            write(ser, f"\r\n*** FTP module load error: {exc} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "FTP"
                    elif menu_action == "files":
                        # Load files module on demand so it can be edited without restarting the hub
                        try:
                            importlib.invalidate_caches()
                            fm = importlib.import_module('rsh_files')
                            importlib.reload(fm)
                            files_module = fm
                            files_session = fm.create_session(
                                ser, use_ansi, base_dir=FILES_DIR
                            )
                        except Exception as e:
                            write(ser, f"\r\n*** Files module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "FILES"
                    elif menu_action in ("text", "textlib"):
                        # Load text module on demand so it can be edited without restarting the hub
                        try:
                            importlib.invalidate_caches()
                            tm = importlib.import_module('rsh_text')
                            importlib.reload(tm)
                            text_module = tm
                            text_list  = sorted([p.name for p in TEXT_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
                            text_session = tm.create_session(ser, use_ansi, files=text_list, base_dir=TEXT_DIR)
                        except Exception as e:
                            write(ser, f"\r\n*** Text module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "TEXT"
                    elif menu_action == "browser":
                        try:
                            importlib.invalidate_caches()
                            browser_module = importlib.import_module('rsh_browser')
                            importlib.reload(browser_module)
                            browser_session = browser_module.create_session(ser, use_ansi)
                        except Exception as e:
                            write(ser, f"\r\n*** Browser module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "BROWSER"
                    elif menu_action == "notes":
                        # Load notes module on demand so it can be edited without restarting the hub
                        try:
                            importlib.invalidate_caches()
                            nm = importlib.import_module('rsh_notes')
                            importlib.reload(nm)
                            notes_module = nm
                            refresh_notes_session()
                        except Exception as e:
                            write(ser, f"\r\n*** Notes module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "NOTES"
                    elif menu_action == "keyboard":
                        run_keyboard_bridge_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "welcome_banner":
                        clear_screen(ser, use_ansi)
                        write(ser, "\r\nWelcome Banner\r\n")
                        write(ser, "Current: " + WELCOME_BANNER + "\r\n\r\n")
                        write(
                            ser,
                            "Enter a banner (1-80 printable ASCII characters).\r\n",
                        )
                        write(ser, "Press Enter with an empty line to use config.py default.\r\n")
                        write(ser, "New banner: ")
                        mode = "WELCOME_BANNER"
                    elif menu_action == "com_bridge":
                        # Enter COM Port Bridge: delegate prompts to rsh_bridge module
                        try:
                            importlib.invalidate_caches()
                            bm = importlib.import_module('rsh_bridge')
                            importlib.reload(bm)
                            bridge_module = bm
                            # create a fresh bridge session; pass active port registries so module can handle take-over
                            try:
                                bridge_session = bm.create_session(ser, use_ansi, active_ports=ACTIVE_PORTS, surrendered_ports=SURRENDERED_PORTS)
                            except TypeError:
                                # backward compat: create_session may not accept registries
                                bridge_session = bm.create_session(ser, use_ansi)
                        except Exception as e:
                            write(ser, f"\r\n*** Bridge module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        # The COMBRIDGE prompt handler expects the pending bridge prompts to be
                        # available in `pending_bridge`. Assign the freshly created session so
                        # the prompt state isn't None (which caused a NoneType subscriptable error).
                        pending_bridge = bridge_session
                        mode = "COMBRIDGE_PROMPT"
                    elif menu_action == "wargames":
                        # Enter Wargames mode (load module on demand so it can be edited separately)
                        try:
                            importlib.invalidate_caches()
                            wg = importlib.import_module('rsh_wargames')
                            importlib.reload(wg)
                            wargames_module = wg
                            # create a fresh session; module will print initial header/prompt
                            try:
                                wargames_session = wg.create_session(ser, use_ansi)
                            except AttributeError:
                                # backward compat: try enter()
                                wargames_session = wg.enter(ser, use_ansi)
                        except Exception as e:
                            write(ser, f"\r\n*** Wargames module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "WARGAMES"
                    elif menu_action == "ai":
                        # Enter AI chat mode (load module on demand)
                        try:
                            importlib.invalidate_caches()
                            ai = importlib.import_module('rsh_ai')
                            importlib.reload(ai)
                            ai_module = ai
                            # create a fresh session
                            ai_session = ai.create_session(ser, use_ansi)
                        except Exception as e:
                            write(ser, f"\r\n*** AI module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "AI"
                    elif menu_action == "cli":
                        mode = "CLI"
                        retro_session.cols = terminal_columns(ser)
                        retro_session.active_module = "shell"
                        write(ser, "\r\nRetro Serial Hub CLI. Type 'help' for commands, 'exit' for menu.\r\ncli> ")
                        continue
                    elif menu_action in ("disconnect", "exit_hub"):
                        write(ser, "\r\nDisconnecting from Retro Serial Hub.\r\n")
                        retro_session.state = "disconnected"
                        event_bus.publish("session.disconnected", retro_session)
                        return
                    elif menu_action == "apps":
                        if line_str and line_str.upper().startswith("APPS ") and len(line_str) > 5:
                            write(ser, "\r\n")
                            try:
                                response = retro_shell.execute(line_str)
                                render_shell_result(response)
                            except Exception as exc:
                                write(ser, f"Apps error: {exc}\r\n")
                            write(ser, "\r\n")
                            wait_for_key(ser)
                        else:
                            run_apps_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "launch":
                        if line_str and line_str.upper().startswith("LAUNCH ") and len(line_str) > 7:
                            app_name = line_str[7:].strip()
                            try:
                                response = retro_shell.execute(f"launch {app_name}")
                                write(ser, "\r\n" + response + "\r\n")
                            except Exception as exc:
                                write(ser, f"Launch error: {exc}\r\n")
                            if shell_requested_module:
                                requested_module = shell_requested_module.pop()
                                if isinstance(requested_module, tuple) and requested_module[0] in ("app_interactive", "host_terminal"):
                                    _, target, app_args = requested_module
                                    echo_opt = False if "powershell" in str(target).lower() else True
                                    run_interactive_app(target, app_args, local_echo=echo_opt)
                                    show_main_menu(ser, use_ansi)
                                    continue
                                elif isinstance(requested_module, tuple) and requested_module[0] == "app_keyboard":
                                    _, target, app_args = requested_module
                                    launch_with_keyboard_bridge(target, app_args)
                                    show_main_menu(ser, use_ansi)
                                    continue
                            wait_for_key(ser)
                        else:
                            run_apps_menu(launch_first=True)
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "host_terminal":
                        run_host_terminal_menu(line_str)
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "view":
                        if line_str and line_str.upper().startswith("VIEW ") and len(line_str) > 5:
                            file_name = line_str[5:].strip().strip("'\"")
                            try:
                                response = retro_shell.execute(f'view "{file_name}"')
                                render_shell_result(response)
                            except Exception as exc:
                                write(ser, f"Viewer error: {exc}\r\n")
                            write(ser, "\r\n")
                            wait_for_key(ser)
                        else:
                            run_document_viewer_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "calc":
                        if line_str and line_str.upper().startswith("CALC ") and len(line_str) > 5:
                            expr = line_str[5:].strip()
                            try:
                                response = retro_shell.execute(f"calc {expr}")
                                write(ser, f"\r\nResult: {response}\r\n")
                            except Exception as exc:
                                write(ser, f"Calc error: {exc}\r\n")
                            wait_for_key(ser)
                        else:
                            run_calc_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "logo":
                        run_logo_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "mail":
                        if line_str and line_str.upper().startswith("MAIL ") and len(line_str) > 5:
                            try:
                                response = retro_shell.execute(line_str)
                                render_shell_result(response)
                            except Exception as exc:
                                write(ser, f"Mail error: {exc}\r\n")
                            write(ser, "\r\n")
                            wait_for_key(ser)
                        else:
                            run_mail_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "games":
                        sub = run_games_menu()
                        if sub == "wargames":
                            try:
                                importlib.invalidate_caches()
                                wg = importlib.import_module('rsh_wargames')
                                importlib.reload(wg)
                                wargames_module = wg
                                try:
                                    wargames_session = wg.create_session(ser, use_ansi)
                                except AttributeError:
                                    wargames_session = wg.enter(ser, use_ansi)
                            except Exception as e:
                                write(ser, f"\r\n*** Wargames module load error: {e} ***\r\n")
                                wait_for_key(ser)
                                show_main_menu(ser, use_ansi)
                                continue
                            mode = "WARGAMES"
                            continue
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "mines":
                        if line_str and line_str.upper().startswith("MINES ") and len(line_str) > 6:
                            sub = line_str[6:].strip()
                            res = retro_shell.execute(f"mines {sub}")
                            render_shell_result(res)
                            write(ser, "\r\n")
                            wait_for_key(ser)
                        else:
                            run_minesweeper_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "solitaire":
                        if line_str and (line_str.upper().startswith("SOLITAIRE ") or line_str.upper().startswith("SOL ")):
                            sub = line_str.split(" ", 1)[1]
                            res = retro_shell.execute(f"solitaire {sub}")
                            render_shell_result(res)
                            write(ser, "\r\n")
                            wait_for_key(ser)
                        else:
                            run_solitaire_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "wumpus":
                        run_wumpus_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "lander":
                        run_lander_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "blackjack":
                        run_card_or_code_game("blackjack", "BLACKJACK", "Blackjack [H=hit, S=stand, N=new, Q=quit]> ", ("You win!", "Dealer wins.", "Push.", "Bust!", "BLACKJACK!"))
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "mastermind":
                        run_card_or_code_game("mastermind", "MASTERMIND", "Mastermind [G 1234=guess, N=new, Q=quit]> ", ("YOU WIN!", "Out of guesses."))
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "wordguess":
                        run_word_guess_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "trek":
                        run_trek_session()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "help_menu":
                        if line_str and line_str.upper().startswith("HELP ") and len(line_str) > 5:
                            from retro_os.help_data import get_topic_content
                            topic = line_str[5:].strip()
                            content = get_topic_content(topic)
                            write(ser, "\r\n")
                            render_shell_result(content)
                            write(ser, "\r\n")
                            wait_for_key(ser)
                        else:
                            run_help_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "mailto":
                        if line_str and line_str.upper().startswith("MAILTO "):
                            parts = line_str.split(" ", 2)
                            addr = parts[1]
                            subj = parts[2] if len(parts) > 2 else ""
                            cmd = f"mail mailto {addr} {subj}" if subj else f"mail mailto {addr}"
                        else:
                            write(ser, "\r\nEnter email address for host mailto (Q to cancel): ")
                            addr = read_input_line(ser).strip()
                            if not addr or addr.upper() == "Q":
                                show_main_menu(ser, use_ansi)
                                continue
                            write(ser, "Subject (optional): ")
                            subj = read_input_line(ser).strip()
                            cmd = f"mail mailto {addr} {subj}" if subj else f"mail mailto {addr}"
                        try:
                            res = retro_shell.execute(cmd)
                            write(ser, f"\r\n{res}\r\n")
                        except Exception as exc:
                            write(ser, f"Mailto error: {exc}\r\n")
                        wait_for_key(ser)
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "ascii_viewer":
                        if line_str and line_str.upper().startswith("ASCII ") and len(line_str) > 6:
                            img_path = line_str[6:].strip()
                            try:
                                response = retro_shell.execute(f"ascii {img_path}")
                                render_shell_result(response)
                            except Exception as exc:
                                write(ser, f"ASCII viewer error: {exc}\r\n")
                            write(ser, "\r\n")
                            wait_for_key(ser)
                        else:
                            run_ascii_viewer_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "print":
                        if line_str and line_str.upper().startswith("PRINT ") and len(line_str) > 6:
                            p_text = line_str[6:].strip()
                            try:
                                response = retro_shell.execute(f"print {p_text}")
                                write(ser, "\r\n" + response + "\r\n")
                            except Exception as exc:
                                write(ser, f"Print error: {exc}\r\n")
                            wait_for_key(ser)
                        else:
                            run_print_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "kb":
                        if line_str and line_str.upper().startswith("KB ") and len(line_str) > 3:
                            try:
                                response = retro_shell.execute(line_str)
                                render_shell_result(response)
                            except Exception as exc:
                                write(ser, f"KB profile error: {exc}\r\n")
                            wait_for_key(ser)
                        else:
                            run_keyboard_profiles_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "scheduler":
                        if line_str and (line_str.upper().startswith("SCHEDULE ") or line_str.upper().startswith("SCHEDULER ")):
                            cmd = "schedule " + line_str.split(" ", 1)[1]
                            try:
                                response = retro_shell.execute(cmd)
                                render_shell_result(response)
                            except Exception as exc:
                                write(ser, f"Scheduler error: {exc}\r\n")
                            wait_for_key(ser)
                        else:
                            run_scheduler_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "fetch":
                        if line_str and (line_str.upper().startswith("FETCH ") or line_str.upper().startswith("DOWNLOAD ")):
                            try:
                                response = retro_shell.execute(line_str)
                                write(ser, f"\r\n{response}\r\n")
                            except Exception as exc:
                                write(ser, f"Fetch error: {exc}\r\n")
                            wait_for_key(ser)
                        else:
                            run_document_viewer_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "shortcut_add":
                        run_add_shortcut_flow()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "shortcut_del":
                        run_remove_shortcut_flow()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif isinstance(menu_action, str) and menu_action.startswith("shortcut_run:"):
                        cmd_to_run = menu_action.split(":", 1)[1].strip()
                        write(ser, f"\r\nExecuting: {cmd_to_run}\r\n")
                        try:
                            response = retro_shell.execute(cmd_to_run)
                        except Exception as exc:
                            response = f"Command failed: {exc}"
                        if response:
                            render_shell_result(response)
                        if shell_requested_module:
                            requested_module = shell_requested_module.pop()
                            handled = handle_shell_action(requested_module)
                            if handled:
                                continue
                            elif handled is None:
                                retro_session.active_module = requested_module
                                mode = "MENU"
                                menu_action = requested_module
                                continue
                        else:
                            write(ser, "\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                    elif menu_action in ("host_media", "sysinfo"):
                        if menu_action == "sysinfo" or (line_str and any(line_str.upper().split()[0] in ("SYS", "SYSINFO", "TOP") for _ in [0] if line_str.strip())):
                            is_snapshot = bool(line_str and any(flag in line_str.upper().split() for flag in ("SNAPSHOT", "SNAP", "STATIC", "-S")))
                            run_sysinfo_display(realtime=not is_snapshot)
                        elif line_str and any(line_str.upper().startswith(p) for p in ("CLIP ", "COPY ", "MEDIA ", "VOL ")):
                            try:
                                res = retro_shell.execute(line_str)
                                render_shell_result(res)
                            except Exception as exc:
                                write(ser, f"Error: {exc}\r\n")
                            wait_for_key(ser)
                        else:
                            run_host_media_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "weather_news":
                        if line_str and any(line_str.upper().startswith(p) for p in ("WEATHER ", "NEWS ", "BRIEFING ")):
                            try:
                                res = retro_shell.execute(line_str)
                                render_shell_result(res)
                            except Exception as exc:
                                write(ser, f"Error: {exc}\r\n")
                            wait_for_key(ser)
                        else:
                            run_weather_news_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "terminal_settings":
                        if line_str and (line_str.upper().startswith("CAPS ") or line_str.upper().startswith("PACE ")):
                            try:
                                res = retro_shell.execute(line_str)
                                render_shell_result(res)
                            except Exception as exc:
                                write(ser, f"Settings error: {exc}\r\n")
                            if shell_requested_module:
                                handle_shell_action(shell_requested_module.pop())
                            wait_for_key(ser)
                        else:
                            run_terminal_settings_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "host_settings":
                        run_host_settings_menu()
                        show_main_menu(ser, use_ansi)
                        continue
                    elif menu_action == "direct_transfer":
                        try:
                            res = retro_shell.execute(line_str)
                            write(ser, f"\r\n{res}\r\n")
                        except Exception as exc:
                            write(ser, f"Transfer error: {exc}\r\n")
                        if shell_requested_module:
                            handle_shell_action(shell_requested_module.pop())
                        wait_for_key(ser)
                        show_main_menu(ser, use_ansi)
                        continue
                    else:
                        flyout = getattr(ser, "_rsh_flyout_menu", None)
                        sec_idx = getattr(flyout, "active_section_idx", 0) if flyout else 0
                        set_terminal_activity(ser, f"section:{sec_idx + 1}", default_name=name)
                        write(ser, "Invalid command\r\n")
                        write(ser, "Command: ")
                    continue

                if mode == "TELNET":
                    try:
                        consumed, action = telnet_module.handle_input(
                            telnet_session,
                            line_str,
                            ser,
                            use_ansi,
                            add_bbs_entry=add_bbs_entry,
                        )
                        if consumed:
                            if action == "MENU":
                                mode = "MENU"
                                show_main_menu(ser, use_ansi)
                            elif (
                                isinstance(action, tuple)
                                and action[0] == "CONNECT"
                            ):
                                _, host, port = action
                                write(ser, f"\r\nConnecting to {host}:{port}...\r\n")
                                tcp_sock = connect_host(host, port, ser)
                                if tcp_sock and inbound_translator:
                                    inbound_translator.reset()
                                elif not tcp_sock:
                                    telnet_module.show_menu(
                                        ser, telnet_session, use_ansi
                                    )
                            continue
                    except Exception as exc:
                        write(ser, f"\r\n*** Telnet error: {exc} ***\r\n")
                        mode = "MENU"
                        show_main_menu(ser, use_ansi)
                        continue

                if mode == "FTP":
                    try:
                        consumed, action = ftp_module.handle_input(
                            ftp_session, line_str, ser, use_ansi
                        )
                        if not consumed:
                            continue
                        if action == "MENU":
                            ftp_module.close_session(ftp_session)
                            mode = "MENU"
                            show_main_menu(ser, use_ansi)
                            continue
                        if (
                            isinstance(action, tuple)
                            and action[0] == "DOWNLOAD_TO_HOST"
                        ):
                            remote_name = action[1]
                            candidate = FILES_DIR / remote_name
                            stem, suffix = candidate.stem, candidate.suffix
                            sequence = 2
                            while candidate.exists():
                                candidate = FILES_DIR / (
                                    f"{stem} ({sequence}){suffix}"
                                )
                                sequence += 1
                            write(
                                ser,
                                f"\r\nDownloading to host: {candidate.name}\r\n",
                            )
                            try:
                                ftp_module.download_to_path(
                                    ftp_session, remote_name, candidate
                                )
                            except Exception as exc:
                                ftp_module.download_finished(
                                    ftp_session,
                                    ser,
                                    use_ansi,
                                    notice=f"Download failed: {exc}",
                                )
                            else:
                                ftp_module.download_finished(
                                    ftp_session,
                                    ser,
                                    use_ansi,
                                    notice=f"Saved to host as {candidate.name}.",
                                )
                            continue
                        if (
                            isinstance(action, tuple)
                            and action[0] == "DOWNLOAD_TO_SERIAL"
                        ):
                            _, remote_name, transfer_type = action
                            transfer_name = pathlib.Path(remote_name).name
                            try:
                                with tempfile.TemporaryDirectory() as temp_dir:
                                    local_path = pathlib.Path(temp_dir) / transfer_name
                                    write(
                                        ser,
                                        f"\r\nDownloading {transfer_name} for "
                                        f"{transfer_type.replace('_SEND', '')}...\r\n",
                                    )
                                    ftp_module.download_to_path(
                                        ftp_session, remote_name, local_path
                                    )
                                    if files_module is None:
                                        files_module = importlib.import_module(
                                            "rsh_files"
                                        )
                                        importlib.reload(files_module)
                                    transfer_func = getattr(
                                        files_module, transfer_type.lower()
                                    )
                                    if transfer_type == "XMODEM_SEND":
                                        transfer_func(ser, str(local_path), name)
                                    else:
                                        transfer_func(ser, str(local_path))
                            except Exception as exc:
                                ftp_module.download_finished(
                                    ftp_session,
                                    ser,
                                    use_ansi,
                                    notice=f"Direct download/transfer failed: {exc}",
                                )
                            else:
                                ftp_module.download_finished(
                                    ftp_session,
                                    ser,
                                    use_ansi,
                                    notice="Direct download and transfer complete.",
                                )
                            continue
                    except Exception as exc:
                        write(ser, f"\r\n*** FTP error: {exc} ***\r\n")
                        if ftp_module and ftp_session:
                            ftp_module.close_session(ftp_session)
                        mode = "MENU"
                        show_main_menu(ser, use_ansi)
                        continue

                if mode == "BBS_MANAGE":
                    try:
                        bbs_module.handle_directory_manager_input(
                            bbs_session, line_str, ser, use_ansi
                        )
                        if bbs_session.get("submode") == "BBS_MENU":
                            mode = "BBS"
                    except Exception as exc:
                        write(ser, f"\r\n*** BBS directory manager error: {exc} ***\r\n")
                        mode = "BBS"
                        return_to_connection_menu()
                    continue

                if mode == "BBS":
                    # Quit back to main menu
                    if upper == "Q":
                        mode = "MENU"
                        show_main_menu(ser, use_ansi)
                        continue

                    if not line_str:  # user just pressed Enter
                        # Re-render via module if available
                        if bbs_module:
                            try:
                                bbs_session = bbs_module.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
                            except Exception:
                                # fallback to main file menu if something fails
                                show_bbs_menu(ser, use_ansi)
                        else:
                            show_bbs_menu(ser, use_ansi)
                        continue

                    # If connected, allow ATH to hang up
                    if tcp_sock and upper == "ATH":
                        write(ser, "\r\nDisconnecting...\r\n")
                        tcp_sock.close()
                        tcp_sock = None
                        # show menu from module if loaded
                        if bbs_module:
                            try:
                                bbs_session = bbs_module.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
                            except Exception:
                                show_bbs_menu(ser, use_ansi)
                        else:
                            show_bbs_menu(ser, use_ansi)
                        continue

                    # If not connected, interpret numeric selection
                    if not tcp_sock:
                        if upper == "M":
                            bbs_module.start_directory_manager(
                                bbs_session, ser, use_ansi
                            )
                            mode = "BBS_MANAGE"
                            continue
                        try:
                            num = int(upper)
                            if 1 <= num <= len(BBSS):
                                write(ser, f"\r\nDialing {BBSS[num-1]}...\r\n")
                                tcp_sock = connect_bbs(num-1, ser)
                                if tcp_sock and inbound_translator:
                                    inbound_translator.reset()
                                if not tcp_sock:
                                    if bbs_module:
                                        try:
                                            bbs_session = bbs_module.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
                                        except Exception:
                                            show_bbs_menu(ser, use_ansi)
                                    else:
                                        show_bbs_menu(ser, use_ansi)
                            else:
                                write(ser, "Invalid BBS number\r\n")
                                write(ser, "Command: ")
                        except ValueError:
                            write(ser, "Invalid command\r\n")
                            write(ser, "Command: ")
                        continue

                    # If connected, forward everything else to the BBS
                    if tcp_sock:
                        tcp_sock.sendall(raw_line + b"\r\n")
                    continue

                if mode == "FILES":
                    try:
                        consumed, action = files_module.handle_input(files_session, line_str, ser, use_ansi)
                        if consumed:
                            if isinstance(action, str):
                                # Handle file transfer actions returned by module
                                if any(action.startswith(prefix) for prefix in ('XMODEM_SEND:', 'YMODEM_SEND:', 'ASCII_SEND:')):
                                    transfer_type, fname = action.split(':', 1)
                                    transfer_func = getattr(files_module, transfer_type.lower())
                                    # Only XMODEM gets the name parameter
                                    if transfer_type == 'XMODEM_SEND':
                                        transfer_func(ser, fname, name)
                                    else:
                                        transfer_func(ser, fname)
                                    # Refresh the current directory after transfer.
                                    files_session = files_module.create_session(
                                        ser,
                                        use_ansi,
                                        base_dir=FILES_DIR,
                                        transfer_mode=files_session["transfer_mode"],
                                        current_dir=files_session["current_dir"],
                                        root_mode=files_session.get("root_mode", False),
                                    )
                                    continue
                                elif action == 'MENU':
                                    mode = 'MENU'
                                    show_main_menu(ser, use_ansi)
                                    continue
                            continue
                    except Exception as e:
                        write(ser, f"\r\n*** Files module error: {e} ***\r\n")
                        mode = "MENU"
                        show_main_menu(ser, use_ansi)
                    continue
                # UPLOAD flow is handled by the files module (rsh_files). The module
                # will prompt for a filename and perform the receive into the
                # configured base_dir. The hub no longer performs upload handling
                # directly here.
                if mode == "TEXT":
                    # Delegate to text module if available
                    if text_module:
                        try:
                            consumed, action = text_module.handle_input(text_session, line_str, ser, use_ansi)
                            if consumed:
                                if action == 'MENU':
                                    mode = 'MENU'
                                    show_main_menu(ser, use_ansi)
                                continue
                        except Exception as e:
                            write(ser, f"\r\n*** Text module error: {e} ***\r\n")
                            wait_for_key(ser)
                            mode = "MENU"
                            show_main_menu(ser, use_ansi)
                        continue
                    
                    # No module available - return to menu
                    write(ser, "\r\n*** Text module not available ***\r\n")
                    wait_for_key(ser)
                    mode = "MENU"
                    show_main_menu(ser, use_ansi)
                    continue

                if mode == "BROWSER":
                    if browser_module:
                        try:
                            consumed, action = browser_module.handle_input(
                                browser_session, line_str, ser, use_ansi
                            )
                            if consumed:
                                if action == 'MENU':
                                    mode = 'MENU'
                                    show_main_menu(ser, use_ansi)
                                continue
                        except Exception as e:
                            write(ser, f"\r\n*** Browser module error: {e} ***\r\n")
                            wait_for_key(ser)
                            mode = 'MENU'
                            show_main_menu(ser, use_ansi)
                            continue

                    write(ser, "\r\n*** Browser module not available ***\r\n")
                    wait_for_key(ser)
                    mode = 'MENU'
                    show_main_menu(ser, use_ansi)
                    continue
                if mode == "COMBRIDGE_PROMPT":
                    # Delegate staged COM bridge prompts to the rsh_bridge module
                    if bridge_module and pending_bridge is not None:
                        try:
                            consumed, action = bridge_module.handle_input(pending_bridge, line_str, ser, use_ansi)
                            if consumed:
                                # Module opened the bridge and returned the serial
                                if isinstance(action, tuple) and action[0] == 'OPEN_BRIDGE':
                                    opened_serial = action[1]
                                    port_name = action[2] if len(action) > 2 else None
                                    try:
                                        write(ser, f"\r\nRouting {port_name} <-> this session. Type ATM to stop.\r\n")
                                    except Exception:
                                        pass
                                    # Create a runtime bridge session in the module if available
                                    try:
                                        if hasattr(bridge_module, 'create_runtime_session'):
                                            bridge_session = bridge_module.create_runtime_session(opened_serial, port_name, active_ports=ACTIVE_PORTS, surrendered_ports=SURRENDERED_PORTS, ser=ser, use_ansi=use_ansi)
                                        else:
                                            # backward compat: store minimal runtime info
                                            bridge_session = {'stage':'runtime','bridge_serial': opened_serial, 'port_name': port_name, 'active_ports': ACTIVE_PORTS, 'surrendered_ports': SURRENDERED_PORTS}
                                    except Exception as e:
                                        write(ser, f"\r\n*** Bridge session init failed: {e} ***\r\n")
                                        wait_for_key(ser)
                                        pending_bridge = None
                                        mode = 'MENU'
                                        show_main_menu(ser, use_ansi)
                                        continue
                                    pending_bridge = None
                                    mode = 'COMBRIDGE'
                                elif action == 'MENU':
                                    mode = 'MENU'
                                    show_main_menu(ser, use_ansi)
                                # consumed and handled by module
                                continue
                        except Exception as e:
                            write(ser, f"\r\n*** Bridge module error: {e} ***\r\n")
                            wait_for_key(ser)
                            mode = 'MENU'
                            show_main_menu(ser, use_ansi)
                            continue

                    # No module/pending session: return to menu
                    write(ser, "\r\n*** Bridge module not available ***\r\n")
                    wait_for_key(ser)
                    pending_bridge = None
                    mode = 'MENU'
                    show_main_menu(ser, use_ansi)
                    continue
                if mode == "COMBRIDGE":
                    # Delegate all runtime COM bridge behavior to the bridge module
                    if bridge_module and bridge_session is not None:
                        try:
                            # Prefer the dispatch wrapper if available (handles runtime vs prompt)
                            if hasattr(bridge_module, 'handle_input_dispatch'):
                                consumed, action = bridge_module.handle_input_dispatch(bridge_session, line_str, ser, use_ansi, raw_line=raw_line)
                            elif hasattr(bridge_module, 'handle_input'):
                                # fallback: try the normal handle_input with raw_line if supported
                                try:
                                    consumed, action = bridge_module.handle_input(bridge_session, line_str, ser, use_ansi, raw_line)
                                except TypeError:
                                    consumed, action = bridge_module.handle_input(bridge_session, line_str, ser, use_ansi)
                            else:
                                consumed, action = (False, None)

                            if consumed:
                                if action == 'MENU':
                                    # ensure module cleaned up; if not, attempt to close underlying serial
                                    try:
                                        bs = bridge_session.get('bridge_serial') if isinstance(bridge_session, dict) else None
                                        if bs:
                                            try:
                                                bs.close()
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                                    bridge_session = None
                                    mode = 'MENU'
                                    show_main_menu(ser, use_ansi)
                                continue
                        except Exception as e:
                            write(ser, f"\r\n*** Bridge module error: {e} ***\r\n")
                            wait_for_key(ser)
                            bridge_session = None
                            mode = 'MENU'
                            show_main_menu(ser, use_ansi)
                            continue

                    # No module available - inform user and return to menu
                    write(ser, "\r\n*** COM bridge not available. Returning to menu.\r\n")
                    wait_for_key(ser)
                    bridge_session = None
                    mode = "MENU"
                    show_main_menu(ser, use_ansi)
                    continue
                if mode == "NOTES":
                    # Delegate to notes module if available
                    if notes_module:
                        try:
                            consumed, action = notes_module.handle_input(notes_session, line_str, ser, use_ansi)
                            if consumed:
                                # module may return ('SHOW_NOTE', lines)
                                if isinstance(action, tuple) and action[0] == 'SHOW_NOTE':
                                    lines = action[1]
                                    try:
                                        clear_screen(ser, use_ansi)
                                        write(ser, "\r\n")
                                        paginate_lines(
                                            ser, lines, page_lines=22, quit_msg=True
                                        )
                                        refresh_notes_session()
                                        continue
                                    except Exception as e:
                                        write(ser, f"\r\n*** Error displaying note: {e} ***\r\n")
                                        wait_for_key(ser)
                                        try:
                                            notes_session = notes_module.create_session(ser, use_ansi, notes=notes_list, base_dir=NOTES_DIR)
                                        except Exception:
                                            show_main_menu(ser, use_ansi)
                                        continue
                                if isinstance(action, tuple) and action[0] == 'COPY_TO_CLIPBOARD':
                                    note_path = NOTES_DIR / action[1]
                                    try:
                                        note_text = note_path.read_text(encoding="utf-8", errors="ignore")
                                        if host_env.set_clipboard(note_text):
                                            refresh_notes_session(f"Copied {note_path.name} to the host clipboard.")
                                        else:
                                            refresh_notes_session("Could not write to the host clipboard.")
                                    except OSError as exc:
                                        refresh_notes_session(f"Could not read {note_path.name}: {exc}")
                                    continue
                                if isinstance(action, str) and action.startswith('SHOW_NOTE:'):
                                    fname = action.split(':',1)[1]
                                    path = NOTES_DIR / fname
                                    try:
                                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                                            lines = [ln.rstrip("\r\n") for ln in f.readlines()]
                                        clear_screen(ser, use_ansi)
                                        write(ser, "\r\n")
                                        paginate_lines(
                                            ser, lines, page_lines=22, quit_msg=True
                                        )
                                        refresh_notes_session()
                                        continue
                                    except Exception as e:
                                        write(ser, f"\r\n*** Error reading note: {e} ***\r\n")
                                        wait_for_key(ser)
                                        try:
                                            notes_list = sorted([p.name for p in NOTES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
                                            notes_session = notes_module.create_session(ser, use_ansi, notes=notes_list, base_dir=NOTES_DIR)
                                        except Exception:
                                            show_notes_menu(ser, notes_list, use_ansi)
                                        continue
                                if action == 'CREATE':
                                    write(ser, "\r\nEnter a note name (without .txt). Q=Cancel: ")
                                    mode = "CREATE_NOTE_NAME"
                                    continue
                                if action == 'PASTE_CLIPBOARD':
                                    clip_text = host_env.get_clipboard()
                                    if not clip_text:
                                        refresh_notes_session("Host clipboard is empty or unavailable.")
                                        continue
                                    if clip_text.startswith("[Clipboard read error:"):
                                        refresh_notes_session(clip_text)
                                        continue
                                    write(ser, "\r\nSave host clipboard as a note. Name (Q=Cancel): ")
                                    clip_title = read_input_line(ser).strip()
                                    if not clip_title or clip_title.upper() == "Q":
                                        refresh_notes_session("Clipboard capture cancelled.")
                                        continue
                                    invalid_chars = '<>:"/\\|?*'
                                    if any(ord(ch) < 32 or ch in invalid_chars for ch in clip_title) or pathlib.Path(clip_title).name != clip_title or clip_title.endswith((".", " ")):
                                        refresh_notes_session("Invalid note name.")
                                        continue
                                    clip_filename = clip_title if clip_title.lower().endswith(".txt") else clip_title + ".txt"
                                    clip_path = NOTES_DIR / clip_filename
                                    try:
                                        with clip_path.open("x", encoding="utf-8", newline="") as clip_file:
                                            clip_file.write(clip_text)
                                    except FileExistsError:
                                        refresh_notes_session(f"A note named {clip_filename} already exists.")
                                    except OSError as exc:
                                        refresh_notes_session(f"Could not save clipboard note: {exc}")
                                    else:
                                        refresh_notes_session(f"Saved host clipboard as {clip_filename}.")
                                    continue
                                if action and action.startswith('DELETE:'):
                                    fname = action.split(':',1)[1]
                                    pending_delete = NOTES_DIR / fname
                                    write(ser, f"\r\nAre you sure you want to delete {fname}? (Y/N): ")
                                    mode = "CONFIRM_DELETE"
                                    continue
                                if action == 'MENU':
                                    mode = 'MENU'
                                    show_main_menu(ser, use_ansi)
                                    continue
                                # consumed but no action to core
                                continue
                        except Exception as e:
                            write(ser, f"\r\n*** Notes module error: {e} ***\r\n")
                            # fall through to fallback

                    # No inline fallback: Notes must be implemented in rsh_notes.py
                    write(ser, "\r\n*** Notes module not available. Returning to main menu. ***\r\n")
                    wait_for_key(ser)
                    mode = "MENU"
                    show_main_menu(ser, use_ansi)
                    continue

                if mode == "CREATE_NOTE_NAME":
                    write(ser, "\r\n")
                    if upper == "Q":
                        mode = "NOTES"
                        refresh_notes_session("Note creation cancelled.")
                        continue

                    title = line_str.strip()
                    invalid_characters = '<>:"/\\|?*'
                    reserved_names = {
                        "CON", "PRN", "AUX", "NUL",
                        *(f"COM{index}" for index in range(1, 10)),
                        *(f"LPT{index}" for index in range(1, 10)),
                    }
                    if (
                        not title
                        or any(
                            ord(character) < 32 or character in invalid_characters
                            for character in title
                        )
                        or title[-1:] in (".", " ")
                        or pathlib.Path(title).name != title
                        or pathlib.Path(title).stem.upper() in reserved_names
                    ):
                        write(ser, "Invalid note name. Use a simple filename without path characters.\r\n")
                        write(ser, "Note name (without .txt). Q=Cancel: ")
                        continue

                    note_filename = (
                        title if title.lower().endswith(".txt") else f"{title}.txt"
                    )
                    note_path = NOTES_DIR / note_filename
                    if note_path.exists():
                        write(ser, "A note with that name already exists.\r\n")
                        write(ser, "Choose another name (without .txt). Q=Cancel: ")
                        continue

                    note_buffer = []
                    mode = "CREATE_NOTE"
                    write(ser, "Enter note text. Type END on a line by itself to finish; Q cancels.\r\n")
                    continue

                if mode == "CREATE_NOTE":
                    write(ser, "\r\n")
                    if upper == "Q":
                        note_buffer = []
                        mode = "NOTES"
                        refresh_notes_session("Note creation cancelled.")
                        continue
                    if upper == "END":
                        try:
                            with note_path.open("x", encoding="utf-8", newline="") as note_file:
                                if note_buffer:
                                    note_file.write("\n".join(note_buffer) + "\n")
                        except FileExistsError:
                            mode = "CREATE_NOTE_NAME"
                            write(ser, "A note with that name already exists.\r\n")
                            write(ser, "Choose another name (without .txt). Q=Cancel: ")
                            continue
                        except OSError as exc:
                            note_buffer = []
                            mode = "NOTES"
                            refresh_notes_session(f"Could not save note: {exc}")
                            continue

                        note_buffer = []
                        mode = "NOTES"
                        refresh_notes_session(f"Saved {note_filename}.")
                        continue
                    note_buffer.append(line_str)
                    continue

                if mode == "CONFIRM_DELETE":
                    write(ser, "\r\n")
                    if upper in ("Y", "YES"):
                        if pending_delete is None:
                            mode = "NOTES"
                            refresh_notes_session(
                                "Could not delete note: no note is selected."
                            )
                            continue
                        try:
                            pending_delete.unlink()
                        except OSError as exc:
                            notice = f"Could not delete note: {exc}"
                        else:
                            notice = f"Deleted {pending_delete.name}."
                        pending_delete = None
                        mode = "NOTES"
                        refresh_notes_session(notice)
                        continue
                    if upper in ("N", "NO", "Q"):
                        pending_delete = None
                        mode = "NOTES"
                        refresh_notes_session("Note deletion cancelled.")
                        continue
                    write(ser, "Please enter Y to delete or N to cancel: ")
                    continue

                if mode == "WARGAMES":
                    # Delegate to wargames module if loaded
                    if wargames_module:
                        try:
                            # module should provide a handle_input(session, line_str, ser, use_ansi)
                            consumed, new_mode = wargames_module.handle_input(wargames_session, line_str, ser, use_ansi)
                            # consumed=True means module handled the input and already printed responses
                            if consumed:
                                # module can request mode changes by returning new_mode.
                                # Special protocol: if module returns 'CONNECT_BBS:<index>' then core performs connect_bbs.
                                if new_mode:
                                    if isinstance(new_mode, str) and new_mode.startswith('CONNECT_BBS:'):
                                        try:
                                            idx = int(new_mode.split(':',1)[1])
                                            write(ser, f"\r\nDialing {BBSS[idx]}...\r\n")
                                            tcp = connect_bbs(idx, ser)
                                            if tcp:
                                                tcp_sock = tcp
                                                if inbound_translator:
                                                    inbound_translator.reset()
                                                mode = 'BBS'
                                            else:
                                                # show BBS menu again via module create_session
                                                try:
                                                    wargames_module.create_session(ser, use_ansi)
                                                except Exception:
                                                    # try to show BBS menu via module if present, otherwise main menu
                                                    if bbs_module:
                                                        try:
                                                            bbs_session = bbs_module.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
                                                        except Exception:
                                                            show_main_menu(ser, use_ansi)
                                                    else:
                                                        show_main_menu(ser, use_ansi)
                                                mode = 'WARGAMES'
                                        except Exception as e:
                                            write(ser, f"\r\n*** Connect request failed: {e} ***\r\n")
                                            mode = 'WARGAMES'
                                        continue
                                    else:
                                        # generic mode change
                                        mode = new_mode
                                continue
                        except Exception as e:
                            write(ser, f"\r\n*** Wargames module error: {e} ***\r\n")
                            # fall through to default behavior

                    # No inline fallback: wargames must be implemented in rsh_wargames.py
                    write(ser, "\r\n*** Wargames module not available. Returning to main menu. ***\r\n")
                    wait_for_key(ser)
                    mode = "MENU"
                    show_main_menu(ser, use_ansi)
                    continue

                if mode == "AI":
                    # Delegate to AI module if loaded
                    if ai_module:
                        try:
                            consumed, action = ai_module.handle_input(ai_session, line_str, ser, use_ansi)
                            if consumed:
                                if action == 'MENU':
                                    mode = 'MENU'
                                    show_main_menu(ser, use_ansi)
                                continue
                        except Exception as e:
                            write(ser, f"\r\n*** AI module error: {e} ***\r\n")
                            wait_for_key(ser)
                            mode = "MENU"
                            show_main_menu(ser, use_ansi)
                            continue

                    # No inline fallback: AI must be implemented in rsh_ai.py
                    write(ser, "\r\n*** AI module not available. Returning to main menu. ***\r\n")
                    wait_for_key(ser)
                    mode = "MENU"
                    show_main_menu(ser, use_ansi)
                    continue
        # tcp side (only when in BBS mode and connected)
        # tcp side (only when in BBS mode and connected)
        if tcp_sock:
            rlist, _, _ = select.select([tcp_sock], [], [], 0.01)
            for r in rlist:
                data = tcp_sock.recv(1024)
                if not data:
                    write(ser, "\r\n*** Connection closed by remote ***\r\n")
                    tcp_sock.close()
                    tcp_sock = None
                    return_to_connection_menu()
                else:
                    if inbound_translator:
                        data = inbound_translator.feed(data)
                    if data:
                        ser.write(data)

        # COM bridge routing: delegate polling/forwarding to the bridge module if present
        if bridge_session:
            try:
                if bridge_module and hasattr(bridge_module, 'poll_bridge'):
                    # let the module handle reading from its bridged serial and writing to `ser`
                    try:
                        bridge_module.poll_bridge(bridge_session, ser)
                    except Exception:
                        # per-iteration errors shouldn't crash the loop
                        pass
                else:
                    # fallback: if the runtime session stores an underlying serial, forward from it
                    try:
                        bs = bridge_session.get('bridge_serial') if isinstance(bridge_session, dict) else None
                        if bs and getattr(bs, 'in_waiting', 0):
                            d = bs.read(bs.in_waiting)
                            if d:
                                try:
                                    ser.write(d)
                                except Exception:
                                    write(ser, "\r\n*** COM bridge local write failed ***\r\n")
                                    try:
                                        bs.close()
                                    except Exception:
                                        pass
                                    bridge_session = None
                                    mode = "MENU"
                                    show_main_menu(ser, use_ansi)
                    except Exception:
                        pass
            except Exception:
                pass

def main():
    global CONSOLE, TELNET_ACCESS
    threads = []
    addresses = local_ipv4_addresses() if TELNET_SERVER_CONFIGS else []
    profiles = {}
    for name in dict.fromkeys((*SERIAL_CONFIGS, *TELNET_SERVER_CONFIGS)):
        cfg = SERIAL_CONFIGS.get(name, {})
        server_cfg = TELNET_SERVER_CONFIGS.get(name)
        if isinstance(server_cfg, dict):
            host = server_cfg.get("host", "0.0.0.0")
            port = server_cfg.get("port")
            if host == "0.0.0.0":
                connect_host = ", ".join(addresses) if addresses else "LAN IP unavailable"
            else:
                connect_host = host
            endpoint = f"{connect_host}:{port}" if port else None
            tcp_status = "STARTING"
        else:
            port = None
            endpoint = None
            tcp_status = "DISABLED"
        profiles[name] = {
            "serial_port": cfg.get("port", "N/A"),
            "baud": cfg.get("baud"),
            "serial_status": "STARTING",
            "tcp_port": port,
            "tcp_status": tcp_status,
            "endpoint": endpoint,
        }

    CONSOLE = ConsoleDashboard(profiles)
    host_terminal = None
    if CONSOLE.host_input_available():
        host_terminal = HostTerminal(CONSOLE.append_host_output)
        CONSOLE.set_host_terminal(host_terminal)
    TELNET_ACCESS = None
    if TELNET_SERVER_CONFIGS:
        TELNET_ACCESS = TelnetAccess(
            TELNET_ALLOWLIST_FILE, start_remote_client, console_log,
            interactive=CONSOLE.host_input_available(),
        )
        CONSOLE.set_telnet_access(TELNET_ACCESS)
    CONSOLE.start()
    if host_terminal is not None:
        host_terminal.start(host_console_worker)
    if TELNET_ACCESS is not None:
        TELNET_ACCESS.start()

    for name, server_cfg in TELNET_SERVER_CONFIGS.items():
        cfg = SERIAL_CONFIGS.get(name)
        if cfg is None:
            CONSOLE.update_profile(name, tcp="ERROR")
            console_log(
                f"{name}: TCP listener has no matching SERIAL_CONFIGS profile; skipping.",
                level="red",
            )
            continue
        if not isinstance(server_cfg, dict):
            CONSOLE.update_profile(name, tcp="ERROR")
            console_log(
                f"{name}: TCP server configuration must be a dictionary; skipping.",
                level="red",
            )
            continue
        t = threading.Thread(
            target=telnet_server_worker,
            args=(name, cfg, server_cfg),
            name=f"{name}-tcp-server",
            daemon=True,
        )
        t.start()
        threads.append(t)

    for name, cfg in SERIAL_CONFIGS.items():
        t = threading.Thread(
            target=port_worker,
            args=(name, cfg),
            daemon=True
        )
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console_log("Shutting down.")
    finally:
        if host_terminal is not None:
            host_terminal.stop()
        CONSOLE.stop()
        if TELNET_ACCESS is not None:
            TELNET_ACCESS.stop()


if __name__ == "__main__":
    main()
