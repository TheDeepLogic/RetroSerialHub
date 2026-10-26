"""Session tools: captures, diagnostics, file search, and persisted launch presets."""
from rsh_storage import settings_dir, settings_path
import fnmatch
import os
from pathlib import Path
import shlex
import time

from rsh_preferences import MachinePreferences
from rsh_session import services
from .toolkit import JsonRecords
from .workshop import hexdump


class SessionTools:
    def __init__(self, context, files):
        self.context, self.files = context, files
        root = context.fs.get('tool_data', settings_dir(files.root.parent))
        self.presets = JsonRecords(root / 'launch_presets.json')
        self.preferences = MachinePreferences(root / 'machine_preferences.json')

    def terminal(self):
        return getattr(self.context.host_env, 'terminal', None)

    def service(self):
        terminal = self.terminal()
        service = getattr(terminal, '_rsh_services', None)
        if service is None:
            raise ValueError('This command requires a connected hub session.')
        return service

    def capture(self, args):
        service = self.service()
        action = args[0].lower() if args else 'status'
        if action == 'start' and len(args) == 2:
            return service.start_capture(args[1])
        if action == 'stop':
            return service.stop_capture()
        if action == 'list':
            return '\n'.join(p.name for p in sorted(service.root.glob('*.txt'))) or 'No captures.'
        if action in ('view','export') and len(args) >= 2:
            name = args[1].removesuffix('.txt')
            if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
                raise ValueError('Choose a capture name from the list.')
            path = service.root / (name + '.txt')
            if action == 'view':
                return self.context.host_env.shell.execute(shlex.join(['view', str(path)]))
            if len(args) != 3:
                raise ValueError('capture export <name> <new-output-path>')
            with path.open('rb') as source, Path(args[2]).expanduser().open('xb') as output:
                import shutil
                shutil.copyfileobj(source, output)
            return 'Capture exported.'
        if action == 'status':
            return ('Capturing: ' + str(service.capture_path)) if service.capture else 'Session capture is off. Binary transfers and secret input are excluded.'
        return 'capture [status | start <name> | stop | list | view <name> | export <name> <new-path>]'

    def diagnostics(self, args):
        action = args[0].lower() if args else 'list'
        records = services()
        if len(args) > 1:
            records = [s for s in records if args[1].casefold() in
                       (str(getattr(s.terminal, '_terminal_name', '')).casefold(), str(getattr(s.terminal, 'port', '')).casefold())]
        if not records:
            return 'No matching connected sessions.'
        lines = []
        for service in records:
            t = service.terminal
            if action == 'cancel':
                if self.context.session.client_type != 'host':
                    raise ValueError('Transfer cancellation is available at the host console.')
                service.cancelled.set()
                lines.append('Cancellation requested.')
                continue
            label = getattr(t, '_terminal_name', getattr(t, '_profile_name', 'Terminal'))
            lines.append(f'{label} | {getattr(t, "port", None) or "host/network"}')
            lines.append(f'RX {service.received} B | TX {service.sent} B | Pending {len(service.pending)}')
            lines.append('Last input: ' + (f'{int(time.monotonic()-service.last_input)}s ago' if service.last_input is not None else 'none'))
            if action in ('info','hex'):
                lines.append(' '.join(f'{key}={getattr(t,key,"n/a")}' for key in ('baudrate','bytesize','parity','stopbits','xonxoff','rtscts')))
                for key in ('cts','dsr','cd','ri'):
                    try:
                        value = getattr(t, key, 'unsupported')
                    except OSError:
                        value = 'unavailable'
                    lines.append(f'{key.upper()}: {value}')
            if service.progress:
                lines.append('Transfer: ' + str(service.progress))
            if action == 'hex':
                lines.extend(('Recent RX (secret input excluded):', hexdump(service.last_rx), 'Recent TX (binary transfers excluded):', hexdump(service.last_tx)))
        return '\n'.join(lines)

    def notifications(self, args):
        service = self.service()
        if args and args[0] in ('quiet','on','off'):
            value = args[-1].lower()
            if value not in ('on','off'):
                return 'notifications quiet <on|off>'
            service.quiet = value == 'on'
            return 'Quiet mode ' + value + '.'
        return service.deliver(force=True)

    def machine(self, args):
        name = getattr(self.terminal(), '_profile_name', self.context.session.user or 'Host')
        if not args or args[0] == 'list':
            from rsh_preferences import DEFAULTS
            settings = dict(DEFAULTS, **self.preferences.get(name))
            return f'Machine: {name}\n' + '\n'.join(f'{k}: {v}' for k,v in settings.items())
        if len(args) != 2:
            return 'machine <setting> <value> | machine list'
        key, value = args
        value = self.preferences.set(name, key, value)
        terminal = self.terminal()
        if terminal:
            apply_preferences(terminal, {key:value}, self.context.session)
        return f'Saved {key}: {value}. Starting screen and reconnect policy apply on the next entry.'

    def find(self, args):
        if not args or args == ['help']:
            return 'findfiles <filename-pattern> [host-folder]\nExamples: *.dsk, *manual*, *.mp3. Results support fileman actions by number.'
        pattern = args[0].casefold()
        if not any(c in pattern for c in '*?['):
            pattern = '*' + pattern + '*'
        root = self.files.path(args[1], numbered=False) if len(args) > 1 else self.files.cwd
        if not root.is_dir():
            raise ValueError('Choose a search directory.')
        results, skipped, incomplete = [], [], False
        deadline = time.monotonic() + 5
        for folder, directories, names in os.walk(root, followlinks=False, onerror=lambda e: skipped.append(str(e))):
            directories.sort(key=str.casefold)
            for name in sorted(names, key=str.casefold):
                if fnmatch.fnmatchcase(name.casefold(), pattern):
                    results.append(Path(folder) / name)
                    if len(results) >= 200:
                        break
            if len(results) >= 200 or time.monotonic() >= deadline:
                incomplete = True; break
        self.files.entries = results
        lines = [f'{i}. {p}' for i,p in enumerate(results,1)] or ['No matching files.']
        if incomplete:
            lines.append('Search limited to 200 results / 5 seconds; narrow the folder or pattern.')
        if skipped:
            lines.append(f'Skipped {len(skipped)} inaccessible locations.')
        return '\n'.join(lines)


    def preset(self, args):
        action = args[0].lower() if args else 'list'
        if action == 'add-menu' and len(args) == 6:
            from .core import Shell
            args = ['add',*args[1:5],*([] if args[5] == '-' else Shell.split_line(args[5]))]
            action = 'add'
        rows = self.presets.load()
        if action == 'list':
            return '\n'.join(f'{r["name"]}: {r["mode"]} {r["app"]} ({r["cwd"]})' for r in rows) or 'No launch presets.'
        if action == 'add' and len(args) >= 5:
            name, mode, cwd, app, *arguments = args[1:]
            if mode not in ('background','terminal','keyboard'):
                raise ValueError('Mode: background, terminal, keyboard.')
            folder = Path(cwd).expanduser().resolve(strict=True)
            if not folder.is_dir():
                raise ValueError('Working directory must be a folder.')
            def add(records):
                if any(r['name'].casefold() == name.casefold() for r in records):
                    raise ValueError('Preset name already exists.')
                records.append({'name':name,'mode':mode,'cwd':str(folder),'app':app,'args':arguments})
            self.presets.change(add)
            return 'Launch preset saved.'
        if action in ('run','delete') and len(args) == 2:
            row = next((r for r in rows if r['name'].casefold() == args[1].casefold()), None)
            if not row:
                raise ValueError('Preset not found.')
            if action == 'delete':
                self.presets.change(lambda records: records.remove(next(r for r in records if r['name'] == row['name'])))
                return 'Preset deleted.'
            if row['mode'] == 'background':
                self.context.host_env.launch_app(row['app'], row['args'], cwd=row['cwd'])
            elif self.context.activate_module:
                self.context.activate_module(('preset_launch', row))
            return 'Launching ' + row['name']
        return 'presets [list | add <name> <background|terminal|keyboard> <work-dir> <app> [args...] | run <name> | delete <name>]'


def apply_preferences(terminal, settings, session=None):
    if 'pace_ms' in settings:
        terminal._rsh_pace_delay = settings['pace_ms'] / 1000
        if session:
            session.pace_delay = terminal._rsh_pace_delay
    if 'caps' in settings:
        terminal._rsh_caps_only = settings['caps']
        if session:
            session.caps_only = settings['caps']
    if 'columns' in settings:
        terminal._rsh_columns = settings['columns']
        if session:
            session.cols = settings['columns']
    if 'rows' in settings:
        rows = int(settings['rows'])
        if not 16 <= rows <= 100:
            raise ValueError('Terminal height must be 16-100 rows.')
        terminal._rsh_rows = rows
        if session:
            session.rows = rows
    if settings.get('clear_sequence'):
        terminal._rsh_clear_sequence = bytes.fromhex(settings['clear_sequence'])
    if 'protocol' in settings:
        terminal._rsh_transfer_mode = settings['protocol']
    if 'idle_seconds' in settings:
        tracker = getattr(terminal, '_rsh_activity_tracker', None)
        if tracker:
            tracker.timeout = settings['idle_seconds']
    if 'quiet' in settings and getattr(terminal, '_rsh_services', None):
        terminal._rsh_services.quiet = settings['quiet']
    terminal._rsh_machine_settings = dict(getattr(terminal, '_rsh_machine_settings', {}), **settings)
