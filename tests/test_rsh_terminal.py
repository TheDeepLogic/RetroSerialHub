import unittest

from rsh_terminal import AnsiToTextTranslator


class AnsiToTextTranslatorTests(unittest.TestCase):
    def test_clear_home_and_color_sequences(self):
        translator = AnsiToTextTranslator()
        translated = translator.feed(
            b"\x1b[2J\x1b[HHello \x1b[31mRed\x1b[0m"
        )
        self.assertEqual(translated, b"\x0cHello Red")

    def test_default_erase_in_display_clears_between_frames(self):
        translator = AnsiToTextTranslator()
        self.assertEqual(translator.feed(b"first frame"), b"first frame")
        self.assertEqual(translator.feed(b"\x1b[H\x1b[J"), b"\r\x0c")
        self.assertEqual(translator.feed(b"second frame"), b"second frame")

    def test_cursor_home_clears_animated_frames_when_enabled(self):
        translator = AnsiToTextTranslator(clear_on_home=True)
        translated = translator.feed(b"FRAME 1\x1b[HFRAME 2\x1b[HFRAME 3")
        self.assertEqual(translated, b"FRAME 1\x0cFRAME 2\x0cFRAME 3")

    def test_cursor_home_does_not_clear_unless_enabled(self):
        translator = AnsiToTextTranslator()
        self.assertEqual(translator.feed(b"FRAME 1\x1b[HFRAME 2"), b"FRAME 1\rFRAME 2")

    def test_cursor_addressed_rows_are_linearized(self):
        translator = AnsiToTextTranslator()
        translated = translator.feed(
            b"\x1b[2J\x1b[1;1H+---+\x1b[2;1H|***|\x1b[3;1H+---+"
        )
        self.assertEqual(translated, b"\x0c+---+\r\n|***|\r\n+---+")

    def test_cp437_line_art_is_approximated(self):
        translator = AnsiToTextTranslator()
        self.assertEqual(translator.feed(bytes((218, 196, 191))), b"+-+")

    def test_telnet_negotiation_and_subnegotiation_are_removed(self):
        translator = AnsiToTextTranslator()
        self.assertEqual(
            translator.feed(b"\xff\xfb\x01A\xff\xfa\x18x\xff\xf0B"),
            b"AB",
        )

    def test_control_sequences_can_cross_input_chunks(self):
        translator = AnsiToTextTranslator()
        self.assertEqual(translator.feed(b"Hi\x1b["), b"Hi")
        self.assertEqual(translator.feed(b"31m!"), b"!")

    def test_clear_sequence_can_be_configured(self):
        translator = AnsiToTextTranslator(clear_sequence=b"\x1bv")
        self.assertEqual(translator.feed(b"\x1b[2J"), b"\x1bv")

    def test_vt100_home_redraw_maps_to_custom_emulation_clear(self):
        translator = AnsiToTextTranslator(
            clear_sequence=b"\x1bv",
            clear_on_home=True,
        )
        translated = translator.feed(
            b"\x1b[2J\x1b[Hfirst frame\x1b[Hsecond frame"
        )
        self.assertEqual(
            translated,
            b"\x1bv\x1bvfirst frame\x1bvsecond frame",
        )

    def test_form_feed_maps_to_configured_clear_sequence(self):
        translator = AnsiToTextTranslator(clear_sequence=b"\x1bv")
        self.assertEqual(
            translator.feed(b"\x05\x1b[6n\x0c\r\n\x0c"),
            b"\x1bv\r\r\n\x1bv",
        )


if __name__ == "__main__":
    unittest.main()
