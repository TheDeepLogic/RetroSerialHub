import unittest
from unittest.mock import patch

import rsh_bbs
from rsh_bbs import _two_column_pages


class BbsMenuPaginationTests(unittest.TestCase):
    def test_pages_are_filled_to_capacity_before_continuing(self):
        items = ["BBS %02d" % number for number in range(1, 65)]
        pages = _two_column_pages(items, page_lines=19)

        self.assertEqual(len(pages), 2)
        self.assertEqual(len(pages[0]), 19)
        self.assertTrue(pages[0][0].startswith(" 1] BBS 01"))
        self.assertIn("20] BBS 20", pages[0][0])
        self.assertTrue(pages[0][-1].startswith("19] BBS 19"))
        self.assertIn("38] BBS 38", pages[0][-1])
        self.assertEqual(len(pages[1]), 19)
        self.assertTrue(pages[1][0].startswith("39] BBS 39"))
        self.assertIn("58] BBS 58", pages[1][0])
        self.assertTrue(pages[1][6].startswith("45] BBS 45"))
        self.assertIn("64] BBS 64", pages[1][6])
        self.assertTrue(pages[1][-1].startswith("57] BBS 57"))

    def test_one_screen_balances_items_into_two_columns(self):
        items = ["BBS %02d" % number for number in range(1, 31)]
        pages = _two_column_pages(items, page_lines=19)

        self.assertEqual(len(pages), 1)
        self.assertEqual(len(pages[0]), 19)
        self.assertTrue(pages[0][0].startswith(" 1] BBS 01"))
        self.assertIn("20] BBS 20", pages[0][0])
        self.assertTrue(pages[0][10].startswith("11] BBS 11"))
        self.assertIn("30] BBS 30", pages[0][10])
        self.assertTrue(pages[0][-1].startswith("19] BBS 19"))

    def test_empty_directory_has_no_pages(self):
        self.assertEqual(_two_column_pages([]), [])

    def test_40_column_layout_uses_one_column_pages(self):
        pages = _two_column_pages(
            [f"BBS {index}" for index in range(1, 22)],
            page_lines=19,
            columns=40,
        )

        self.assertEqual([len(page) for page in pages], [19, 2])
        self.assertEqual(pages[0][0], " 1] BBS 1")
        self.assertEqual(pages[0][-1], "19] BBS 19")
        self.assertEqual(pages[1][0], "20] BBS 20")

    def test_manager_adds_entry_and_persists_directory(self):
        names = ["Default"]
        hosts = ["default.example.org"]
        ports = [23]
        serial = FakeSerial()
        session = rsh_bbs.create_session(
            serial, use_ansi=False, BBSS=names, IPS=hosts, PORTS=ports
        )
        rsh_bbs.start_directory_manager(session, serial, use_ansi=False)

        with patch("rsh_bbs.save_directory") as save_directory:
            for value in ("A", "New BBS", "new.example.org", "6502"):
                rsh_bbs.handle_directory_manager_input(
                    session, value, serial, use_ansi=False
                )

        self.assertEqual(names, ["Default", "New BBS"])
        self.assertEqual(hosts, ["default.example.org", "new.example.org"])
        self.assertEqual(ports, [23, 6502])
        save_directory.assert_called_once_with(
            [
                {
                    "name": "Default",
                    "host": "default.example.org",
                    "port": 23,
                },
                {"name": "New BBS", "host": "new.example.org", "port": 6502},
            ]
        )

    def test_manager_can_edit_and_delete_configured_entry(self):
        names = ["Default"]
        hosts = ["default.example.org"]
        ports = [23]
        serial = FakeSerial()
        session = rsh_bbs.create_session(
            serial, use_ansi=False, BBSS=names, IPS=hosts, PORTS=ports
        )
        rsh_bbs.start_directory_manager(session, serial, use_ansi=False)

        with patch("rsh_bbs.save_directory") as save_directory:
            for value in (
                "E",
                "1",
                "Updated",
                "updated.example.org",
                "6502",
                "D",
                "1",
                "Y",
            ):
                rsh_bbs.handle_directory_manager_input(
                    session, value, serial, use_ansi=False
                )

        self.assertEqual(names, [])
        self.assertEqual(hosts, [])
        self.assertEqual(ports, [])
        self.assertEqual(save_directory.call_count, 2)


class FakeSerial:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)


if __name__ == "__main__":
    unittest.main()
