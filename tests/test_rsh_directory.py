import json
import tempfile
import unittest
from pathlib import Path

from rsh_directory import load_directory, save_directory


class BbsDirectoryStorageTests(unittest.TestCase):
    def test_missing_directory_reports_json_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bbs.json"
            with self.assertRaisesRegex(ValueError, 'settings/defaults/bbs_directory.json'):
                load_directory(path)

    def test_saved_directory_round_trips_structured_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bbs.json"
            saved = [
                {"name": "Custom", "host": "custom.example.org", "port": 2323}
            ]
            save_directory(saved, path)

            entries = load_directory(path)

        self.assertEqual(entries, saved)

    def test_saved_directory_requires_valid_entry_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bbs.json"
            path.write_text(
                json.dumps([{"name": "Broken", "host": "example.org", "port": 0}]),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "invalid port"):
                load_directory(path)

    def test_parallel_lists_are_not_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bbs.json"
            path.write_text(json.dumps({'names': ['Name'], 'hosts': ['host'], 'ports': [23]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'list of entries'):
                load_directory(path)


if __name__ == "__main__":
    unittest.main()
