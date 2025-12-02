#!/usr/bin/env python3
"""
LogicNet Multi-port Serial <-> TCP bridge with BBS-style menus.

Features per serial port:
- Main menu (ATM to return from anywhere)
- Bulletin Boards directory with ADTnn dialing and ATH hangup
- File Transfers: two-column file list, select number to XMODEM-send
- Text Library: list *.txt files, view with pagination
- URL Reader: fetch URL text, strip HTML, paginate, loop

Each configured COM port is opened (if available) and runs its own
independent bridge loop. If a port isn't present, it's skipped.

UX Design:
- Menu uses 80-column, two-column lists (column 2 starts at 40)
- ATM cancels any active BBS connection and returns to main menu
"""

import serial, socket, select, threading, time, os, sys, pathlib, urllib.request, urllib.error, html, re, importlib

# Import configuration from config.py
try:
    from config import SERIAL_CONFIGS, BBSS, IPS, PORTS, EIGHTBITS, SEVENBITS, PARITY_NONE, STOPBITS_ONE
except ImportError:
    print("ERROR: config.py not found. Please ensure config.py exists in the same directory.")
    print("See config.py for configuration examples.")
    sys.exit(1)

# Global registry: map port name -> {'thread': thread_name, 'serial': Serial()}
ACTIVE_PORTS = {}
# Ports that have been surrendered/taken over by a COM-bridge request. Worker threads should stop retrying if their port is surrendered.
SURRENDERED_PORTS = set()

# ---------------- Paths ----------------
BASE_DIR = pathlib.Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "files"
TEXT_DIR  = BASE_DIR / "text"
NOTES_DIR = BASE_DIR / "notes"
FILES_DIR.mkdir(exist_ok=True)
TEXT_DIR.mkdir(exist_ok=True)
NOTES_DIR.mkdir(exist_ok=True)

# ---------------- UI helpers ----------------
def clear_screen(ser, use_ansi=True):
    if use_ansi:
        # ANSI clear screen + cursor home
        ser.write(b"\x1b[2J\x1b[H")
    else:
        # Fallback: just drop a bunch of newlines
        # ser.write(b"\r\n" * 24)
        ser.write(b"\r\n")

def write(ser, s):
    ser.write(s.encode('ascii', errors='ignore'))

def write_bytes(ser, b):
    ser.write(b)

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

def two_column_list(items, left_pad=38):
    half = (len(items) + 1) // 2
    left = items[:half]
    right = items[half:]
    if len(right) < len(left):
        right.append("")
    lines = []
    for i in range(len(left)):
        left_num = f"{i+1:2d}] {left[i]}"
        if i < len(right) and right[i]:
            right_num = f"{i+1+half:2d}] {right[i]}"
            line = f"{left_num:<{left_pad}}{right_num}"
        else:
            line = f"{left_num}"
        lines.append(line)
    return lines

def show_main_menu(ser, use_ansi=True):
    clear_screen(ser, use_ansi)
    write(ser, "\r\nWelcome to the LogicNet Bulletin Board System\r\n")
    write(ser, "v1.0, copyright (c) 2025\r\n\r\n")
    write(ser, "Please select a command from the options below:\r\n\r\n")
    write(ser, " 1] Bulletin Boards\r\n")
    write(ser, " 2] File Transfers\r\n")
    write(ser, " 3] Text Library\r\n")
    write(ser, " 4] URL Reader\r\n")
    write(ser, " 5] Notes\r\n")
    write(ser, " 6] COM Port Bridge\r\n")
    write(ser, " 7] Wargames\r\n")
    write(ser, " 8] AI Assistant\r\n\r\n")
    write(ser, "Command: ")

def show_notes_menu(ser, notes, use_ansi=True):
    clear_screen(ser, use_ansi)
    write(ser, "\r\nNotes:\r\n\r\n")
    display_names = [truncate_name(f) for f in notes]
    lines = two_column_list(display_names, left_pad=38)
    for line in two_column_list(display_names, left_pad=38):
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
    for line in two_column_list(display_names, left_pad=38):
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
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect((host, port))
        s.settimeout(None)
        write(ser, "\r\nCONNECT\r\n")
        return s
    except Exception:
        write(ser, f"\r\n*** Unable to connect to {host}:{port} ***\r\n")
        write(ser, "NO CARRIER\r\n")
        wait_for_key(ser)
        return None

# ---------------- URL Reader ----------------

def strip_html_to_text(html_bytes):
    try:
        text = html_bytes.decode('utf-8', errors='ignore')
    except Exception:
        text = html_bytes.decode(errors='ignore')
    # Remove scripts/styles
    text = re.sub(r"(?is)<script.*?>.*?</script>", "", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", "", text)
    # Replace breaks and paragraphs with newlines
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    # Strip tags
    text = re.sub(r"(?is)<.*?>", "", text)
    # Unescape entities
    text = html.unescape(text)
    # Normalize whitespace
    lines = [ln.rstrip() for ln in text.splitlines()]
    # Collapse long blank runs
    cleaned = []
    blank = 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank <= 1:
                cleaned.append("")
        else:
            blank = 0
            cleaned.append(ln)
    return cleaned

def fetch_url_text(url, ser):
    # Add scheme if missing
    if not re.match(r"^[a-z]+://", url, re.I):
        url = "http://" + url
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read()
            return strip_html_to_text(data)
    except urllib.error.URLError as e:
        write(ser, f"\r\n*** URL error: {e} ***\r\n")
    except Exception as e:
        write(ser, f"\r\n*** Fetch failed: {e} ***\r\n")
    wait_for_key(ser)
    return None
# File transfer functionality is handled by rsh_files.py

# ---------------- Per-port bridge loop ----------------
def port_worker(name, cfg):
    """Worker thread for each serial port. Only retries if a port was once open and then lost."""
    while True:
        try:
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
            print(f"[{name}] Listening on {cfg['port']} at {cfg['baud']} baud")
            # Register active port
            try:
                ACTIVE_PORTS[cfg['port'].upper()] = {'thread': name, 'serial': ser}
            except Exception:
                pass
            # Run bridge loop until it throws (e.g. port disappears)
            bridge_loop(name, ser, cfg.get("ansi", True))
            # When bridge_loop exits normally, unregister
            try:
                ACTIVE_PORTS.pop(cfg['port'].upper(), None)
            except Exception:
                pass
        except serial.SerialException as e:
            # If the port was never present at startup, bail out permanently
            if "FileNotFoundError" in str(e) or "cannot find the file" in str(e):
                print(f"[{name}] Port {cfg['port']} not present on this system. Skipping.")
                return
            else:
                # If this port was surrendered for COM bridge takeover, wait until it's returned
                if cfg['port'].upper() in SURRENDERED_PORTS:
                    print(f"[{name}] Port {cfg['port']} surrendered to COM bridge. Waiting to be returned...")
                    # ensure it's unregistered
                    ACTIVE_PORTS.pop(cfg['port'].upper(), None)
                    # Block here until the surrender is cleared
                    while cfg['port'].upper() in SURRENDERED_PORTS:
                        time.sleep(1)
                    print(f"[{name}] Port {cfg['port']} returned. Retrying open...")
                    time.sleep(1)
                    continue
                print(f"[{name}] Serial error on {cfg['port']}: {e}. Retrying in 5s...")
                time.sleep(5)
                continue
        except Exception as e:
            print(f"[{name}] Unexpected error: {e}. Retrying in 5s...")
            time.sleep(5)
            continue

def bridge_loop(name, ser, use_ansi):
    tcp_sock = None
    # For COM Port Bridge mode: separate serial to bridge
    bridge_serial = None
    pending_bridge = None
    input_buffer = b""
    mode = "MENU"  # MENU, BBS, FILES, TEXT, URL
    # dynamic module handles (loaded on demand)
    wargames_module = None
    wargames_session = None
    # BBS module handles
    bbs_module = None
    bbs_session = None
    # AI module handles
    ai_module = None
    ai_session = None
    # Bridge runtime session (created when COM bridge opens)
    bridge_session = None
    # Text module handles
    text_module = None
    text_session = None
    # Notes module handles
    notes_module = None
    notes_session = None
    # buffer to assemble a single input line while connected to a remote BBS
    bbs_line_buffer = b""

    # Pre-compute files lists
    notes_list = sorted([p.name for p in NOTES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
    files_list = sorted([p.name for p in FILES_DIR.iterdir() if p.is_file()])
    text_list  = sorted([p.name for p in TEXT_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
    # dynamic module handles for menus loaded on demand
    wargames_module = None
    wargames_session = None
    files_module = None
    files_session = None

    show_main_menu(ser, use_ansi)

    while True:
        # serial input
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)

            # Echo in command-mode only (i.e., not while transparent BBS session)
            if mode != "BBS" or (mode == "BBS" and not tcp_sock):
                ser.write(data)

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

            # If we're currently connected to a remote BBS, forward bytes immediately
            # to the TCP socket and assemble a small line buffer so we can still
            # detect an 'ATH' hangup when the user presses Enter.
            if mode == "BBS" and tcp_sock:
                try:
                    tcp_sock.sendall(data)
                except Exception:
                    write(ser, "\r\n*** Connection to remote lost ***\r\n")
                    try:
                        tcp_sock.close()
                    except Exception:
                        pass
                    tcp_sock = None
                    # re-render BBS menu (module or fallback)
                    if bbs_module:
                        try:
                            bbs_session = bbs_module.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
                        except Exception:
                            show_main_menu(ser, use_ansi)
                    else:
                        show_main_menu(ser, use_ansi)
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
                                # show BBS menu via module if available
                                if bbs_module:
                                    try:
                                        bbs_session = bbs_module.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
                                    except Exception:
                                        show_bbs_menu(ser, use_ansi)
                                else:
                                    show_bbs_menu(ser, use_ansi)
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
            input_buffer += data

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
                    show_main_menu(ser, use_ansi)
                    continue

                if mode == "MENU":
                    # Echo full command line
                    if upper == "1":
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
                    elif upper == "2":
                        # Load files module on demand so it can be edited without restarting the hub
                        try:
                            importlib.invalidate_caches()
                            fm = importlib.import_module('rsh_files')
                            importlib.reload(fm)
                            files_module = fm
                            files_list = sorted([p.name for p in FILES_DIR.iterdir() if p.is_file()])
                            files_session = fm.create_session(ser, use_ansi, files=files_list, base_dir=FILES_DIR)
                        except Exception as e:
                            write(ser, f"\r\n*** Files module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "FILES"
                    elif upper == "3":
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
                    elif upper == "4":
                        # Load URL module on demand so it can be edited without restarting the hub
                        try:
                            importlib.invalidate_caches()
                            um = importlib.import_module('rsh_url')
                            importlib.reload(um)
                            url_module = um
                            url_session = um.create_session(ser, use_ansi)
                        except Exception as e:
                            write(ser, f"\r\n*** URL module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "URL"
                    elif upper == "5":
                        # Load notes module on demand so it can be edited without restarting the hub
                        try:
                            importlib.invalidate_caches()
                            nm = importlib.import_module('rsh_notes')
                            importlib.reload(nm)
                            notes_module = nm
                            notes_list = sorted([p.name for p in NOTES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
                            notes_session = nm.create_session(ser, use_ansi, notes=notes_list, base_dir=NOTES_DIR)
                        except Exception as e:
                            write(ser, f"\r\n*** Notes module load error: {e} ***\r\n")
                            wait_for_key(ser)
                            show_main_menu(ser, use_ansi)
                            continue
                        mode = "NOTES"
                    elif upper == "6":
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
                    elif upper == "7":
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
                    elif upper == "8":
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
                    else:
                        write(ser, "Invalid command\r\n")
                        write(ser, "Command: ")
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
                        try:
                            num = int(upper)
                            if 1 <= num <= len(BBSS):
                                write(ser, f"\r\nDialing {BBSS[num-1]}...\r\n")
                                tcp_sock = connect_bbs(num-1, ser)
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
                                        transfer_func(ser, str(FILES_DIR / fname), name)
                                    else:
                                        transfer_func(ser, str(FILES_DIR / fname))
                                    # Refresh files and session after transfer
                                    files_list = sorted([p.name for p in FILES_DIR.iterdir() if p.is_file()])
                                    files_session = files_module.create_session(ser, use_ansi, files=files_list, base_dir=FILES_DIR)
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

                if mode == "URL":
                    # Delegate all URL behavior to the rsh_url module
                    if url_module:
                        try:
                            consumed, action = url_module.handle_input(url_session, line_str, ser, use_ansi)
                            if consumed:
                                if action == 'MENU':
                                    mode = 'MENU'
                                    show_main_menu(ser, use_ansi)
                                # consumed and handled by module; continue loop
                                continue
                        except Exception as e:
                            write(ser, f"\r\n*** URL module error: {e} ***\r\n")
                            wait_for_key(ser)
                            mode = "MENU"
                            show_main_menu(ser, use_ansi)
                            continue

                    # No module available - inform user and return to menu
                    write(ser, "\r\n*** URL module not available ***\r\n")
                    wait_for_key(ser)
                    mode = "MENU"
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
                                        result = paginate_lines(ser, lines, page_lines=22, quit_msg=True)
                                        if result == "QUIT":
                                            try:
                                                notes_list = sorted([p.name for p in NOTES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
                                                notes_session = notes_module.create_session(ser, use_ansi, notes=notes_list, base_dir=NOTES_DIR)
                                            except Exception:
                                                show_notes_menu(ser, notes_list, use_ansi)
                                            continue
                                    except Exception as e:
                                        write(ser, f"\r\n*** Error displaying note: {e} ***\r\n")
                                        wait_for_key(ser)
                                        try:
                                            notes_session = notes_module.create_session(ser, use_ansi, notes=notes_list, base_dir=NOTES_DIR)
                                        except Exception:
                                            show_main_menu(ser, use_ansi)
                                        continue
                                if isinstance(action, str) and action.startswith('SHOW_NOTE:'):
                                    fname = action.split(':',1)[1]
                                    path = NOTES_DIR / fname
                                    try:
                                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                                            lines = [ln.rstrip("\r\n") for ln in f.readlines()]
                                        clear_screen(ser, use_ansi)
                                        write(ser, "\r\n")
                                        result = paginate_lines(ser, lines, page_lines=22, quit_msg=True)
                                        if result == "QUIT":
                                            try:
                                                notes_list = sorted([p.name for p in NOTES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
                                                notes_session = notes_module.create_session(ser, use_ansi, notes=notes_list, base_dir=NOTES_DIR)
                                            except Exception:
                                                show_notes_menu(ser, notes_list, use_ansi)
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
                                    write(ser, "\r\nEnter note text. Type END on a line by itself to finish.\r\n")
                                    mode = "CREATE_NOTE"
                                    note_buffer = []
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
                # Note: inline create/delete note flows removed. rsh_notes.py must implement
                # any create/delete interactions. If rsh_notes is not available the hub
                # returns to the main menu (handled above).
                
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
                    # Render BBS menu via module if available, otherwise return to main menu
                    if bbs_module:
                        try:
                            bbs_session = bbs_module.create_session(ser, use_ansi, BBSS=BBSS, IPS=IPS, PORTS=PORTS)
                        except Exception:
                            show_main_menu(ser, use_ansi)
                    else:
                        show_main_menu(ser, use_ansi)
                else:
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
    threads = []
    for name, cfg in SERIAL_CONFIGS.items():
        t = threading.Thread(
            target=port_worker,
            args=(name, cfg),
            daemon=True
        )
        t.start()
        threads.append(t)

    # keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting.")
        os._exit(0)


if __name__ == "__main__":
    main()