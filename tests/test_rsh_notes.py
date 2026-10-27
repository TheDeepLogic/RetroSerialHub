"""Notes remain usable when a listed file can no longer be edited."""
from pathlib import Path
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
