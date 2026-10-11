import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rsh_text
from rsh_terminal import configure_screen_clearing


class FakeSerial:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)


class TextPaginationTests(unittest.TestCase):
    def test_pagination_reserves_prompt_rows_at_40_and_80_columns(self):
        cases = (
            (80, 80, 22),
            (40, 40, 22),
            (40, 80, 11),
        )
        prompt = b"Press any key to continue (Q to quit)..."

        for columns, line_width, expected_lines in cases:
            with self.subTest(columns=columns, line_width=line_width):
                with tempfile.TemporaryDirectory() as temp_directory:
                    path = Path(temp_directory) / "sample.txt"
                    path.write_text(
                        "\n".join(["X" * line_width] * 30),
                        encoding="ascii",
                    )
                    ser = FakeSerial()
                    configure_screen_clearing(
                        ser,
                        translate_ansi=True,
                        clear_sequence=b"\x1bv",
                        columns=columns,
                    )
                    session = rsh_text.create_session(
                        ser,
                        use_ansi=False,
                        files=[path.name],
                        base_dir=path.parent,
                    )
                    ser.writes.clear()

                    with patch.object(rsh_text, "_wait_for_key", return_value="Q"):
                        rsh_text.handle_input(session, "1", ser, use_ansi=False)

                    output = b"".join(ser.writes)
                    body_before_prompt = output.split(prompt, 1)[0]
                    self.assertEqual(
                        body_before_prompt.count(b"X" * line_width),
                        expected_lines,
                    )

    def test_full_final_page_only_shows_one_continue_prompt(self):
        ser = FakeSerial()
        configure_screen_clearing(ser, columns=80)

        with patch.object(rsh_text, "_wait_for_key", return_value=" ") as wait:
            result = rsh_text._paginate_lines(ser, ["line"] * 22)

        self.assertEqual(result, "DONE")
        wait.assert_called_once()


if __name__ == "__main__":
    unittest.main()
