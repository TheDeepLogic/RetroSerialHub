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

    def test_main_menu_groups_options_in_two_80_column_layouts(self):
        import RETRO_SERIAL_HUB

        ser = FakeSerial()
        RETRO_SERIAL_HUB.show_main_menu(ser, use_ansi=False)
        output = b"".join(ser.writes)

        for heading in (
            b"[ Accessories ]",
            b"[ Bridging ]",
            b"[ Tools ]",
            b"[ Various ]",
            b"[ System ]",
        ):
            self.assertIn(heading, output)
        self.assertIn(b" 1] Bulletin Boards", output)
        self.assertIn(b" 2] Web Browser", output)
        self.assertIn(b" 4] FTP", output)
        self.assertIn(b" 5] COM Port", output)
        self.assertIn(b" 6] Keyboard", output)
        self.assertIn(b" 7] File Transfers", output)
        self.assertIn(b"10] AI Assistant", output)
        self.assertIn(b"11] Wargames", output)
        self.assertIn(b"12] Welcome Banner", output)
        self.assertIn(b"13] Switch to 40 Columns", output)
        self.assertNotIn(b"14] Disconnect", output)
        self.assertIn(b"v1.2, copyright (c) 2025", output)
        self.assertIn(
            b"v1.2, copyright (c) 2025\r\n\r\n[ Accessories ]",
            output,
        )
        self.assertIn(
            b"Type ATM to return to this menu.",
            output,
        )
        self.assertIn(b"Type ATM to return to this menu.\r\n\r\nCommand:", output)
        self.assertLess(output.index(b"[ Accessories ]"), output.index(b"[ Bridging ]"))
        self.assertLess(output.index(b"[ Bridging ]"), output.index(b"[ Tools ]"))
        self.assertLess(output.index(b"[ Various ]"), output.index(b"[ System ]"))

    def test_main_menu_shows_disconnect_option_for_remote_terminal(self):
        import socket
        import RETRO_SERIAL_HUB

        client, peer = socket.socketpair()
        try:
            RETRO_SERIAL_HUB.show_main_menu(
                RETRO_SERIAL_HUB.SocketTerminal(client), use_ansi=False
            )
            output = peer.recv(4096)
        finally:
            client.close()
            peer.close()

        self.assertIn(b"14] Disconnect", output)

    def test_main_menu_status_shows_time_and_active_connection_counts(self):
        import RETRO_SERIAL_HUB

        ser = FakeSerial()
        with (
            patch.object(RETRO_SERIAL_HUB.time, "strftime", return_value="12:34:56"),
            patch.object(
                RETRO_SERIAL_HUB,
                "get_active_connection_counts",
                return_value=(2, 3),
            ),
        ):
            RETRO_SERIAL_HUB.show_main_menu(ser, use_ansi=False)

        output = b"".join(ser.writes)
        self.assertIn(
            b"Status: 12:34:56 | Serial ports: 2 | Telnet clients: 3",
            output,
        )
        self.assertLess(output.index(b"Telnet clients: 3"), output.index(b"Type ATM"))

    def test_numbered_lists_use_single_column_in_40_column_mode(self):
        from rsh_terminal import format_numbered_list

        lines = format_numbered_list(["ALPHA", "BETA"], columns=40)
        self.assertEqual(lines, [" 1] ALPHA", " 2] BETA"])
        self.assertTrue(all(len(line) <= 39 for line in lines))

    def test_numbered_lists_keep_two_columns_in_80_column_mode(self):
        from rsh_terminal import format_numbered_list

        lines = format_numbered_list(["ALPHA", "BETA"], columns=80)
        self.assertEqual(len(lines), 1)
        self.assertIn(" 1] ALPHA", lines[0])
        self.assertIn(" 2] BETA", lines[0])

    def test_terminal_profile_stores_its_column_width(self):
        from rsh_terminal import configure_screen_clearing, terminal_columns

        ser = FakeSerial()
        configure_screen_clearing(ser, columns=40)
        self.assertEqual(terminal_columns(ser), 40)

    def test_main_menu_uses_compact_two_option_rows_at_40_columns(self):
        import RETRO_SERIAL_HUB

        ser = FakeSerial()
        configure_screen_clearing(ser, columns=40)
        RETRO_SERIAL_HUB.show_main_menu(ser, use_ansi=False)
        output = b"".join(ser.writes)

        self.assertIn(b" 5] COM Port", output)
        self.assertIn(b" 6] Keyboard", output)
        self.assertIn(b" 7] File Transfers", output)
        self.assertIn(b"10] AI Assistant   11] Wargames", output)
        self.assertIn(b"13] 80 Columns", output)
        self.assertIn(
            b"v1.2, copyright (c) 2025\r\n\r\n[ Accessories ]\r\n",
            output,
        )
        self.assertLess(output.index(b"[ Accessories ]"), output.index(b"[ Bridging ]"))
        self.assertLess(output.index(b"[ Bridging ]"), output.index(b"[ Tools ]"))
        self.assertLess(output.index(b"[ Tools ]"), output.index(b"[ Various ]"))
        self.assertIn(
            b"Type ATM to return to this menu.\r\nCommand:",
            output,
        )
        self.assertNotIn(
            b"Type ATM to return to this menu.\r\n\r\nCommand:",
            output,
        )
        self.assertFalse(output.startswith(b"\r\n\r\nWelcome"))
        self.assertLessEqual(max(map(len, output.split(b"\r\n"))), 40)

    def test_column_preferences_are_saved_and_loaded_per_profile(self):
        import tempfile
        import RETRO_SERIAL_HUB
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_directory:
            path = Path(temp_directory) / "terminal_columns.json"
            preferences = RETRO_SERIAL_HUB.save_column_preference(
                path, {}, "APPLE2", 40
            )

            self.assertEqual(preferences, {"APPLE2": 40})
            self.assertEqual(
                RETRO_SERIAL_HUB.load_column_preferences(path),
                {"APPLE2": 40},
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
