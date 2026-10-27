"""Socket-backed terminal stream used by remote TCP clients."""

import select
import socket


class SocketTerminal:
    """Adapt a TCP socket to the serial-like interface used by the hub."""

    _IAC = 255
    _DO = 253
    _WILL = 251
    _SB = 250
    _SE = 240

    def __init__(self, client_socket):
        self._socket = client_socket
        self._buffer = bytearray()
        self._eof = False
        self._telnet_state = "data"
        self._telnet_command = None
        self._telnet_protocol = False
        self.port = None
        self._rsh_clear_sequence = b"\x0c"

    @property
    def in_waiting(self):
        # Bound each poll even if the peer continuously sends negotiation only.
        for _ in range(16):
            if self._buffer or self._eof:
                break
            readable, _, _ = select.select([self._socket], [], [], 0)
            if not readable:
                break
            data = self._socket.recv(4096)
            if not data:
                self._eof = True
                break
            self._consume_telnet_data(data)
        return len(self._buffer) or (1 if self._eof else 0)

    def read(self, size=1):
        if not self._buffer and not self._eof:
            self.in_waiting
        if not self._buffer:
            return b""

        count = min(size, len(self._buffer))
        data = bytes(self._buffer[:count])
        del self._buffer[:count]
        return data

    def write(self, data):
        written = len(data)
        if self._telnet_protocol:
            data = data.replace(b"\xff", b"\xff\xff")
        self._socket.sendall(data)
        return written

    def close(self):
        self._socket.close()

    def _consume_telnet_data(self, data):
        output = bytearray()
        for byte in data:
            if self._telnet_state == "data":
                if byte == self._IAC:
                    self._telnet_protocol = True
                    self._telnet_state = "iac"
                else:
                    output.append(byte)
            elif self._telnet_state == "iac":
                if byte == self._IAC:
                    output.append(byte)
                    self._telnet_state = "data"
                elif byte in (251, 252, self._DO, 254):
                    self._telnet_command = byte
                    self._telnet_state = "option"
                elif byte == self._SB:
                    self._telnet_state = "subnegotiation"
                else:
                    self._telnet_state = "data"
            elif self._telnet_state == "option":
                if self._telnet_command == self._DO:
                    self._socket.sendall(bytes((self._IAC, 252, byte)))
                elif self._telnet_command == self._WILL:
                    self._socket.sendall(bytes((self._IAC, 254, byte)))
                self._telnet_command = None
                self._telnet_state = "data"
            elif self._telnet_state == "subnegotiation":
                if byte == self._IAC:
                    self._telnet_state = "subnegotiation_iac"
            elif self._telnet_state == "subnegotiation_iac":
                self._telnet_state = (
                    "data" if byte == self._SE else "subnegotiation"
                )
        self._buffer.extend(output)
