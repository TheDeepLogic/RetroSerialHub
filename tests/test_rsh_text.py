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
            (80, 80, 19),
            (40, 40, 19),
            (40, 80, 9),
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
                    configure_screen_clearing(ser, columns=columns)
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


if __name__ == "__main__":
    unittest.main()
