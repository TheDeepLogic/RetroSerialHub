import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rsh_terminal import clear_terminal_screen, configure_screen_clearing


class FakeSerial:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)


class ScreenClearingTests(unittest.TestCase):
    def test_native_ansi_uses_clear_and_home(self):
        ser = FakeSerial()
        clear_terminal_screen(ser, use_ansi=True)
        self.assertEqual(ser.writes, [b"\x1b[2J\x1b[H"])

    def test_translated_terminal_uses_configured_clear_once(self):
        ser = FakeSerial()
        configure_screen_clearing(
            ser, translate_ansi=True, clear_sequence=b"\x1bv"
        )
        clear_terminal_screen(ser, use_ansi=False)
        self.assertEqual(ser.writes, [b"\x1bv"])

    def test_unconfigured_non_ansi_terminal_uses_newline_fallback(self):
        ser = FakeSerial()
        clear_terminal_screen(ser, use_ansi=False)
        self.assertEqual(ser.writes, [b"\r\n"])

    def test_main_menu_uses_configured_terminal_clear(self):
        import RETRO_SERIAL_HUB

        ser = FakeSerial()
        configure_screen_clearing(
            ser, translate_ansi=True, clear_sequence=b"\x1bv"
        )
        RETRO_SERIAL_HUB.show_main_menu(ser, use_ansi=False)
        self.assertEqual(ser.writes[0], b"\x1bv")

    def test_main_menu_options_are_contiguous_and_match_requested_order(self):
        import RETRO_SERIAL_HUB

        ser = FakeSerial()
        RETRO_SERIAL_HUB.show_main_menu(ser, use_ansi=False)
        output = b"".join(ser.writes)

        self.assertIn(
            b" 1] Bulletin Boards\r\n 2] Web Browser\r\n"
            b" 3] Telnet\r\n 4] FTP\r\n"
            b" 5] File Transfers\r\n 6] Text Library\r\n"
            b" 7] AI Assistant\r\n 8] Wargames\r\n"
            b" 9] Notes\r\n10] COM Port Bridge\r\n"
            b"11] Keyboard Bridge\r\n12] Welcome Banner",
            output,
        )
        self.assertIn(b"v1.1, copyright (c) 2025", output)
        self.assertIn(
            b"Type ATM at any time to return to this menu.",
            output,
        )

    def test_main_menu_displays_active_welcome_banner(self):
        import RETRO_SERIAL_HUB

        ser = FakeSerial()
        with patch.object(RETRO_SERIAL_HUB, "WELCOME_BANNER", "My Custom Banner"):
            RETRO_SERIAL_HUB.show_main_menu(ser, use_ansi=False)

        self.assertIn(b"My Custom Banner", b"".join(ser.writes))

    def test_translated_clear_is_used_by_menu_renderers(self):
        import rsh_bbs
        import rsh_browser
        import rsh_files
        import rsh_notes
        import rsh_text
        import rsh_bridge
        import rsh_telnet
        import rsh_ftp
        import rsh_wargames

        with tempfile.TemporaryDirectory() as temp_directory:
            renderers = (
                lambda ser: rsh_bbs.create_session(ser, False),
                lambda ser: rsh_browser.create_session(ser, False),
                lambda ser: rsh_files.create_session(ser, False),
                lambda ser: rsh_notes.create_session(ser, False),
                lambda ser: rsh_text.create_session(ser, False),
                lambda ser: rsh_bridge.create_session(ser, False),
                lambda ser: rsh_telnet.create_session(
                    ser,
                    False,
                    bookmarks_path=Path(temp_directory) / "bookmarks.json",
                ),
                lambda ser: rsh_ftp.create_session(ser, False),
                lambda ser: rsh_wargames.create_session(ser, False),
            )
            for render in renderers:
                with self.subTest(renderer=render):
                    ser = FakeSerial()
                    configure_screen_clearing(
                        ser, translate_ansi=True, clear_sequence=b"\x1bv"
                    )
                    render(ser)
                    self.assertEqual(ser.writes[0], b"\x1bv")

    def test_wargames_submenu_clears_before_render(self):
        import rsh_wargames

        ser = FakeSerial()
        configure_screen_clearing(
            ser, translate_ansi=True, clear_sequence=b"\x1bv"
        )
        session = rsh_wargames.create_session(ser, use_ansi=False)
        ser.writes.clear()
        rsh_wargames.handle_input(session, "term", ser, use_ansi=False)
        self.assertEqual(ser.writes[0], b"\x1bv")


if __name__ == "__main__":
    unittest.main()
