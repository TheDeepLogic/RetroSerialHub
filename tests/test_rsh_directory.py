import json
import tempfile
import unittest
from pathlib import Path

from rsh_directory import load_directory, save_directory


class BbsDirectoryStorageTests(unittest.TestCase):
    def test_load_seeds_defaults_when_no_saved_directory_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bbs.json"
            entries = load_directory(
                ["Default BBS"], ["bbs.example.org"], [23], path
            )

        self.assertEqual(
            entries,
            [{"name": "Default BBS", "host": "bbs.example.org", "port": 23}],
        )

    def test_saved_directory_overrides_config_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bbs.json"
            saved = [
                {"name": "Custom", "host": "custom.example.org", "port": 2323}
            ]
            save_directory(saved, path)

            entries = load_directory(
                ["Default BBS"], ["bbs.example.org"], [23], path
            )

        self.assertEqual(entries, saved)

    def test_saved_directory_requires_valid_entry_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bbs.json"
            path.write_text(
                json.dumps([{"name": "Broken", "host": "example.org", "port": 0}]),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "invalid port"):
                load_directory([], [], [], path)

    def test_default_lists_must_remain_synchronized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bbs.json"
            with self.assertRaisesRegex(ValueError, "same number"):
                load_directory(["Name"], ["host"], [], path)


if __name__ == "__main__":
    unittest.main()
