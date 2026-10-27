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

import pathlib
import re
from tempfile import NamedTemporaryFile

from rsh_terminal import clear_terminal_screen, format_numbered_list, terminal_columns, terminal_rows


def _write(ser, s):
    ser.write(s.encode('ascii', errors='ignore'))


def two_column_list(items, left_pad=38):
    return format_numbered_list(items, left_pad=left_pad)


def create_session(ser, use_ansi=True, notes=None, base_dir=None, notice=None):
    sess = {
        'notes': list(notes) if notes else [],
        'base_dir': base_dir,
        'use_ansi': use_ansi,
        'notice': notice,
    }
    _render_menu(ser, sess)
    return sess


def _render_menu(ser, sess):
    clear_terminal_screen(ser, sess.get('use_ansi', True))
    items = sess.get('notes', [])
    if not items:
        _write(ser, "No notes available.\r\n")
        _write(ser, "\r\nC=Create, P=Save Host Clipboard as Note, Q=Quit\r\n")
        if sess.get('notice'):
            _write(ser, f"\r\n{sess['notice']}\r\n")
        _write(ser, "\r\nCommand: ")
        return

    size=max(1,min(8,terminal_rows(ser)-12))
    sess['page_size']=size
    sess['page'] = min(sess.get('page',0),max(0,(len(items)-1)//size))
    start = sess['page']*size
    lines = format_numbered_list(items[start:start+size], terminal_columns(ser))
    if start:
        lines = [re.sub(r'(\d+)(?=\])',lambda match: str(int(match[0])+start),line) for line in lines]
    _write(ser, "\r\nNotes:\r\n\r\n")
    for ln in lines:
        _write(ser, ln + "\r\n")

    _write(ser, "\r\nNumber=Read C=Create C#=Copy clipboard\r\nP=Paste clipboard D#=Delete O=More\r\nN/B=Page Q=Back\r\n")
    if sess.get('notice'):
        _write(ser, f"\r\n{sess['notice']}\r\n")
    _write(ser, "\r\nCommand: ")


def handle_input(sess, line_str, ser, use_ansi=True):
    txt = line_str.strip()
    if txt == "":
        if sess.get("editing"):
            _render_editor(ser,sess)
            return True,None
        sess.pop("note_operation",None)
        _render_menu(ser, sess)
        return True, None
    upper = txt.upper()
    base = pathlib.Path(sess['base_dir']) if sess.get('base_dir') else pathlib.Path('.')
    if sess.get('editing'):
        if upper == 'Q':
            sess.pop('editing'); sess.pop('edit_lines', None)
            _render_menu(ser,sess); return True,None
        try:
            operation = txt.split(maxsplit=1)[0].lower() if txt else ''
            lines = sess['edit_lines']
            if operation == 'save':
                path = base / sess['editing']
                if path.read_text(encoding='utf-8') != sess['edit_original']:
                    raise ValueError('Note changed in another session. Cancel and reopen before saving.')
                with NamedTemporaryFile(mode='w',encoding='utf-8',dir=base,suffix='.tmp',delete=False) as output:
                    output.write('\n'.join(lines) + '\n')
                    temporary = pathlib.Path(output.name)
                temporary.replace(path)
                sess.pop('editing'); sess.pop('edit_lines'); sess['notice'] = 'Note saved.'
                _render_menu(ser,sess); return True,None
            if operation in ('n','b'):
                page = sess.get('edit_page',0) + (1 if operation == 'n' else -1)
                sess['edit_page'] = max(0,min(page,max(0,(len(lines)-1)//8)))
            elif operation == 'append':
                lines.append(txt.split(maxsplit=1)[1] if len(txt.split(maxsplit=1)) > 1 else '')
            elif operation in ('replace','delete'):
                parts = txt.split(maxsplit=2)
                index = int(parts[1])-1
                if not 0 <= index < len(lines):
                    raise ValueError('Invalid line number.')
                if operation == 'delete':
                    lines.pop(index)
                else:
                    lines[index] = parts[2] if len(parts) > 2 else ''
            elif operation:
                raise ValueError('replace <line> <text>, append <text>, delete <line>, save, N/B=Page, Q=Cancel')
            _render_editor(ser,sess)
        except (ValueError,IndexError,OSError) as exc:
            _write(ser,str(exc) + '\r\nEdit: ')
        return True,None
    if sess.pop('more',False):
        if upper == 'Q':
            _render_menu(ser,sess); return True,None
        if upper == 'A':
            upper = 'ALL'
    if upper == 'O':
        clear_terminal_screen(ser,sess.get('use_ansi',True))
        sess['more'] = True
        _write(ser,'\r\nE#=Edit R#=Rename X#=Export\r\nF text=Search A=All notes Q=Back\r\nCommand: ')
        return True,None
    if upper in ('N','B'):
        sess['page'] = max(0,min(sess.get('page',0)+(1 if upper == 'N' else -1),max(0,(len(sess.get('notes',[]))-1)//sess.get('page_size',8))))
        _render_menu(ser,sess); return True,None
    if sess.get('note_operation'):
        operation, name = sess.pop('note_operation')
        try:
            if txt and upper != 'Q':
                path = base / name
                if operation == 'rename':
                    new_name = pathlib.Path(txt).name
                    if new_name != txt or not new_name or new_name in ('.','..'):
                        raise ValueError('Use a filename, not a path.')
                    if not new_name.lower().endswith('.txt'):
                        new_name += '.txt'
                    destination = base / new_name
                    if destination.exists():
                        raise ValueError('Destination already exists.')
                    path.rename(destination)
                else:
                    with pathlib.Path(txt).expanduser().open('xb') as output:
                        output.write(path.read_bytes())
                sess['notes'] = sorted(p.name for p in base.glob('*.txt'))
                sess['notice'] = 'Note ' + ('renamed.' if operation == 'rename' else 'exported.')
        except (OSError,ValueError) as exc:
            sess['notice'] = str(exc)
        _render_menu(ser,sess); return True,None
    if upper.startswith('F '):
        query = txt[2:].casefold()
        sess['notes'] = [p.name for p in sorted(base.glob('*.txt'))
                         if query in p.name.casefold() or (p.stat().st_size <= 1024*1024 and query in p.read_text(encoding='utf-8',errors='replace').casefold())]
        _render_menu(ser,sess); return True,None
    if upper == 'ALL':
        sess['notes'] = sorted(p.name for p in base.glob('*.txt'))
        _render_menu(ser,sess); return True,None
    match = re.fullmatch(r'([ERX])\s*(\d+)',upper)
    if match:
        number = int(match[2])-1
        if not 0 <= number < len(sess.get('notes',[])):
            _write(ser,'Invalid note number.\r\nCommand: '); return True,None
        name = sess['notes'][number]
        if match[1] == 'E':
            try:
                original = (base / name).read_text(encoding='utf-8')
            except (OSError, UnicodeError) as exc:
                sess['notice'] = f'Cannot edit note: {exc}'
                _render_menu(ser,sess)
                return True,None
            sess['editing'] = name
            sess['edit_original'] = original
            sess['edit_lines'] = sess['edit_original'].splitlines()
            sess['edit_page'] = 0
            _render_editor(ser,sess)
        else:
            sess['note_operation'] = ('rename' if match[1] == 'R' else 'export',name)
            _write(ser,'New filename: ' if match[1] == 'R' else 'New host output path: ')
        return True,None
    if upper == 'Q':
        return True, 'MENU'
    if upper == 'C':
        return True, 'CREATE'
    if upper == 'P':
        return True, 'PASTE_CLIPBOARD'
    if upper.startswith('C') and len(txt) > 1:
        rest = txt[1:].strip()
        try:
            num = int(rest)
        except ValueError:
            num = 0
        if 1 <= num <= len(sess.get('notes', [])):
            return True, ('COPY_TO_CLIPBOARD', sess['notes'][num - 1])
        _write(ser, "Invalid note number for clipboard copy\r\n")
        _write(ser, "\r\nCommand: ")
        return True, None
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
                _write(ser, "\r\nCommand: ")
                return True, None
        except ValueError:
            _write(ser, "Invalid delete syntax\r\n")
            _write(ser, "\r\nCommand: ")
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
            _write(ser, "\r\nCommand: ")
            return True, None
    except ValueError:
        _write(ser, "Invalid command\r\n")
        _write(ser, "\r\nCommand: ")
        return True, None


def _render_editor(ser,sess):
    clear_terminal_screen(ser,sess.get('use_ansi',True))
    start = sess.get('edit_page',0)*8
    for index,line in enumerate(sess['edit_lines'][start:start+8],start+1):
        # Long lines are previewed; replacing a line retains all typed text.
        width = terminal_columns(ser)-len(str(index))-3
        _write(ser,f'{index}: {line[:width]}\r\n')
    _write(ser,'\r\nreplace # text / append text / delete #\r\nsave / N=Next B=Previous Q=Cancel\r\n\r\nEdit: ')
