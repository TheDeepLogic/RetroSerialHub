"""Fault injection for shared tool records, reader state, and ZIP extraction."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from retro_os.reader import run_reader
from retro_os.toolkit import FileTools, JsonRecords


class ToolReliabilityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def test_records_failed_replace_preserves_original_and_retry_succeeds(self):
        store = JsonRecords(self.root / 'contacts.json')
        store.save([{'name': 'Original'}])
        original = store.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=PermissionError('file locked')):
            with self.assertRaises(PermissionError):
                store.change(lambda rows: rows.append({'name': 'New'}))
        self.assertEqual(store.path.read_bytes(), original)
        self.assertEqual(list(self.root.glob('*.tmp')), [])
        store.change(lambda rows: rows.append({'name': 'New'}))
        self.assertEqual(len(store.load()), 2)

    def test_records_partial_serialization_and_sync_failures_preserve_original(self):
        store = JsonRecords(self.root / 'appointments.json')
        store.save([{'title': 'Original'}])
        original = store.path.read_bytes()
        with self.assertRaises(TypeError):
            store.save([{'title': 'New'}, {'bad': object()}])
        self.assertEqual(store.path.read_bytes(), original)
        self.assertEqual(list(self.root.glob('*.tmp')), [])
        with patch('retro_os.toolkit.os.fsync', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                store.save([{'title': 'New'}])
        self.assertEqual(store.path.read_bytes(), original)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_records_do_not_touch_existing_temporary_files(self):
        sentinel = self.root / 'records.tmp'
        sentinel.write_text('unrelated')
        JsonRecords(self.root / 'records.json').save([{'value': 1}])
        JsonRecords(self.root / 'records.data').save([{'value': 2}])
        self.assertEqual(sentinel.read_text(), 'unrelated')
        self.assertEqual(JsonRecords(self.root / 'records.json').load(), [{'value': 1}])
        self.assertEqual(JsonRecords(self.root / 'records.data').load(), [{'value': 2}])

    def read_document(self, store, choices, text=None):
        document = self.root / 'document.txt'
        document.write_text(text or '\n'.join(f'Line {i}' for i in range(12)), encoding='utf-8')
        inputs, output = iter(choices), []
        run_reader(document, store, lambda: next(inputs), output.append, lambda: None, rows=12)
        return ''.join(output)

    def test_reader_corrupt_state_does_not_block_reading_or_overwrite_file(self):
        store = self.root / 'positions.json'
        for contents in ('{truncated', '{}', '[null]'):
            with self.subTest(contents=contents):
                store.write_text(contents)
                with self.assertLogs('retro_os.reader', level='WARNING'):
                    output = self.read_document(store, ['', 'Q'])
                self.assertIn('Line 0', output)
                self.assertIn('Line 4', output)
                self.assertIn('Reading position not saved.', output)
                self.assertEqual(store.read_text(), contents)

    def test_reader_unreadable_state_does_not_block_reading(self):
        with patch.object(JsonRecords, 'load', side_effect=PermissionError('locked')):
            with self.assertLogs('retro_os.reader', level='WARNING'):
                output = self.read_document(self.root / 'positions.json', ['Q'])
        self.assertIn('Line 0', output)
        self.assertIn('Reading position not saved.', output)

    def test_reader_ignores_bad_offsets_and_keeps_unrelated_records(self):
        store = self.root / 'positions.json'
        document = self.root / 'document.txt'
        for offset in (-1, 'bad', [], True):
            with self.subTest(offset=offset):
                store.write_text(json.dumps([{'unrelated': 'keep'}, {
                    'path': str(document.resolve()), 'columns': 80,
                    'line': offset, 'bookmark_line': offset,
                }]))
                output = self.read_document(store, ['R', 'Q'])
                self.assertIn('Page 1/3', output)
                self.assertIn({'unrelated': 'keep'}, json.loads(store.read_text()))

    def test_reader_clamps_stale_offsets_and_accepts_legacy_pages(self):
        store = self.root / 'positions.json'
        document = self.root / 'document.txt'
        for offsets, page in [({'line': 100000, 'bookmark_line': 100000}, 3),
                              ({'page': 1, 'bookmark': 1}, 2)]:
            with self.subTest(offsets=offsets):
                store.write_text(json.dumps([{
                    'path': str(document.resolve()), 'columns': 80, **offsets,
                }]))
                self.assertIn(f'Page {page}/3', self.read_document(store, ['R', 'Q']))

    def test_reader_unicode_search_finds_next_and_wraps(self):
        output = self.read_document(self.root / 'positions.json', ['F', 'STRASSE', 'N', 'N', 'Q'],
                                    'zero\none\nStraße\nthree\nfour\nfive\nSTRASSE\nseven')
        self.assertEqual(output.count('Match on line 3.'), 2)
        self.assertEqual(output.count('Match on line 7.'), 1)

    def archive_tools(self):
        archive_path = self.root / 'software.zip'
        with zipfile.ZipFile(archive_path, 'w') as archive:
            archive.writestr('docs/readme.txt', 'complete instructions')
            archive.writestr('program.bin', b'program')
        tools = FileTools(self.root, SimpleNamespace(fs={'tool_data': self.root}))
        tools.archive_command(['open', archive_path.name])
        return tools

    def test_zip_partial_copy_is_removed_and_same_member_can_be_retried(self):
        tools = self.archive_tools()
        def fail_copy(source, output):
            output.write(source.read(3))
            raise OSError('disk full')
        with patch('retro_os.toolkit.shutil.copyfileobj', side_effect=fail_copy):
            with self.assertRaisesRegex(OSError, 'disk full'):
                tools.archive_command(['extract', '1', 'unpacked'])
        target = self.root / 'unpacked/docs/readme.txt'
        self.assertFalse(target.exists())
        tools.archive_command(['extract', '1', 'unpacked'])
        self.assertEqual(target.read_text(), 'complete instructions')

    def test_zip_member_open_failure_does_not_leave_empty_output(self):
        tools = self.archive_tools()
        with patch.object(zipfile.ZipFile, 'open', side_effect=zipfile.BadZipFile('CRC error')):
            with self.assertRaises(zipfile.BadZipFile):
                tools.archive_command(['extract', '1', 'unpacked'])
        self.assertFalse((self.root / 'unpacked/docs/readme.txt').exists())

    def test_zip_racing_existing_file_is_preserved(self):
        tools = self.archive_tools()
        original_open = Path.open
        target = self.root / 'unpacked/docs/readme.txt'
        def open_file(path, mode='r', *args, **kwargs):
            if path == target and mode == 'xb':
                path.write_bytes(b'created by another writer')
            return original_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', open_file):
            with self.assertRaises(FileExistsError):
                tools.archive_command(['extract', '1', 'unpacked'])
        self.assertEqual(target.read_bytes(), b'created by another writer')

    def test_zip_failure_preserves_already_completed_members(self):
        tools = self.archive_tools()
        import shutil
        original_copy = shutil.copyfileobj
        def copy(source, output):
            if Path(output.name).name == 'program.bin':
                output.write(b'partial')
                raise OSError('disk full')
            original_copy(source, output)
        with patch('retro_os.toolkit.shutil.copyfileobj', side_effect=copy):
            with self.assertRaises(OSError):
                tools.archive_command(['extract', 'all', 'unpacked'])
        self.assertEqual((self.root / 'unpacked/docs/readme.txt').read_text(), 'complete instructions')
        self.assertFalse((self.root / 'unpacked/program.bin').exists())
        tools.archive_command(['extract', '2', 'unpacked'])
        self.assertEqual((self.root / 'unpacked/program.bin').read_bytes(), b'program')


if __name__ == '__main__':
    unittest.main()
