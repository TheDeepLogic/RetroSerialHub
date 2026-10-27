"""Reproduce engineering-note measurements without opening real ports or personal data.

Run from the repository root: python -m tests.measure_technical_behaviors
"""

import io
import json
import math
import os
from pathlib import Path
import platform
from types import SimpleNamespace
import tempfile
from unittest.mock import patch

from retro_os.menu import OSFlyoutMenu
from rsh_console import ConsoleDashboard, VERSION
from rsh_host_access import HostCommandAccess
from rsh_host_screen import HostScreen
from rsh_session import SessionServices
from rsh_transfer import ACK, NAK, xsend
import rsh_notes
from tests.test_rsh_console import VirtualScreen


class MemoryTerminal:
    _rsh_columns = 80
    _rsh_rows = 24
    secret_input = False

    def __init__(self, incoming=b''):
        self.incoming = bytearray(incoming)
        self.output = bytearray()
        self.read_bytes = 0

    def write(self, data):
        self.output.extend(data)
        return len(data)

    def read(self, count=1):
        data = bytes(self.incoming[:count])
        del self.incoming[:count]
        self.read_bytes += len(data)
        return data


class Shortcuts:
    def __init__(self, count):
        self.items = [{'name': f'Tool {index}', 'command': f'calc {index}'} for index in range(count)]

    def has_shortcuts(self):
        return bool(self.items)

    def list_shortcuts(self):
        return self.items


def layout_measurements():
    native_cases = 0
    capacities = {}
    for width in (40, 80):
        for height in (16, 20, 24, 25, 30, 43):
            for shortcuts in (0, 2, 8, 17):
                for section in ['shortcuts', *range(7)]:
                    for remote in (False, True):
                        for unread in (0, 3):
                            menu = OSFlyoutMenu(section, shortcuts_manager=Shortcuts(shortcuts))
                            text = menu.render(columns=width, rows=height, is_remote=remote,
                                               status='12:34 | Serial 4 Telnet 3', messages_count=unread)
                            lines = text.split('\r\n')
                            screen = VirtualScreen(width, height)
                            screen.feed(text)
                            assert len(lines) == height and all(len(line) < width for line in lines)
                            assert screen.scrolls == 0 and screen.row == height - 1
                            native_cases += 1
                            capacities[str(height)] = menu.page_capacity
    host_cases = 0
    counts = {'stacked': 0, 'side_by_side': 0, 'status_above': 0}
    for width in (20, 40, 80, 100, 123, 124, 150, 200):
        for height in (5, 12, 16, 24, 30, 40, 50):
            for scenario in ('empty', 'four_profiles', 'crowded'):
                profiles = {} if scenario == 'empty' else {
                    f'P{index}': {'serial_port': f'COM{index+1}', 'serial_status': 'OPEN',
                                 'tcp_status': 'LISTENING', 'tcp_port': 6400+index,
                                 'endpoint': f'192.0.2.1:{6400+index}'} for index in range(4)}
                dashboard = ConsoleDashboard(profiles)
                dashboard._color = False
                dashboard.set_host_terminal(MemoryTerminal())
                if scenario == 'crowded':
                    for index in range(40):
                        dashboard.set_user_activity(str(index), 'calc', user_label=f'Client{index}')
                    requests = [{'id': index, 'ip': f'192.0.2.{index}', 'profile': 'P0',
                                 'seconds_left': 60} for index in range(1, 21)]
                    dashboard.set_telnet_access(SimpleNamespace(pending=lambda: requests))
                    dashboard._events.append(('Synthetic failure', 'red'))
                dashboard.append_host_output('Menu heading\ncli> ')
                capture = io.StringIO()
                with patch('rsh_console.sys.stdout', capture), patch('shutil.get_terminal_size',
                           return_value=os.terminal_size((width, height))):
                    dashboard._draw_frame()
                viewport = VirtualScreen(width, height)
                viewport.feed(capture.getvalue())
                assert viewport.scrolls == 0 and dashboard._frame_lines <= height
                assert 0 <= viewport.row < height and 0 <= viewport.column < width
                assert 'cli>' in viewport.text()
                full_status = dashboard._status_panel_rows(width-1)
                kind = ('stacked' if width < 124 or height < 8 else
                        'status_above' if height >= len(full_status)+31 else 'side_by_side')
                counts[kind] += 1
                host_cases += 1
    return {'native_menu_cases': native_cases, 'native_scrolls': 0,
            'menu_action_capacity_by_height': capacities, 'host_cases': host_cases,
            'host_scrolls': 0, 'host_layouts': counts}


def screen_measurements():
    fixtures = {
        'erase_suffix': ('Downloading 100 percent\rDone\x1b[K', ['Done']),
        'clear_and_home': ('Old\ntext\x1b[2J\x1b[HReady: ', ['Ready: ', '']),
        'cursor_restore': ('Header\nOld row\nInput: \x1b[s\x1b[2;1HNew\x1b[K\x1b[u',
                           ['Header', 'New', 'Input: ']),
        'osc_and_sgr': ('\x1b]0;not-a-dashboard-title\x07\x1b[31mPrompt: \x1b[0m', ['Prompt: ']),
    }
    partitions = 0
    for text, expected in fixtures.values():
        for split in range(len(text)+1):
            screen = HostScreen()
            screen.feed(text[:split])
            screen.feed(text[split:])
            assert screen.lines == expected
            partitions += 1
        screen = HostScreen()
        for char in text:
            screen.feed(char)
        assert screen.lines == expected
    guard = HostScreen()
    guard.feed('A'*80+'\r\nB')
    assert guard.lines == ['A'*80, 'B'] and guard.line_events == 1
    return {'control_fixtures': len(fixtures), 'two_chunk_partitions': partitions,
            'byte_at_a_time_runs': len(fixtures), 'fragmentation_mismatches': 0,
            'exact_80_columns_plus_crlf_line_events': guard.line_events}


def scrollback_measurements():
    dashboard = ConsoleDashboard({})
    dashboard.set_host_terminal(MemoryTerminal())
    for number in range(100):
        dashboard.append_host_output(f'Original row {number:03}\n')
    size = os.terminal_size((150, 40))
    dashboard._frame(height=40, terminal_size=size)
    dashboard._host_special_key('page_up')
    before = dashboard._frame(height=40, terminal_size=size)
    def originals(frame):
        return [line for line in frame if 'Original row' in line]
    dashboard.append_host_output('\x1b[2J\x1b[H')
    for number in range(700):
        dashboard.append_host_output(f'Fresh output {number:03}\n')
    after = dashboard._frame(height=40, terminal_size=size)
    assert originals(before)
    assert originals(before) == originals(after)
    assert dashboard._scrollback_new_lines == 700
    frozen = len(dashboard._scrollback)
    retained = len(dashboard._screen.lines)
    dashboard._host_special_key('end')
    live = '\n'.join(dashboard._frame(height=40, terminal_size=size))
    assert 'Fresh output 699' in live and 'Original row' not in live
    assert dashboard._scrollback_new_lines == 0
    return {'original_rows': 100, 'new_lines_after_clear': 700,
            'frozen_logical_rows': frozen, 'live_rows_retained': retained,
            'visible_original_rows_preserved': len(originals(before)),
            'end_resets_counter': dashboard._scrollback_new_lines == 0}


def message_measurements(root):
    terminal = MemoryTerminal()
    service = SessionServices(terminal, root / 'captures')
    try:
        terminal.write(b'Choice: par')
        service.notify('Incoming text from Host: sample.txt\n'+'Long body line\n'*500)
        idle_bytes = len(terminal.output)-len(b'Choice: par')
        assert b'Long body line' not in terminal.output
        assert terminal.output.endswith(b'Choice: par')
        terminal.output.clear()
        with service.transfer():
            terminal.write(b'PACKET')
            with service.transfer():
                service.notify('Arrived during transfer')
            assert terminal.output == b'PACKET'
            terminal.write(b'FINAL ACK')
            protected_bytes = len(terminal.output)
        assert terminal.output.index(b'NEW MESSAGE') > terminal.output.index(b'FINAL ACK')
        notices = terminal.output.count(b'NEW MESSAGE')
        assert notices == 1 and len(service.pending) == 2
        service.announce_pending()
        assert terminal.output.count(b'NEW MESSAGE') == notices
        text = service.read_message(1)
        assert 'Long body line' in text and len(service.pending) == 1
        assert len(service.message_list()) == 2
        return {'file_message_characters': len(text), 'idle_notice_bytes': idle_bytes,
                'file_body_in_notice': False, 'prompt_restored': True,
                'protected_wire_bytes': protected_bytes,
                'notices_inside_transfer': 0, 'notices_after_transfer': notices,
                'read_message_retained': len(service.message_list()) == 2}
    finally:
        service.close()


def approval_measurements(root):
    now = [0.0]
    access = HostCommandAccess(root / 'host_access.json', clock=lambda: now[0], max_pending=2)
    serial = SimpleNamespace(port='com02')
    address = SimpleNamespace(_remote_address=('192.0.2.7', 1234))
    assert not access.request(serial)[0] and not access.request(address)[0]
    assert not access.request(serial)[2] and len(access.pending()) == 2
    full = access.request(SimpleNamespace(port='COM4'))[1]
    assert 'queue is full' in full
    with patch.object(access, '_save', side_effect=OSError('Simulated disk failure')):
        try:
            access.decide(1, True)
        except OSError:
            pass
        else:
            raise AssertionError('Approval must not succeed after failed persistence')
    assert not access.request(serial)[0]
    access.decide(1, True)
    access.decide(2, True)
    restored = HostCommandAccess(access.path, clock=lambda: now[0])
    assert restored.request(SimpleNamespace(port=r'\\.\COM2'))[0]
    assert restored.request(SimpleNamespace(_remote_address=('192.0.2.7', 9999)))[0]
    assert not restored.request(SimpleNamespace(_remote_address=('192.0.2.8', 9999)))[0]
    now[0] = 121.0
    assert restored.pending() == []
    expired = False
    try:
        restored.decide(1, True)
    except ValueError:
        expired = True
    assert expired
    return {'sources_initially_denied': 2, 'duplicate_request_rows': 1,
            'bounded_queue_test_limit': 2, 'production_queue_limit': HostCommandAccess().max_pending,
            'failed_save_grants': 0, 'restored_sources_allowed': 2,
            'different_ip_allowed': False, 'expired_approval_accepted': False}


def notepad_measurements(root):
    outcomes = []
    for failure in ('deleted', 'permission', 'invalid_utf8'):
        base = root / failure
        base.mkdir()
        note = base / 'note.txt'
        note.write_bytes(b'Original\n')
        terminal = MemoryTerminal()
        session = rsh_notes.create_session(terminal, False, [note.name], base)
        if failure == 'deleted':
            note.unlink()
        elif failure == 'invalid_utf8':
            note.write_bytes(b'\xff\xfe')
        before = note.read_bytes() if note.exists() else None
        if failure == 'permission':
            with patch.object(Path, 'read_text', side_effect=PermissionError('Access denied')):
                result = rsh_notes.handle_input(session, 'E1', terminal, False)
        else:
            result = rsh_notes.handle_input(session, 'E1', terminal, False)
        assert result == (True, None)
        assert not any(key in session for key in ('editing', 'edit_original', 'edit_lines', 'edit_page'))
        assert terminal.output.endswith(b'Command: ')
        assert (note.read_bytes() if note.exists() else None) == before
        note.write_text('Recovered\n', encoding='utf-8')
        rsh_notes.handle_input(session, 'E1', terminal, False)
        assert session['edit_lines'] == ['Recovered']
        outcomes.append({'failure': failure, 'partial_editor_state': False,
                         'source_changed_on_failure': False, 'retry_succeeded': True})
    return outcomes


def transfer_measurements(root):
    rows = []
    for length in (0, 1, 127, 128, 129, 1024, 4096):
        source = root / 'payload.bin'
        source.write_bytes(bytes(index % 251 for index in range(length)))
        blocks = math.ceil(length / 128)
        for crc in (False, True):
            terminal = MemoryTerminal((b'C' if crc else bytes([NAK])) + bytes([ACK])*(blocks+1))
            assert xsend(terminal, source) == length and not terminal.incoming
            sent = len(terminal.output)
            assert sent == blocks*(133 if crc else 132)+1
            assert terminal.read_bytes == blocks+2
            rows.append({'payload_bytes': length, 'check': 'CRC16' if crc else 'checksum',
                         'blocks': blocks, 'sender_bytes': sent, 'receiver_bytes': terminal.read_bytes,
                         'combined_wire_bytes': sent+terminal.read_bytes})
    source.write_bytes(b'A'*1024)
    retry = MemoryTerminal(b'C'+bytes([NAK])+bytes([ACK])*9)
    xsend(retry, source)
    assert not retry.incoming
    assert len(retry.output)+retry.read_bytes == 1209
    return {'cases': rows, 'one_nak_1024_payload_wire_bytes': len(retry.output)+retry.read_bytes}


def run_measurements():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        return {'version': VERSION, 'python': platform.python_version(), 'os': platform.system(),
                'layout': layout_measurements(), 'screen_controls': screen_measurements(),
                'scrollback': scrollback_measurements(), 'messages': message_measurements(root),
                'approvals': approval_measurements(root), 'notepad': notepad_measurements(root),
                'xmodem': transfer_measurements(root)}


if __name__ == '__main__':
    print(json.dumps(run_measurements(), indent=2))
