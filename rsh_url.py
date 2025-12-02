"""
rsh_url.py - URL fetcher and viewer

This module provides URL fetching and viewing functionality for
the RetroSerialHub system. It handles:
- URL input and validation
- Fetching URL content
- HTML stripping
- Text display with pagination

All URL functionality is self-contained in this module to keep the hub clean.
"""

import urllib.request
import urllib.error
import html
import re
import time


def _write(ser, s):
    """Write string to serial port encoded as ASCII"""
    ser.write(s.encode('ascii', errors='ignore'))


def _clear_screen(ser, use_ansi=True):
    """Clear the terminal screen"""
    if use_ansi:
        _write(ser, "\x1b[2J\x1b[H")  # ANSI clear screen + home cursor
    else:
        _write(ser, "\r\n")  # Simple newline for non-ANSI terminals


def _wait_for_key(ser):
    """Wait for a keypress"""
    while True:
        if ser.in_waiting:
            ch = ser.read(1)
            try:
                return ch.decode(errors='ignore').upper()
            except Exception:
                return ""
        time.sleep(0.05)


def _paginate_lines(ser, lines, page_lines=22, quit_msg=False):
    """Display lines with pagination"""
    count = 0
    for ln in lines:
        _write(ser, ln + "\r\n")
        count += 1
        if count >= page_lines:
            if quit_msg:
                _write(ser, "\r\nPress any key to continue (Q to quit)...\r\n")
            else:
                _write(ser, "\r\nPress any key to continue...\r\n")
            key = _wait_for_key(ser)
            if key == "Q":
                return "QUIT"
            count = 0
    return "DONE"


def strip_html_to_text(html_bytes):
    try:
        text = html_bytes.decode('utf-8', errors='ignore')
    except Exception:
        text = html_bytes.decode(errors='ignore')
    # Remove scripts/styles
    text = re.sub(r"(?is)<script.*?>.*?</script>", "", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", "", text)
    # Replace breaks and paragraphs with newlines
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    # Strip tags
    text = re.sub(r"(?is)<.*?>", "", text)
    # Unescape entities
    text = html.unescape(text)
    # Normalize whitespace
    lines = [ln.rstrip() for ln in text.splitlines()]
    # Collapse long blank runs
    cleaned = []
    blank = 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank <= 1:
                cleaned.append("")
        else:
            blank = 0
            cleaned.append(ln)
    return cleaned


def create_session(ser, use_ansi=True):
    sess = {'stage': 0}
    _render_prompt(ser)
    return sess


def _render_prompt(ser):
    _write(ser, "\r\nURL Reader: enter a URL to fetch and display text.\r\n")
    _write(ser, "Enter Q to return to the main menu.\r\n\r\n")
    _write(ser, "URL: ")


def handle_input(sess, line_str, ser, use_ansi=True):
    """Handle input in URL mode. Returns (consumed, action) tuple.
    
    consumed: True if input was handled
    action: String indicating action for hub:
        'MENU' - return to main menu
        None - no action needed
    """
    txt = line_str.strip()
    
    # Handle quit
    if txt.upper() == 'Q':
        return True, 'MENU'
    
    # Handle empty line
    if not txt:
        _render_prompt(ser)
        return True, None
        
    # Treat input as URL and attempt to fetch
    url = txt
    if not re.match(r'^[a-z]+://', url, re.I):
        url = 'http://' + url
        
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read()
            lines = strip_html_to_text(data)
            
            # Display the content with pagination
            result = _paginate_lines(ser, lines, page_lines=22, quit_msg=False)
            
            # Always re-render prompt after displaying content
            _render_prompt(ser)
            
    except urllib.error.URLError as e:
        _write(ser, f"\r\n*** URL error: {e} ***\r\n")
        _wait_for_key(ser)
        _render_prompt(ser)
    except Exception as e:
        _write(ser, f"\r\n*** Fetch failed: {e} ***\r\n")
        _wait_for_key(ser)
        _render_prompt(ser)
        
    return True, None
