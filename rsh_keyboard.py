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
    "ESC": 0x1B,
    "SPACE": 0x20,
    "WIN": 0x5B,
    "CTRL": 0x11,
    "ALT": 0x12,
    "SHIFT": 0x10,
}
SHORTCUT_MODIFIERS = {"WIN", "CTRL", "ALT", "SHIFT"}


def _key_code(key_name):
    if key_name in SPECIAL_KEYS:
        return SPECIAL_KEYS[key_name]
    if len(key_name) == 1 and key_name.isalnum():
        return ord(key_name.upper())
    raise ValueError(f"Unsupported shortcut key: {key_name}")


def _send_windows_shortcut(action):
    keys = action.upper().split("+")
    modifiers = [key for key in keys[:-1] if key in SHORTCUT_MODIFIERS]
    key = keys[-1]
    virtual_keys = [
        0x5B if modifier == "WIN" else _key_code(modifier)
        for modifier in modifiers
    ]
    virtual_keys.append(_key_code(key))
    for virtual_key in virtual_keys:
        _send_keyboard_input(_KeybdInput(virtual_key, 0, 0, 0, 0))
    for virtual_key in reversed(virtual_keys):
        _send_keyboard_input(
            _KeybdInput(virtual_key, 0, KEYEVENTF_KEYUP, 0, 0)
        )


def _pynput_shortcut_sender():
    try:
        keyboard = importlib.import_module("pynput.keyboard")
    except ImportError as exc:
        raise OSError(
            "The keyboard bridge on macOS and Linux requires pynput. "
            "Install it with: python -m pip install pynput"
        ) from exc
    controller = keyboard.Controller()
    platform_modifier = getattr(keyboard.Key, "cmd", None) or getattr(
        keyboard.Key, "super", None
    )
    modifier_keys = {
        "WIN": platform_modifier,
        "CTRL": keyboard.Key.ctrl,
        "ALT": keyboard.Key.alt,
        "SHIFT": keyboard.Key.shift,
    }

    def send_shortcut(action):
        keys = action.upper().split("+")
        pressed = []
        try:
            for modifier in keys[:-1]:
                key = modifier_keys.get(modifier)
                if key is None:
                    raise ValueError(f"Unsupported shortcut modifier: {modifier}")
                controller.press(key)
                pressed.append(key)
            key_name = keys[-1]
            special = {
                "ENTER": keyboard.Key.enter,
                "TAB": keyboard.Key.tab,
                "BACKSPACE": keyboard.Key.backspace,
                "ESC": keyboard.Key.esc,
                "SPACE": keyboard.Key.space,
            }
            key = special.get(key_name, key_name.lower())
            controller.press(key)
            controller.release(key)
        finally:
            for key in reversed(pressed):
                controller.release(key)

    return send_shortcut


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


def send_shortcut(action):
    """Inject one modifier/key chord using the current host platform."""
    if sys.platform == "win32":
        return _send_windows_shortcut(action)
    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        return _pynput_shortcut_sender()(action)
    raise OSError(f"Shortcut injection is not supported on {sys.platform}.")


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
        "ESC": keyboard.Key.esc,
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

    def __init__(
        self,
        send_character=None,
        send_key=None,
        send_shortcut=None,
        shortcut_mappings=None,
        on_shortcut=None,
        exit_byte=0x18,
    ):
        if not isinstance(exit_byte, int) or not 0x01 <= exit_byte <= 0x1A:
            raise ValueError("Keyboard bridge exit binding must be Ctrl+A through Ctrl+Z.")
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
        if send_shortcut is not None:
            self._send_shortcut = send_shortcut
        elif sys.platform == "win32":
            self._send_shortcut = _send_windows_shortcut
        else:
            self._send_shortcut = None
        self._shortcut_mappings = shortcut_mappings or {}
        self._on_shortcut = on_shortcut
        self._skip_line_feed = False
        self._exit_byte = exit_byte

    def feed(self, data):
        """Inject data as keyboard input; the configured Ctrl+letter exits."""
        for byte in data:
            if byte == self._exit_byte:
                return True
            if 0x01 <= byte <= 0x1A:
                shortcut = f"CTRL+{chr(byte + 0x40)}"
                mappings = (
                    self._shortcut_mappings()
                    if callable(self._shortcut_mappings)
                    else self._shortcut_mappings
                )
                action = mappings.get(shortcut)
                if action:
                    if self._send_shortcut is None:
                        if sys.platform == "darwin" or sys.platform.startswith("linux"):
                            self._send_shortcut = _pynput_shortcut_sender()
                        else:
                            raise OSError(
                                "Shortcut injection is not supported on this platform."
                            )
                    self._send_shortcut(action)
                    if self._on_shortcut:
                        self._on_shortcut(shortcut, action)
                    if byte == 0x0D:
                        self._skip_line_feed = True
                    continue
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
            elif byte == 0x1B:
                self._send_key("ESC")
            elif 0x20 <= byte <= 0x7E:
                self._send_character(chr(byte))
        return False
