import unittest
from types import SimpleNamespace
from unittest.mock import patch

import rsh_keyboard
from rsh_keyboard import KeyboardBridge


class KeyboardBridgeTests(unittest.TestCase):
    def setUp(self):
        self.characters = []
        self.keys = []
        self.bridge = KeyboardBridge(
            send_character=self.characters.append,
            send_key=self.keys.append,
        )

    def test_printable_ascii_is_forwarded(self):
        self.assertFalse(self.bridge.feed(b"Hello, world!"))
        self.assertEqual(self.characters, list("Hello, world!"))
        self.assertEqual(self.keys, [])

    def test_enter_crlf_backspace_and_tab_map_to_host_keys(self):
        self.assertFalse(self.bridge.feed(b"A\r\nB\x08\tC\n"))
        self.assertEqual(self.characters, ["A", "B", "C"])
        self.assertEqual(
            self.keys, ["ENTER", "BACKSPACE", "TAB", "ENTER"]
        )

    def test_escape_exits_without_being_injected(self):
        self.assertTrue(self.bridge.feed(b"before\x1bafter"))
        self.assertEqual(self.characters, list("before"))
        self.assertEqual(self.keys, [])

    def test_ctrl_x_exits_without_being_injected(self):
        self.assertTrue(self.bridge.feed(b"before\x18after"))
        self.assertEqual(self.characters, list("before"))
        self.assertEqual(self.keys, [])

    def test_ctrl_right_bracket_also_exits_without_being_injected(self):
        self.assertTrue(self.bridge.feed(b"before\x1dafter"))
        self.assertEqual(self.characters, list("before"))
        self.assertEqual(self.keys, [])

    def test_other_control_bytes_are_ignored(self):
        self.assertFalse(self.bridge.feed(b"\x00\x01\x02AB"))
        self.assertEqual(self.characters, ["A", "B"])

    def test_macos_uses_pynput_keyboard_controller(self):
        calls = []

        class FakeController:
            def type(self, character):
                calls.append(("type", character))

            def press(self, key):
                calls.append(("press", key))

            def release(self, key):
                calls.append(("release", key))

        keyboard = SimpleNamespace(
            Controller=FakeController,
            Key=SimpleNamespace(enter="enter", backspace="backspace", tab="tab"),
        )
        with patch.object(rsh_keyboard.sys, "platform", "darwin"):
            with patch.object(
                rsh_keyboard.importlib, "import_module", return_value=keyboard
            ) as import_module:
                bridge = KeyboardBridge()
                self.assertFalse(bridge.feed(b"A\r"))

        import_module.assert_called_once_with("pynput.keyboard")
        self.assertEqual(
            calls, [("type", "A"), ("press", "enter"), ("release", "enter")]
        )

    def test_linux_without_pynput_reports_install_instructions(self):
        with patch.object(rsh_keyboard.sys, "platform", "linux"):
            with patch.object(
                rsh_keyboard.importlib,
                "import_module",
                side_effect=ImportError("missing"),
            ):
                with self.assertRaisesRegex(OSError, "pip install pynput"):
                    KeyboardBridge()

    def test_unsupported_platform_is_reported(self):
        with patch.object(rsh_keyboard.sys, "platform", "freebsd"):
            with self.assertRaisesRegex(OSError, "not supported on freebsd"):
                KeyboardBridge()

    def test_unicode_character_is_sent_as_key_down_and_key_up(self):
        with patch.object(rsh_keyboard, "_send_keyboard_input") as send_input:
            rsh_keyboard._send_unicode_character("A")

        self.assertEqual(send_input.call_count, 2)
        key_down = send_input.call_args_list[0].args[0]
        key_up = send_input.call_args_list[1].args[0]
        self.assertEqual(key_down.wVk, 0)
        self.assertEqual(key_down.wScan, ord("A"))
        self.assertEqual(key_down.dwFlags, rsh_keyboard.KEYEVENTF_UNICODE)
        self.assertEqual(
            key_up.dwFlags,
            rsh_keyboard.KEYEVENTF_UNICODE | rsh_keyboard.KEYEVENTF_KEYUP,
        )

    def test_special_key_is_sent_as_key_down_and_key_up(self):
        with patch.object(rsh_keyboard, "_send_keyboard_input") as send_input:
            rsh_keyboard._send_special_key("ENTER")

        self.assertEqual(send_input.call_count, 2)
        key_down = send_input.call_args_list[0].args[0]
        key_up = send_input.call_args_list[1].args[0]
        self.assertEqual(key_down.wVk, rsh_keyboard.SPECIAL_KEYS["ENTER"])
        self.assertEqual(key_down.dwFlags, 0)
        self.assertEqual(key_up.dwFlags, rsh_keyboard.KEYEVENTF_KEYUP)

    def test_input_layout_matches_windows_abi_size(self):
        import ctypes

        expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(rsh_keyboard._Input), expected_size)


if __name__ == "__main__":
    unittest.main()
