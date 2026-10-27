"""Validated JSON hub settings and atomic, conflict-aware host configuration saves."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import tempfile
import threading

from rsh_storage import settings_path
from rsh_welcome import validate_banner

_LOCK = threading.RLock()
PROFILE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,31}')
SPEECH_DEFAULTS = dict(enabled=True, rate=145, volume=85, voice='en-us', pitch=25,
                       gap=3, executable='')


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{label} must be {minimum}-{maximum}.')


def _text(value, label, maximum=256, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or
            (not empty and not value.strip()) or any(ord(char) < 32 for char in value)):
        raise ValueError(f'Invalid {label}.')


def port_identity(port):
    match = re.fullmatch(r'(?:\\\\\.\\)?COM(\d+)', port, re.IGNORECASE)
    return 'COM'+str(int(match[1])) if match else port


def validate_settings(data):
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        raise ValueError('hub_config.json requires schema_version 1.')
    result = deepcopy(data)
    if 'configuration_completed' in result and type(result['configuration_completed']) is not bool:
        raise ValueError('configuration_completed must be true or false.')
    _text(result.get('welcome_banner'), 'welcome banner', 80)
    result['welcome_banner'] = validate_banner(result['welcome_banner'])
    _integer(result.get('serial_idle_timeout_seconds'), 0, 86400, 'Serial inactivity timeout')
    profiles = result.get('serial_profiles')
    listeners = result.get('telnet_listeners')
    if not isinstance(profiles, dict) or not isinstance(listeners, dict):
        raise ValueError('serial_profiles and telnet_listeners must be objects.')
    seen_ports = set()
    for name, profile in profiles.items():
        if not isinstance(name, str) or not PROFILE_NAME.fullmatch(name) or not isinstance(profile, dict):
            raise ValueError('Profile names use 1-32 letters, digits, underscores, or hyphens.')
        _text(profile.get('port'), f'{name} serial port')
        identity = port_identity(profile['port'])
        if identity in seen_ports:
            raise ValueError(f'Serial port {profile["port"]} is assigned more than once.')
        seen_ports.add(identity)
        _integer(profile.get('baud'), 50, 4000000, f'{name} baud')
        if type(profile.get('bytesize', 8)) is not int or profile.get('bytesize', 8) not in (5, 6, 7, 8):
            raise ValueError('Data bits must be 5, 6, 7, or 8.')
        if profile.get('parity', 'N') not in ('N', 'E', 'O', 'M', 'S'):
            raise ValueError('Parity must be N, E, O, M, or S.')
        if type(profile.get('stopbits', 1)) not in (int, float) or profile.get('stopbits', 1) not in (1, 1.5, 2):
            raise ValueError('Stop bits must be 1, 1.5, or 2.')
        if type(profile.get('columns', 80)) is not int or profile.get('columns', 80) not in (40, 80):
            raise ValueError('Terminal width must be 40 or 80.')
        _integer(profile.get('rows', 24), 16, 100, 'Terminal height')
        for key in ('xonxoff', 'rtscts', 'ansi', 'translate_ansi', 'ansi_home_clears_screen'):
            if key in profile and type(profile[key]) is not bool:
                raise ValueError(f'{name} {key} must be true or false.')
        if 'idle_timeout_seconds' in profile:
            _integer(profile['idle_timeout_seconds'], 0, 86400, 'Profile inactivity timeout')
        sequence = profile.get('clear_sequence_hex', '')
        try:
            if not isinstance(sequence, str) or len(bytes.fromhex(sequence)) > 32:
                raise ValueError()
        except ValueError as exc:
            raise ValueError('Screen clear sequence must be at most 32 hex bytes.') from exc
    seen_listeners = []
    for name, listener in listeners.items():
        if name not in profiles or not isinstance(listener, dict):
            raise ValueError('Every Telnet listener must refer to a serial profile.')
        _text(listener.get('host'), 'Telnet bind address')
        _integer(listener.get('port'), 1, 65535, 'Telnet port')
        host, port = listener['host'], listener['port']
        for previous_host, previous_port in seen_listeners:
            if port == previous_port and (host == previous_host or host in ('0.0.0.0', '::') or previous_host in ('0.0.0.0', '::')):
                raise ValueError('Telnet listeners have conflicting bind addresses and ports.')
        seen_listeners.append((host, port))
    speech = result.get('wopr_speech')
    if not isinstance(speech, dict):
        raise ValueError('wopr_speech must be an object.')
    speech = result['wopr_speech'] = {**SPEECH_DEFAULTS, **speech}
    if type(speech['enabled']) is not bool:
        raise ValueError('Speech enabled must be true or false.')
    for key, minimum, maximum in (('rate', 80, 450), ('volume', 0, 100), ('pitch', 0, 99), ('gap', 0, 100)):
        _integer(speech[key], minimum, maximum, 'Speech '+key)
    _text(speech['voice'], 'speech voice', 100)
    _text(speech['executable'], 'speech executable', 1024, empty=True)
    return result


def _read(path):
    try:
        return validate_settings(json.loads(path.read_text(encoding='utf-8')))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Invalid JSON in {path}.') from exc


def _save(path, data):
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            json.dump(data, output, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


class HubConfigStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else settings_path('hub_config.json')

    def load(self):
        with _LOCK:
            return _read(self.path)

    def save(self, data, expected=None):
        validated = validate_settings(data)
        with _LOCK:
            if expected is not None and self.load() != expected:
                raise ValueError('Configuration changed while this wizard was open. Cancel and reopen it.')
            _save(self.path, validated)
        return validated


def load_settings():
    return HubConfigStore().load()


def serial_profiles(settings):
    profiles = deepcopy(settings['serial_profiles'])
    for profile in profiles.values():
        sequence = profile.pop('clear_sequence_hex', '')
        if sequence:
            profile['ansi_clear_sequence'] = bytes.fromhex(sequence)
    return profiles
