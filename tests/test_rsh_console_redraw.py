import io
import os
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from rsh_console import ConsoleDashboard
from tests.test_rsh_console import VirtualScreen


class IncrementalRedrawTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.dashboard = ConsoleDashboard({})
        self.dashboard.set_host_terminal(MagicMock())
        self.dashboard.append_host_output('Menu heading\ncli> ')
        self.output = io.StringIO()
        self.size = os.terminal_size((150, 40))
        self.clock = '2026-10-26 12:00:00'
        stack.enter_context(patch('rsh_console.sys.stdout', self.output))
        stack.enter_context(patch('shutil.get_terminal_size', side_effect=lambda **kwargs: self.size))
        stack.enter_context(patch('rsh_console.time.strftime', side_effect=lambda *args: self.clock))

    def draw(self, force=False):
        self.output.seek(0)
        self.output.truncate()
        self.dashboard._draw_frame(force=force)
        return self.output.getvalue()

    def compare_with_full_paint(self, screen, incremental):
        screen.feed(incremental)
        expected = VirtualScreen(self.size.columns, self.size.lines)
        expected.feed(self.draw(force=True))
        self.assertEqual(screen.lines, expected.lines)
        self.assertEqual((screen.row, screen.column), (expected.row, expected.column))
        self.assertEqual(screen.scrolls, 0)

    def test_idle_writes_nothing_and_typing_repaints_only_prompt_row(self):
        screen = VirtualScreen(*self.size)
        first = self.draw()
        screen.feed(first)
        self.assertEqual(first.count('\x1b[2K'), self.size.lines)
        with patch.object(self.output, 'flush', wraps=self.output.flush) as flush:
            for _ in range(100):
                self.assertEqual(self.draw(), '')
            flush.assert_not_called()
        for char in 'calc 123456789 + 987654321':
            self.dashboard._host_command += char
            update = self.draw()
            # A trailing space can leave the padded row unchanged; only its
            # cursor position needs updating in the uncolored case.
            self.assertEqual(update.count('\x1b[2K'), 0 if char == ' ' else 1)
            self.assertNotIn('\x1b[2J', update)
            self.assertLess(len(update), len(first) // 10)
            self.compare_with_full_paint(screen, update)

    def test_clock_repaints_only_title_and_cursor_only_moves_without_row_erases(self):
        self.draw()
        self.clock = '2026-10-26 12:00:01'
        update = self.draw()
        self.assertEqual(update.count('\x1b[2K'), 1)
        self.assertIn('\x1b[1;1H', update)
        self.assertIn('12:00:01', update)
        self.dashboard.append_host_output('\x1b[2D')
        update = self.draw()
        self.assertNotIn('\x1b[2K', update)
        self.assertIn('\x1b[?25h', update)
        self.assertEqual(self.draw(), '')

    def test_resize_and_theme_changes_force_full_repaint_including_empty_space(self):
        self.draw()
        for size in ((40, 12), (80, 24), (123, 24), (124, 40), (150, 50)):
            self.size = os.terminal_size(size)
            screen = VirtualScreen(*size)
            update = self.draw()
            self.assertIn('\x1b[H\x1b[2J', update)
            self.compare_with_full_paint(screen, update)
        self.dashboard._color = True
        self.draw()
        for name, background, colors in (('Windows 95', True, True),
                                          ('Windows 95', False, True),
                                          ('Windows 95', False, False),
                                          ('Apple IIGS', True, True)):
            self.dashboard._theme.name = name
            self.dashboard._theme.background = background
            self.dashboard._theme.colors = colors
            update = self.draw()
            self.assertIn(self.dashboard._theme.ansi('desktop') + '\x1b[H\x1b[2J', update)
            self.assertEqual(self.draw(), '')

    def test_disappearing_notices_and_changing_approvals_leave_no_stale_text(self):
        screen = VirtualScreen(*self.size)
        screen.feed(self.draw())
        self.dashboard._events.append(('A temporary error', 'red'))
        self.compare_with_full_paint(screen, self.draw())
        self.dashboard._events.clear()
        self.compare_with_full_paint(screen, self.draw())
        self.assertNotIn('A temporary error', screen.text())
        access = MagicMock()
        self.dashboard.set_telnet_access(access)
        access.pending.return_value = [{'id': 1, 'ip': '192.168.1.2',
                                       'profile': 'APPLE2', 'seconds_left': 60}]
        self.compare_with_full_paint(screen, self.draw())
        access.pending.return_value = []
        self.compare_with_full_paint(screen, self.draw())
        self.assertNotIn('APPROVAL #1', screen.text())

    def test_shorter_frames_erase_vacated_rows_and_failed_writes_invalidate_cache(self):
        screen = VirtualScreen(*self.size)
        frames = [['Header', 'Keep', 'Old text', 'More old text'], ['Header', 'Keep']]
        with patch.object(self.dashboard, '_frame', return_value=frames[0]):
            screen.feed(self.draw())
        with patch.object(self.dashboard, '_frame', return_value=frames[1]):
            update = self.draw()
            self.assertEqual(update.count('\x1b[2K'), 2)
            screen.feed(update)
            self.assertNotIn('Old text', screen.text())
            self.assertNotIn('More old text', screen.text())
            self.assertEqual(self.draw(), '')
        self.dashboard._host_command = 'different'
        with patch.object(self.output, 'write', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.draw()
        self.assertIn('\x1b[H\x1b[2J', self.draw())

    def test_new_output_stream_gets_full_frame_even_if_content_is_identical(self):
        self.draw()
        replacement = io.StringIO()
        with patch('rsh_console.sys.stdout', replacement):
            self.dashboard._draw_frame()
        self.assertIn('\x1b[H\x1b[2J', replacement.getvalue())


if __name__ == '__main__':
    unittest.main()
