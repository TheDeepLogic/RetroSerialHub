from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from rsh_console import ConsoleDashboard
from rsh_host_access import HostCommandAccess


class HostAccessTests(unittest.TestCase):
    def test_serial_and_ip_require_separate_explicit_approval_and_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "host_commands.json"
            access = HostCommandAccess(path)
            serial = SimpleNamespace(port="com02")
            ip = SimpleNamespace(_remote_address=("192.168.1.7", 1234), port=None)
            self.assertFalse(access.request(serial)[0])
            self.assertFalse(access.request(ip)[0])
            self.assertEqual(len(access.pending()), 2)
            self.assertFalse(access.request(serial)[2])
            access.decide(1, True)
            restored = HostCommandAccess(path)
            self.assertTrue(restored.request(SimpleNamespace(port=r"\\.\COM2"))[0])
            self.assertFalse(restored.request(ip)[0])
            access.decide(2, True)
            self.assertTrue(restored.request(SimpleNamespace(_remote_address=("192.168.1.7", 9999)))[0])
            self.assertFalse(restored.request(SimpleNamespace(_remote_address=("192.168.1.8", 9999)))[0])

    def test_failed_persistence_never_grants_access(self):
        access = HostCommandAccess()
        source = SimpleNamespace(port="COM2")
        access.request(source)
        with patch.object(access, "_save", side_effect=OSError("Disk full")):
            with self.assertRaises(OSError):
                access.decide(1, True)
        self.assertFalse(access.request(source)[0])
        self.assertEqual(len(access.pending()), 1)

    def test_denial_expiration_and_bounded_queue(self):
        now = [0]
        access = HostCommandAccess(clock=lambda: now[0], timeout=10, max_pending=1)
        first, second = SimpleNamespace(port="COM2"), SimpleNamespace(port="COM4")
        access.request(first)
        self.assertIn("queue is full", access.request(second)[1])
        access.decide(1, False)
        self.assertFalse(access.request(first)[0])
        now[0] = 11
        self.assertEqual(access.pending(), [])
        with self.assertRaises(ValueError):
            access.decide(2, True)
        self.assertTrue(access.request(second)[2])

    def test_corrupt_and_manually_revoked_policy_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "host_commands.json"
            access = HostCommandAccess(path)
            source = SimpleNamespace(port="COM2")
            access.request(source)
            access.decide(1, True)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                access.request(source)
            path.unlink()
            self.assertFalse(access.request(source)[0])

    def test_remote_command_requires_local_grant_and_cannot_approve_others(self):
        dashboard = ConsoleDashboard({})
        dashboard._running = True
        dashboard.host_input_available = lambda: True
        terminal = MagicMock(secret_input=False, closed=False)
        dashboard.set_host_terminal(terminal)
        source = SimpleNamespace(port="COM2")
        ok, message = dashboard.submit_remote_command("theme Commodore", source)
        self.assertFalse(ok)
        self.assertIn("allow host 1", message)
        self.assertIn("not been executed", message)
        self.assertEqual(dashboard._theme.name, "Ocean")
        dashboard.handle_host_command("allow host 1")
        self.assertTrue(dashboard.submit_remote_command("theme Commodore", source)[0])
        self.assertEqual(dashboard._theme.name, "Commodore")
        other = SimpleNamespace(port="COM4")
        dashboard.submit_remote_command("calc 1 + 1", other)
        ok, message = dashboard.submit_remote_command("allow host 2", source)
        self.assertFalse(ok)
        self.assertIn("local console", message)
        self.assertFalse(dashboard.submit_remote_command("calc 1 + 1", other)[0])
        self.assertTrue(dashboard.submit_remote_command("calc 6 * 7", source)[0])
        terminal.submit.assert_called_once_with("calc 6 * 7")

    def test_forwarded_input_preserves_local_draft_and_masks_password_commands(self):
        dashboard = ConsoleDashboard({})
        dashboard._running = True
        dashboard.host_input_available = lambda: True
        terminal = MagicMock(secret_input=False, closed=False)
        dashboard.set_host_terminal(terminal)
        source = SimpleNamespace(port="COM2")
        dashboard.submit_remote_command("help", source)
        dashboard.handle_host_command("allow host 1")
        dashboard._host_command = "local draft"
        self.assertFalse(dashboard.submit_remote_command("help", source)[0])
        self.assertEqual(dashboard._host_command, "local draft")
        terminal.submit.assert_not_called()
        dashboard._host_command = ""
        terminal.secret_input = True
        dashboard.submit_remote_command("theme Hot Pink", source)
        terminal.submit.assert_called_once_with("theme Hot Pink")
        self.assertEqual(dashboard._theme.name, "Ocean")
        self.assertNotIn("theme Hot Pink", dashboard._command_history)


if __name__ == "__main__":
    unittest.main()
