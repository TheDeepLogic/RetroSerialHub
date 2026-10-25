"""Host CLI integration: local input, shared messaging, menus, and session isolation."""

from contextlib import ExitStack
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from rsh_console import ConsoleDashboard
from rsh_host import HostTerminal


class HostTerminalTests(unittest.TestCase):
    def test_input_queue_preserves_lines_and_output_never_uses_stdout(self):
        output = []
        terminal = HostTerminal(output.append)
        terminal.submit("calc 6 * 7")
        terminal.submit("")
        terminal.send_key("\x18")
        self.assertEqual(terminal.in_waiting, 1)
        self.assertEqual(terminal.read(100), b"calc 6 * 7\r\r\x18")
        self.assertEqual(terminal.write(b"result\r\n"), 8)
        self.assertEqual(output, [b"result\r\n"])
        terminal.close()
        with self.assertRaises(ConnectionError):
            terminal.submit("calc 1+1")

    def test_dashboard_dispatches_commands_and_keeps_approvals_local(self):
        dashboard = ConsoleDashboard({})
        terminal, access = MagicMock(), MagicMock()
        dashboard.set_host_terminal(terminal)
        dashboard.set_telnet_access(access)
        with patch.object(dashboard, "host_input_available", return_value=True):
            dashboard.handle_host_command("msg to APPLE2 Hello From Host")
            dashboard.handle_host_command("")
            dashboard.handle_host_command("allow 3")
        self.assertEqual(terminal.submit.call_args_list[0].args, ("msg to APPLE2 Hello From Host",))
        self.assertEqual(terminal.submit.call_count, 2)
        access.allow.assert_called_once_with(3)

    def test_redirected_input_cannot_execute_commands(self):
        dashboard = ConsoleDashboard({})
        terminal = MagicMock()
        dashboard.set_host_terminal(terminal)
        dashboard._tty = True
        with patch("rsh_console.sys.stdin", io.StringIO("calc 1+1\n")), patch.object(dashboard, "log"):
            dashboard.handle_host_command("calc 1+1")
        terminal.submit.assert_not_called()

    def test_password_input_is_masked_not_saved_in_history_or_treated_as_approval(self):
        dashboard = ConsoleDashboard({})
        terminal, access = MagicMock(), MagicMock()
        terminal.secret_input = True
        dashboard.set_host_terminal(terminal)
        dashboard.set_telnet_access(access)
        access.pending.return_value = []
        with patch.object(dashboard, "host_input_available", return_value=True):
            for key in "allow 3":
                dashboard._host_key(key)
            self.assertNotIn("Host> allow 3", "\n".join(dashboard._frame()))
            dashboard._host_key("\r")
        self.assertEqual(list(dashboard._command_history), [])
        terminal.submit.assert_called_once_with("allow 3")
        access.allow.assert_not_called()

    def test_output_capture_history_scrolling_and_clear(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_host_terminal(MagicMock())
        dashboard.append_host_output(b"cli> cal")
        dashboard.append_host_output(b"c 6*7\r")
        dashboard.append_host_output(b"\n\x1b[32m42\x1b[0m\r\ncli> ")
        self.assertEqual(list(dashboard._host_output), ["cli> calc 6*7", "42"])
        self.assertEqual(dashboard._host_output_line, "cli> ")
        for index in range(40):
            dashboard.append_host_output(f"row {index}\r\n".encode())
        with patch.object(dashboard, "host_input_available", return_value=True):
            dashboard._frame()
            dashboard._host_special_key("page_up")
            self.assertGreater(dashboard._host_output_offset, 0)
            dashboard._host_key("a")
            dashboard._host_key("\r")
            dashboard._host_key("b")
            dashboard._host_special_key("history_up")
            self.assertEqual(dashboard._host_command, "a")
            dashboard._host_special_key("history_down")
            self.assertEqual(dashboard._host_command, "b")
            dashboard.handle_host_command("clear")
        self.assertEqual(list(dashboard._host_output), [])


class HostHubIntegrationTests(unittest.TestCase):
    def setUp(self):
        import RETRO_SERIAL_HUB as hub
        from retro_os.scheduler import TaskScheduler
        self.hub = hub
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ("files", "notes", "text"):
            (self.root / folder).mkdir()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (("BASE_DIR", self.root), ("FILES_DIR", self.root / "files"),
                            ("NOTES_DIR", self.root / "notes"), ("TEXT_DIR", self.root / "text"),
                            ("CONSOLE", None)):
            self.stack.enter_context(patch.object(hub, name, value))
        self.stack.enter_context(patch.object(TaskScheduler, "start"))
        self.stack.enter_context(patch("retro_os.toolkit.start_calendar_reminders"))
        self.output = bytearray()
        self.output_lock = threading.Lock()
        def collect(data):
            with self.output_lock:
                self.output.extend(data)
        self.terminal = HostTerminal(collect)
        self.addCleanup(self.terminal.stop)
        self.terminal.start(hub.host_console_worker)
        self.wait_for(lambda: b"cli> " in self.output)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.01)
        self.fail("Host session did not respond: " + self.output.decode(errors="replace")[-1500:])

    def test_host_lists_terminals_sends_targeted_message_and_broadcasts(self):
        class OtherTerminal:
            _profile_name = "APPLE2"
            _terminal_name = "APPLE2"
            def __init__(self):
                self.output = bytearray()
            def write(self, data):
                self.output.extend(data)
        apple, ibm = OtherTerminal(), OtherTerminal()
        ibm._profile_name = "IBM"
        ibm._terminal_name = "IBM@192.168.7.20"
        for terminal in (apple, ibm):
            self.hub.register_active_terminal(terminal)
            self.addCleanup(self.hub.unregister_active_terminal, terminal)
        self.terminal.submit("terminals")
        self.wait_for(lambda: b"Connected terminals:" in self.output and b"IBM@192.168.7.20" in self.output)
        self.terminal.submit("msg to APPLE2 Hello From The Host")
        self.wait_for(lambda: b"[MESSAGE from Host] Hello From The Host" in apple.output)
        self.assertNotIn(b"Hello From The Host", ibm.output)
        self.terminal.submit("broadcast Hello Everybody")
        self.wait_for(lambda: b"[ALERT from Host] Hello Everybody" in apple.output and b"Hello Everybody" in ibm.output)
        self.terminal.submit("calc 6 * 7")
        self.wait_for(lambda: b"\r\n42\r\n" in self.output)

    def test_host_can_open_numbered_menus_and_complete_interactive_tool(self):
        for command in ("ATM", "5", "E", "1", "72", "F", "C"):
            self.terminal.submit(command)
        self.wait_for(lambda: b"22.2222222222" in self.output)
        self.assertIn(b"--- UNIT CONVERTER ---", self.output)
        self.terminal.submit("Q")
        self.terminal.submit("CLI")
        self.terminal.submit("calc 12 * 12")
        self.wait_for(lambda: b"\r\n144\r\n" in self.output)

    def test_host_and_remote_runtime_keep_their_context_and_share_one_scheduler(self):
        from retro_os.core import Session
        from retro_os.runtime import create_runtime
        from retro_os.modules import games
        files = {"files": self.root / "files", "notes": self.root / "notes",
                 "text": self.root / "text", "mail": self.root / "mail"}
        host_requests, remote_requests = [], []
        host_session = Session(client_type="host", user="Host")
        remote_session = Session(client_type="telnet", user="IBM")
        _, _, host, host_shell, _ = create_runtime(files, session=host_session, activate_module=host_requests.append, profiles_path=self.root / "keyboard.json")
        _, _, remote, _, _ = create_runtime(files, session=remote_session, activate_module=remote_requests.append, profiles_path=self.root / "keyboard.json")
        self.assertIs(host.scheduler, remote.scheduler)
        host_shell.execute("logo")
        self.assertEqual(host_requests, ["logo"])
        self.assertEqual(remote_requests, [])
        host_shell.execute("games wordguess new")
        self.assertIn(host_session.id, games._word_guess_games)
        self.assertNotIn(remote_session.id, games._word_guess_games)
        self.assertIn("Host", host.mail_manager.get_sender_identity())


if __name__ == "__main__":
    unittest.main()
