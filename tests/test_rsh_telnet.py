import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rsh_telnet import create_session, handle_input


class FakeSerial:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)


class TelnetMenuTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.bookmarks_path = Path(self.temp_directory.name) / "telnet.json"
        self.serial = FakeSerial()
        self.session = create_session(
            self.serial, use_ansi=False, bookmarks_path=self.bookmarks_path
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def handle(self, text, **kwargs):
        return handle_input(self.session, text, self.serial, False, **kwargs)

    def test_direct_destination_can_be_saved_as_telnet_bookmark(self):
        self.handle("A")
        self.handle("bbs.example.org")
        self.handle("2323")
        self.handle("Test BBS")
        consumed, action = self.handle("T")

        self.assertTrue(consumed)
        self.assertEqual(action, ("CONNECT", "bbs.example.org", 2323))
        self.assertEqual(
            json.loads(self.bookmarks_path.read_text(encoding="utf-8")),
            [
                {
                    "name": "Test BBS",
                    "host": "bbs.example.org",
                    "port": 2323,
                }
            ],
        )

    def test_direct_destination_can_be_added_to_bbs_directory_instead(self):
        saved_entries = []

        def add_bbs_entry(name, host, port):
            saved_entries.append((name, host, port))

        self.handle("A")
        self.handle("bbs.example.org")
        self.handle("23")
        self.handle("BBS")
        _, action = self.handle("B", add_bbs_entry=add_bbs_entry)

        self.assertEqual(saved_entries, [("BBS", "bbs.example.org", 23)])
        self.assertEqual(action, ("CONNECT", "bbs.example.org", 23))
        self.assertFalse(self.bookmarks_path.exists())

    def test_invalid_port_keeps_prompt_active(self):
        self.handle("A")
        self.handle("bbs.example.org")
        _, action = self.handle("70000")

        self.assertIsNone(action)
        self.assertEqual(self.session["submode"], "PORT")
        self.assertIn(b"1 to 65535", b"".join(self.serial.writes))

    def test_bookmark_can_be_selected_and_deleted(self):
        self.session["bookmarks"] = [
            {"name": "Saved", "host": "bbs.example.org", "port": 23}
        ]
        consumed, action = self.handle("1")
        self.assertTrue(consumed)
        self.assertEqual(action, ("CONNECT", "bbs.example.org", 23))

        self.handle("D")
        self.handle("1")
        self.assertEqual(self.session["bookmarks"], [])
        self.assertEqual(
            json.loads(self.bookmarks_path.read_text(encoding="utf-8")), []
        )

    def test_invalid_host_is_rejected(self):
        self.handle("A")
        _, action = self.handle("bad host")

        self.assertIsNone(action)
        self.assertEqual(self.session["submode"], "HOST")
        self.assertIn(b"valid hostname", b"".join(self.serial.writes))

    def prepare_save(self):
        for text in ("A", "bbs.example.org", "23", "Saved"):
            self.handle(text)

    def test_failed_save_preserves_state_and_retry_does_not_duplicate(self):
        self.prepare_save()
        with patch("rsh_telnet.Path.replace", side_effect=OSError("disk full")):
            self.assertEqual(self.handle("T"), (True, None))
        self.assertEqual(self.session["bookmarks"], [])
        self.assertEqual(self.session["submode"], "SAVE")
        self.assertEqual(list(self.bookmarks_path.parent.iterdir()), [])
        self.assertIn(b"disk full", b"".join(self.serial.writes))
        self.assertEqual(self.handle("T")[1], ("CONNECT", "bbs.example.org", 23))
        self.assertEqual(len(json.loads(self.bookmarks_path.read_text())), 1)

    def test_failed_delete_preserves_disk_and_memory_and_can_cancel(self):
        self.prepare_save()
        self.handle("T")
        original = self.bookmarks_path.read_bytes()
        self.handle("D")
        with patch("rsh_telnet.Path.replace", side_effect=PermissionError("locked")):
            self.assertEqual(self.handle("1"), (True, None))
        self.assertEqual(self.bookmarks_path.read_bytes(), original)
        self.assertEqual(len(self.session["bookmarks"]), 1)
        self.assertEqual(self.session["submode"], "DELETE")
        self.assertEqual(list(self.bookmarks_path.parent.glob("*.tmp")), [])
        self.handle("Q")
        self.assertEqual(self.session["submode"], "MENU")

    def test_bbs_save_failure_can_connect_without_saving(self):
        self.prepare_save()
        with patch("rsh_telnet._save_bookmarks") as save:
            def fail(*args):
                raise OSError("read only")
            self.assertEqual(self.handle("B", add_bbs_entry=fail), (True, None))
            self.assertEqual(self.session["submode"], "SAVE")
            self.assertEqual(self.handle("N")[1], ("CONNECT", "bbs.example.org", 23))
            save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
