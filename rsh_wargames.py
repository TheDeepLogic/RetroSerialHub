"""
rsh_wargames.py

Pluggable Wargames module for RETRO_SERIAL_HUB.

Interface:
- create_session(ser, use_ansi) -> session_object
- handle_input(session, line_str, ser, use_ansi) -> (consumed:bool, new_mode_or_None)

Session object can be any Python object (dict recommended) and will be passed back to handle_input
so the module can keep per-session state (e.g., which subsystem the user is in).

The IMSAI shell delegates the simulated WOPR terminal to rsh_joshua.
"""

import re
import rsh_cpm as cpm
import rsh_joshua as joshua
from rsh_terminal import clear_terminal_screen

GAMES_LIST = joshua.GAMES


def _write(ser, s):
    ser.write(s.encode('ascii', errors='ignore'))


def create_session(ser, use_ansi=True, **kwargs):
    """Create and initialize a session. Returns a session dict."""
    clear_terminal_screen(ser, use_ansi)
    sess = {
        'submode': 'CPM',  # CPM, DIALER, TERM, TERM_SCHOOL, TERM_AIRLINE, TERM_BANK, TERM_PROTO
        'cpm_drive': 'A',
        'cpm_disks': cpm.new_disks(),
        'student_name': '',
        'joshua': joshua.new_state(),
        'dialed': [],
    }
    # Print header
    _write(ser, "IMSAI 8080 CP/M version 1.0\r\n")
    _write(ser, "(c) 1974 Digital Research Inc.\r\n")
    _write(ser, "64K RAM SYSTEM   2 DISK DRIVES\r\nHELP for commands. ATM returns to the hub.\r\n\r\n")
    cpm.prompt(sess, ser)
    return sess


def handle_input(sess, line_str, ser, use_ansi=True):
    """
    Handle a line of input. Returns (consumed, new_mode)
    consumed=True if WARGAMES handled the input and printed output.
    new_mode can be a string like 'MENU' to tell the core to switch modes.
    """
    cmd = line_str.strip()
    upper = cmd.upper()

    # Global ATM handled in core; this module doesn't handle ATM

    # CPM prompt
    if sess['submode'] == 'CPM':
        program = cpm.handle(sess, cmd, ser, use_ansi)
        if program == 'MENU':
            return True, 'MENU'
        if program == 'DIALER':
            sess['submode'] = 'DIALER'
            _enter_dialer(ser, use_ansi)
        elif program == 'TERM':
            sess['submode'] = 'TERM'
            _enter_term(ser, use_ansi)
        return True, None

    # The dialer scans fictional records; no host modem or network is used.
    if sess['submode'] == 'DIALER':
        if upper in ('Q', 'QUIT', 'EXIT'):
            sess['submode'] = 'CPM'
            _write(ser, "\r\n")
            cpm.prompt(sess, ser)
        elif cmd:
            digits = re.sub(r'[^0-9]', '', cmd)
            if len(digits) not in (3, 6, 7, 10):
                joshua.emit(ser, "\nENTER AN AREA CODE, PREFIX, OR PHONE NUMBER.")
                _write(ser, "SCAN: ")
            else:
                sess['dialed'] = ['(311) 437-1083 SCHOOL', '(311) 936-2364 AIRLINE',
                                  '(311) 399-0003 BANK', '(311) 767-7305 UNKNOWN']
                joshua.emit(ser, "\nSCANNING LOCAL SIMULATION RECORDS\n" + "\n".join(sess['dialed']) +
                            "\nSCAN COMPLETE. USE TERM TO CONNECT.")
                sess['submode'] = 'CPM'
                cpm.prompt(sess, ser)
        else:
            sess['submode'] = 'CPM'
            _write(ser, "\r\n")
            cpm.prompt(sess, ser)
        return True, None

    # Terminal menu handling
    if sess['submode'] == 'TERM':
        selection = {'3114371083': '1', '3119362364': '2', '3113990003': '3', '3117677305': '4'}.get(re.sub(r'[^0-9]', '', cmd), upper)
        if selection == '1':
            sess['submode'] = 'TERM_SCHOOL'
            _write(ser, "\r\nENTER STUDENT NAME: ")
            return True, None
        if selection == '2':
            sess['submode'] = 'TERM_AIRLINE'
            _write(ser, "\r\nPAN AM AIRLINES RESERVATION SYSTEM\r\n")
            _write(ser, "LOGIN: ")
            return True, None
        if selection == '3':
            sess['submode'] = 'TERM_BANK'
            _write(ser, "\r\nWELCOME TO FIRST NATIONAL BANK\r\n\r\n")
            _write(ser, "LOGIN: ")
            return True, None
        if selection == '4':
            sess['submode'] = 'TERM_PROTO'
            joshua.connect(sess, ser)
            return True, None
        # fallback
        _write(ser, "\r\nInvalid selection. Press any key to return to CP/M.\r\n")
        sess['submode'] = 'CPM'
        _write(ser, "IMSAI 8080 CP/M version 1.0\r\n")
        _write(ser, "(c) 1974 Digital Research Inc.\r\n\r\n")
        cpm.prompt(sess, ser)
        return True, None

    # School: receive student name then show grades
    if sess['submode'] == 'TERM_SCHOOL':
        name = cmd
        if name:
            sess['student_name'] = name
            _write(ser, "\r\nENTER STUDENT NAME: " + name + "\r\n\r\n")
            _write(ser, "ASS #  COURSE TITLE                 GRADE    TEACH\r\n")
            _write(ser, "--------------------------------------------\r\n")
            _write(ser, "202   BIOLOGY 2                     D       LIGGE\r\n")
            _write(ser, "314   ENGLISH 11B                   C       TURMA\r\n")
            _write(ser, "\r\nPress any key to return to CP/M.\r\n")
            sess['submode'] = 'CPM'
            return True, None
        # if empty input, prompt again
        _write(ser, "ENTER STUDENT NAME: ")
        return True, None

    # Airline/login – just deny and return to CPM on any input
    if sess['submode'] == 'TERM_AIRLINE':
        _write(ser, "\r\nACCESS DENIED\r\n")
        sess['submode'] = 'CPM'
        _write(ser, "IMSAI 8080 CP/M version 1.0\r\n")
        _write(ser, "(c) 1974 Digital Research Inc.\r\n\r\n")
        cpm.prompt(sess, ser)
        return True, None

    if sess['submode'] == 'TERM_BANK':
        _write(ser, "\r\nACCESS DENIED\r\n")
        sess['submode'] = 'CPM'
        _write(ser, "IMSAI 8080 CP/M version 1.0\r\n")
        _write(ser, "(c) 1974 Digital Research Inc.\r\n\r\n")
        cpm.prompt(sess, ser)
        return True, None

    # Keep Joshua state on hangup so reconnecting can resume the game.
    if sess['submode'] == 'TERM_PROTO':
        joshua.handle(sess, cmd, ser, use_ansi)
        return True, None

    # default: not handled
    return False, None


# helper printers
def _enter_dialer(ser, use_ansi=True):
    clear_terminal_screen(ser, use_ansi)
    _write(ser, "\r\nTO SCAN FOR CARRIER TONES, PLEASE LIST\r\n")
    _write(ser, "DESIRED AREA CODES AND PREFIXES\r\n\r\n")
    joshua.emit(ser, "SCAN AN AREA CODE OR PREFIX.\nEXAMPLE: 311 OR 311767\nQ RETURNS TO CP/M.")
    _write(ser, "SCAN: ")



def _enter_term(ser, use_ansi=True):
    clear_terminal_screen(ser, use_ansi)
    _write(ser, "\r\nTERMINAL PROGRAM v1.0\r\n\r\n")
    _write(ser, "1] School System\r\n")
    _write(ser, "2] Airline System\r\n")
    _write(ser, "3] Banking System\r\n")
    _write(ser, "4] Protovision / Unknown Carrier\r\n\r\n")
    _write(ser, "Select system (1-4) or phone number: ")

def poll(sess, ser, use_ansi=True):
    """Advance the active terminal display without blocking other sessions."""
    if sess and sess.get('submode') == 'TERM_PROTO':
        joshua.poll(sess, ser, use_ansi)


def stop_speech(sess):
    joshua.stop_speech(sess)
