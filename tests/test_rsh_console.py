import io
import unittest
from unittest.mock import patch

from rsh_console import ConsoleDashboard


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
        self.assertIn("Retro Serial Hub v1.2", text)
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


if __name__ == "__main__":
    unittest.main()
