import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rsh_files
from rsh_terminal import configure_screen_clearing


class FakeSerial:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)


class FileDirectoryNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.home = self.root / "files"
        self.child = self.home / "nested folder"
        self.child.mkdir(parents=True)
        (self.home / "home.txt").write_text("home", encoding="ascii")
        (self.child / "nested.txt").write_text("nested", encoding="ascii")
        self.serial = FakeSerial()
        configure_screen_clearing(self.serial, columns=80)
        self.session = rsh_files.create_session(
            self.serial, base_dir=self.home
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_numbered_directory_navigation_and_parent_home_shortcuts(self):
        self.assertEqual(self.session["current_dir"], self.home.resolve())
        self.assertEqual(
            self.session["entries"],
            [
                ("directory", self.child),
                ("file", self.home / "home.txt"),
            ],
        )

        consumed, action = rsh_files.handle_input(
            self.session, "1", self.serial
        )
        self.assertTrue(consumed)
        self.assertIsNone(action)
        self.assertEqual(self.session["current_dir"], self.child)

        rsh_files.handle_input(self.session, "B", self.serial)
        self.assertEqual(self.session["current_dir"], self.home.resolve())
        rsh_files.handle_input(self.session, "1", self.serial)
        self.assertEqual(self.session["current_dir"], self.child)
        rsh_files.handle_input(self.session, "H", self.serial)
        self.assertEqual(self.session["current_dir"], self.home.resolve())

    def test_typed_directory_jumps_directly_and_file_action_is_absolute(self):
        consumed, action = rsh_files.handle_input(
            self.session, str(self.child), self.serial
        )
        self.assertTrue(consumed)
        self.assertIsNone(action)
        self.assertEqual(self.session["current_dir"], self.child)

        consumed, action = rsh_files.handle_input(
            self.session, "1", self.serial
        )
        self.assertTrue(consumed)
        self.assertEqual(
            action, f"XMODEM_SEND:{self.child / 'nested.txt'}"
        )

    def test_drive_command_lists_roots_and_number_opens_selected_drive(self):
        drive_c = self.root / "drive-c"
        drive_d = self.root / "drive-d"
        drive_c.mkdir()
        drive_d.mkdir()
        with patch.object(rsh_files, "_root_directories", return_value=[drive_c, drive_d]):
            rsh_files.handle_input(self.session, "D", self.serial)
            self.assertTrue(self.session["root_mode"])
            self.assertEqual(
                self.session["entries"],
                [("directory", drive_c), ("directory", drive_d)],
            )

            rsh_files.handle_input(self.session, "2", self.serial)

        self.assertFalse(self.session["root_mode"])
        self.assertEqual(self.session["current_dir"], drive_d)


if __name__ == "__main__":
    unittest.main()
