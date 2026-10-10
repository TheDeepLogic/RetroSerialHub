import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
