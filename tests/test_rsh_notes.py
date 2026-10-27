"""Notes remain usable when a listed file can no longer be edited."""
from pathlib import Path
from contextlib import contextmanager
import tempfile
import unittest
from unittest.mock import patch

import rsh_notes


class Terminal:
    def __init__(self):
        self.output = bytearray()

    def write(self, data):
        self.output.extend(data)
        return len(data)


class NotesEditTests(unittest.TestCase):
    def test_search_skips_io_failures_and_preserves_filename_matches(self):
        for failure in ('stat', 'read_text'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                for name in ('bad.txt', 'good.txt', 'needle.txt', 'large.txt'):
                    (base / name).write_text('Needle in contents', encoding='utf-8')
                (base / 'large.txt').write_bytes(b'x'*(1024*1024) + b'needle')
                terminal = Terminal()
                session = rsh_notes.create_session(terminal, False, [], base)
                real_method = getattr(Path, failure)
                real_read = Path.read_text

                def fail_one(path, *args, **kwargs):
                    if path.name == 'bad.txt':
                        raise OSError('Note became unavailable')
                    return real_method(path, *args, **kwargs)

                def read_content(path, *args, **kwargs):
                    self.assertNotIn(path.name, ('needle.txt', 'large.txt'))
                    return real_read(path, *args, **kwargs)

                with patch.object(Path, 'read_text', read_content):
                    with patch.object(Path, failure, fail_one):
                        self.assertEqual(rsh_notes.handle_input(session, 'F NEEDLE', terminal, False), (True, None))
                self.assertEqual(session['notes'], ['good.txt', 'needle.txt'])
                self.assertIn('skipped 1', session['notice'])
                self.assertTrue(terminal.output.endswith(b'Command: '))
                rsh_notes.handle_input(session, 'F NEEDLE', terminal, False)
                self.assertEqual(session['notes'], ['bad.txt', 'good.txt', 'needle.txt'])
                self.assertIsNone(session['notice'])

    def test_failed_save_cleans_temporary_file_and_preserves_edits_for_retry(self):
        real_temporary_file = rsh_notes.NamedTemporaryFile

        @contextmanager
        def failed_write(*args, **kwargs):
            with real_temporary_file(*args, **kwargs) as output:
                # Simulate a failure after some data reached the temporary file.
                output.write('Partial')
                with patch.object(output, 'write', side_effect=OSError('Disk full')):
                    yield output

        for failure in ('write', 'replace'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                note = base / 'note.txt'
                note.write_bytes(b'Original\n')
                terminal = Terminal()
                session = rsh_notes.create_session(terminal, False, [note.name], base)
                rsh_notes.handle_input(session, 'E1', terminal, False)
                rsh_notes.handle_input(session, 'replace 1 Updated', terminal, False)
                fault = (patch('rsh_notes.NamedTemporaryFile', failed_write) if failure == 'write'
                         else patch.object(Path, 'replace', side_effect=PermissionError('File busy')))
                with fault:
                    self.assertEqual(rsh_notes.handle_input(session, 'save', terminal, False), (True, None))
                self.assertEqual(note.read_bytes(), b'Original\n')
                self.assertEqual(list(base.iterdir()), [note])
                self.assertEqual(session['editing'], note.name)
                self.assertEqual(session['edit_lines'], ['Updated'])
                self.assertEqual(session['edit_original'], 'Original\n')
                self.assertTrue(terminal.output.endswith(b'Edit: '))
                rsh_notes.handle_input(session, 'save', terminal, False)
                self.assertEqual(note.read_text(encoding='utf-8'), 'Updated\n')
                self.assertNotIn('editing', session)
                self.assertEqual(list(base.iterdir()), [note])

    def test_failed_edit_keeps_menu_usable_and_allows_retry(self):
        for failure in ('deleted', 'permission', 'invalid_utf8'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                note = base / 'note.txt'
                note.write_bytes(b'Original\n')
                terminal = Terminal()
                session = rsh_notes.create_session(terminal, False, [note.name], base)
                if failure == 'deleted':
                    note.unlink()
                elif failure == 'invalid_utf8':
                    note.write_bytes(b'\xff\xfe')
                if failure == 'permission':
                    with patch.object(Path, 'read_text', side_effect=PermissionError('Access denied')):
                        result = rsh_notes.handle_input(session, 'E1', terminal, False)
                else:
                    result = rsh_notes.handle_input(session, 'E1', terminal, False)
                self.assertEqual(result, (True, None))
                for key in ('editing', 'edit_original', 'edit_lines', 'edit_page'):
                    self.assertNotIn(key, session)
                self.assertIn(b'Cannot edit note:', terminal.output)
                self.assertTrue(terminal.output.endswith(b'Command: '))
                self.assertEqual(rsh_notes.handle_input(session, 'Q', terminal, False), (True, 'MENU'))
                if note.exists():
                    expected = b'\xff\xfe' if failure == 'invalid_utf8' else b'Original\n'
                    self.assertEqual(note.read_bytes(), expected)
                note.write_text('Recovered\n', encoding='utf-8')
                rsh_notes.handle_input(session, 'E1', terminal, False)
                self.assertEqual(session['edit_lines'], ['Recovered'])


if __name__ == '__main__':
    unittest.main()
