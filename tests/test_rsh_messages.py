from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from rsh_session import SessionServices
from retro_os.menu import OSFlyoutMenu


class Terminal:
    secret_input = False
    _rsh_columns = 40

    def __init__(self):
        self.output = bytearray()

    def write(self, data):
        self.output.extend(data)
        return len(data)

    def read(self, count=1):
        return b''


class MessageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.terminal = Terminal()
        self.service = SessionServices(self.terminal, Path(self.temp.name))
        self.addCleanup(self.service.close)

    def test_idle_terminal_gets_immediate_notice_and_preserves_unread_message(self):
        self.terminal._rsh_activity_tracker = SimpleNamespace(active=False)
        self.terminal.write(b'Select: par')
        self.assertTrue(self.service.notify('Message from Host: Hello'))
        text = self.terminal.output.decode()
        self.assertIn('NEW MESSAGE', text)
        self.assertIn('M=Messages', text)
        self.assertTrue(text.endswith('Select: par'))
        self.assertEqual(len(self.service.pending), 1)
        item = self.service.message_list()[0]
        self.assertFalse(item['read'])
        self.assertEqual(self.service.read_message(item['id']), 'Message from Host: Hello')
        self.assertEqual(len(self.service.pending), 0)
        self.assertTrue(self.service.message_list()[0]['read'])
        self.assertEqual(self.service.read_message(item['id']), 'Message from Host: Hello')

    def test_file_message_announces_filename_without_dumping_contents(self):
        content = 'Incoming text from Host: guide.txt\n' + 'Long body line\n' * 500
        self.service.notify(content)
        self.assertIn(b'guide.txt', self.terminal.output)
        self.assertNotIn(b'Long body line', self.terminal.output)
        self.assertEqual(self.service.read_message(1), content)

    def test_nested_transfers_defer_then_announce_once_after_final_packet(self):
        with self.service.transfer():
            self.terminal.write(b'PACKET')
            with self.service.transfer():
                self.service.notify('Waiting message')
            self.assertEqual(self.terminal.output, b'PACKET')
            self.terminal.write(b'FINAL ACK')
        output = self.terminal.output
        self.assertLess(output.index(b'FINAL ACK'), output.index(b'NEW MESSAGE'))
        self.assertEqual(output.count(b'NEW MESSAGE'), 1)
        self.assertEqual(len(self.service.pending), 1)
        self.service.announce_pending()
        self.assertEqual(output.count(b'NEW MESSAGE'), 1)

    def test_history_is_bounded_and_unread_count_matches_retained_messages(self):
        self.service.quiet = True
        for number in range(105):
            self.service.notify(str(number))
            if number % 2 == 0:
                self.service.read_message(number + 1)
        retained = self.service.message_list()
        self.assertEqual(len(retained), 100)
        self.assertEqual(len(self.service.pending), sum(not item['read'] for item in retained))
        self.assertEqual(retained[0]['text'], '104')
        self.assertEqual(self.terminal.output, b'')

    def test_unread_shortcut_fits_both_menu_widths_without_extra_rows(self):
        for columns in (40, 80):
            menu = OSFlyoutMenu()
            output = menu.render(columns=columns, rows=24, messages_count=3)
            lines = output.split('\r\n')
            self.assertEqual(len(lines), 24)
            self.assertIn('M=Messages (3 unread)', lines[-3])
            self.assertTrue(all(len(line) < columns for line in lines))
            self.assertEqual(len(menu.SECTIONS), 7)
            clean = menu.render(columns=columns, rows=24)
            self.assertNotIn('M=Messages', clean)

    def test_ascii_send_defers_banner_until_all_file_bytes_are_written(self):
        from rsh_files import ascii_send
        source = Path(self.temp.name) / 'send.txt'
        source.write_text('first line\nlast line\n', encoding='ascii')
        raw_write = self.service._write

        def arriving_message(data):
            result = raw_write(data)
            if data == b'first line':
                self.assertGreater(self.service.protected, 0)
                self.service.notify('Arrived while sending')
                self.assertNotIn(b'NEW MESSAGE', self.terminal.output)
            return result

        self.service._write = arriving_message
        ascii_send(self.terminal, source)
        self.assertLess(self.terminal.output.index(b'last line'),
                        self.terminal.output.index(b'NEW MESSAGE'))
        self.assertEqual(len(self.service.pending), 1)


if __name__ == '__main__':
    unittest.main()
