"""Preference saves preserve existing settings and recover from disk failures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsh_preferences import MachinePreferences


class MachinePreferencesTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'preferences.json'
        self.preferences = MachinePreferences(self.path)
        self.preferences.set('APPLE2', 'columns', 40)
        self.original = self.path.read_bytes()

    def test_failed_replacement_preserves_settings_and_retry_works(self):
        with patch.object(Path, 'replace', side_effect=PermissionError('File busy')):
            with self.assertRaisesRegex(PermissionError, 'File busy'):
                self.preferences.set('APPLE2', 'rows', 25)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        self.preferences.set('APPLE2', 'rows', 25)
        self.assertEqual(self.preferences.get('APPLE2'), {'columns': 40, 'rows': 25})

    def test_partial_write_failure_cleans_up_and_preserves_settings(self):
        def failing_temporary_file(**kwargs):
            output = tempfile.NamedTemporaryFile(**kwargs)
            original_write = output.write

            def partial_write(text):
                original_write(text[:5])
                output.flush()
                raise OSError('Disk full')

            output.write = partial_write
            return output

        with patch('rsh_preferences.NamedTemporaryFile', side_effect=failing_temporary_file):
            with self.assertRaisesRegex(OSError, 'Disk full'):
                self.preferences.set('APPLE2', 'caps', 'on')
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        self.preferences.set('APPLE2', 'caps', 'on')
        self.assertTrue(self.preferences.get('APPLE2')['caps'])

    def test_unique_temporary_save_does_not_touch_unrelated_tmp_file(self):
        unrelated = self.path.with_suffix('.tmp')
        unrelated.write_text('other writer', encoding='utf-8')
        self.preferences.set('C64', 'columns', 40)
        self.assertEqual(unrelated.read_text(encoding='utf-8'), 'other writer')
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8')),
                         {'APPLE2': {'columns': 40}, 'C64': {'columns': 40}})
