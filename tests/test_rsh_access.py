"""Admission must precede every remote session; local input is the only prompt path."""

import io
import json
from pathlib import Path
import select
import socket
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from rsh_access import IPAllowlist, TelnetAccess
from rsh_console import ConsoleDashboard


class TelnetAccessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "telnet_allowlist.json"
        self.admit = MagicMock()
        self.notify = MagicMock()
        self.now = [100.0]
        self.access = TelnetAccess(self.path, self.admit, self.notify, interactive=True,
                                   timeout=10, max_pending=2, clock=lambda: self.now[0])
        self.addCleanup(self.access.stop)

    def connection(self, ip="192.168.7.13", access=None, profile="APPLE2"):
        client, peer = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(peer.close)
        peer.settimeout(1)
        (access or self.access).accept(profile, {}, client, (ip, 50000))
        return client, peer

    def write_policy(self, ips):
        self.path.write_text(json.dumps({"allowed_ips": ips}), encoding="utf-8")

    def test_unknown_address_waits_and_host_approval_saves_before_admission(self):
        client, peer = self.connection()
        self.assertIn(b"Waiting for approval", peer.recv(4096))
        self.admit.assert_not_called()
        self.assertEqual(self.access.pending()[0]["ip"], "192.168.7.13")
        self.access.allow(1)
        self.assertEqual(IPAllowlist(self.path).allowed(), {"192.168.7.13"})
        self.admit.assert_called_once_with("APPLE2", {}, client, ("192.168.7.13", 50000))
        self.assertIn(b"Host approved", peer.recv(4096))
        self.assertEqual(self.access.pending(), [])

    def test_saved_address_works_after_restart_across_profiles_without_prompt(self):
        self.write_policy(["192.168.7.13"])
        restarted = TelnetAccess(self.path, self.admit, self.notify, interactive=False)
        self.addCleanup(restarted.stop)
        self.connection(access=restarted, profile="IBM")
        self.admit.assert_called_once()
        self.assertEqual(restarted.pending(), [])
        self.notify.assert_not_called()

    def test_private_and_loopback_addresses_are_not_implicitly_trusted(self):
        self.connection(ip="127.0.0.1")
        self.connection(ip="10.0.0.1")
        self.admit.assert_not_called()
        self.assertEqual(len(self.access.pending()), 2)

    def test_remote_allow_command_and_pretyped_host_commands_are_discarded(self):
        client, peer = self.connection()
        peer.recv(4096)
        peer.sendall(b"allow 1\rterminal cmd\rlaunch anything\r")
        self.access.poll()
        self.admit.assert_not_called()
        self.assertFalse(self.path.exists())
        self.access.allow(1)
        self.assertFalse(select.select([client], [], [], 0)[0])
        self.admit.assert_called_once()

    def test_denial_timeout_and_disconnect_do_not_save_or_open_sessions(self):
        _, peer = self.connection()
        peer.recv(4096)
        self.access.deny(1)
        self.assertIn(b"denied", peer.recv(4096))
        self.assertEqual(peer.recv(4096), b"")
        _, second = self.connection(ip="192.168.7.14")
        second.recv(4096)
        self.now[0] += 11
        self.access.poll()
        self.assertIn(b"timed out", second.recv(4096))
        _, third = self.connection(ip="192.168.7.15")
        third.close()
        self.access.poll()
        self.assertEqual(self.access.pending(), [])
        self.assertFalse(self.path.exists())
        self.admit.assert_not_called()
        with self.assertRaises(ValueError):
            self.access.allow(2)

    def test_headless_mode_requires_manual_json_and_never_autoapproves(self):
        self.access.interactive = False
        _, peer = self.connection()
        self.assertIn(b"Host approval required", peer.recv(4096))
        self.assertEqual(self.access.pending(), [])
        self.admit.assert_not_called()
        self.write_policy(["192.168.7.13"])
        self.connection()
        self.admit.assert_called_once()

    def test_manual_json_addition_admits_waiting_client_and_removal_gates_reconnect(self):
        self.connection()
        self.write_policy(["192.168.7.13"])
        self.access.poll()
        self.admit.assert_called_once()
        self.write_policy([])
        self.connection()
        self.assertEqual(len(self.access.pending()), 1)
        self.assertEqual(self.admit.call_count, 1)

    def test_malformed_policy_and_cidr_or_hostname_entries_fail_closed(self):
        for content in ('{', '{}', '[]', '{"allowed_ips": [true]}',
                        '{"allowed_ips": ["0.0.0.0/0"]}', '{"allowed_ips": ["localhost"]}'):
            self.path.write_text(content, encoding="utf-8")
            _, peer = self.connection()
            self.assertIn(b"Access denied", peer.recv(4096))
            self.assertEqual(self.access.pending(), [])
        self.admit.assert_not_called()

    def test_saving_error_does_not_grant_access(self):
        self.connection()
        with patch.object(self.access.store, "approve", side_effect=OSError("read only")):
            with self.assertRaises(OSError):
                self.access.allow(1)
        self.admit.assert_not_called()
        self.assertEqual(len(self.access.pending()), 1)

    def test_expired_or_denied_request_number_cannot_approve_a_new_request(self):
        self.connection()
        self.access.deny(1)
        self.connection(ip="192.168.7.14")
        with self.assertRaises(ValueError):
            self.access.allow(1)
        self.assertEqual(self.access.pending()[0]["id"], 2)
        self.admit.assert_not_called()

    def test_background_monitor_creates_empty_file_and_applies_manual_addition(self):
        admitted = threading.Event()
        self.access.admit = lambda *_args: admitted.set()
        self.access.start()
        self.assertEqual(self.access.store.allowed(), set())
        _, peer = self.connection()
        peer.recv(4096)
        self.write_policy(["192.168.7.13"])
        self.assertTrue(admitted.wait(2))
        self.assertIn(b"Host approved", peer.recv(4096))

    def test_pending_queue_is_bounded_and_duplicate_ip_is_not_enqueued(self):
        self.connection()
        _, duplicate = self.connection()
        self.assertIn(b"already", duplicate.recv(4096))
        self.connection(ip="192.168.7.14")
        _, overflow = self.connection(ip="192.168.7.15")
        self.assertIn(b"queue is full", overflow.recv(4096))
        self.assertEqual([row["id"] for row in self.access.pending()], [1, 2])
        self.admit.assert_not_called()

    def test_simultaneous_polling_opens_exactly_one_session(self):
        self.connection()
        self.write_policy(["192.168.7.13"])
        workers = [threading.Thread(target=self.access.poll) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.admit.assert_called_once()

    def test_shutting_down_closes_pending_and_rejects_even_preapproved_clients(self):
        self.connection()
        self.access.stop()
        self.write_policy(["192.168.7.13"])
        _, peer = self.connection()
        self.assertIn(b"shutting down", peer.recv(4096))
        self.admit.assert_not_called()

    def test_accepting_listener_routes_connection_through_gate_not_worker(self):
        import RETRO_SERIAL_HUB as hub
        client, peer = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(peer.close)
        listener = MagicMock()
        listener.__enter__.return_value = listener
        listener.accept.side_effect = [(client, ("192.168.7.13", 1234)), OSError("end test")]
        with patch.object(hub.socket, "socket", return_value=listener), patch.object(hub, "TELNET_ACCESS", self.access), patch.object(hub, "CONSOLE", None), patch.object(hub, "console_log"), patch.object(hub, "remote_client_worker") as worker:
            hub.telnet_server_worker("APPLE2", {}, {"port": 6400})
        worker.assert_not_called()
        self.admit.assert_not_called()
        self.assertEqual(len(self.access.pending()), 1)


class HostApprovalConsoleTests(unittest.TestCase):
    def test_dashboard_shows_request_and_only_local_keyboard_approves_specific_id(self):
        access = MagicMock()
        access.pending.return_value = [{"id": 7, "ip": "192.168.7.13", "profile": "APPLE2", "seconds_left": 110}]
        dashboard = ConsoleDashboard({})
        dashboard.set_telnet_access(access)
        with patch.object(dashboard, "host_input_available", return_value=True):
            for key in "allow 7\r":
                dashboard._host_key(key)
            access.allow.assert_called_once_with(7)
            frame = "\n".join(dashboard._frame())
        self.assertIn("APPROVAL #7", frame)
        self.assertIn("192.168.7.13", frame)
        self.assertIn("Host>", frame)
        self.assertEqual(dashboard._host_command, "")

    def test_redirected_input_cannot_approve_and_host_denial_calls_gate(self):
        dashboard = ConsoleDashboard({})
        access = MagicMock()
        dashboard.set_telnet_access(access)
        dashboard._tty = True
        with patch("rsh_console.sys.stdin", io.StringIO("allow 1\n")), patch.object(dashboard, "log"):
            self.assertFalse(dashboard.host_input_available())
            dashboard.handle_host_command("allow 1")
        access.allow.assert_not_called()
        with patch.object(dashboard, "host_input_available", return_value=True):
            dashboard.handle_host_command("deny 3")
        access.deny.assert_called_once_with(3)

    def test_serial_bridge_has_no_access_gate_and_remote_shell_has_no_approval_command(self):
        import RETRO_SERIAL_HUB as hub
        from retro_os.runtime import create_runtime
        from retro_os.scheduler import TaskScheduler
        with tempfile.TemporaryDirectory() as directory, patch.object(TaskScheduler, "start"):
            root = Path(directory)
            _, _, _, shell, _ = create_runtime(
                {"files": root / "files", "notes": root / "notes", "text": root / "text"},
                profiles_path=root / "keyboard.json",
            )
            self.assertIn("Unknown command", shell.execute("allow 1"))
        gate = MagicMock()
        serial = MagicMock()
        missing = hub.serial.SerialException("FileNotFoundError")
        with patch.object(hub, "TELNET_ACCESS", gate), patch.object(hub, "CONSOLE", None), patch.object(hub, "console_log"), patch.object(hub.serial, "Serial", side_effect=[serial, missing]), patch.object(hub, "bridge_loop") as bridge, patch.object(hub, "configure_screen_clearing"):
            hub.port_worker("TEST", {"port": "TEST", "baud": 9600})
        bridge.assert_called_once()
        gate.accept.assert_not_called()


if __name__ == "__main__":
    unittest.main()
