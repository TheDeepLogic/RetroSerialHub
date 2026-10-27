import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from rsh_console import ConsoleDashboard


class ScrollbackTests(unittest.TestCase):
    def dashboard(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_host_terminal(MagicMock())
        dashboard._tty = False
        for number in range(100):
            dashboard.append_host_output(f'Original row {number:03}\n')
        return dashboard

    def frame(self, dashboard, columns=150, height=40):
        return '\n'.join(dashboard._strip_ansi(row) for row in dashboard._frame(
            height=height, terminal_size=os.terminal_size((columns, height))))

    def history(self, frame):
        return [line.split('Original row ', 1)[1].split('|')[0].split('\u2502')[0].strip()
                for line in frame.splitlines() if 'Original row ' in line]

    def test_output_preserves_visible_rows_and_counts_new_lines_in_both_layouts(self):
        for columns in (80, 150):
            dashboard = self.dashboard()
            self.frame(dashboard, columns)
            dashboard._host_special_key('page_up')
            before = self.frame(dashboard, columns)
            self.assertIn('Scrollback - 0 new lines', before)
            dashboard.append_host_output('New line one\r\nNew line two\r\n')
            after = self.frame(dashboard, columns)
            self.assertEqual(self.history(after), self.history(before))
            self.assertNotIn('New line one', after)
            self.assertIn('Scrollback - 2 new lines', after)
            self.assertIn('End=Live', after)
            dashboard._host_special_key('end')
            live = self.frame(dashboard, columns)
            self.assertIn('New line two', live)
            self.assertNotIn('Scrollback -', live)
            self.assertEqual(dashboard._scrollback_new_lines, 0)

    def test_screen_clears_and_history_eviction_do_not_replace_frozen_history(self):
        dashboard = self.dashboard()
        self.frame(dashboard)
        dashboard._host_special_key('page_up')
        before = self.history(self.frame(dashboard))
        dashboard.append_host_output('\x1b[2J\x1b[H')
        for number in range(700):
            dashboard.append_host_output(f'Fresh output {number}\n')
        paused = self.frame(dashboard)
        self.assertEqual(self.history(paused), before)
        self.assertIn('Scrollback - 700 new lines', paused)
        self.assertLessEqual(len(dashboard._scrollback), 500)
        self.assertLessEqual(len(dashboard._screen.lines), 500)
        dashboard._host_special_key('end')
        live = self.frame(dashboard)
        self.assertIn('Fresh output 699', live)
        self.assertNotIn('Original row', live)

    def test_resize_keeps_the_same_source_line_at_the_top(self):
        dashboard = self.dashboard()
        self.frame(dashboard)
        dashboard._host_special_key('page_up')
        before = self.history(self.frame(dashboard))[0]
        dashboard.append_host_output('Incoming\n' * 5)
        for columns, height in ((80, 24), (40, 24), (150, 50)):
            resized = self.frame(dashboard, columns, height)
            self.assertEqual(self.history(resized)[0], before)
            self.assertIn('5 new lines', resized)

    def test_paging_and_submit_or_clear_resume_live(self):
        dashboard = self.dashboard()
        dashboard.host_input_available = lambda: True
        self.frame(dashboard)
        dashboard._host_special_key('page_up')
        first = self.history(self.frame(dashboard))[0]
        dashboard._host_special_key('page_up')
        self.assertLess(self.history(self.frame(dashboard))[0], first)
        dashboard.append_host_output('Newest output\n')
        for _ in range(100):
            if dashboard._scrollback is None:
                break
            dashboard._host_special_key('page_down')
            self.frame(dashboard)
        self.assertIsNone(dashboard._scrollback)
        self.assertIn('Newest output', self.frame(dashboard))
        dashboard._host_special_key('page_up')
        dashboard._host_command = 'draft'
        self.assertIsNotNone(dashboard._scrollback)
        dashboard.handle_host_command('calc 6 * 7')
        self.assertIsNone(dashboard._scrollback)
        dashboard._host_terminal.submit.assert_called_once_with('calc 6 * 7')
        dashboard._host_special_key('page_up')
        dashboard.clear_host_output()
        self.assertIsNone(dashboard._scrollback)

    def test_partial_and_wrapped_output_counts_line_events_once(self):
        dashboard = self.dashboard()
        self.frame(dashboard)
        dashboard._host_special_key('page_up')
        dashboard.append_host_output('Partial')
        self.assertEqual(dashboard._scrollback_new_lines, 0)
        dashboard.append_host_output('\r\n' + 'X' * 81)
        self.assertEqual(dashboard._scrollback_new_lines, 2)
        dashboard.append_host_output('\x1b[2J\x1b[H')
        self.assertEqual(dashboard._scrollback_new_lines, 2)

    def test_page_up_can_hold_a_short_history_without_older_pages(self):
        dashboard = ConsoleDashboard({})
        dashboard.set_host_terminal(MagicMock())
        dashboard.append_host_output('Only one output line\n')
        self.frame(dashboard)
        dashboard._host_special_key('page_up')
        dashboard.append_host_output('Arrived later\n')
        frozen = self.frame(dashboard)
        self.assertIn('Only one output line', frozen)
        self.assertNotIn('Arrived later', frozen)
        self.assertIn('Scrollback - 1 new line', frozen)
        dashboard._host_special_key('page_down')
        self.assertIn('Arrived later', self.frame(dashboard))

    def test_end_key_is_read_on_windows_and_common_ansi_terminals(self):
        for sequence in (None, b'\x1b[F', b'\x1bOF', b'\x1b[4~', b'\x1b[8~'):
            dashboard = self.dashboard()
            self.frame(dashboard)
            dashboard._host_special_key('page_up')
            dashboard._running = True
            dispatch = dashboard._host_special_key
            actions = []

            def stop_after_key(action):
                actions.append(action)
                dispatch(action)
                dashboard._running = False

            if sequence is None:
                keys = iter(('\xe0', 'O'))
                modules = {'msvcrt': SimpleNamespace(kbhit=lambda: True, getwch=lambda: next(keys))}
                platform = 'nt'
            else:
                modules = {'select': SimpleNamespace(select=lambda *args: ([3], [], [])),
                           'termios': SimpleNamespace(tcgetattr=lambda fd: [], tcsetattr=lambda *args: None,
                                                      TCSADRAIN=0),
                           'tty': SimpleNamespace(setcbreak=lambda fd: None)}
                platform = 'posix'
            with patch.dict(sys.modules, modules), patch('rsh_console.os.name', platform), \
                    patch.object(dashboard, '_host_special_key', side_effect=stop_after_key), \
                    patch('rsh_console.sys.stdin', SimpleNamespace(fileno=lambda: 3)), \
                    patch('rsh_console.os.read', side_effect=[bytes((byte,)) for byte in sequence or b'']):
                dashboard._host_input_loop()
            self.assertEqual(actions, ['end'])
            self.assertIsNone(dashboard._scrollback)


if __name__ == '__main__':
    unittest.main()
