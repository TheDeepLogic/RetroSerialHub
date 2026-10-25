"""A local console terminal that uses the same hub session loop as other clients."""

from __future__ import annotations

import threading


class HostTerminal:
    """Queue local keyboard input and route session output into the dashboard."""

    _rsh_host_console = True
    _profile_name = "Host"
    _terminal_name = "Host"
    _client_id = "host-console"
    _rsh_columns = 80
    _rsh_input_seen = True
    secret_input = False
    port = None

    def __init__(self, output):
        self.output = output
        self._lock = threading.RLock()
        self._input = bytearray()
        self._closed = False
        self._thread = None

    @property
    def closed(self):
        with self._lock:
            return self._closed

    @property
    def in_waiting(self):
        with self._lock:
            if self._closed:
                raise ConnectionError("Host console session closed.")
            # Do not prefetch following lines: an interactive submenu may need
            # them after the current command is dispatched.
            return min(1, len(self._input))

    def read(self, size=1):
        with self._lock:
            if self._closed:
                raise ConnectionError("Host console session closed.")
            count = min(size, len(self._input))
            data = bytes(self._input[:count])
            del self._input[:count]
            return data

    def write(self, data):
        if self.closed:
            raise ConnectionError("Host console session closed.")
        self.output(bytes(data))
        return len(data)

    def send_key(self, text):
        data = text.encode("ascii", errors="replace") if isinstance(text, str) else bytes(text)
        with self._lock:
            if self._closed:
                raise ConnectionError("Host console session is not running.")
            if len(self._input) + len(data) > 65536:
                raise ValueError("Host input queue is full; wait for the current operation.")
            self._input.extend(data)

    def submit(self, command):
        self.send_key(command + "\r")

    def start(self, runner):
        def run():
            try:
                runner(self)
            except Exception as exc:
                if not self.closed:
                    self.output(f"\r\nHost session stopped: {exc}\r\n".encode("ascii", errors="replace"))
            finally:
                self.close()
        self._thread = threading.Thread(target=run, name="host-hub-session", daemon=True)
        self._thread.start()

    def close(self):
        with self._lock:
            self._closed = True
            self._input.clear()

    def stop(self):
        self.close()
        if self._thread is not None:
            self._thread.join(timeout=1)
