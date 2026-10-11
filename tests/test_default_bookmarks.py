import unittest
from pathlib import Path

import rsh_browser
import rsh_ftp


class DefaultBookmarkTests(unittest.TestCase):
    def test_browser_has_the_requested_default_bookmarks(self):
        self.assertEqual(
            rsh_browser._load_bookmarks(
                Path(__file__).resolve().parents[1] / "browser_bookmarks.json"
            ),
            [
                {
                    "name": "The Deep Logic",
                    "url": "https://github.com/TheDeepLogic",
                },
                {
                    "name": "AII Usenet Archive",
                    "url": "https://usenet.trashworldnews.com/?group=comp.sys.apple2",
                },
                {
                    "name": "C64 Demos",
                    "url": "https://c64ntsc.blogspot.com/?m=1",
                },
                {"name": "99er", "url": "https://www.99er.net/"},
                {"name": "WinWorld", "url": "https://winworldpc.com/home"},
            ],
        )

    def test_ftp_has_the_requested_anonymous_plain_ftp_defaults(self):
        bookmarks = rsh_ftp._load_bookmarks(
            Path(__file__).resolve().parents[1] / "ftp_bookmarks.json"
        )
        self.assertEqual(
            bookmarks,
            [
                {
                    "name": "ftp.cdrom.com",
                    "host": "ftp.cdrom.com",
                    "port": 21,
                    "secure": False,
                    "username": "anonymous",
                },
                {
                    "name": "ftp.oldskool.org",
                    "host": "ftp.oldskool.org",
                    "port": 21,
                    "secure": False,
                    "username": "anonymous",
                },
                {
                    "name": "ftp.ngdc.noaa.gov",
                    "host": "ftp.ngdc.noaa.gov",
                    "port": 21,
                    "secure": False,
                    "username": "anonymous",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
