import io
import unittest
from unittest.mock import patch

from rsh_console import ConsoleDashboard, VERSION


class ConsoleDashboardTests(unittest.TestCase):
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
        self.assertIn("Active connections: 2", text)

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
        self.assertIn("*[B] Calc", full_text)
        self.assertIn("[UserAlpha+2]", full_text)

    def test_frame_includes_interface_rows(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_user_activity("u1", "cli", user_label="Hacker")
        with patch("shutil.get_terminal_size", return_value=type("TermSize", (), {"columns": 80, "lines": 24})()):
            frame = dashboard._frame()
        frame_text = "\n".join(frame)
        self.assertIn("Retro Serial Hub Interface", frame_text)
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
