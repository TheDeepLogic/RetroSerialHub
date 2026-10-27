import unittest

import rsh_wargames as wargames
from tests.test_rsh_wargames import Terminal


class CPMTests(unittest.TestCase):
    def setUp(self):
        self.ser = Terminal()
        self.session = wargames.create_session(self.ser, False)

    def command(self, text):
        self.ser.writes.clear()
        result = wargames.handle_input(self.session, text, self.ser, False)
        return self.ser.text(), result

    def test_startup_and_help_do_not_spoil_program_discovery(self):
        startup = self.ser.text()
        self.assertIn("64K RAM", startup)
        self.assertNotIn("DIALER", startup)
        self.assertNotIn("TERM", startup)
        text, _ = self.command("HELP")
        self.assertIn("TYPE README.TXT", text)
        self.assertNotIn("DIALER", text)
        text, _ = self.command("TYPE README.TXT")
        self.assertIn("MODEM.DOC", text)
        text, _ = self.command("TYPE MODEM.DOC")
        self.assertIn("DIALER.COM", text)
        self.assertIn("TERM.COM", text)

    def test_directory_patterns_and_40_column_layout(self):
        text, _ = self.command("dir *.com")
        self.assertIn("DIALER", text)
        self.assertIn("STAT", text)
        self.assertNotIn("README", text)
        text, _ = self.command("DIR ?E??.COM")
        self.assertIn("TERM", text)
        self.assertIn("HELP", text)
        self.assertNotIn("DIALER", text)
        self.ser._rsh_columns = 40
        text, _ = self.command("DIR")
        self.assertTrue(all(len(line) <= 39 for line in text.splitlines()))

    def test_copy_rename_type_erase_and_drive_switch(self):
        self.command("PIP B:=A:NOTES.TXT")
        text, _ = self.command("B:")
        self.assertTrue(text.endswith("B>"))
        self.command("REN WORK.TXT=NOTES.TXT")
        text, _ = self.command("TYPE WORK.TXT")
        self.assertIn("Finish homework", text)
        self.command("ERA W*.TXT")
        text, _ = self.command("DIR")
        self.assertIn("NO FILE", text)
        text, _ = self.command("TYPE A:NOTES.TXT")
        self.assertIn("Finish homework", text)

    def test_programs_survive_rename_and_copy(self):
        self.command("REN CALL.COM=DIALER.COM")
        self.command("PIP B:SCAN.COM=CALL.COM")
        self.command("B:")
        self.command("SCAN")
        self.assertEqual(self.session["submode"], "DIALER")
        text, _ = self.command("Q")
        self.assertTrue(text.endswith("B>"))
        self.command("A:TERM.COM")
        self.assertEqual(self.session["submode"], "TERM")

    def test_disk_operations_are_isolated_to_session(self):
        self.command("ERA *.*")
        text, _ = self.command("DIR")
        self.assertIn("NO FILE", text)
        other = wargames.create_session(Terminal(), False)
        self.assertIn("DIALER.COM", other["cpm_disks"]["A"])

    def test_save_stat_dump_and_native_clear(self):
        self.command("SAVE 2 B:TEST.BIN")
        self.assertEqual(self.session["cpm_disks"]["B"]["TEST.BIN"]["size"], 512)
        text, _ = self.command("STAT B:")
        self.assertIn("1 FILES", text)
        text, _ = self.command("DUMP README.TXT")
        self.assertIn("0000 49 4D 53 41 49", text)
        self.command("CLS")
        self.assertIn(b"\x1bv", self.ser.writes)

    def test_errors_do_not_mutate_disk_or_change_drive(self):
        for command, error in (("Z:", "SELECT"), ("TYPE ../../README", "BAD FILE NAME"),
                               ("REN TERM.COM=DIALER.COM", "FILE EXISTS"),
                               ("PIP B:=MISSING.TXT", "NO FILE"),
                               ("SAVE 999 X.BIN", "SAVE pages"),
                               ("XYZZY", "XYZZY?")):
            before = dict(self.session["cpm_disks"]["A"])
            text, _ = self.command(command)
            self.assertIn(error, text)
            self.assertEqual(self.session["cpm_disks"]["A"], before)
            self.assertEqual(self.session["cpm_drive"], "A")
        self.assertEqual(self.command("EXIT")[1], (True, "MENU"))


if __name__ == "__main__":
    unittest.main()
