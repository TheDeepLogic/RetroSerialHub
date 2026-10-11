"""
rsh_bbs.py - BBS directory and connection handling

This module provides BBS directory browsing and connection management for
the RetroSerialHub system. It handles:
- BBS directory display
- BBS connection management
- BBS connection state
- Input handling for BBS mode
"""

import socket
import time
from rsh_terminal import (
    clear_terminal_screen,
    format_numbered_list,
    terminal_columns,
)
from rsh_directory import save_directory


def _write(ser, s):
    ser.write(s.encode('ascii', errors='ignore'))


def _wait_for_key(ser, quit_msg=False):
    """Wait for a single non-CR/LF keypress and return it uppercased.

    If there are bytes already queued, discard any leading CR/LF characters
    so an old Enter doesn't immediately advance pagination. If a non-CR/LF
    byte is already queued, use it immediately.
    """
    if quit_msg:
        _write(ser, "\r\nPress any key to continue (Q to quit)...\r\n")
    else:
        _write(ser, "\r\nPress any key to continue...\r\n")

    # If there's buffered input, read it and check for a usable key
    try:
        avail = ser.in_waiting
    except Exception:
        avail = 0
    if avail:
        buf = ser.read(avail)
        # find first byte that isn't CR/LF
        for b in buf:
            if b not in (10, 13):
                try:
                    return bytes((b,)).decode(errors='ignore').upper()
                except Exception:
                    return ""
        # only CR/LF present -> fall through to blocking wait

    while True:
        if ser.in_waiting:
            ch = ser.read(1)
            try:
                if ch and ch not in (b"\r", b"\n"):
                    return ch.decode(errors='ignore').upper()
                # otherwise loop and keep waiting
            except Exception:
                return ""
        time.sleep(0.05)


def _paginate_lines(ser, lines, page_lines=19, quit_msg=True):
    count = 0
    total_lines = len(lines)
    displayed_lines = 0
    
    for ln in lines:
        _write(ser, ln + "\r\n")
        count += 1
        displayed_lines += 1
        if count >= page_lines and displayed_lines < total_lines:
            key = _wait_for_key(ser, quit_msg=quit_msg)
            if key == 'Q':
                return 'QUIT'
            count = 0
    
    # Only show command prompt at the end
    if displayed_lines >= total_lines:
        _write(ser, "\r\nCommand: ")
    
    return 'DONE'


def two_column_list(items, left_pad=38):
    return format_numbered_list(items, left_pad=left_pad)


def _two_column_pages(items, page_lines=19, left_pad=38, columns=80):
    if not items:
        return []

    pages = []
    page_size = page_lines if columns == 40 else 2 * page_lines
    for start in range(0, len(items), page_size):
        page_items = items[start:start + page_size]
        if columns == 40:
            pages.append([
                f"{start + index + 1:2d}] {str(item)[:35]}"
                for index, item in enumerate(page_items)
            ])
            continue
        left_items = page_items[:page_lines]
        right_items = page_items[page_lines:]
        lines = []

        for row, left_item in enumerate(left_items):
            left_number = start + row + 1
            left_text = f"{left_number:2d}] {left_item}"
            right_row = row
            if right_row < len(right_items):
                right_number = start + page_lines + right_row + 1
                right_text = f"{right_number:2d}] {right_items[right_row]}"
                lines.append(f"{left_text:<{left_pad}}{right_text}")
            else:
                lines.append(left_text)
        pages.append(lines)

    return pages


def _render_menu(ser, sess, use_ansi=True):
    clear_terminal_screen(ser, use_ansi)
    items = sess.get('bbss', [])
    if not items:
        _write(ser, "\r\nNo BBS entries configured.\r\n")
        _write(ser, "\r\nM=Manage directory, Q=Main menu\r\n")
        _write(ser, "Command: ")
        return 'DONE'

    columns = terminal_columns(ser)
    pages = _two_column_pages(
        items, page_lines=19, left_pad=38, columns=columns
    )
    for page_index, lines in enumerate(pages):
        _write(ser, "\r\nAvailable BBS Systems")
        if len(pages) > 1:
            _write(ser, " (Page %d/%d)" % (page_index + 1, len(pages)))
        _write(ser, ":\r\n\r\n")
        for line in lines:
            _write(ser, line + "\r\n")
        if page_index < len(pages) - 1:
            key = _wait_for_key(ser, quit_msg=True)
            if key == 'Q':
                return 'QUIT'
            clear_terminal_screen(ser, use_ansi)
    _write(ser, "\r\nM=Manage directory, Q=Main menu\r\n")
    _write(ser, "Command: ")
    return 'DONE'


def _render_manager(ser, sess, use_ansi=True, notice=None):
    clear_terminal_screen(ser, use_ansi)
    _write(ser, "\r\nManage Bulletin Board Directory\r\n\r\n")
    columns = terminal_columns(ser)
    if columns == 40:
        lines = [
            line
            for index, (name, host, port) in enumerate(
                zip(sess["bbss"], sess["ips"], sess["ports"]), start=1
            )
            for line in (f"{index:2d}] {name[:35]}", f"    {host[:29]}:{port}")
        ]
    else:
        lines = [
            f"{index:2d}] {name[:20]:<20} {host[:36]}:{port}"
            for index, (name, host, port) in enumerate(
                zip(sess["bbss"], sess["ips"], sess["ports"]), start=1
            )
        ]
    page_capacity = 18 if columns == 40 else 19
    pages = [
        lines[start:start + page_capacity]
        for start in range(0, len(lines), page_capacity)
    ]
    for page_index, page in enumerate(pages):
        if len(pages) > 1:
            _write(ser, f"Page {page_index + 1}/{len(pages)}\r\n")
        for line in page:
            _write(ser, line + "\r\n")
        if page_index < len(pages) - 1:
            if _wait_for_key(ser, quit_msg=True) == "Q":
                break
            clear_terminal_screen(ser, use_ansi)
    if notice:
        _write(ser, f"\r\n*** {notice} ***\r\n")
    _write(
        ser,
        "\r\nA=Add, E=Edit, D=Delete, Q=Return to directory\r\n",
    )
    _write(ser, "Command: ")


def start_directory_manager(sess, ser, use_ansi=True):
    sess["submode"] = "MANAGE"
    sess["manager_action"] = None
    _render_manager(ser, sess, use_ansi)


def _directory_snapshot(sess):
    return (
        list(sess["bbss"]),
        list(sess["ips"]),
        list(sess["ports"]),
    )


def _save_session_directory(sess, snapshot):
    entries = [
        {"name": name, "host": host, "port": port}
        for name, host, port in zip(
            sess["bbss"], sess["ips"], sess["ports"]
        )
    ]
    try:
        save_directory(entries)
    except OSError:
        sess["bbss"][:] = snapshot[0]
        sess["ips"][:] = snapshot[1]
        sess["ports"][:] = snapshot[2]
        raise


def _manager_error(ser, sess, use_ansi, message):
    sess["manager_action"] = None
    _render_manager(ser, sess, use_ansi, notice=message)


def handle_directory_manager_input(sess, line_str, ser, use_ansi=True):
    """Handle one BBS directory manager command or field."""
    text = line_str.strip()
    state = sess.get("manager_action")
    names, hosts, ports = sess["bbss"], sess["ips"], sess["ports"]

    if state is None:
        upper = text.upper()
        if upper == "Q":
            sess["submode"] = "BBS_MENU"
            _render_menu(ser, sess, use_ansi)
        elif upper == "A":
            sess["manager_action"] = "ADD_NAME"
            _write(ser, "\r\nNew entry name: ")
        elif upper == "E":
            sess["manager_action"] = "EDIT_INDEX"
            _write(ser, "\r\nEntry number to edit: ")
        elif upper == "D":
            sess["manager_action"] = "DELETE_INDEX"
            _write(ser, "\r\nEntry number to delete: ")
        else:
            _write(ser, "\r\nChoose A, E, D, or Q.\r\nCommand: ")
        return True

    if state == "ADD_NAME":
        if not text:
            return _manager_error(ser, sess, use_ansi, "Name cannot be empty")
        sess["manager_name"] = text
        sess["manager_action"] = "ADD_HOST"
        _write(ser, "\r\nHost or IP address: ")
    elif state == "ADD_HOST":
        if not text or any(character.isspace() for character in text):
            _write(ser, "Enter a valid host or IP address: ")
            return True
        sess["manager_host"] = text
        sess["manager_action"] = "ADD_PORT"
        _write(ser, "\r\nPort (1-65535): ")
    elif state == "ADD_PORT":
        try:
            port = int(text)
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            _write(ser, "Port must be from 1 to 65535: ")
            return True
        snapshot = _directory_snapshot(sess)
        names.append(sess["manager_name"])
        hosts.append(sess["manager_host"])
        ports.append(port)
        try:
            _save_session_directory(sess, snapshot)
        except OSError as exc:
            return _manager_error(ser, sess, use_ansi, str(exc))
        _write(ser, "\r\nBBS entry added.\r\n")
        sess["manager_action"] = None
        _render_manager(ser, sess, use_ansi)
    elif state in ("EDIT_INDEX", "DELETE_INDEX"):
        try:
            index = int(text) - 1
            if not 0 <= index < len(names):
                raise ValueError
        except ValueError:
            _write(ser, "Enter a valid entry number: ")
            return True
        sess["manager_index"] = index
        if state == "DELETE_INDEX":
            sess["manager_action"] = "DELETE_CONFIRM"
            _write(ser, f"\r\nDelete {names[index]}? (Y/N): ")
        else:
            sess["manager_action"] = "EDIT_NAME"
            _write(ser, f"\r\nNew name (Enter to keep {names[index]}): ")
    elif state == "DELETE_CONFIRM":
        if text.upper() not in ("Y", "N"):
            _write(ser, "Enter Y or N: ")
            return True
        if text.upper() == "N":
            sess["manager_action"] = None
            _render_manager(ser, sess, use_ansi)
            return True
        snapshot = _directory_snapshot(sess)
        index = sess["manager_index"]
        del names[index]
        del hosts[index]
        del ports[index]
        try:
            _save_session_directory(sess, snapshot)
        except OSError as exc:
            return _manager_error(ser, sess, use_ansi, str(exc))
        _write(ser, "\r\nBBS entry deleted.\r\n")
        sess["manager_action"] = None
        _render_manager(ser, sess, use_ansi)
    elif state == "EDIT_NAME":
        index = sess["manager_index"]
        if text:
            sess["edited_name"] = text
        else:
            sess["edited_name"] = names[index]
        sess["manager_action"] = "EDIT_HOST"
        _write(ser, f"\r\nNew host (Enter to keep {hosts[index]}): ")
    elif state == "EDIT_HOST":
        index = sess["manager_index"]
        if text and any(character.isspace() for character in text):
            _write(ser, "Host cannot contain whitespace: ")
            return True
        sess["edited_host"] = text or hosts[index]
        sess["manager_action"] = "EDIT_PORT"
        _write(ser, f"\r\nNew port (Enter to keep {ports[index]}): ")
    elif state == "EDIT_PORT":
        index = sess["manager_index"]
        try:
            port = ports[index] if not text else int(text)
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            _write(ser, "Port must be from 1 to 65535: ")
            return True
        snapshot = _directory_snapshot(sess)
        names[index] = sess["edited_name"]
        hosts[index] = sess["edited_host"]
        ports[index] = port
        try:
            _save_session_directory(sess, snapshot)
        except OSError as exc:
            return _manager_error(ser, sess, use_ansi, str(exc))
        _write(ser, "\r\nBBS entry updated.\r\n")
        sess["manager_action"] = None
        _render_manager(ser, sess, use_ansi)
    return True


def _connect_bbs(index, ser, BBSS, IPS, PORTS):
    """Establish connection to a BBS by index"""
    host, port = IPS[index], PORTS[index]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect((host, port))
        s.settimeout(None)
        _write(ser, "\r\nCONNECT\r\n")
        return s
    except Exception:
        _write(ser, f"\r\n*** Unable to connect to {host}:{port} ***\r\n")
        _write(ser, "NO CARRIER\r\n")
        _wait_for_key(ser)
        return None

def create_session(ser, use_ansi=True, BBSS=None, IPS=None, PORTS=None):
    """Initialize BBS module session"""
    sess = {
        'submode': 'BBS_MENU',
        'bbss': BBSS if BBSS is not None else [],
        'ips': IPS if IPS is not None else [],
        'ports': PORTS if PORTS is not None else [],
        'sock': None,
        'line_buffer': b""
    }
    _render_menu(ser, sess, use_ansi)
    return sess


def handle_input(sess, line_str, ser, use_ansi=True):
    """Handle input in BBS mode. Returns (consumed, action) tuple.
    
    consumed: True if input was handled
    action: String indicating action for hub:
        'MENU' - return to main menu
        'CONNECT_BBS:n' - connect to BBS index n
        None - no action needed
    """
    txt = line_str.strip()
    sock = sess.get('sock')
    
    # Always handle ATH if connected
    if sock and txt.upper() == "ATH":
        _write(ser, "\r\nDisconnecting...\r\n")
        try:
            sock.close()
        except Exception:
            pass
        sess['sock'] = None
        sess['line_buffer'] = b""
        _render_menu(ser, sess, use_ansi)
        return True, None

    # If connected, forward all input
    if sock:
        try:
            # Add to line buffer for ATH detection
            for byte in txt.encode('ascii', errors='ignore'):
                if byte in (10, 13):  # LF or CR
                    if sess['line_buffer']:
                        try:
                            s = sess['line_buffer'].decode(errors='ignore').strip().upper()
                        except Exception:
                            s = ""
                        if s == 'ATH':
                            # local hangup request
                            _write(ser, "\r\nDisconnecting...\r\n")
                            try:
                                sock.close()
                            except Exception:
                                pass
                            sess['sock'] = None
                            sess['line_buffer'] = b""
                            _render_menu(ser, sess, use_ansi)
                            return True, None
                        sess['line_buffer'] = b""
                    else:
                        # ignore stray CR/LF
                        pass
                else:
                    sess['line_buffer'] += bytes((byte,))

            # Forward the line
            sock.sendall(txt.encode('ascii', errors='ignore') + b"\r\n")
            return True, None
        except Exception:
            _write(ser, "\r\n*** Connection lost ***\r\n")
            try:
                sock.close()
            except Exception:
                pass
            sess['sock'] = None
            sess['line_buffer'] = b""
            _render_menu(ser, sess, use_ansi)
            return True, None

    # Not connected - handle menu commands
    if txt == "":
        result = _render_menu(ser, sess, use_ansi)
        if result == 'QUIT':
            return True, 'MENU'
        return True, None

    upper = txt.upper()
    if upper == 'Q':
        return True, 'MENU'

    try:
        num = int(txt)
        if 1 <= num <= len(sess.get('bbss', [])):
            # Connect immediately if possible
            sock = _connect_bbs(num-1, ser, sess['bbss'], sess['ips'], sess['ports'])
            if sock:
                sess['sock'] = sock
                sess['line_buffer'] = b""
                return True, None
            # Otherwise let the hub try to handle it
            return True, f'CONNECT_BBS:{num-1}'
        else:
            _write(ser, "Invalid BBS number\r\n")
            _write(ser, "Command: ")
            return True, None
    except ValueError:
        _write(ser, "Invalid command\r\n")
        _write(ser, "Command: ")
        return True, None
