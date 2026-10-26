"""Verify upgrade migration, private data preservation, and public defaults."""
import json
from pathlib import Path
import tempfile
import unittest

from rsh_storage import settings_dir, settings_path


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
        return path

    def test_upgrade_preserves_personal_bytes_and_moves_all_legacy_locations(self):
        paths = ['ai_config.json', 'mail/hub_mail.json',
                 'hub_tools/contacts.json', 'retro_os/keyboard_profiles.json']
        for name in paths:
            self.write(name, '{"personal": "keep exactly"}\n')
        capture = self.write('hub_tools/captures/session.txt', 'keep capture')
        local = settings_dir(self.root)
        for name in paths:
            self.assertFalse((self.root / name).exists())
            self.assertEqual((local / Path(name).name).read_bytes(),
                             b'{"personal": "keep exactly"}\n')
        self.assertTrue(capture.exists())
        self.assertEqual(settings_dir(self.root), local)

    def test_local_wins_and_conflicting_legacy_data_is_backed_up(self):
        self.write('settings/local/ai_config.json', '{"key":"new"}')
        self.write('ai_config.json', '{"key":"old"}')
        local = settings_dir(self.root)
        self.assertEqual(json.loads((local/'ai_config.json').read_text()), {'key':'new'})
        backups = list((local/'legacy').glob('*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text()), {'key':'old'})
        settings_dir(self.root)
        self.assertEqual(len(list((local/'legacy').glob('*.json'))), 1)

    def test_defaults_seed_only_missing_files_and_never_receive_live_changes(self):
        template = self.write('settings/defaults/browser_bookmarks.json', '[{"name":"Public"}]')
        self.write('settings/defaults/telnet_allowlist.example.json', '{}')
        live = settings_path('browser_bookmarks.json', self.root)
        self.assertEqual(live.read_bytes(), template.read_bytes())
        live.write_text('[{"name":"Private"}]', encoding='utf-8')
        settings_dir(self.root)
        self.assertIn('Private', live.read_text())
        self.assertNotIn('Private', template.read_text())
        self.assertFalse((live.parent/'telnet_allowlist.example.json').exists())

    def test_legacy_personal_settings_take_priority_over_templates(self):
        self.write('settings/defaults/ai_config.json', '{"api_key":"placeholder"}')
        self.write('ai_config.json', '{"api_key":"personal"}')
        live = settings_path('ai_config.json', self.root)
        self.assertEqual(json.loads(live.read_text()), {'api_key':'personal'})

    def test_path_rejects_names_outside_settings(self):
        for name in ('../secret.json', 'mail/config.json', 'not-json.txt'):
            with self.assertRaises(ValueError):
                settings_path(name, self.root)
