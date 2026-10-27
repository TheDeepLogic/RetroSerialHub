import socket
import unittest

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


if __name__ == "__main__":
    unittest.main()
