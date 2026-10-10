import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rsh_ftp


class FakeSerial:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)


class FakeFtp:
    def __init__(self, *args, **kwargs):
        self.connected_to = None
        self.logged_in = None
        self.protected = False
        self.passive = None
        self.cwd_path = "/"
        self.retr_command = None
        self.closed = False

    def connect(self, host, port, timeout):
        self.connected_to = (host, port, timeout)

    def login(self, username, password):
        self.logged_in = (username, password)

    def prot_p(self):
        self.protected = True

    def set_pasv(self, enabled):
        self.passive = enabled

    def pwd(self):
        return self.cwd_path

    def mlsd(self):
        return iter(
            [
                ("docs", {"type": "dir"}),
                ("readme.txt", {"type": "file", "size": "5"}),
            ]
        )

    def nlst(self):
        return ["readme.txt"]

    def retrbinary(self, command, callback):
        self.retr_command = command
        callback(b"hello")

    def quit(self):
        self.closed = True

    def close(self):
        self.closed = True


class FtpMenuTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.bookmarks_path = Path(self.temp_directory.name) / "ftp.json"
        self.serial = FakeSerial()
        self.session = rsh_ftp.create_session(
            self.serial,
            use_ansi=False,
            bookmarks_path=self.bookmarks_path,
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def connect_steps(self, secure="N"):
        for value in (
            "ftp.example.org",
            "",
            secure,
            "",
            "",
        ):
            rsh_ftp.handle_input(self.session, value, self.serial, False)

    def test_connection_uses_anonymous_ftp_and_passive_listing(self):
        fake_ftp = FakeFtp()
        with patch.object(rsh_ftp.ftplib, "FTP", return_value=fake_ftp):
            self.connect_steps()

        self.assertEqual(fake_ftp.connected_to, ("ftp.example.org", 21, 20))
        self.assertEqual(fake_ftp.logged_in, ("anonymous", ""))
        self.assertTrue(fake_ftp.passive)
        self.assertEqual(
            [entry["name"] for entry in self.session["entries"]],
            ["docs", "readme.txt"],
        )
        self.assertEqual(self.session["submode"], "LISTING")

    def test_explicit_ftps_logs_in_and_protects_data_connection(self):
        fake_ftp = FakeFtp()
        with patch.object(rsh_ftp.ftplib, "FTP_TLS", return_value=fake_ftp):
            self.connect_steps(secure="Y")

        self.assertTrue(fake_ftp.protected)
        self.assertTrue(fake_ftp.passive)

    def test_file_selection_can_choose_host_or_serial_download(self):
        self.session.update(
            {
                "ftp": FakeFtp(),
                "submode": "LISTING",
                "entries": [{"name": "readme.txt", "is_dir": False, "size": "5"}],
            }
        )
        _, action = rsh_ftp.handle_input(
            self.session, "1", self.serial, use_ansi=False
        )
        self.assertIsNone(action)
        _, action = rsh_ftp.handle_input(
            self.session, "H", self.serial, use_ansi=False
        )
        self.assertEqual(action, ("DOWNLOAD_TO_HOST", "readme.txt"))

        self.session["submode"] = "LISTING"
        rsh_ftp.handle_input(self.session, "1", self.serial, use_ansi=False)
        rsh_ftp.handle_input(self.session, "D", self.serial, use_ansi=False)
        _, action = rsh_ftp.handle_input(
            self.session, "Y", self.serial, use_ansi=False
        )
        self.assertEqual(
            action, ("DOWNLOAD_TO_SERIAL", "readme.txt", "YMODEM_SEND")
        )

    def test_download_writes_file_atomically_and_uses_remote_name(self):
        fake_ftp = FakeFtp()
        self.session["ftp"] = fake_ftp
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "readme.txt"
            result = rsh_ftp.download_to_path(
                self.session, "readme.txt", destination
            )

            self.assertEqual(result, destination)
            self.assertEqual(destination.read_bytes(), b"hello")
            self.assertEqual(fake_ftp.retr_command, "RETR readme.txt")
            self.assertEqual(list(Path(directory).iterdir()), [destination])

    def test_unsafe_remote_name_is_rejected_before_download(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unsafe"):
                rsh_ftp.download_to_path(
                    {"ftp": FakeFtp()},
                    "..\\outside.txt",
                    Path(directory) / "outside.txt",
                )

    def test_quit_disconnects_from_ftp(self):
        fake_ftp = FakeFtp()
        self.session["ftp"] = fake_ftp
        self.session["submode"] = "LISTING"
        consumed, action = rsh_ftp.handle_input(
            self.session, "Q", self.serial, use_ansi=False
        )

        self.assertTrue(consumed)
        self.assertEqual(action, "MENU")
        self.assertTrue(fake_ftp.closed)
        self.assertIsNone(self.session["ftp"])

    def test_current_site_can_be_bookmarked_without_saving_password(self):
        self.session.update(
            {
                "ftp": FakeFtp(),
                "host": "secure.example.org",
                "port": 2121,
                "secure": True,
                "username": "retro-user",
                "submode": "LISTING",
                "entries": [],
            }
        )
        rsh_ftp.handle_input(self.session, "A", self.serial, use_ansi=False)
        rsh_ftp.handle_input(
            self.session, "My FTP", self.serial, use_ansi=False
        )

        saved = json.loads(self.bookmarks_path.read_text(encoding="utf-8"))
        self.assertEqual(
            saved,
            [
                {
                    "name": "My FTP",
                    "host": "secure.example.org",
                    "port": 2121,
                    "secure": True,
                    "username": "retro-user",
                }
            ],
        )
        self.assertNotIn("password", saved[0])

    def test_saved_bookmark_restores_connection_settings_and_prompts_password(self):
        self.bookmarks_path.write_text(
            json.dumps(
                [
                    {
                        "name": "Saved FTPS",
                        "host": "secure.example.org",
                        "port": 2121,
                        "secure": True,
                        "username": "retro-user",
                    }
                ]
            ),
            encoding="utf-8",
        )
        self.session = rsh_ftp.create_session(
            self.serial,
            use_ansi=False,
            bookmarks_path=self.bookmarks_path,
        )
        fake_ftp = FakeFtp()
        with patch.object(rsh_ftp.ftplib, "FTP_TLS", return_value=fake_ftp):
            rsh_ftp.handle_input(self.session, "M", self.serial, use_ansi=False)
            rsh_ftp.handle_input(self.session, "1", self.serial, use_ansi=False)
            self.assertEqual(self.session["submode"], "PASSWORD")
            self.assertEqual(self.session["host"], "secure.example.org")
            self.assertEqual(self.session["port"], 2121)
            self.assertTrue(self.session["secure"])
            self.assertEqual(self.session["username"], "retro-user")
            rsh_ftp.handle_input(
                self.session, "temporary-secret", self.serial, use_ansi=False
            )

        self.assertTrue(fake_ftp.protected)
        self.assertEqual(fake_ftp.logged_in, ("retro-user", "temporary-secret"))
        self.assertEqual(self.session["password"], "")
        self.assertEqual(self.session["submode"], "LISTING")

    def test_saved_bookmark_can_be_deleted(self):
        self.session["bookmarks"] = [
            {
                "name": "Saved FTP",
                "host": "ftp.example.org",
                "port": 21,
                "secure": False,
                "username": "anonymous",
            }
        ]
        rsh_ftp.handle_input(self.session, "M", self.serial, use_ansi=False)
        rsh_ftp.handle_input(self.session, "D1", self.serial, use_ansi=False)

        self.assertEqual(self.session["bookmarks"], [])
        self.assertEqual(
            json.loads(self.bookmarks_path.read_text(encoding="utf-8")), []
        )


if __name__ == "__main__":
    unittest.main()
