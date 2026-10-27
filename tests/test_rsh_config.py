"""JSON configuration, wizard transactions, and physical-console boundaries."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from rsh_config import HubConfigStore, serial_profiles, validate_settings
from rsh_config_wizard import ConfigWizard
from rsh_console import ConsoleDashboard

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)/'hub_config.json'
        self.data = json.loads((ROOT/'settings/defaults/hub_config.json').read_text(encoding='utf-8'))
        self.data['telnet_listeners'] = {'APPLE2': {'host': '0.0.0.0', 'port': 6400},
                                         'C64': {'host': '0.0.0.0', 'port': 6401}}
        self.path.write_text(json.dumps(self.data), encoding='utf-8')
        self.store = HubConfigStore(self.path)

    def wizard(self, callback=None):
        return ConfigWizard(self.store, callback, scanner=lambda: [('COM99', 'USB Serial Adapter')])

    def fill_profile(self, wizard, **overrides):
        wizard.feed('1')
        while wizard.step < len(wizard._fields()):
            key = wizard._fields()[wizard.step][0]
            wizard.feed(str(overrides.get(key, {'name': 'NEW', 'port': '1'}.get(key, ''))))

    def test_defaults_validate_and_clear_bytes_round_trip(self):
        actual = self.store.load()
        self.assertEqual(actual['serial_profiles'], self.data['serial_profiles'])
        for name, profile in self.data['serial_profiles'].items():
            runtime = serial_profiles(actual)[name]
            self.assertNotIn('clear_sequence_hex', runtime)
            if profile.get('clear_sequence_hex'):
                self.assertEqual(runtime['ansi_clear_sequence'], bytes.fromhex(profile['clear_sequence_hex']))

    def test_rejects_duplicate_ports_listener_conflicts_and_bad_dimensions(self):
        for field, value in [('columns', 41), ('rows', 15), ('baud', True),
                             ('xonxoff', 'false'), ('clear_sequence_hex', 'not hex')]:
            with self.subTest(field=field):
                data = deepcopy(self.data)
                data['serial_profiles']['APPLE2'][field] = value
                with self.assertRaises(ValueError):
                    validate_settings(data)
        data = deepcopy(self.data)
        data['serial_profiles']['DUPLICATE'] = {**data['serial_profiles']['APPLE2'], 'port': r'\\.\COM02'}
        with self.assertRaisesRegex(ValueError, 'assigned more than once'):
            validate_settings(data)
        data = deepcopy(self.data)
        data['telnet_listeners']['C64']['port'] = data['telnet_listeners']['APPLE2']['port']
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            validate_settings(data)

    def test_failed_save_preserves_existing_file_and_cleans_temporary(self):
        before = self.path.read_bytes()
        data = self.store.load()
        data['welcome_banner'] = 'Updated'
        with patch.object(Path, 'replace', side_effect=PermissionError('File busy')):
            with self.assertRaises(OSError):
                self.store.save(data)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_conflicting_save_does_not_replace_newer_settings(self):
        original = self.store.load()
        updated = deepcopy(original)
        updated['welcome_banner'] = 'Other operator'
        self.store.save(updated)
        with self.assertRaisesRegex(ValueError, 'changed while'):
            self.store.save(original, expected=original)
        self.assertEqual(self.store.load()['welcome_banner'], 'Other operator')

    def test_wizard_saves_scanned_port_only_after_confirmation_and_starts_once(self):
        callback = Mock()
        wizard = self.wizard(callback)
        before = self.path.read_bytes()
        self.fill_profile(wizard, columns='40', rows='25', baud='2400', telnet='yes')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIn('COM99', '\n'.join(wizard.lines()))
        self.assertIn('40 columns x 25 rows', '\n'.join(wizard.lines()))
        wizard.feed('yes')
        saved = self.store.load()
        self.assertEqual(saved['serial_profiles']['NEW']['port'], 'COM99')
        self.assertEqual(saved['serial_profiles']['NEW']['columns'], 40)
        self.assertEqual(saved['serial_profiles']['NEW']['rows'], 25)
        self.assertEqual(saved['telnet_listeners']['NEW']['port'], 6402)
        callback.assert_called_once_with('NEW', saved)
        self.assertIn('started', wizard.notice)

    def test_cancel_back_and_validation_leave_live_configuration_unchanged(self):
        wizard = self.wizard()
        before = self.path.read_bytes()
        wizard.feed('1')
        with self.assertRaises(ValueError):
            wizard.feed('APPLE2')
        wizard.feed('NEW')
        with self.assertRaisesRegex(ValueError, 'Select a detected port'):
            wizard.feed('')
        wizard.feed('COM98')
        with self.assertRaises(ValueError):
            wizard.feed('-1')
        self.assertEqual(wizard.values['baud'], 9600)
        wizard.feed('back')
        self.assertIn('Serial port', wizard.prompt)
        wizard.feed('cancel')
        wizard.feed('q')
        self.assertFalse(wizard.active)
        self.assertEqual(self.path.read_bytes(), before)

    def test_general_and_speech_settings_require_confirmation_and_restart(self):
        wizard = self.wizard()
        wizard.feed('3')
        wizard.feed('New welcome')
        wizard.feed('0')
        wizard.feed('yes')
        self.assertEqual(self.store.load()['welcome_banner'], 'New welcome')
        self.assertEqual(self.store.load()['serial_idle_timeout_seconds'], 0)
        self.assertIn('Restart', wizard.notice)
        wizard.feed('4')
        wizard.feed('no')
        while wizard.step < len(wizard._fields()):
            wizard.feed('')
        wizard.feed('yes')
        self.assertFalse(self.store.load()['wopr_speech']['enabled'])

    def test_scan_failure_manual_port_and_activation_failure_remain_recoverable(self):
        callback = Mock(side_effect=OSError('Device unavailable'))
        wizard = ConfigWizard(self.store, callback, scanner=Mock(side_effect=OSError('Scan failed')))
        self.fill_profile(wizard, port='COM98')
        wizard.feed('yes')
        self.assertIn('activation failed', wizard.notice)
        self.assertIn('NEW', self.store.load()['serial_profiles'])

    def test_host_wizard_does_not_submit_to_hub_or_accept_remote_input(self):
        dashboard = ConsoleDashboard({})
        terminal = Mock(secret_input=False, closed=False)
        dashboard.set_host_terminal(terminal)
        dashboard.set_configuration(self.store)
        dashboard._running = True
        with patch.object(dashboard, 'host_input_available', return_value=True):
            self.assertFalse(dashboard._dispatch_host_command('config', remote=True))
            self.assertTrue(dashboard.handle_host_command('config'))
            self.assertTrue(dashboard.handle_host_command('1'))
            self.assertFalse(dashboard._dispatch_host_command('WRONG', remote=True))
            self.assertEqual(dashboard._config_wizard.step, 0)
            frame = '\n'.join(dashboard._frame(height=40, terminal_size=os.terminal_size((150,40))))
            self.assertIn('Profile name', frame)
            self.assertIn('HOST CONFIGURATION', frame)
            dashboard.handle_host_command('cancel')
            dashboard.handle_host_command('q')
            self.assertIsNone(dashboard._config_wizard)
        terminal.submit.assert_not_called()

    def test_new_profile_runtime_starts_workers_without_restarting_existing_profiles(self):
        import RETRO_SERIAL_HUB as hub
        data = self.store.load()
        data['serial_profiles']['NEW'] = dict(port='COM99', baud=2400)
        data['telnet_listeners']['NEW'] = dict(host='127.0.0.1', port=6500)
        dashboard, access = Mock(profiles={}), Mock()
        with patch.object(hub, 'SERIAL_CONFIGS', {}), patch.object(hub, 'TELNET_SERVER_CONFIGS', {}), \
             patch.object(hub, 'CONSOLE', dashboard), patch.object(hub, 'TELNET_ACCESS', None), \
             patch.object(hub, 'TelnetAccess', return_value=access), patch.object(hub.threading, 'Thread') as thread, \
             patch.object(hub, 'local_ipv4_addresses', return_value=['192.0.2.1']):
            hub.activate_configured_profile('NEW', data)
            self.assertEqual(thread.call_count, 2)
            self.assertEqual(thread.return_value.start.call_count, 2)
            access.start.assert_called_once()
            self.assertEqual(dashboard.profiles['NEW']['tcp_port'], 6500)
            with self.assertRaises(ValueError):
                hub.activate_configured_profile('NEW', data)

    def test_configuration_menu_fits_standard_height_and_remote_gate_keeps_cursor_visible(self):
        from tests.test_rsh_console import VirtualScreen
        import io
        dashboard = ConsoleDashboard({name: {'serial_port': cfg['port']} for name, cfg in self.data['serial_profiles'].items()})
        dashboard.set_host_terminal(Mock(secret_input=False, closed=False))
        dashboard.set_configuration(self.store)
        with patch.object(dashboard, 'host_input_available', return_value=True):
            dashboard.handle_host_command('config')
            for width in (80, 100, 124, 150):
                with self.subTest(width=width):
                    output = io.StringIO()
                    with patch('rsh_console.sys.stdout', output), patch('shutil.get_terminal_size', return_value=os.terminal_size((width,24))):
                        dashboard._draw_frame()
                    screen = VirtualScreen(width,24)
                    screen.feed(output.getvalue())
                    self.assertEqual(screen.scrolls, 0)
                    self.assertIn('1 Add serial', screen.text())
                    self.assertIn('Q Return to hub', screen.text())
                    self.assertIn('Configuration>', screen.text())

    def test_new_install_seeds_two_profiles_without_touching_an_existing_local_copy(self):
        from rsh_storage import settings_dir
        root = self.path.parent
        defaults = root/'settings/defaults'
        defaults.mkdir(parents=True)
        for name in ('hub_config.json', 'bbs_directory.json'):
            (defaults/name).write_bytes((ROOT/'settings/defaults'/name).read_bytes())
        local = settings_dir(root)
        data = HubConfigStore(local/'hub_config.json').load()
        self.assertEqual({name: p['port'] for name,p in data['serial_profiles'].items()}, {'APPLE2':'COM1','C64':'COM2'})
        self.assertEqual(data['telnet_listeners'], {})
        (local/'hub_config.json').write_text(json.dumps(self.data), encoding='utf-8')
        settings_dir(root)
        self.assertEqual(HubConfigStore(local/'hub_config.json').load()['telnet_listeners'], self.data['telnet_listeners'])

    def test_failed_wizard_save_stays_on_confirmation_without_starting_workers(self):
        callback = Mock()
        wizard = self.wizard(callback)
        self.fill_profile(wizard)
        before = self.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):
                wizard.feed('yes')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIn('Save this configuration?', wizard.prompt)
        callback.assert_not_called()
        wizard.feed('yes')
        callback.assert_called_once()

    def test_first_launch_opens_configuration_once_and_acknowledges_defaults_on_exit(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_host_terminal(Mock(secret_input=False, closed=False))
        dashboard.set_configuration(self.store)
        done = Mock()
        self.assertTrue(dashboard.start_first_run_configuration(done))
        self.assertIn('First launch', '\n'.join(dashboard._config_wizard.lines()))
        with patch.object(dashboard, 'host_input_available', return_value=True):
            dashboard.handle_host_command('q')
        done.assert_called_once()
        self.assertTrue(self.store.load()['configuration_completed'])
        self.assertEqual(self.store.load()['serial_profiles'], self.data['serial_profiles'])
        self.assertFalse(dashboard.start_first_run_configuration())

    def test_edit_existing_profile_preserves_others_and_waits_for_restart(self):
        callback = Mock()
        wizard = self.wizard(callback)
        wizard.feed('5')
        wizard.feed('1')
        while wizard.step < len(wizard._fields()):
            key = wizard._fields()[wizard.step][0]
            wizard.feed({'port':'1', 'columns':'40', 'rows':'25'}.get(key,''))
        wizard.feed('yes')
        saved = self.store.load()
        self.assertEqual(saved['serial_profiles']['APPLE2']['port'], 'COM99')
        self.assertEqual(saved['serial_profiles']['APPLE2']['columns'], 40)
        self.assertEqual(saved['serial_profiles']['C64'], self.data['serial_profiles']['C64'])
        callback.assert_not_called()
        self.assertIn('Restart', wizard.notice)

    def test_first_setup_starts_no_workers_until_configuration_menu_closes(self):
        import RETRO_SERIAL_HUB as hub
        import threading
        from contextlib import ExitStack
        saved = deepcopy(self.data)
        saved['telnet_listeners'] = {}
        saved['serial_profiles']['NEW'] = dict(port='COM99', baud=2400)
        dashboard = Mock(profiles={})
        dashboard._lock = threading.RLock()
        completed = []

        def finish(callback):
            completed.append(True)
            callback()
            return True

        def worker(**kwargs):
            self.assertTrue(completed)
            return Mock()

        dashboard.start_first_run_configuration.side_effect = finish
        with ExitStack() as stack:
            for name, value in [('SERIAL_CONFIGS', {}), ('TELNET_SERVER_CONFIGS', {}),
                                ('CONSOLE', None), ('TELNET_ACCESS', None),
                                ('SERIAL_IDLE_TIMEOUT_SECONDS', 300),
                                ('CONFIG_WELCOME_BANNER', 'Old'), ('WELCOME_BANNER', 'Old')]:
                stack.enter_context(patch.object(hub, name, value))
            stack.enter_context(patch.object(hub, 'load_settings', return_value=saved))
            stack.enter_context(patch.object(hub, 'load_banner', return_value='New'))
            stack.enter_context(patch.object(hub, 'ConsoleDashboard', return_value=dashboard))
            stack.enter_context(patch.object(hub, 'HostTerminal'))
            threads = stack.enter_context(patch.object(hub.threading, 'Thread', side_effect=worker))
            stack.enter_context(patch.object(hub.time, 'sleep', side_effect=KeyboardInterrupt))
            hub.main()
            self.assertEqual(threads.call_count, 3)
            self.assertIn('NEW', hub.SERIAL_CONFIGS)


if __name__ == '__main__':
    unittest.main()
