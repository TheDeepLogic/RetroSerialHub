"""Reader and file-browser navigation shortcuts for the v2.7 release."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from retro_os.file_browser import run_file_browser
from retro_os.reader import run_reader
from retro_os.toolkit import FileTools


class NavigationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.tools = FileTools(self.root, SimpleNamespace(fs={'tool_data': self.root}))

    def read_document(self, choices):
        document = self.root / 'document.txt'
        document.write_text('\n'.join(f'Line {i}' for i in range(12)))
        inputs, screens = iter(choices), []
        run_reader(document, self.root / 'positions.json', lambda: next(inputs),
                   lambda text: screens[-1].append(text), lambda: screens.append([]), rows=12)
        return [''.join(screen) for screen in screens]

    def test_reader_first_last_and_direct_page_keep_position(self):
        screens = self.read_document(['L', 'H', '2', 'Q'])
        for screen, page in zip(screens, [1, 3, 1, 2]):
            self.assertIn(f'Page {page}/3', screen)
        self.assertIn('Line 8', screens[1])
        self.assertIn('Line 4', screens[-1])
        self.assertEqual(json.loads((self.root / 'positions.json').read_text())[0]['page'], 1)
        for line in screens[0].splitlines():
            if 'G/#' in line or 'Enter/B' in line:
                self.assertLessEqual(len(line), 39)

    def test_reader_full_word_aliases_and_bookmark_recall(self):
        screens = self.read_document(['2', 'M', 'END', 'HOME', 'R', 'Q'])
        self.assertIn('Page 3/3', screens[3])
        self.assertIn('Page 1/3', screens[4])
        self.assertIn('Page 2/3', screens[5])

    def test_reader_invalid_page_and_cancel_preserve_current_page(self):
        screens = self.read_document(['2', '0', 'G', '99', 'G', '', 'G', 'Q', 'Q'])
        self.assertEqual(len(screens), 6)
        for screen in screens[1:]:
            self.assertIn('Page 2/3', screen)
        self.assertIn('Page must be 1-3.', screens[2])
        self.assertIn('Page must be 1-3.', screens[3])

    def test_previous_folder_toggles_and_same_directory_preserves_history(self):
        other = self.root / 'other'
        other.mkdir()
        self.tools.command(['cd', str(other)])
        self.tools.command(['cd', '.'])
        self.tools.command(['cd', '-'])
        self.assertEqual(self.tools.cwd, self.root)
        self.tools.command(['previous'])
        self.assertEqual(self.tools.cwd, other)
        self.tools.command(['p'])
        self.assertEqual(self.tools.cwd, self.root)

    def test_previous_folder_is_session_local_and_missing_history_is_actionable(self):
        other = self.root / 'other'
        other.mkdir()
        self.tools.command(['cd', str(other)])
        second = FileTools(self.root, SimpleNamespace(fs={'tool_data': self.root}))
        with self.assertRaisesRegex(ValueError, 'No previous folder'):
            second.command(['cd', '-'])
        self.assertEqual(second.cwd, self.root)
        self.assertEqual(self.tools.cwd, other)

    def test_failed_navigation_keeps_current_folder_and_history(self):
        first, second = self.root / 'first', self.root / 'second'
        first.mkdir()
        second.mkdir()
        self.tools.command(['cd', str(first)])
        with patch.object(self.tools, 'listing', side_effect=PermissionError('access denied')):
            with self.assertRaises(PermissionError):
                self.tools.command(['cd', str(second)])
        self.assertEqual(self.tools.cwd, first)
        self.assertEqual(self.tools.previous_cwd, self.root)
        self.tools.command(['cd', '-'])
        self.assertEqual(self.tools.cwd, self.root)

    def test_deleted_previous_folder_does_not_change_current_folder(self):
        other = self.root / 'other'
        other.mkdir()
        self.tools.command(['cd', str(other)])
        self.tools.command(['home'])
        other.rmdir()
        with self.assertRaisesRegex(ValueError, 'Choose a directory'):
            self.tools.command(['previous'])
        self.assertEqual(self.tools.cwd, self.root)

    def test_file_browser_previous_key_uses_same_history(self):
        other = self.root / 'other'
        other.mkdir()
        choices = iter(['G', str(other), 'P', 'Q'])
        output = []
        run_file_browser(self.tools, lambda _command: '', lambda: next(choices),
                         output.append, lambda *args, **kwargs: None, lambda: None, lambda: None)
        self.assertEqual(self.tools.cwd, self.root)
        self.assertEqual(self.tools.previous_cwd, other)
        self.assertIn('P=Previous', ''.join(output))

    def test_release_version_is_shared_by_banner_and_http_client(self):
        from rsh_console import VERSION as banner_version
        from rsh_version import VERSION
        from retro_os.viewer import USER_AGENT
        self.assertEqual(VERSION, '2.7')
        self.assertEqual(banner_version, VERSION)
        self.assertEqual(USER_AGENT, f'RetroSerialHub/{VERSION} (Vintage Terminal Host)')


if __name__ == '__main__':
    unittest.main()
