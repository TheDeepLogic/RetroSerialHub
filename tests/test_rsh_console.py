import io
import os
import re
import unittest
from unittest.mock import MagicMock, patch

from rsh_console import ConsoleDashboard, VERSION


class VirtualScreen:
    """Minimal ANSI viewport that detects wrapping and scrolling in redraws."""

    def __init__(self, columns, height):
        self.columns, self.height = columns, height
        self.lines = [[" "] * columns for _ in range(height)]
        self.row = self.column = self.scrolls = 0

    def newline(self):
        self.row += 1
        if self.row >= self.height:
            self.lines.pop(0)
            self.lines.append([" "] * self.columns)
            self.row = self.height - 1
            self.scrolls += 1

    def feed(self, output):
        position = 0
        while position < len(output):
            escape = re.match(r"\x1b\[([0-9;]*)([A-Za-z])", output[position:])
            if escape:
                arguments = [int(value or 0) for value in escape[1].split(";")]
                action = escape[2]
                if action in ("H", "f"):
                    self.row = min(self.height - 1, max(0, (arguments[0] or 1) - 1))
                    self.column = min(self.columns - 1, max(0, ((arguments[1] if len(arguments) > 1 else 1) or 1) - 1))
                elif action == "A":
                    self.row = max(0, self.row - (arguments[0] or 1))
                elif action == "K":
                    start = 0 if arguments[0] == 2 else self.column
                    self.lines[self.row][start:] = [" "] * (self.columns - start)
                elif action == "J":
                    self.lines[self.row][self.column:] = [" "] * (self.columns - self.column)
                    for row in range(self.row + 1, self.height):
                        self.lines[row] = [" "] * self.columns
                position += len(escape[0])
                continue
            character = output[position]
            position += 1
            if character == "\r":
                self.column = 0
            elif character == "\n":
                self.newline()
            elif character.isprintable():
                if self.column >= self.columns:
                    self.column = 0
                    self.newline()
                self.lines[self.row][self.column] = character
                self.column += 1

    def text(self):
        return "\n".join("".join(row).rstrip() for row in self.lines)


class ConsoleDashboardTests(unittest.TestCase):
    def test_host_typing_and_approval_footer_growth_do_not_scroll_or_shift_header(self):
        dashboard = ConsoleDashboard({})
        dashboard._tty = True
        dashboard._running = True
        access = MagicMock()
        access.pending.return_value = []
        dashboard.set_telnet_access(access)
        screen = VirtualScreen(80, 24)
        output = io.StringIO()

        def verify_redraw():
            screen.feed(output.getvalue())
            output.seek(0)
            output.truncate()
            self.assertTrue("".join(screen.lines[0]).startswith("Retro Serial Hub"))
            self.assertIn("Host>", screen.text())
            self.assertEqual(screen.scrolls, 0)

        with patch("rsh_console.sys.stdout", output), patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))), patch.object(dashboard, "host_input_available", return_value=True):
            dashboard._draw_frame()
            verify_redraw()
            for key in "pending\r":
                # Simulate cursor drift from host interaction between frames.
                screen.row, screen.column = 6, 12
                dashboard._host_key(key)
                verify_redraw()
            access.pending.return_value = [{"id": 1, "ip": "192.168.7.13", "profile": "APPLE2", "seconds_left": 120}]
            for index in range(4):
                dashboard.log(f"Approval event {index}")
                verify_redraw()
            access.pending.return_value = []
            dashboard._draw_frame()
            verify_redraw()
        self.assertNotIn("TELNET APPROVAL REQUIRED", screen.text())

    def test_resizing_keeps_redraw_inside_viewport_and_preserves_host_prompt(self):
        dashboard = ConsoleDashboard({})
        dashboard._tty = True
        access = MagicMock()
        access.pending.return_value = []
        dashboard.set_telnet_access(access)
        dashboard.set_host_terminal(MagicMock())
        for index in range(20):
            dashboard.append_host_output(f"Command response {index}\r\n".encode())
        for columns, height in ((120, 50), (80, 24), (40, 12), (20, 5)):
            output = io.StringIO()
            screen = VirtualScreen(columns, height)
            with patch("rsh_console.sys.stdout", output), patch("shutil.get_terminal_size", return_value=os.terminal_size((columns, height))), patch.object(dashboard, "host_input_available", return_value=True):
                dashboard._draw_frame()
            screen.feed(output.getvalue())
            self.assertEqual(screen.scrolls, 0)
            self.assertLessEqual(dashboard._frame_lines, height)
            self.assertIn("Host>", screen.text())
            self.assertTrue(screen.text().startswith("Retro Serial Hub"))

    def test_row_clipping_preserves_colors_and_prevents_wrap_or_embedded_newlines(self):
        clip = ConsoleDashboard._clip_screen_row
        colored = clip("\x1b[31mABCDE\x1b[0m", 3)
        self.assertEqual(ConsoleDashboard._strip_ansi(colored), "ABC")
        self.assertTrue(colored.endswith("\x1b[0m"))
        self.assertEqual(clip("A\nB\rC", 10), "A B C")
        self.assertEqual(clip("界界X", 4), "界界")
        self.assertEqual(clip("\x1b[2Jtext", 10), "text")

    def test_noninteractive_console_reports_profiles_and_state_changes(self):
        output = io.StringIO()
        profile = {
            "APPLE2": {
                "serial_port": "COM2",
                "baud": 19200,
                "serial_status": "STARTING",
                "tcp_port": 6400,
                "tcp_status": "STARTING",
                "endpoint": "192.168.1.20:6400",
            }
        }
        with patch("rsh_console.sys.stdout", output):
            dashboard = ConsoleDashboard(profile)
            dashboard.start()
            dashboard.update_profile("APPLE2", serial="OPEN", tcp="LISTENING")
            dashboard.add_client(1, "APPLE2", ("192.168.1.10", 5000))
            dashboard.remove_client(1)

        text = output.getvalue()
        self.assertIn(f"Retro Serial Hub v{VERSION}", text)
        self.assertIn("Connect 192.168.1.20:6400", text)
        self.assertIn("Serial COM2: OPEN 19200 | TCP 6400: LISTENING (0)", text)
        self.assertIn("TCP 6400: LISTENING (1)", text)
        self.assertIn("Telnet clients: 1", text)
        self.assertIn("Telnet clients: 0", text)
        self.assertIn("Active connections: 1", text)

    def test_noninteractive_console_logs_errors_without_ansi_colors(self):
        output = io.StringIO()
        with patch("rsh_console.sys.stdout", output):
            dashboard = ConsoleDashboard({})
            dashboard.start()
            dashboard.log("listener failed", level="red")

        text = output.getvalue()
        self.assertIn("listener failed", text)
        self.assertNotIn("\x1b[", text)

    def test_normalize_action(self):
        dashboard = ConsoleDashboard({})
        self.assertEqual(dashboard.normalize_action("1"), "section:1")
        self.assertEqual(dashboard.normalize_action("section:2"), "section:2")
        self.assertEqual(dashboard.normalize_action("main_menu"), "section:0")
        self.assertEqual(dashboard.normalize_action("minesweeper"), "mines")
        self.assertEqual(dashboard.normalize_action("chat"), "ai")
        self.assertEqual(dashboard.normalize_action("cmd"), "host_terminal")
        self.assertEqual(dashboard.normalize_action("schedule"), "scheduler")
        self.assertEqual(dashboard.normalize_action("shortcut_run: weather Dallas"), "weather_news")
        self.assertEqual(dashboard.normalize_action("shortcut_run: foobar"), "shortcuts")

    def test_user_activity_tracking_and_clearing(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_user_activity("serial:COM1", "bbs", user_label="COM1")
        activities = dashboard.get_user_activities()
        self.assertEqual(activities, {"serial:COM1": {"action": "bbs", "user": "COM1"}})

        # Add client and test auto user label
        dashboard.add_client(42, "C64", ("10.0.0.5", 6400))
        dashboard.set_user_activity(42, "games")
        activities = dashboard.get_user_activities()
        self.assertEqual(activities[42]["action"], "games")
        self.assertEqual(activities[42]["user"], "C64@10.0.0.5")

        # Clear specific user activity
        dashboard.clear_user_activity("serial:COM1")
        self.assertNotIn("serial:COM1", dashboard.get_user_activities())

        # Removing client clears its user activity automatically
        dashboard.remove_client(42)
        self.assertNotIn(42, dashboard.get_user_activities())

    def test_render_interface_layout_responsiveness(self):
        dashboard = ConsoleDashboard({})
        # Wide layout (>= 70 inner width -> 3 columns)
        rows_wide = dashboard.render_interface(inner_width=80, use_color=False)
        self.assertTrue(len(rows_wide) > 0)
        self.assertTrue(all(len(r) == 80 for r in rows_wide))
        self.assertIn("[1] COMMUNICATIONS", "".join(rows_wide))
        self.assertIn("[2] HOST CONNECTIVITY", "".join(rows_wide))
        self.assertIn("[3] FILES & MEDIA", "".join(rows_wide))

        # Medium layout (46-69 inner width -> 2 columns)
        rows_med = dashboard.render_interface(inner_width=50, use_color=False)
        self.assertTrue(all(len(r) == 50 for r in rows_med))

        # Narrow layout (< 46 inner width -> 1 column)
        rows_narrow = dashboard.render_interface(inner_width=40, use_color=False)
        self.assertTrue(all(len(r) == 40 for r in rows_narrow))

    def test_render_interface_highlighting_active_users(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_user_activity("u1", "bbs", user_label="Alice")
        dashboard.set_user_activity("u2", "section:2", user_label="Bob")

        # Plain-text rendering: check visual indicator and user tags
        rows_plain = dashboard.render_interface(inner_width=80, use_color=False)
        full_text = "\n".join(rows_plain)

        # Alice on BBS: item highlight
        self.assertIn("*[A] BBS", full_text)
        self.assertIn("[Alice]", full_text)

        # Inactive item: no asterisk prefix
        self.assertIn(" [B] Telnet", full_text)

        # Bob on Section 2: section title highlight
        self.assertIn("*[2] HOST CONNECT", full_text)
        self.assertIn("[Bob]", full_text)

        # Color rendering: ANSI highlight sequences
        rows_color = dashboard.render_interface(inner_width=80, use_color=True)
        color_text = "\n".join(rows_color)
        self.assertIn("\x1b[", color_text)
        self.assertIn("Alice", color_text)

    def test_render_interface_multi_user_tag_overflow(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_user_activity("u1", "calc", user_label="UserAlpha")
        dashboard.set_user_activity("u2", "calc", user_label="UserBeta")
        dashboard.set_user_activity("u3", "calc", user_label="UserGamma")

        # In 80 columns, multiple users on same item should fit with +N or *N without line breaking
        rows = dashboard.render_interface(inner_width=80, use_color=False)
        self.assertTrue(all(len(r) == 80 for r in rows))
        full_text = "\n".join(rows)
        self.assertIn("*[C] Calc", full_text)
        self.assertIn("[UserAlpha+2]", full_text)

    def test_frame_includes_interface_rows(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_user_activity("u1", "cli", user_label="Hacker")
        with patch("shutil.get_terminal_size", return_value=type("TermSize", (), {"columns": 80, "lines": 24})()):
            frame = dashboard._frame()
        frame_text = "\n".join(frame)
        self.assertIn("Connected Terminal Activity Monitor", frame_text)
        self.assertIn("*[A] Shell (CLI", frame_text)
        self.assertIn("[Hacker]", frame_text)

    def test_retro_serial_hub_activity_helpers(self):
        import RETRO_SERIAL_HUB as rsh

        dashboard = ConsoleDashboard({})
        with patch.object(rsh, "CONSOLE", dashboard):
            # Serial terminal mock
            class MockSerial:
                _client_id = "serial:COM1"
                _profile_name = "COM1"

            mock_ser = MockSerial()
            rsh.set_terminal_activity(mock_ser, "bbs")
            activities = dashboard.get_user_activities()
            self.assertEqual(activities["serial:COM1"]["action"], "bbs")
            self.assertEqual(activities["serial:COM1"]["user"], "COM1")

            rsh.clear_terminal_activity(mock_ser)
            self.assertNotIn("serial:COM1", dashboard.get_user_activities())


if __name__ == "__main__":
    unittest.main()
