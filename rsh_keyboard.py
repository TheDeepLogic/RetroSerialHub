"""Host keyboard injection for the serial keyboard bridge."""

import ctypes
import importlib
import sys
from ctypes import wintypes


KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
SPECIAL_KEYS = {
    "ENTER": 0x0D,
    "BACKSPACE": 0x08,
    "TAB": 0x09,
}


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KeybdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [
        ("mi", _MouseInput),
        ("ki", _KeybdInput),
        ("hi", ctypes.c_byte * 8),
    ]


class _Input(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _InputUnion),
    ]


def _send_keyboard_input(keyboard_input):
    if sys.platform != "win32":
        raise OSError("The native keyboard injector is supported only on Windows.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    send_input = user32.SendInput
    send_input.argtypes = (
        wintypes.UINT,
        ctypes.POINTER(_Input),
        ctypes.c_int,
    )
    send_input.restype = wintypes.UINT

    event = _Input(INPUT_KEYBOARD, _InputUnion(ki=keyboard_input))
    if send_input(1, ctypes.byref(event), ctypes.sizeof(_Input)) != 1:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, "Windows could not inject a keyboard event.")


def _send_unicode_character(character):
    scan_code = ord(character)
    _send_keyboard_input(
        _KeybdInput(0, scan_code, KEYEVENTF_UNICODE, 0, 0)
    )
    _send_keyboard_input(
        _KeybdInput(
            0, scan_code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0
        )
    )


def _send_special_key(key_name):
    virtual_key = SPECIAL_KEYS[key_name]
    _send_keyboard_input(_KeybdInput(virtual_key, 0, 0, 0, 0))
    _send_keyboard_input(
        _KeybdInput(virtual_key, 0, KEYEVENTF_KEYUP, 0, 0)
    )


def _pynput_senders():
    try:
        keyboard = importlib.import_module("pynput.keyboard")
    except ImportError as exc:
        raise OSError(
            "The keyboard bridge on macOS and Linux requires pynput. "
            "Install it with: python -m pip install pynput"
        ) from exc

    controller = keyboard.Controller()
    special_keys = {
        "ENTER": keyboard.Key.enter,
        "BACKSPACE": keyboard.Key.backspace,
        "TAB": keyboard.Key.tab,
    }

    def send_character(character):
        controller.type(character)

    def send_key(key_name):
        key = special_keys[key_name]
        controller.press(key)
        controller.release(key)

    return send_character, send_key


class KeyboardBridge:
    """Translate serial ASCII input to host keyboard events."""

    def __init__(self, send_character=None, send_key=None):
        if sys.platform == "win32":
            default_character_sender = _send_unicode_character
            default_key_sender = _send_special_key
        elif sys.platform == "darwin" or sys.platform.startswith("linux"):
            default_character_sender, default_key_sender = _pynput_senders()
        else:
            raise OSError(
                f"The keyboard bridge is not supported on {sys.platform}."
            )
        self._send_character = send_character or default_character_sender
        self._send_key = send_key or default_key_sender
        self._skip_line_feed = False

    def feed(self, data):
        """Inject data as keyboard input. Ctrl+X, Escape, or Ctrl+] exits."""
        for byte in data:
            if byte in (0x18, 0x1B, 0x1D):
                return True
            if byte == 0x0A and self._skip_line_feed:
                self._skip_line_feed = False
                continue

            self._skip_line_feed = False
            if byte in (0x0A, 0x0D):
                self._send_key("ENTER")
                self._skip_line_feed = byte == 0x0D
            elif byte in (0x08, 0x7F):
                self._send_key("BACKSPACE")
            elif byte == 0x09:
                self._send_key("TAB")
            elif 0x20 <= byte <= 0x7E:
                self._send_character(chr(byte))
        return False
