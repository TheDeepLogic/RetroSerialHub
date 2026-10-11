import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import rsh_browser
import RETRO_SERIAL_HUB


class FakeSerial:
    def __init__(self):
        self.output = bytearray()

    def write(self, data):
        self.output.extend(data)


class FakeResponse:
    def __init__(self, body, content_type="text/plain", url="https://example.com/"):
        self.body = body
        self.headers = self
        self.content_type = content_type
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def get_content_type(self):
        return self.content_type

    def get_content_charset(self):
        return "utf-8"

    def read(self, limit):
        return self.body[:limit]

    def geturl(self):
        return self.url


class BrowserTests(unittest.TestCase):
    def create_session(self, serial=None, bookmarks_path=None):
        return rsh_browser.create_session(
            serial or FakeSerial(), bookmarks_path=bookmarks_path
        )

    def test_parse_html_removes_scripts_and_numbers_links(self):
        lines, links, forms, fields = rsh_browser.parse_html(
            b"<h1>Hello</h1><p>Read <a href='/next'>the next page</a>.</p>"
            b"<script>alert('hidden')</script>"
        )
        text = "\n".join(lines)
        self.assertIn("Hello", text)
        self.assertIn("the next page [1]", text)
        self.assertNotIn("hidden", text)
        self.assertEqual(links, ["/next"])
        self.assertEqual(forms, [])
        self.assertEqual(fields, [])

    def test_search_form_exposes_input_and_submit_controls(self):
        lines, links, forms, fields = rsh_browser.parse_html(
            b'<form action="/search" method="get">'
            b'<input name="query" placeholder="Search">'
            b'<button>Search</button></form>'
        )
        self.assertEqual(links, [])
        self.assertEqual(forms[0]["action"], "/search")
        self.assertEqual(forms[0]["method"], "GET")
        self.assertEqual(fields[0]["name"], "query")
        self.assertEqual(fields[0]["label"], "Search")
        self.assertIn("\x01I1\x02", "\n".join(lines))
        self.assertIn("\x01S1\x02", "\n".join(lines))
        serial = FakeSerial()
        session = self.create_session(serial)
        session.update({"forms": forms, "fields": fields})
        rendered = "\n".join(
            rsh_browser._render_controls(session, line) for line in lines
        )
        self.assertIn("[I1 input: Search = <empty>]", rendered)
        self.assertIn("[S1 submit: Search]", rendered)

    def test_wrapped_lines_fit_terminal_width(self):
        lines = rsh_browser._wrap_text("word " * 40)
        self.assertTrue(all(len(line) <= rsh_browser.LINE_WIDTH for line in lines))

    def test_40_column_browser_wraps_page_text_and_limits_page_size(self):
        serial = FakeSerial()
        RETRO_SERIAL_HUB.configure_screen_clearing(serial, columns=40)
        session = self.create_session(serial)

        self.assertEqual(session["line_width"], 38)
        self.assertEqual(session["page_lines"], rsh_browser.NARROW_PAGE_LINES)
        self.assertTrue(
            all(
                len(line) <= 38
                for line in serial.output.decode("ascii").splitlines()
                if line
            )
        )

        with patch("rsh_browser.urlopen") as urlopen:
            urlopen.return_value = FakeResponse(b"word " * 30)
            _, lines, _, _, _ = rsh_browser._fetch_page(
                "https://example.com", width=session["line_width"]
            )
        self.assertTrue(all(len(line) <= 38 for line in lines))

    def test_40_column_browser_page_rendering_fits_screen_width(self):
        serial = FakeSerial()
        RETRO_SERIAL_HUB.configure_screen_clearing(serial, columns=40)
        session = self.create_session(serial)
        with patch("rsh_browser._fetch_page") as fetch_page:
            fetch_page.return_value = (
                "https://example.com/",
                ["Readable browser page text"] * 30,
                [],
                [],
                [],
            )
            rsh_browser._open_url(
                session, "https://example.com/", serial, use_ansi=False
            )

        fetch_page.assert_called_once_with(
            "https://example.com/",
            method="GET",
            form_data=None,
            width=38,
        )
        self.assertEqual(session["page_lines"], rsh_browser.NARROW_PAGE_LINES)
        lines = serial.output.decode("ascii").splitlines()
        self.assertTrue(all(len(line) <= 40 for line in lines))
        self.assertIn("Page 1/3", serial.output.decode("ascii"))
        self.assertIn("Link number:", serial.output.decode("ascii"))

    def test_only_http_schemes_are_allowed(self):
        with self.assertRaises(ValueError):
            rsh_browser._normalize_url("file:///private/data")
        self.assertEqual(
            rsh_browser._normalize_url("example.com"), "https://example.com"
        )

    @patch("rsh_browser.urlopen")
    def test_fetch_accepts_plain_text(self, urlopen):
        urlopen.return_value = FakeResponse(b"Plain text page")
        url, lines, links, forms, fields = rsh_browser._fetch_page("https://example.com")
        self.assertEqual(url, "https://example.com/")
        self.assertEqual(lines, ["Plain text page"])
        self.assertEqual(links, [])
        self.assertEqual(forms, [])
        self.assertEqual(fields, [])

    def test_backspace_in_url_input_does_not_leave_control_byte(self):
        session = self.create_session()
        with patch("rsh_browser._fetch_page") as fetch_page:
            fetch_page.return_value = (
                "https://marginalia-search.com/",
                ["Page"],
                [],
                [],
                [],
            )
            rsh_browser.handle_input(
                session, "marginalia-searchg\b.com", FakeSerial(), use_ansi=False
            )
        fetch_page.assert_called_once_with(
            "marginalia-search.com", method="GET", form_data=None
        )

    def test_invalid_url_control_byte_is_reported_in_browser(self):
        serial = FakeSerial()
        session = self.create_session(serial)
        rsh_browser._open_url(
            session, "https://example.com/\x01bad", serial, use_ansi=False
        )
        self.assertIn("control characters", session["error"])
        self.assertIn(b"control characters", serial.output)

    def test_serial_line_buffer_applies_backspace(self):
        buffer = RETRO_SERIAL_HUB.update_command_input(
            b"", b"marginalia-searchg\x08.com\r"
        )
        self.assertEqual(buffer, b"marginalia-search.com\r")

    def test_get_form_submission_includes_field_value(self):
        serial = FakeSerial()
        session = self.create_session(serial)
        session.update({
            "url": "https://example.com/",
            "awaiting_url": False,
            "forms": [{
                "action": "/search",
                "method": "GET",
                "fields": [0],
                "submit_labels": ["Search"],
            }],
            "fields": [{
                "name": "query",
                "label": "Search",
                "value": "",
                "type": "search",
                "form": 0,
            }],
        })
        with patch("rsh_browser._fetch_page") as fetch_page:
            fetch_page.return_value = (
                "https://example.com/search?query=retro",
                ["Results"],
                [],
                [],
                [],
            )
            rsh_browser.handle_input(session, "I1", serial, use_ansi=False)
            rsh_browser.handle_input(session, "retro", serial, use_ansi=False)
            rsh_browser.handle_input(session, "S1", serial, use_ansi=False)
        fetch_page.assert_called_once_with(
            "https://example.com/search?query=retro",
            method="GET",
            form_data=None,
        )

    @patch("rsh_browser.urlopen")
    def test_post_form_sends_encoded_values(self, urlopen):
        urlopen.return_value = FakeResponse(
            b"Results", url="https://example.com/search"
        )
        rsh_browser._fetch_page(
            "https://example.com/search",
            method="POST",
            form_data=[("query", "retro search")],
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.data, b"query=retro+search")

    @patch("rsh_browser._fetch_page")
    def test_numbered_link_opens_relative_url(self, fetch_page):
        serial = FakeSerial()
        session = {
            "history": [],
            "url": "https://example.com/start",
            "lines": ["[1] next"],
            "links": ["/next"],
            "page": 0,
            "awaiting_url": False,
            "awaiting_page": False,
            "awaiting_bookmark_name": False,
            "awaiting_field": None,
            "showing_bookmarks": False,
            "error": "",
            "bookmarks_path": Path("unused.json"),
            "bookmarks": [],
        }
        fetch_page.return_value = (
            "https://example.com/next",
            ["Destination"],
            [],
            [],
            [],
        )

        consumed, action = rsh_browser.handle_input(session, "[1]", serial)

        self.assertTrue(consumed)
        self.assertIsNone(action)
        fetch_page.assert_called_once_with(
            "https://example.com/next", method="GET", form_data=None
        )
        self.assertEqual(session["history"], ["https://example.com/start"])
        self.assertIn(b"Destination", serial.output)

    def test_page_navigation_stays_within_bounds(self):
        serial = FakeSerial()
        session = {
            "history": [],
            "url": "https://example.com/",
            "lines": ["line"] * (rsh_browser.PAGE_LINES + 1),
            "links": [],
            "page": 0,
            "awaiting_url": False,
            "awaiting_page": False,
            "awaiting_bookmark_name": False,
            "awaiting_field": None,
            "showing_bookmarks": False,
            "error": "",
            "bookmarks_path": Path("unused.json"),
            "bookmarks": [],
        }
        rsh_browser.handle_input(session, "P", serial, use_ansi=False)
        self.assertEqual(session["page"], 0)
        rsh_browser.handle_input(session, "N", serial, use_ansi=False)
        self.assertEqual(session["page"], 1)
        rsh_browser.handle_input(session, "N", serial, use_ansi=False)
        self.assertEqual(session["page"], 1)

    def test_goto_page_and_first_page(self):
        serial = FakeSerial()
        session = {
            "history": [],
            "url": "https://example.com/",
            "lines": ["line"] * (rsh_browser.PAGE_LINES * 3),
            "links": [],
            "page": 0,
            "awaiting_url": False,
            "awaiting_page": False,
            "awaiting_bookmark_name": False,
            "awaiting_field": None,
            "showing_bookmarks": False,
            "error": "",
            "bookmarks_path": Path("unused.json"),
            "bookmarks": [],
        }
        rsh_browser.handle_input(session, "G", serial, use_ansi=False)
        rsh_browser.handle_input(session, "3", serial, use_ansi=False)
        self.assertEqual(session["page"], 2)
        rsh_browser.handle_input(session, "F", serial, use_ansi=False)
        self.assertEqual(session["page"], 0)

    def test_adding_bookmark_persists_and_reloads(self):
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "bookmarks.json"
            serial = FakeSerial()
            session = self.create_session(serial, path)
            session.update({"url": "https://example.com/path", "awaiting_url": False})

            rsh_browser.handle_input(session, "A", serial, use_ansi=False)
            rsh_browser.handle_input(session, "Example", serial, use_ansi=False)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [
                {"name": "Example", "url": "https://example.com/path"}
            ])
            self.assertEqual(self.create_session(bookmarks_path=path)["bookmarks"], [
                {"name": "Example", "url": "https://example.com/path"}
            ])

    def test_bookmark_menu_opens_and_deletes_entries(self):
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "bookmarks.json"
            path.write_text(
                json.dumps([{"name": "Example", "url": "https://example.com"}]),
                encoding="utf-8",
            )
            serial = FakeSerial()
            session = self.create_session(serial, path)
            session.update({"url": "https://example.com/", "awaiting_url": False})
            with patch("rsh_browser._fetch_page") as fetch_page:
                fetch_page.return_value = (
                    "https://example.com/",
                    ["Page text"],
                    [],
                    [],
                    [],
                )
                rsh_browser.handle_input(session, "M", serial, use_ansi=False)
                rsh_browser.handle_input(session, "1", serial, use_ansi=False)
                fetch_page.assert_called_once_with(
                    "https://example.com", method="GET", form_data=None
                )
            self.assertFalse(session["showing_bookmarks"])
            rsh_browser.handle_input(session, "M", serial, use_ansi=False)
            rsh_browser.handle_input(session, "D 1", serial, use_ansi=False)
            self.assertEqual(session["bookmarks"], [])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
