"""Persistent machine preferences shared by menu and CLI settings."""
import json
from pathlib import Path
import threading
from tempfile import NamedTemporaryFile

_LOCK = threading.RLock()
DEFAULTS = {'pace_ms': 0, 'caps': False, 'protocol': 'XMODEM', 'start': 'menu',
            'reconnect': 'resume', 'idle_seconds': 300, 'columns': 80, 'rows': 24,
            'clear_sequence': '', 'quiet': False}


class MachinePreferences:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('Invalid machine preferences file.')
        return data

    def get(self, name):
        with _LOCK:
            return dict(self._load().get(name, {}))

    def set(self, name, key, value):
        if key not in DEFAULTS:
            raise ValueError('Settings: ' + ', '.join(DEFAULTS))
        if key in ('pace_ms', 'idle_seconds', 'columns', 'rows'):
            value = float(value) if key == 'pace_ms' else int(value)
            if key == 'columns' and value not in (40, 80):
                raise ValueError('Columns: 40 or 80.')
            if key == 'rows' and not 16 <= value <= 100:
                raise ValueError('Terminal height must be 16-100 rows.')
            if key not in ('columns','rows') and not 0 <= value <= (1000 if key == 'pace_ms' else 86400):
                raise ValueError('Setting is out of range.')
        elif key in ('caps', 'quiet'):
            if str(value).lower() not in ('true','false','on','off','1','0'):
                raise ValueError('Use on or off.')
            value = str(value).lower() in ('true','on','1')
        elif key == 'protocol':
            value = str(value).upper()
            if value not in ('XMODEM', 'YMODEM', 'ASCII'):
                raise ValueError('Protocol: XMODEM, YMODEM, ASCII.')
        elif key == 'start' and value not in ('menu','cli'):
            raise ValueError('Starting screen: menu or cli.')
        elif key == 'reconnect' and value not in ('resume','menu'):
            raise ValueError('Reconnect: resume or menu.')
        elif key == 'clear_sequence':
            # Hex bytes avoid embedding control characters into the settings UI.
            value = bytes.fromhex(value).hex()
            if len(value) > 64:
                raise ValueError('Clear sequence must be at most 32 bytes.')
        with _LOCK:
            data = self._load()
            data.setdefault(name, {})[key] = value
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with NamedTemporaryFile(mode='w', encoding='utf-8',
                                        dir=self.path.parent,
                                        prefix=self.path.name + '.', suffix='.tmp',
                                        delete=False) as output:
                    temporary = Path(output.name)
                    output.write(json.dumps(data, indent=2) + '\n')
                temporary.replace(self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return value
