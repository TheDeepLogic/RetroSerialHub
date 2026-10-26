"""Telnet module for Retro Serial OS."""

from __future__ import annotations

from rsh_storage import settings_path

import json
import pathlib
import socket
import time

_context = None


def _get_bookmarks():
    candidates = [settings_path("telnet_bookmarks.json")]
    for p in candidates:
        if p.exists():
            try:
                with p.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return []


def init(context):
    global _context
    _context = context


def register_commands(registry):
    context = _context

    def telnet_command(args):
        if not args:
            if context.activate_module:
                context.session.active_module = "telnet"
                context.activate_module("telnet")
                return "Opening Telnet menu..."
            return "Telnet client is available from the Retro Serial Hub menu."

        sub = args[0].lower()
        if sub in ("list", "bookmarks"):
            bookmarks = _get_bookmarks()
            if not bookmarks:
                return "No saved Telnet bookmarks."
            lines = ["Saved Telnet Bookmarks:"]
            for idx, bm in enumerate(bookmarks, 1):
                lines.append(f"[{idx}] {bm.get('name', 'Bookmark')} ({bm.get('host')}:{bm.get('port')})")
            lines.append("\nUse 'telnet connect <host> [port]' or 'telnet connect <number>'")
            return "\n".join(lines)

        if sub in ("connect", "c", "open"):
            if len(args) < 2:
                return "Usage: telnet connect <host_or_number> [port]"
            target = args[1]
            port = 23
            if target.isdigit():
                bookmarks = _get_bookmarks()
                idx = int(target) - 1
                if 0 <= idx < len(bookmarks):
                    target = bookmarks[idx].get("host")
                    port = bookmarks[idx].get("port", 23)
            elif len(args) >= 3 and args[2].isdigit():
                port = int(args[2])

            context.bus.publish("telnet.connect", {
                "session": context.session,
                "host": target,
                "port": port,
            })
            if context.activate_module:
                context.session.active_module = "telnet"
                context.activate_module(("telnet_connect", target, port))
                return f"Connecting to {target}:{port}..."
            return f"Telnet target: {target}:{port}"

        if sub in ("query", "fetch"):
            if len(args) < 2:
                return "Usage: telnet query <host> [port] [send_keystrokes]"
            host = args[1]
            port = 23
            send_text = ""
            if len(args) >= 3:
                if args[2].isdigit():
                    port = int(args[2])
                    send_text = " ".join(args[3:]) if len(args) > 3 else ""
                else:
                    send_text = " ".join(args[2:])

            try:
                sock = socket.create_connection((host, port), timeout=7)
                sock.settimeout(3.0)
                if send_text:
                    from ..runtime import parse_and_chunk_keystrokes
                    actions = parse_and_chunk_keystrokes(send_text)
                    for act, val in actions:
                        if act == "wait":
                            time.sleep(val)
                        elif act == "send":
                            sock.sendall(val)
                chunks = []
                start = time.time()
                while time.time() - start < 4:
                    try:
                        data = sock.recv(2048)
                        if not data:
                            break
                        chunks.append(data)
                        if len(b"".join(chunks)) > 8192:
                            break
                    except socket.timeout:
                        break
                sock.close()
                raw = b"".join(chunks).decode("ascii", errors="replace")
                return raw or f"Connected to {host}:{port} (no response received)."
            except Exception as exc:
                return f"Telnet query failed: {exc}"

        if sub in ("send", "type"):
            if len(args) < 2:
                return "Usage: telnet send <text>"
            text_to_send = " ".join(args[1:])
            context.bus.publish("session.send_keys", {
                "session": context.session,
                "text": text_to_send,
            })
            return f"Sent: {text_to_send}"

        # If user directly typed `telnet <host> [port]`
        if "." in args[0] or ":" in args[0] or args[0].isdigit():
            return telnet_command(["connect", *args])

        return "Usage: telnet [list | connect <host> [port] | query <host> [port] [text] | send <text>]"

    registry.register_command("telnet", telnet_command)


def register_menu(menu):
    menu.append(("telnet", "telnet"))


def handle_event(event):
    return None

