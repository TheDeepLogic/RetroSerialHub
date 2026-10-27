"""Physical-host configuration menu. Drafts remain in memory until confirmation."""
from copy import deepcopy

from rsh_config import PROFILE_NAME, validate_settings


def scan_ports():
    from serial.tools.list_ports import comports
    return [(port.device, port.description) for port in sorted(comports())]


class ConfigWizard:
    def __init__(self, store, on_profile=None, scanner=scan_ports, first_run=False):
        self.store, self.on_profile, self.scanner = store, on_profile, scanner
        self.active = True
        self.mode = 'menu'
        self.notice = ''
        self.ports = []
        self.port_page = 0
        self.step = 0
        self.settings = store.load()
        self.first_run = first_run
        self.edit_name = None
        self._scan()

    def _scan(self):
        try:
            self.ports = self.scanner()
            self.port_page = 0
        except (OSError, ImportError) as exc:
            self.ports = []
            self.notice = f'Port scan unavailable: {exc}. Enter a port manually.'

    def _fields(self):
        if self.mode == 'profile':
            fields = [
                ('name', 'Profile name', 'name'), ('port', 'Serial port number or device name', 'port'),
                ('baud', 'Baud rate', 'int'), ('bytesize', 'Data bits (5/6/7/8)', 'int'),
                ('parity', 'Parity (N/E/O/M/S)', 'upper'), ('stopbits', 'Stop bits (1/1.5/2)', 'number'),
                ('xonxoff', 'Software flow control', 'bool'), ('rtscts', 'Hardware flow control', 'bool'),
                ('ansi', 'ANSI menus', 'bool'), ('translate_ansi', 'Translate incoming ANSI to text', 'bool'),
                ('clear_sequence_hex', 'Clear sequence, hex bytes (e.g. 1b76; -=empty)', 'hex'),
                ('ansi_home_clears_screen', 'ANSI home clears screen', 'bool'),
                ('columns', 'Terminal columns (40/80)', 'int'), ('rows', 'Terminal rows (16-100)', 'int'),
                ('idle_timeout_seconds', 'Serial inactivity seconds (0=off)', 'int'),
                ('telnet', 'Enable inbound Telnet', 'bool')]
            if self.values['telnet']:
                fields += [('host', 'Telnet bind address', 'text'), ('tcp_port', 'Telnet TCP port', 'int')]
            if self.edit_name:
                fields = [field for field in fields if field[0] != 'name']
            return fields
        if self.mode == 'general':
            return [('welcome_banner', 'Default welcome banner', 'text'),
                    ('serial_idle_timeout_seconds', 'Default serial inactivity seconds (0=off)', 'int')]
        if self.mode == 'speech':
            return [(key, label, kind) for key, label, kind in (
                ('enabled', 'Enable WOPR host speech', 'bool'), ('rate', 'Speech rate (80-450)', 'int'),
                ('volume', 'Speech volume (0-100)', 'int'), ('voice', 'Speech voice', 'text'),
                ('pitch', 'Speech pitch (0-99)', 'int'), ('gap', 'Word gap (0-100)', 'int'),
                ('executable', 'eSpeak executable (-=auto-detect)', 'text'))]
        return []

    def _draft(self):
        draft = deepcopy(self.settings)
        draft['configuration_completed'] = True
        if self.mode == 'profile':
            values = dict(self.values)
            name = values.pop('name')
            enabled, host, port = values.pop('telnet'), values.pop('host'), values.pop('tcp_port')
            draft['serial_profiles'][name] = values
            if enabled:
                draft['telnet_listeners'][name] = {'host': host, 'port': port}
            else:
                draft['telnet_listeners'].pop(name, None)
        elif self.mode == 'general':
            draft.update(self.values)
        elif self.mode == 'speech':
            draft['wopr_speech'] = dict(self.values)
        return draft

    @property
    def prompt(self):
        if self.mode == 'menu':
            return 'Configuration> '
        if self.mode == 'choose':
            return 'Profile number to edit: '
        fields = self._fields()
        if self.step == len(fields):
            return 'Save this configuration? [yes/no]: '
        key, label, kind = fields[self.step]
        value = self.values[key]
        if kind == 'bool':
            value = 'yes' if value else 'no'
        return f'{label} [{value}]: '

    def lines(self):
        lines = ['HOST CONFIGURATION', 'Saved to settings/local/hub_config.json', '']
        if self.mode == 'menu':
            lines += ['1 Add serial / Telnet profile', '2 List profiles',
                      '3 Hub defaults', '4 WOPR speech', '5 Edit existing profile', 'R Rescan COM ports', 'Q Return to hub',
                      '', 'New profiles start after saving. Global changes require restart.']
            if self.first_run:
                lines += ['First launch: edit the starter profiles or add a computer.',
                          'Q finishes setup and starts the saved profiles.']
        elif self.mode == 'choose':
            lines += [f'{index}. {name}: {profile["port"]}' for index, (name, profile) in enumerate(self.settings['serial_profiles'].items(), 1)]
        else:
            fields = self._fields()
            lines += [f'{self.mode.title()} wizard - step {min(self.step+1, len(fields))}/{len(fields)}', '']
            if self.step == len(fields):
                if self.mode == 'profile':
                    v = self.values
                    lines += [f'Name: {v["name"]}   Port: {v["port"]}   Baud: {v["baud"]}',
                              f'Data: {v["bytesize"]}{v["parity"]}{v["stopbits"]}  XON/XOFF: {v["xonxoff"]}  RTS/CTS: {v["rtscts"]}',
                              f'Terminal: {v["columns"]} columns x {v["rows"]} rows',
                              f'ANSI: {v["ansi"]}   Translate: {v["translate_ansi"]}',
                              f'Clear hex: {v["clear_sequence_hex"] or "(none)"}  Home clears: {v["ansi_home_clears_screen"]}',
                              f'Inactivity: {v["idle_timeout_seconds"]} seconds',
                              f'Telnet: {v["host"]}:{v["tcp_port"]}' if v['telnet'] else 'Telnet: disabled']
                else:
                    lines += [f'{key}: {value}' for key, value in self.values.items()]
            elif fields[self.step][0] == 'port':
                lines += ['Detected serial ports (number or type a device name):']
                for index, (device, description) in enumerate(self.ports[self.port_page*8:self.port_page*8+8], self.port_page*8+1):
                    used = any(p['port'] == device for p in self.settings['serial_profiles'].values())
                    lines.append(f'{index}. {device} - {description[:40]}' + (' [assigned]' if used else ''))
                if not self.ports:
                    lines.append('No ports detected. You can enter an offline port manually.')
                lines += ['Next/Prev=port page  R=rescan']
            else:
                lines += ['Enter keeps the displayed default.', 'Back returns to the previous field. Cancel discards the draft.']
        if self.notice:
            lines += [''] + self.notice.splitlines()
        return lines

    def feed(self, text):
        text = text.strip()
        command = text.lower()
        if command in ('cancel', 'config cancel'):
            self.mode, self.notice = 'menu', 'Draft discarded.'
            return
        if self.mode == 'menu':
            self.settings = self.store.load()
            self.notice = ''
            if command in ('q', 'quit', 'back'):
                if self.first_run:
                    updated = deepcopy(self.settings)
                    updated['configuration_completed'] = True
                    self.settings = self.store.save(updated, expected=self.settings)
                self.active = False
            elif command == 'r':
                self._scan()
            elif command == '2':
                self.notice = '\n'.join(f'{name}: {p["port"]} @ {p["baud"]}, {p.get("columns",80)}x{p.get("rows",24)}' for name, p in self.settings['serial_profiles'].items()) or 'No profiles configured.'
            elif command == '1':
                self.edit_name = None
                self._scan()
                self.mode, self.step = 'profile', 0
                self.values = dict(name='', port='', baud=9600, bytesize=8, parity='N', stopbits=1,
                                   xonxoff=False, rtscts=False, ansi=True, translate_ansi=False,
                                   clear_sequence_hex='', ansi_home_clears_screen=False,
                                   columns=80, rows=24, idle_timeout_seconds=self.settings['serial_idle_timeout_seconds'],
                                   telnet=False, host='0.0.0.0', tcp_port=6400)
                used = {row['port'] for row in self.settings['telnet_listeners'].values()}
                while self.values['tcp_port'] in used:
                    self.values['tcp_port'] += 1
            elif command == '5':
                self.mode = 'choose'
            elif command in ('3', '4'):
                self.mode, self.step = ('general' if command == '3' else 'speech'), 0
                self.values = ({key: self.settings[key] for key in ('welcome_banner', 'serial_idle_timeout_seconds')}
                               if command == '3' else dict(self.settings['wopr_speech']))
            elif command:
                self.notice = 'Choose 1-5, R, or Q.'
            return
        if self.mode == 'choose':
            names = list(self.settings['serial_profiles'])
            if not text.isdigit() or not 1 <= int(text) <= len(names):
                raise ValueError('Choose a listed profile number, or Cancel.')
            name = names[int(text)-1]
            original = self.settings['serial_profiles'][name]
            self.feed('cancel')
            self.feed('1')
            self.values.update(original)
            self.values['name'] = name
            listener = self.settings['telnet_listeners'].get(name)
            self.values['telnet'] = listener is not None
            if listener:
                self.values.update(host=listener['host'], tcp_port=listener['port'])
            self.edit_name = name
            self.step = 0
            self.notice = 'Existing profiles apply when setup finishes or after a restart.'
            return
        if command == 'back':
            self.step = max(0, self.step-1)
            self.notice = ''
            return
        fields = self._fields()
        self.notice = ''
        if self.step == len(fields):
            if command in ('n', 'no'):
                self.mode, self.notice = 'menu', 'Draft discarded.'
            elif command in ('yes', 'y'):
                saved = self.store.save(self._draft(), expected=self.settings)
                name = self.values.get('name') if self.mode == 'profile' else None
                self.settings = saved
                self.mode = 'menu'
                self.notice = ('Saved. Changes apply when first setup finishes.' if self.first_run else
                               'Saved. Restart the hub to apply global settings.')
                if name:
                    self.notice = (f'Saved profile {name}. It will start when first setup finishes.' if self.first_run else
                                   f'Saved profile {name}. Restart the hub to apply changes.')
                    if self.on_profile and not self.edit_name:
                        try:
                            self.on_profile(name, saved)
                            self.notice = f'Saved and started profile {name}.'
                        except (OSError, ValueError, RuntimeError) as exc:
                            self.notice = f'Saved profile {name}, but activation failed: {exc}. Restart the hub.'
            else:
                self.notice = 'Type yes to save, no to discard, or Back to revise.'
            return
        key, label, kind = fields[self.step]
        if key == 'port' and command in ('next', 'prev', 'r'):
            if command == 'r':
                self._scan()
            else:
                self.port_page = max(0, min(max(0,(len(self.ports)-1)//8), self.port_page+(1 if command=='next' else -1)))
            return
        value = self.values[key]
        if text:
            if kind == 'bool':
                if command not in ('yes', 'y', 'true', 'on', '1', 'no', 'n', 'false', 'off', '0'):
                    raise ValueError('Use yes or no.')
                value = command in ('yes', 'y', 'true', 'on', '1')
            elif kind == 'int':
                value = int(text)
            elif kind == 'number':
                value = float(text)
            elif kind == 'name':
                value = text.upper()
            elif kind == 'upper':
                value = text.upper()
            elif kind == 'port' and text.isdigit():
                number = int(text)
                if not 1 <= number <= len(self.ports):
                    raise ValueError('Select a detected port number, or type its device name.')
                value = self.ports[number-1][0]
            elif kind == 'hex':
                value = bytes.fromhex('' if text == '-' else text).hex()
            else:
                value = '' if text == '-' else text
        previous = self.values[key]
        self.values[key] = value
        try:
            if key == 'name':
                if not PROFILE_NAME.fullmatch(value) or value in self.settings['serial_profiles']:
                    raise ValueError('Use a new profile name (1-32 letters, digits, underscores, hyphens).')
            elif key == 'port' and not value:
                raise ValueError('Select a detected port or enter its device name.')
            elif self.mode != 'profile' or self.values['port']:
                validate_settings(self._draft())
        except ValueError:
            self.values[key] = previous
            raise
        self.step += 1
