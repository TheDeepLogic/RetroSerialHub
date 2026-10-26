"""BBS module for Retro Serial OS."""

from __future__ import annotations

from rsh_storage import settings_path

import json
import pathlib
import socket
import time

_context = None


def _get_entries():
    candidates = [settings_path("bbs_directory.json")]
    for p in candidates:
        if p.exists():
            try:
                with p.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    try:
        import config
        return [{"name": n, "host": h, "port": p} for n, h, p in zip(config.BBSS, config.IPS, config.PORTS)]
    except Exception:
        return []


def init(context):
    global _context
    _context = context


def register_commands(registry):
    context = _context

    def bbs_command(args):
        if not args:
            if context.activate_module:
                context.session.active_module = "bbs"
                context.activate_module("bbs")
                return "Opening BBS menu..."
            return "BBS directory is available from the Retro Serial Hub menu."

        sub = args[0].lower()
        if sub in ("list", "entries", "directory"):
            entries = _get_entries()
            if not entries:
                return "No BBS entries configured."
            lines = ["Available BBS Systems:"]
            for idx, entry in enumerate(entries, 1):
                lines.append(f"[{idx}] {entry['name']} ({entry['host']}:{entry['port']})")
            lines.append("\nUse 'bbs connect <number>' to connect.")
            return "\n".join(lines)

        if sub in ("connect", "c", "dial"):
            if len(args) < 2:
                return "Usage: bbs connect <number_or_name>"
            target = " ".join(args[1:]).strip()
            entries = _get_entries()
            matched = None
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(entries):
                    matched = entries[idx]
            if not matched:
                t_lower = target.lower()
                for entry in entries:
                    if t_lower in entry["name"].lower():
                        matched = entry
                        break
            if not matched:
                return f"No BBS entry matched '{target}'. Use 'bbs list' to view entries."

            context.bus.publish("bbs.connect", {
                "session": context.session,
                "name": matched["name"],
                "host": matched["host"],
                "port": matched["port"],
            })
            if context.activate_module:
                context.session.active_module = "bbs"
                context.activate_module(("bbs_connect", matched["host"], matched["port"]))
                return f"Connecting to {matched['name']} ({matched['host']}:{matched['port']})..."
            return f"BBS target: {matched['name']} at {matched['host']}:{matched['port']}"

        if sub in ("query", "fetch"):
            if len(args) < 2:
                return "Usage: bbs query <number_or_name> [send_keystrokes]"
            target = args[1]
            send_text = " ".join(args[2:]) if len(args) > 2 else ""
            entries = _get_entries()
            matched = None
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(entries):
                    matched = entries[idx]
            if not matched:
                for entry in entries:
                    if target.lower() in entry["name"].lower():
                        matched = entry
                        break
            if not matched:
                return f"No BBS entry matched '{target}'."

            host, port = matched["host"], matched["port"]
            try:
                sock = socket.create_connection((host, int(port)), timeout=7)
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
                return raw or f"Connected to {matched['name']} (no banner received)."
            except Exception as exc:
                return f"BBS query failed: {exc}"

        if sub in ("send", "type"):
            if len(args) < 2:
                return "Usage: bbs send <text>"
            text_to_send = " ".join(args[1:])
            context.bus.publish("session.send_keys", {
                "session": context.session,
                "text": text_to_send,
            })
            return f"Sent: {text_to_send}"

        # If user directly typed a number, e.g. `bbs 1`
        if args[0].isdigit():
            return bbs_command(["connect", args[0]])

        return "Usage: bbs [list | connect <id> | query <id> [text] | send <text>]"

    registry.register_command("bbs", bbs_command)


def register_menu(menu):
    menu.append(("bbs", "bbs"))


def handle_event(event):
    return None

