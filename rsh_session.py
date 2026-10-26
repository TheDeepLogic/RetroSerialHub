"""Per-terminal capture, traffic diagnostics, and deferred notification delivery."""
from collections import deque
from contextlib import contextmanager
from pathlib import Path
import re
import threading
import time

_SERVICES = {}
_LOCK = threading.RLock()


class SessionServices:
    def __init__(self, terminal, root):
        self.terminal = terminal
        self.root = Path(root)
        self.lock = threading.RLock()
        self.pending = deque(maxlen=100)
        self.quiet = False
        self.protected = 0
        self.received = self.sent = 0
        self.last_input = None
        self.last_rx = self.last_tx = b''
        self.progress = None
        self.cancelled = threading.Event()
        self.capture = None
        self.capture_path = None
        self._read, self._write = terminal.read, terminal.write
        terminal.read, terminal.write = self.read, self.write
        terminal._rsh_services = self
        with _LOCK:
            _SERVICES[id(terminal)] = self

    def read(self, *args, **kwargs):
        tracker = getattr(self.terminal, '_rsh_activity_tracker', None)
        returning = tracker is not None and not tracker.active and self.last_input is not None
        data = self._read(*args, **kwargs)
        if data and returning and not self.protected and getattr(self.terminal,'_rsh_machine_settings',{}).get('reconnect') == 'menu':
            self.terminal._rsh_reconnect_pending = True
        if data:
            with self.lock:
                self.received += len(data)
                self.last_input = time.monotonic()
                if not getattr(self.terminal, 'secret_input', False):
                    self.last_rx = (self.last_rx + data)[-256:]
        return data

    def write(self, data):
        with self.lock:
            result = self._write(data)
            written = len(data) if result is None else result
            self.sent += written
            if not self.protected and not getattr(self.terminal,"secret_input",False):
                self.last_tx = (self.last_tx + bytes(data[:written]))[-256:]
                if self.capture:
                    try:
                        text = self.capture_translator.feed(bytes(data[:written])).decode('ascii',errors='replace')
                        self.capture.write(text)
                        self.capture.flush()
                    except OSError:
                        self.capture.close()
                        self.capture = None
            return result

    def notify(self, text):
        with self.lock:
            self.pending.append(str(text))

    def deliver(self, force=False):
        with self.lock:
            if self.protected:
                return 'Messages deferred until the transfer finishes.'
            if self.quiet and not force:
                return f'{len(self.pending)} notifications waiting.' if self.pending else ''
            messages = '\n'.join(self.pending)
            self.pending.clear()
            return messages or ('No pending notifications.' if force else '')

    @contextmanager
    def transfer(self):
        with self.lock:
            self.protected += 1
            self.cancelled.clear()
        try:
            yield self
        finally:
            with self.lock:
                self.protected -= 1
                self.progress = None

    def start_capture(self, name):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', name):
            raise ValueError('Capture name: 1-60 letters, digits, - or _.')
        with self.lock:
            if self.capture:
                raise ValueError('Stop the current capture first.')
            self.root.mkdir(parents=True, exist_ok=True)
            self.capture_path = self.root / (name + '.txt')
            self.capture = self.capture_path.open('x', encoding='utf-8', newline='')
            from rsh_terminal import AnsiToTextTranslator
            self.capture_translator = AnsiToTextTranslator(clear_sequence=b'\n',columns=getattr(self.terminal,'_rsh_columns',80))
        return 'Capture started: ' + str(self.capture_path)

    def stop_capture(self):
        with self.lock:
            if self.capture:
                self.capture.close()
                self.capture = None
        return 'Capture stopped.'

    def close(self):
        self.stop_capture()
        self.terminal.read, self.terminal.write = self._read, self._write
        with _LOCK:
            _SERVICES.pop(id(self.terminal), None)


def services():
    with _LOCK:
        return list(_SERVICES.values())


def notify(terminal, text):
    service = getattr(terminal, '_rsh_services', None)
    if service:
        service.notify(text)
    else:
        terminal.write(str(text).encode('ascii', errors='replace'))
