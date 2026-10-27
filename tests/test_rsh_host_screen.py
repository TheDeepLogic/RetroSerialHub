import unittest

from rsh_host_screen import HostScreen


class HostScreenTests(unittest.TestCase):
    def test_progress_updates_erase_stale_suffixes(self):
        screen = HostScreen()
        screen.feed("Downloading 100 percent\rDone\x1b[K")
        self.assertEqual(screen.lines, ["Done"])
        self.assertEqual((screen.row, screen.column), (0, 4))

    def test_addressing_moves_and_saved_cursor_update_existing_rows(self):
        screen = HostScreen()
        screen.feed("Header\r\nOld row\r\nInput: ")
        screen.feed("\x1b[s\x1b[2;1HNew\x1b[K\x1b[u")
        self.assertEqual(screen.lines, ["Header", "New", "Input: "])
        self.assertEqual((screen.row, screen.column), (2, 7))
        screen.feed("\x1b[A\x1b[2G!\x1b[1B\x1b[1D?")
        self.assertEqual(screen.lines[1], "N!w")
        self.assertEqual(screen.lines[2], "I?put: ")

    def test_clear_modes_obey_cursor_and_display_regions(self):
        screen = HostScreen()
        screen.feed("Alpha\nBravo\nCharlie\x1b[2;3H\x1b[J")
        self.assertEqual(screen.lines, ["Alpha", "Br"])
        screen.feed("\x1b[2J")
        self.assertEqual((screen.row, screen.column), (1, 2))
        self.assertFalse(any(screen.lines))
        screen.feed("\x1b[HReady: ")
        self.assertEqual(screen.lines[0], "Ready: ")
        self.assertEqual((screen.row, screen.column), (0, 7))

    def test_partial_controls_and_osc_do_not_leak_into_text(self):
        screen = HostScreen()
        for char in "\x1b]0;Untrusted title\x07\x1b[2J\x1b[H\x1b[31mPrompt: \x1b[0m":
            screen.feed(char)
        self.assertEqual(screen.lines, ["Prompt: "])
        self.assertEqual(screen.column, 8)

    def test_saved_cursor_can_be_restored_into_erased_rows(self):
        screen = HostScreen()
        screen.feed("\x1b[10;5H\x1b7\x1b[H\x1b[J\x1b8")
        self.assertEqual((screen.row, screen.column), (9, 4))
        self.assertEqual(len(screen.lines), 10)
        screen.feed("Prompt: ")
        self.assertEqual(screen.lines[9], "    Prompt: ")

    def test_wrapping_and_bounded_history(self):
        screen = HostScreen(columns=8, height=3, capacity=10)
        screen.feed("12345678\r\nNext")
        self.assertEqual(screen.lines, ["12345678", "Next"])
        for number in range(30):
            screen.feed(f"\n{number}")
        self.assertEqual(len(screen.lines), 10)
        self.assertEqual(screen.row, 9)
        screen.feed("\x1b[3J")
        self.assertEqual(len(screen.lines), 3)
        self.assertEqual(screen.row, 2)


if __name__ == "__main__":
    unittest.main()
