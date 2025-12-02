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


def _render_menu(ser, sess, use_ansi=True):
    items = sess.get('bbss', [])
    if not items:
        _write(ser, "\r\nNo BBS entries configured.\r\n")
        _write(ser, "\r\nEnter Q to return to the main menu.\r\n")
        _write(ser, "Command: ")
        return 'DONE'

    if use_ansi:
        _write(ser, "\x1b[2J\x1b[H")
    else:
        _write(ser, "\r\n")

    _write(ser, "\r\nAvailable BBS Systems:\r\n\r\n")
    lines = two_column_list(items, left_pad=38)
    return _paginate_lines(ser, lines, page_lines=19, quit_msg=True)


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
        'bbss': BBSS or [],
        'ips': IPS or [],
        'ports': PORTS or [],
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
