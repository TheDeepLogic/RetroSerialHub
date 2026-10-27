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
        self.inbox = deque(maxlen=100)
        self._next_message = 1
        self._prompt_tail = ''
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
            if not self.protected:
                text = bytes(data[:written]).decode('ascii', errors='replace')
                text = re.sub(r'\x1b(?:\[[0-9;?]*[A-Za-z]|.)', '', text)
                for char in text:
                    if char == '\n':
                        self._prompt_tail = ''
                    elif char in ('\r', '\b'):
                        if char == '\b':
                            self._prompt_tail = self._prompt_tail[:-1]
                    elif char.isprintable():
                        self._prompt_tail = (self._prompt_tail + char)[-160:]
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
            message = {'id': self._next_message, 'text': str(text), 'read': False, 'announced': False}
            self._next_message += 1
            self.inbox.append(message)
            self._sync_pending()
            self._announce_locked()
            return message['announced']

    def _sync_pending(self):
        self.pending.clear()
        self.pending.extend(message['text'] for message in self.inbox if not message['read'])

    def _announce_locked(self):
        if self.protected or self.quiet:
            return
        unseen = [message for message in self.inbox if not message['read'] and not message['announced']]
        if not unseen:
            return
        columns = getattr(self.terminal, '_rsh_columns', 80)
        width = 39 if columns == 40 else 79
        prompt = self._prompt_tail
        lines = [f'*** NEW MESSAGE ({len(self.pending)} unread) ***']
        for message in unseen[:3]:
            preview = next((line.strip() for line in message['text'].splitlines() if line.strip()), 'Message')
            preview = ''.join(char for char in preview if char.isprintable())
            lines.append(preview[:width])
        if len(unseen) > 3:
            lines.append(f'+{len(unseen)-3} more messages')
        lines.append('M=Messages (menu); CLI: MESSAGES')
        try:
            # Same write lock as transfer protection: no banner can enter a packet.
            self.write(('\r\n' + '\r\n'.join(lines) + '\r\n' + prompt).encode('ascii', errors='replace'))
        except OSError:
            return
        for message in unseen:
            message['announced'] = True

    def announce_pending(self):
        with self.lock:
            self._announce_locked()

    def message_list(self):
        with self.lock:
            return [dict(message) for message in reversed(self.inbox)]

    def read_message(self, identifier):
        with self.lock:
            if self.protected:
                return 'Messages deferred until the transfer finishes.'
            for message in self.inbox:
                if message['id'] == identifier:
                    message['read'] = True
                    self._sync_pending()
                    return message['text']
            return 'That message is no longer available.'

    def deliver(self, force=False):
        with self.lock:
            if self.protected:
                return 'Messages deferred until the transfer finishes.'
            if self.quiet and not force:
                return f'{len(self.pending)} messages waiting.' if self.pending else ''
            messages = '\n'.join(self.pending)
            for message in self.inbox:
                message['read'] = True
            self.pending.clear()
            return messages or ('No unread messages.' if force else '')

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
                self._announce_locked()

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
        return service.notify(text)
    else:
        terminal.write(str(text).encode('ascii', errors='replace'))
        return True
