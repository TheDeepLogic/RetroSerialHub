import socket
import unittest
from unittest.mock import Mock, patch

from rsh_server import SocketTerminal


class SocketTerminalTests(unittest.TestCase):
    def setUp(self):
        self.client, self.peer = socket.socketpair()
        self.terminal = SocketTerminal(self.client)

    def tearDown(self):
        self.terminal.close()
        self.peer.close()

    def test_reads_available_input_and_reports_buffered_bytes(self):
        self.peer.sendall(b"hello")

        self.assertEqual(self.terminal.in_waiting, 5)
        self.assertEqual(self.terminal.read(2), b"he")
        self.assertEqual(self.terminal.in_waiting, 3)
        self.assertEqual(self.terminal.read(3), b"llo")
        self.assertEqual(self.terminal.in_waiting, 0)

    def test_writes_output_to_client(self):
        self.assertEqual(self.terminal.write(b"menu"), 4)
        self.assertEqual(self.peer.recv(4), b"menu")

    def test_reports_eof_as_readable_then_returns_empty_bytes(self):
        self.peer.close()

        self.assertEqual(self.terminal.in_waiting, 1)
        self.assertEqual(self.terminal.read(1), b"")

    def test_rejects_telnet_options_and_keeps_terminal_input(self):
        self.peer.sendall(b"\xff\xfb\x01A")

        self.assertEqual(self.terminal.in_waiting, 1)
        self.assertEqual(self.terminal.read(1), b"A")
        self.assertEqual(self.peer.recv(3), b"\xff\xfe\x01")

    def test_escapes_telnet_command_byte_after_negotiation(self):
        self.peer.sendall(b"\xff\xfd\x03")
        self.assertEqual(self.terminal.in_waiting, 0)
        self.assertEqual(self.peer.recv(3), b"\xff\xfc\x03")

        self.assertEqual(self.terminal.write(b"\xff"), 1)
        self.assertEqual(self.peer.recv(2), b"\xff\xff")

    def test_continuous_control_traffic_yields_after_bounded_poll(self):
        client = Mock()
        client.recv.return_value = b"\xff\xf1" * 2048
        terminal = SocketTerminal(client)
        with patch("rsh_server.select.select", return_value=([client], [], [])):
            self.assertEqual(terminal.in_waiting, 0)
        self.assertEqual(client.recv.call_count, 16)
        client.recv.return_value = b"next command\r"
        with patch("rsh_server.select.select", return_value=([client], [], [])):
            self.assertEqual(terminal.read(13), b"next command\r")

    def test_fragmented_negotiation_and_escaped_binary_input(self):
        for data in (b"\xff", b"\xfb", b"\x01"):
            self.peer.sendall(data)
            self.assertEqual(self.terminal.in_waiting, 0)
        self.assertEqual(self.peer.recv(3), b"\xff\xfe\x01")
        self.peer.sendall(b"\xff\xfa\x01ignored\xff\xff\xff\xf0A\xff\xffB")
        self.assertEqual(self.terminal.read(3), b"A\xffB")


if __name__ == "__main__":
    unittest.main()
