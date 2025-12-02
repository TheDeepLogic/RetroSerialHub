"""
rsh_wargames.py

Pluggable Wargames module for RETRO_SERIAL_HUB.

Interface:
- create_session(ser, use_ansi) -> session_object
- handle_input(session, line_str, ser, use_ansi) -> (consumed:bool, new_mode_or_None)

Session object can be any Python object (dict recommended) and will be passed back to handle_input
so the module can keep per-session state (e.g., which subsystem the user is in).

This file implements the current WARGAMES behavior extracted from the monolith.
"""

import time

GAMES_LIST = [
    "FALKEN'S MAZE",
    "BLACK JACK",
    "GIN RUMMY",
    "HEARTS",
    "BRIDGE",
    "CHECKERS",
    "CHESS",
    "POKER",
    "FIGHTER COMBAT",
    "GUERRILLA ENGAGEMENT",
    "DESERT WARFARE",
    "AIR-TO-GROUND ACTIONS",
    "THEATERWIDE TACTICAL WARFARE",
    "THEATERWIDE BIOTOXIC AND CHEMICAL WARFARE",
]


def _write(ser, s):
    ser.write(s.encode('ascii', errors='ignore'))


def create_session(ser, use_ansi=True, **kwargs):
    """Create and initialize a session. Returns a session dict."""
    sess = {
        'submode': 'CPM',  # CPM, DIALER, TERM, TERM_SCHOOL, TERM_AIRLINE, TERM_BANK, TERM_PROTO
        'student_name': '',
    }
    # Print header
    _write(ser, "IMSAI 8080 CP/M version 1.0\r\n")
    _write(ser, "(c) 1974 Digital Research Inc.\r\n")
    _write(ser, "The WarGames plugin is a proof-of-concept and is very much unfinished.\r\n\r\n")
    _write(ser, "A>")
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
        if cmd == '':
            _write(ser, "A>")
            return True, None
        lower = cmd.lower()
        if lower == 'dir':
            _write(ser, "\r\nA: DIALER   COM\r\n")
            _write(ser, "A: TERM     COM\r\n")
            _write(ser, "\r\nA>")
            return True, None
        if lower in ('dialer', 'dialer.com', 'a:dialer', 'a:dialer.com'):
            sess['submode'] = 'DIALER'
            _enter_dialer(ser)
            return True, None
        if lower in ('term', 'term.com', 'a:term', 'a:term.com'):
            sess['submode'] = 'TERM'
            _enter_term(ser)
            return True, None
        # unknown
        _write(ser, "\r\nBad command or file name\r\n")
        _write(ser, "\r\nA>")
        return True, None

    # Dialer: any key returns to CPM prompt
    if sess['submode'] == 'DIALER':
        sess['submode'] = 'CPM'
        _write(ser, "\r\n")
        # Reprint CPM header/prompt
        _write(ser, "IMSAI 8080 CP/M version 1.0\r\n")
        _write(ser, "(c) 1974 Digital Research Inc.\r\n\r\n")
        _write(ser, "A>")
        return True, None

    # Terminal menu handling
    if sess['submode'] == 'TERM':
        if upper == '1':
            sess['submode'] = 'TERM_SCHOOL'
            _write(ser, "\r\nENTER STUDENT NAME: ")
            return True, None
        if upper == '2':
            sess['submode'] = 'TERM_AIRLINE'
            _write(ser, "\r\nPAN AM AIRLINES RESERVATION SYSTEM\r\n")
            _write(ser, "LOGIN: ")
            return True, None
        if upper == '3':
            sess['submode'] = 'TERM_BANK'
            _write(ser, "\r\nWELCOME TO FIRST NATIONAL BANK\r\n\r\n")
            _write(ser, "LOGIN: ")
            return True, None
        if upper == '4':
            sess['submode'] = 'TERM_PROTO'
            _write(ser, "\r\nGREETINGS PROFESSOR FALKEN.\r\n\r\n")
            _write(ser, "> ")
            return True, None
        # fallback
        _write(ser, "\r\nInvalid selection. Press any key to return to CP/M.\r\n")
        sess['submode'] = 'CPM'
        _write(ser, "IMSAI 8080 CP/M version 1.0\r\n")
        _write(ser, "(c) 1974 Digital Research Inc.\r\n\r\n")
        _write(ser, "A>")
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
        _write(ser, "A>")
        return True, None

    if sess['submode'] == 'TERM_BANK':
        _write(ser, "\r\nACCESS DENIED\r\n")
        sess['submode'] = 'CPM'
        _write(ser, "IMSAI 8080 CP/M version 1.0\r\n")
        _write(ser, "(c) 1974 Digital Research Inc.\r\n\r\n")
        _write(ser, "A>")
        return True, None

    # Protovision prompt
    if sess['submode'] == 'TERM_PROTO':
        lower = cmd.lower()
        if lower == 'list games':
            _write(ser, "\r\n")
            for g in GAMES_LIST:
                _write(ser, g + "\r\n")
            _write(ser, "\r\n> ")
            return True, None
        # default response
        _write(ser, "\r\nI'M NOT SURE I UNDERSTAND.\r\n\r\n> ")
        return True, None

    # default: not handled
    return False, None


# helper printers
def _enter_dialer(ser):
    _write(ser, "\r\nTO SCAN FOR CARRIER TONES, PLEASE LIST\r\n")
    _write(ser, "DESIRED AREA CODES AND PREFIXES\r\n\r\n")
    _write(ser, "     AREA           AREA           AREA           AREA\r\n")
    _write(ser, "CODE PRFX NUMBER  CODE PRFX NUMBER  CODE PRFX NUMBER  CODE PRFX NUMBER\r\n\r\n")
    _write(ser, "(311) 399-0001   (311) 437        (311) 767\r\n")
    _write(ser, "(311) 399-0002\r\n")
    _write(ser, "(311) 399-0003\r\n")
    _write(ser, "\r\nDIALING...")


def _enter_term(ser):
    _write(ser, "\r\nTERMINAL PROGRAM v1.0\r\n\r\n")
    _write(ser, "1] School System\r\n")
    _write(ser, "2] Airline System\r\n")
    _write(ser, "3] Banking System\r\n")
    _write(ser, "4] Protovision\r\n\r\n")
    _write(ser, "Select system (1-4): ")