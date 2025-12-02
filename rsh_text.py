"""
rsh_text.py - Text library viewer

This module provides text file browsing and viewing functionality for
the RetroSerialHub system. It handles:
- Text file listing
- File selection and reading
- Text display with pagination
- Error handling and recovery

All text functionality is self-contained in this module to keep the hub clean.
"""

import time
import pathlib


def _write(ser, s):
    """Write string to serial port encoded as ASCII"""
    ser.write(s.encode('ascii', errors='ignore'))


def _clear_screen(ser, use_ansi=True):
    """Clear the terminal screen"""
    if use_ansi:
        _write(ser, "\x1b[2J\x1b[H")  # ANSI clear screen + home cursor
    else:
        _write(ser, "\r\n")  # Simple newline for non-ANSI terminals


def _wait_for_key(ser):
    """Wait for a keypress"""
    while True:
        if ser.in_waiting:
            ch = ser.read(1)
            try:
                return ch.decode(errors='ignore').upper()
            except Exception:
                return ""
        time.sleep(0.05)


def _paginate_lines(ser, lines, page_lines=22, quit_msg=True):
    """Display lines with pagination"""
    count = 0
    for ln in lines:
        _write(ser, ln + "\r\n")
        count += 1
        if count >= page_lines:
            if quit_msg:
                _write(ser, "\r\nPress any key to continue (Q to quit)...\r\n")
            else:
                _write(ser, "\r\nPress any key to continue...\r\n")
            key = _wait_for_key(ser)
            if key == "Q":
                return "QUIT"
            count = 0
    # Only pause at EOF if requested
    if quit_msg:
        _write(ser, "\r\nPress any key to continue (Q to quit)...\r\n")
        key = _wait_for_key(ser)
        if key == "Q":
            return "QUIT"
    return "DONE"


def _read_text_file(path):
    """Read a text file and return its lines"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return [ln.rstrip("\r\n") for ln in f.readlines()]


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


def create_session(ser, use_ansi=True, files=None, base_dir=None):
    sess = {
        'files': list(files) if files else [],
        'page_idx': 0,
        'base_dir': base_dir,
    }
    _render_menu(ser, sess)
    return sess


def _render_menu(ser, sess):
    items = sess.get('files', [])
    if not items:
        _write(ser, "\r\nNo text files available.\r\n")
        _write(ser, "\r\nEnter Q to return to the main menu.\r\n")
        _write(ser, "Command: ")
        return

    lines = two_column_list(items, left_pad=38)
    _write(ser, "\r\nText library:\r\n\r\n")
    for ln in lines:
        _write(ser, ln + "\r\n")
    _write(ser, "\r\nEnter the number to read the file. Enter Q to return to the main menu.\r\n")
    _write(ser, "Command: ")


def handle_input(sess, line_str, ser, use_ansi=True):
    """Handle input in text mode. Returns (consumed, action) tuple.
    
    consumed: True if input was handled
    action: String indicating action for hub:
        'MENU' - return to main menu
        None - no action needed
    """
    txt = line_str.strip()
    
    # Handle quit
    if txt.upper() == 'Q':
        return True, 'MENU'
    
    # Handle empty line - redraw menu
    if not txt:
        _render_menu(ser, sess)
        return True, None
        
    # Handle numeric selection
    try:
        num = int(txt)
        files = sess.get('files', [])
        if 1 <= num <= len(files):
            fname = files[num-1]
            base = sess.get('base_dir')
            if base:
                path = base / fname
            else:
                path = fname
                
            try:
                # Read and display the file
                lines = _read_text_file(path)
                _clear_screen(ser, use_ansi)
                _write(ser, "\r\n")
                result = _paginate_lines(ser, lines, page_lines=22, quit_msg=True)
                
                # Refresh file list and redraw menu
                if base:
                    new_files = sorted([p.name for p in base.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
                    sess['files'] = new_files
                
                if result == "QUIT":
                    _render_menu(ser, sess)
                else:
                    _render_menu(ser, sess)
                    
            except Exception as e:
                _write(ser, f"\r\n*** Error reading file: {e} ***\r\n")
                while ser.in_waiting:  # Clear any pending input
                    ser.read()
                _wait_for_key(ser)
                _render_menu(ser, sess)
                
            return True, None
            
        else:
            _write(ser, "Invalid file number\r\n")
            _write(ser, "Command: ")
            return True, None
            
    except ValueError:
        _write(ser, "Invalid command\r\n")
        _write(ser, "Command: ")
        return True, None
