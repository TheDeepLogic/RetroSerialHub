"""Text-first web browser for serial terminals."""

from rsh_storage import settings_dir, settings_path
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from rsh_terminal import clear_terminal_screen, terminal_columns


PAGE_LINES = 20
LINE_WIDTH = 76
NARROW_PAGE_LINES = 14
MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_BOOKMARKS_PATH = settings_path("browser_bookmarks.json")
BLOCK_TAGS = {
    "address", "article", "blockquote", "dd", "div", "dl", "dt", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
    "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
    "table", "tr", "ul",
}
HIDDEN_TAGS = {"script", "style", "noscript", "svg"}
INPUT_MARKER = re.compile(r"\x01I(\d+)\x02")
SUBMIT_MARKER = re.compile(r"\x01S(\d+)\x02")


def _write(ser, text):
    ser.write(text.encode("ascii", errors="replace"))


def _clear_screen(ser, use_ansi):
    clear_terminal_screen(ser, use_ansi)


def _line_width(ser):
    return 38 if terminal_columns(ser) == 40 else LINE_WIDTH


def _page_size(session, ser):
    return session.get(
        "page_lines",
        NARROW_PAGE_LINES if terminal_columns(ser) == 40 else PAGE_LINES,
    )


class _PageTextParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.fragments = []
        self.links = []
        self.forms = []
        self.fields = []
        self.hidden_tags = []
        self.active_link = None
        self.current_form = None
        self.active_button = None
        self.button_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in HIDDEN_TAGS:
            self.hidden_tags.append(tag)
            return
        if self.hidden_tags:
            return
        if tag == "form":
            form = {
                "action": attrs.get("action", ""),
                "method": attrs.get("method", "get").upper(),
                "fields": [],
                "submit_labels": [],
            }
            self.forms.append(form)
            self.current_form = len(self.forms) - 1
            self.fragments.append("\n")
            return
        if self.current_form is not None and tag == "input":
            self._add_input(attrs)
            return
        if self.current_form is not None and tag == "button":
            self.active_button = attrs.get("type", "submit").lower() == "submit"
            self.button_text = []
            return
        if tag in BLOCK_TAGS or tag == "br":
            self.fragments.append("\n")
        if tag == "img" and attrs.get("alt"):
            self.fragments.append(" " + attrs["alt"] + " ")
        if tag == "a" and attrs.get("href"):
            self.active_link = len(self.links)
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag in HIDDEN_TAGS:
            if tag in self.hidden_tags:
                self.hidden_tags.remove(tag)
            return
        if self.hidden_tags:
            return
        if tag == "button" and self.active_button is not None:
            if self.active_button:
                form = self.forms[self.current_form]
                label = " ".join(" ".join(self.button_text).split()) or "Submit"
                form["submit_labels"].append(label)
            self.active_button = None
            self.button_text = []
            return
        if tag == "form":
            if self.current_form is not None:
                form_index = self.current_form + 1
                form = self.forms[self.current_form]
                label = ", ".join(form["submit_labels"]) or "Submit"
                self.fragments.append("\n\x01S%d\x02\n" % form_index)
                self.current_form = None
            return
        if tag == "a" and self.active_link is not None:
            self.fragments.append(" [%d] " % (self.active_link + 1))
            self.active_link = None
        if tag in BLOCK_TAGS:
            self.fragments.append("\n")

    def handle_data(self, data):
        if not self.hidden_tags:
            if self.active_button:
                self.button_text.append(data)
            self.fragments.append(re.sub(r"\s+", " ", data))

    def _add_input(self, attrs):
        input_type = attrs.get("type", "text").lower()
        if attrs.get("disabled") is not None or input_type in {
            "button", "reset", "image",
        }:
            return
        form = self.forms[self.current_form]
        if input_type == "submit":
            label = attrs.get("value") or "Submit"
            form["submit_labels"].append(label)
            return
        if input_type not in {"hidden", "text", "search", "email", "url", "tel", "number", "password", "checkbox", "radio"}:
            return
        name = attrs.get("name", "")
        value = attrs.get("value", "")
        if input_type in {"checkbox", "radio"} and attrs.get("checked") is None:
            value = ""
        label = (
            attrs.get("aria-label")
            or attrs.get("placeholder")
            or name
            or attrs.get("id")
            or "field"
        )
        field = {
            "name": name,
            "label": label,
            "value": value,
            "type": input_type,
            "form": self.current_form,
        }
        self.fields.append(field)
        field_index = len(self.fields)
        form["fields"].append(field_index - 1)
        if input_type != "hidden":
            self.fragments.append("\n\x01I%d\x02\n" % field_index)


def _wrap_text(text, width=LINE_WIDTH):
    lines = []
    for raw_line in text.splitlines():
        words = raw_line.split()
        if not words:
            if lines and lines[-1]:
                lines.append("")
            continue
        current = ""
        for word in words:
            while len(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:width])
                word = word[width:]
            if current and len(current) + len(word) + 1 > width:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        if current:
            lines.append(current)
    while lines and not lines[-1]:
        lines.pop()
    return lines or ["(This page contains no readable text.)"]


def parse_html(data, width=LINE_WIDTH):
    parser = _PageTextParser()
    parser.feed(data.decode("utf-8", errors="replace"))
    parser.close()
    text = "".join(parser.fragments)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _wrap_text(text, width), parser.links, parser.forms, parser.fields


def _normalize_url(url):
    url = url.strip()
    if not url:
        raise ValueError("Enter a web address.")
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        raise ValueError("Address contains control characters; edit and try again.")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
        url = "https://" + url
    if urlsplit(url).scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS addresses are supported.")
    return url


def _fetch_page(url, method="GET", form_data=None, width=LINE_WIDTH):
    data = None
    if form_data is not None and method.upper() == "POST":
        data = urlencode(form_data).encode("ascii")
    request = Request(
        _normalize_url(url),
        data=data,
        headers={"User-Agent": "RetroSerialHub"},
        method=method.upper(),
    )
    with urlopen(request, timeout=15) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise ValueError("Only HTML and plain-text pages are supported.")
        data = response.read(MAX_RESPONSE_BYTES + 1)
        truncated = len(data) > MAX_RESPONSE_BYTES
        data = data[:MAX_RESPONSE_BYTES]
        if content_type == "text/plain":
            charset = response.headers.get_content_charset() or "utf-8"
            lines = _wrap_text(data.decode(charset, errors="replace"), width)
            links, forms, fields = [], [], []
        else:
            lines, links, forms, fields = parse_html(data, width)
        if truncated:
            lines.extend(["", "[Page truncated: response exceeded 1 MiB.]"])
        return response.geturl(), lines, links, forms, fields


def _load_bookmarks(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as bookmark_file:
        bookmarks = json.load(bookmark_file)
    if not isinstance(bookmarks, list) or any(
        not isinstance(bookmark, dict)
        or not isinstance(bookmark.get("name"), str)
        or not isinstance(bookmark.get("url"), str)
        for bookmark in bookmarks
    ):
        raise ValueError("Bookmark file must contain a list of name/URL entries.")
    return bookmarks


def _save_bookmarks(session, bookmarks):
    path = session["bookmarks_path"]
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as bookmark_file:
            temporary_path = Path(bookmark_file.name)
            json.dump(bookmarks, bookmark_file, indent=2)
            bookmark_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def create_session(ser, use_ansi=True, bookmarks_path=None):
    bookmark_path = Path(bookmarks_path) if bookmarks_path else DEFAULT_BOOKMARKS_PATH
    columns = terminal_columns(ser)
    session = {
        "history": [],
        "url": "",
        "lines": [],
        "links": [],
        "page": 0,
        "awaiting_url": True,
        "awaiting_page": False,
        "awaiting_bookmark_name": False,
        "awaiting_field": None,
        "showing_bookmarks": False,
        "error": "",
        "bookmarks_path": bookmark_path,
        "bookmarks": _load_bookmarks(bookmark_path),
        "forms": [],
        "fields": [],
        "use_ansi": use_ansi,
        "line_width": columns - 2,
        "page_lines": NARROW_PAGE_LINES if columns == 40 else PAGE_LINES,
    }
    _render_url_prompt(ser, use_ansi)
    return session


def _render_url_prompt(ser, use_ansi=True):
    _clear_screen(ser, use_ansi)
    _write(ser, "\r\nWeb Browser\r\n")
    if terminal_columns(ser) == 40:
        _write(ser, "Text pages, links, and forms\r\nare supported.\r\n")
        _write(ser, "Enter an HTTP(S) address.\r\nQ returns to menu.\r\n")
    else:
        _write(ser, "Text pages, numbered links, and simple search forms are supported.\r\n")
        _write(ser, "Enter an HTTP(S) address, or Q to return to the menu.\r\n")
    _write(ser, "URL: ")


def _render_page(session, ser, use_ansi):
    line_width = session.get("line_width", _line_width(ser))
    page_lines = _page_size(session, ser)
    _clear_screen(ser, use_ansi)
    _write(ser, "\r\nWeb Browser\r\n")
    _write(ser, session["url"][:line_width] + "\r\n")
    if session["error"]:
        error_lines = _wrap_text("*** " + session["error"] + " ***", line_width)
        _write(ser, "\r\n" + "\r\n".join(error_lines) + "\r\n")
    if session["lines"]:
        start = session["page"] * page_lines
        for line in session["lines"][start:start + page_lines]:
            line = _render_controls(session, line, line_width)
            _write(ser, line + "\r\n")
    total_pages = max(1, (len(session["lines"]) + page_lines - 1) // page_lines)
    if line_width < LINE_WIDTH:
        _write(
            ser,
            "\r\nPage %d/%d | N/P scroll G goto\r\n"
            % (session["page"] + 1, total_pages),
        )
        _write(ser, "F first B back U URL Q menu\r\n")
        _write(ser, "I# input S# submit A save M marks\r\n")
        _write(ser, "Link number: ")
    else:
        _write(
            ser,
            "\r\nPage %d/%d | N/P=scroll G=goto F=first B=back U=URL\r\n"
            % (session["page"] + 1, total_pages),
        )
        _write(ser, "I#=input S#=submit G=goto F=first A=save M=bookmarks\r\n")
        _write(ser, "B=back U=URL Q=menu | link number: ")


def _render_controls(session, line, line_width=LINE_WIDTH):
    def render_input(match):
        index = int(match.group(1)) - 1
        field = session["fields"][index]
        value = field["value"] or "<empty>"
        control_text = "[I%d input: %s = %s]" % (
            index + 1,
            field["label"],
            value,
        )
        return re.sub(r"[\x00-\x1f\x7f]", " ", control_text)[:line_width]

    def render_submit(match):
        index = int(match.group(1)) - 1
        form = session["forms"][index]
        label = ", ".join(form["submit_labels"]) or "Submit"
        control_text = "[S%d submit: %s]" % (index + 1, label)
        return re.sub(r"[\x00-\x1f\x7f]", " ", control_text)[:line_width]

    line = INPUT_MARKER.sub(render_input, line)
    return SUBMIT_MARKER.sub(render_submit, line)[:line_width]


def _render_bookmarks(session, ser, use_ansi):
    _clear_screen(ser, use_ansi)
    _write(ser, "\r\nBookmarks\r\n\r\n")
    if not session["bookmarks"]:
        _write(ser, "No bookmarks saved.\r\n")
    for index, bookmark in enumerate(session["bookmarks"], 1):
        if terminal_columns(ser) == 40:
            _write(ser, "%2d] %s\r\n" % (index, bookmark["name"][:35]))
            _write(ser, "    %s\r\n" % bookmark["url"][:35])
        else:
            name = bookmark["name"][:28]
            url = bookmark["url"][:45]
            _write(ser, "%2d] %-28s %s\r\n" % (index, name, url))
    if terminal_columns(ser) == 40:
        _write(ser, "\r\nNumber opens; D# deletes; Q returns.\r\n")
    else:
        _write(ser, "\r\nEnter number to open, D number to delete, Q to return.\r\n")
    _write(ser, "Command: ")


def _show_error(session, message, ser, use_ansi):
    session["error"] = message
    _render_page(session, ser, use_ansi)


def _open_url(
    session,
    url,
    ser,
    use_ansi,
    add_history=True,
    method="GET",
    form_data=None,
):
    columns = terminal_columns(ser)
    line_width = _line_width(ser)
    page_lines = NARROW_PAGE_LINES if columns == 40 else PAGE_LINES
    try:
        fetch_options = {"method": method, "form_data": form_data}
        if line_width != LINE_WIDTH:
            fetch_options["width"] = line_width
        final_url, lines, links, forms, fields = _fetch_page(url, **fetch_options)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        session["error"] = "Could not load page: %s" % exc
        session["lines"] = []
        session["links"] = []
        session["forms"] = []
        session["fields"] = []
        session["awaiting_url"] = False
        _render_page(session, ser, use_ansi)
        return
    if add_history and session["url"]:
        session["history"].append(session["url"])
    session.update({
        "url": final_url,
        "lines": lines,
        "links": links,
        "forms": forms,
        "fields": fields,
        "page": 0,
        "awaiting_url": False,
        "error": "",
        "line_width": line_width,
        "page_lines": page_lines,
    })
    _render_page(session, ser, use_ansi)


def _submit_form(session, form_index, ser, use_ansi):
    if not 0 <= form_index < len(session["forms"]):
        _write(ser, "\r\nNo form with that number.\r\n")
        _render_page(session, ser, use_ansi)
        return
    form = session["forms"][form_index]
    method = form["method"]
    if method not in {"GET", "POST"}:
        _show_error(session, "This form uses an unsupported method.", ser, use_ansi)
        return
    values = [
        (field["name"], field["value"])
        for field_index in form["fields"]
        for field in (session["fields"][field_index],)
        if field["name"]
        and not (
            field["type"] in {"checkbox", "radio"} and not field["value"]
        )
    ]
    action = urljoin(session["url"], form["action"] or session["url"])
    if method == "GET" and values:
        parts = urlsplit(action)
        query = parts.query
        encoded_values = urlencode(values)
        query = query + "&" + encoded_values if query else encoded_values
        action = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, query, parts.fragment)
        )
    _open_url(
        session,
        action,
        ser,
        use_ansi,
        method=method,
        form_data=values if method == "POST" else None,
    )


def handle_input(session, line_str, ser, use_ansi=True):
    edited = []
    for char in line_str:
        if char in ("\b", "\x7f"):
            if edited:
                edited.pop()
        elif ord(char) >= 32:
            edited.append(char)
    text = "".join(edited).strip()
    upper = text.upper()

    if session["showing_bookmarks"]:
        if upper == "Q":
            session["showing_bookmarks"] = False
            _render_page(session, ser, use_ansi)
            return True, None
        if upper.startswith("D"):
            number = upper[1:].strip()
            if not number:
                _write(ser, "\r\nUse D followed by a bookmark number.\r\n")
                _render_bookmarks(session, ser, use_ansi)
                return True, None
            try:
                index = int(number)
            except ValueError:
                index = 0
            if not 1 <= index <= len(session["bookmarks"]):
                _write(ser, "\r\nNo bookmark with that number.\r\n")
                _render_bookmarks(session, ser, use_ansi)
                return True, None
            updated = session["bookmarks"][:]
            removed = updated.pop(index - 1)
            try:
                _save_bookmarks(session, updated)
            except OSError as exc:
                _write(ser, "\r\n*** Could not save bookmarks: %s ***\r\n" % exc)
            else:
                session["bookmarks"] = updated
                _write(ser, "\r\nRemoved bookmark: %s\r\n" % removed["name"])
            _render_bookmarks(session, ser, use_ansi)
            return True, None
        try:
            index = int(text)
        except ValueError:
            index = 0
        if not 1 <= index <= len(session["bookmarks"]):
            _write(ser, "\r\nEnter a bookmark number, D number, or Q.\r\n")
            _render_bookmarks(session, ser, use_ansi)
            return True, None
        session["showing_bookmarks"] = False
        _open_url(session, session["bookmarks"][index - 1]["url"], ser, use_ansi)
        return True, None

    if session["awaiting_bookmark_name"]:
        session["awaiting_bookmark_name"] = False
        if upper == "Q":
            _render_page(session, ser, use_ansi)
            return True, None
        name = text or urlsplit(session["url"]).hostname or session["url"]
        updated = session["bookmarks"] + [{"name": name, "url": session["url"]}]
        try:
            _save_bookmarks(session, updated)
        except OSError as exc:
            _show_error(session, "Could not save bookmark: %s" % exc, ser, use_ansi)
        else:
            session["bookmarks"] = updated
            _write(ser, "\r\nBookmark saved: %s\r\n" % name)
            _render_page(session, ser, use_ansi)
        return True, None

    if session["awaiting_field"] is not None:
        field_index = session["awaiting_field"]
        session["awaiting_field"] = None
        if upper != "Q":
            session["fields"][field_index]["value"] = text
        _render_page(session, ser, use_ansi)
        return True, None

    field_match = re.fullmatch(r"I(\d+)", upper)
    if field_match:
        field_index = int(field_match.group(1)) - 1
        if not 0 <= field_index < len(session["fields"]):
            _write(ser, "\r\nNo input field with that number.\r\n")
            _render_page(session, ser, use_ansi)
            return True, None
        session["awaiting_field"] = field_index
        field = session["fields"][field_index]
        _write(ser, "\r\n%s (Q cancels): " % field["label"])
        return True, None

    submit_match = re.fullmatch(r"S(\d+)", upper)
    if submit_match:
        _submit_form(session, int(submit_match.group(1)) - 1, ser, use_ansi)
        return True, None

    if session["awaiting_page"]:
        session["awaiting_page"] = False
        if upper == "Q" or not text:
            _render_page(session, ser, use_ansi)
            return True, None
        try:
            page_number = int(text)
        except ValueError:
            _show_error(session, "Enter a page number.", ser, use_ansi)
            return True, None
        page_lines = _page_size(session, ser)
        page_count = max(1, (len(session["lines"]) + page_lines - 1) // page_lines)
        if not 1 <= page_number <= page_count:
            _show_error(
                session,
                "Page number must be between 1 and %d." % page_count,
                ser,
                use_ansi,
            )
            return True, None
        session["page"] = page_number - 1
        session["error"] = ""
        _render_page(session, ser, use_ansi)
        return True, None

    if upper == "Q":
        return True, "MENU"

    if session["awaiting_url"]:
        if text:
            _open_url(session, text, ser, use_ansi)
        else:
            _render_url_prompt(ser, use_ansi)
        return True, None

    if upper == "U":
        session["awaiting_url"] = True
        _clear_screen(ser, use_ansi)
        _write(ser, "\r\nURL (Q returns to menu): ")
        return True, None
    if upper == "G":
        session["awaiting_page"] = True
        _write(ser, "\r\nPage number: ")
        return True, None
    if upper == "F":
        session["page"] = 0
        session["error"] = ""
        _render_page(session, ser, use_ansi)
        return True, None
    if upper == "A":
        if not session["url"]:
            _write(ser, "\r\nLoad a page before adding a bookmark.\r\n")
            _render_page(session, ser, use_ansi)
            return True, None
        session["awaiting_bookmark_name"] = True
        _write(ser, "\r\nBookmark name (Enter uses the site name, Q cancels): ")
        return True, None
    if upper == "M":
        session["showing_bookmarks"] = True
        _render_bookmarks(session, ser, use_ansi)
        return True, None
    if upper == "B":
        if session["history"]:
            _open_url(
                session, session["history"].pop(), ser, use_ansi, add_history=False
            )
        else:
            _write(ser, "\r\nNo previous page.\r\n")
            _render_page(session, ser, use_ansi)
        return True, None
    if upper in {"N", " "}:
        page_lines = _page_size(session, ser)
        max_page = max(0, (len(session["lines"]) - 1) // page_lines)
        session["page"] = min(max_page, session["page"] + 1)
        _render_page(session, ser, use_ansi)
        return True, None
    if upper == "P":
        session["page"] = max(0, session["page"] - 1)
        _render_page(session, ser, use_ansi)
        return True, None

    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    try:
        link_number = int(text)
    except ValueError:
        _write(ser, "\r\nUse N, P, G, F, A, M, B, U, Q, or a link number.\r\n")
        _write(ser, "Enter command: ")
        return True, None
    if not 1 <= link_number <= len(session["links"]):
        _write(ser, "\r\nNo link with that number.\r\n")
        _write(ser, "Enter command: ")
        return True, None
    target = urljoin(session["url"], session["links"][link_number - 1])
    _open_url(session, target, ser, use_ansi)
    return True, None
