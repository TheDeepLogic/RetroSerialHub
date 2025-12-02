"""
rsh_notes.py

Pluggable Notes menu module for RETRO_SERIAL_HUB.

Interface:
- create_session(ser, use_ansi=True, notes=None) -> session_object
- handle_input(session, line_str, ser, use_ansi=True) -> (consumed:bool, action_or_None)

Actions returned to core:
- 'SHOW_NOTE:<filename>' -> core opens and paginates the note
- 'CREATE' -> core should switch to CREATE_NOTE mode to accept note text
- 'DELETE:<filename>' -> core should prompt for confirmation and delete
- 'MENU' -> return to main menu

This module renders the notes list and returns high-level actions to the core.
"""


def _write(ser, s):
    ser.write(s.encode('ascii', errors='ignore'))


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


def create_session(ser, use_ansi=True, notes=None, base_dir=None):
    sess = {
        'notes': list(notes) if notes else [],
        'base_dir': base_dir,
    }
    _render_menu(ser, sess)
    return sess


def _render_menu(ser, sess):
    items = sess.get('notes', [])
    clear = "\r\n"
    if not items:
        _write(ser, f"{clear}No notes available.\r\n")
        _write(ser, "\r\nC=Create, Q=Quit\r\n")
        _write(ser, "Command: ")
        return

    lines = two_column_list(items, left_pad=38)
    _write(ser, "\r\nNotes:\r\n\r\n")
    for ln in lines:
        _write(ser, ln + "\r\n")
    _write(ser, "\r\nEnter number to read, C=Create, D=Delete, Q=Quit\r\n")
    _write(ser, "Command: ")


def handle_input(sess, line_str, ser, use_ansi=True):
    txt = line_str.strip()
    if txt == "":
        _render_menu(ser, sess)
        return True, None
    upper = txt.upper()
    if upper == 'Q':
        return True, 'MENU'
    if upper == 'C':
        return True, 'CREATE'
    if upper.startswith('D') and len(txt) > 1:
        # allow 'D 3' or 'D3' to delete specific index
        rest = txt[1:].strip()
        try:
            num = int(rest)
            if 1 <= num <= len(sess.get('notes', [])):
                fname = sess['notes'][num-1]
                return True, f'DELETE:{fname}'
            else:
                _write(ser, "Invalid note number\r\n")
                _write(ser, "Command: ")
                return True, None
        except ValueError:
            _write(ser, "Invalid delete syntax\r\n")
            _write(ser, "Command: ")
            return True, None
    # numeric selection
    try:
        num = int(txt)
        if 1 <= num <= len(sess.get('notes', [])):
            fname = sess['notes'][num-1]
            # try to open and return lines so core can paginate
            try:
                base = sess.get('base_dir')
                if base:
                    p = base / fname
                else:
                    p = fname
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = [ln.rstrip('\r\n') for ln in f.readlines()]
                return True, ('SHOW_NOTE', lines)
            except Exception:
                return True, f'SHOW_NOTE:{fname}'
        else:
            _write(ser, "Invalid note number\r\n")
            _write(ser, "Command: ")
            return True, None
    except ValueError:
        _write(ser, "Invalid command\r\n")
        _write(ser, "Command: ")
        return True, None
