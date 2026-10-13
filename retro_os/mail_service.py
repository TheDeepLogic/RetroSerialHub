"""Comprehensive Electronic Mail Service for Retro Serial Hub.

Provides:
1. Integrated Hub Mail: Central shared mailbox between vintage terminals and host.
   Messages are stamped with the machine name and connection type.
2. Internet Email: True IMAP inbox listing & reading, and SMTP sending.
3. Host Desktop Auth Window: Tkinter configuration popup.
"""

from __future__ import annotations

import datetime
import email
import email.header
import email.policy
from email.message import EmailMessage
import imaplib
import json
import os
import pathlib
import smtplib
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


def _decode_header_str(val: str) -> str:
    if not val:
        return ""
    try:
        parts = email.header.decode_header(val)
        out = []
        for text, enc in parts:
            if isinstance(text, bytes):
                out.append(text.decode(enc or "utf-8", errors="replace"))
            else:
                out.append(str(text))
        return "".join(out)
    except Exception:
        return str(val)


def _clean_ascii(text: str) -> str:
    """Sanitize Unicode into standard ASCII for retro screens."""
    if not text:
        return ""
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2014": "--",
        "\u2013": "-",
        "\u2026": "...",
        "\u00b0": " deg",
        "\u2022": "*",
        "\t": "    ",
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return text.encode("ascii", errors="replace").decode("ascii")


class MailManager:
    """Manages both Integrated Hub Mail and External Internet Email."""

    def __init__(self, mail_dir: pathlib.Path, bus=None, session=None):
        self.mail_dir = pathlib.Path(mail_dir)
        self.mail_dir.mkdir(parents=True, exist_ok=True)
        self.hub_mail_path = self.mail_dir / "hub_mail.json"
        self.config_path = self.mail_dir / "mail_config.json"
        self.bus = bus
        self.session = session
        self._ensure_files()

    def _ensure_files(self):
        if not self.hub_mail_path.exists():
            # Seed with a welcome message from the Hub Sysop
            initial_mail = [
                {
                    "id": 1,
                    "from": "Hub System [Local]",
                    "to": "ALL",
                    "subject": "Welcome to Retro Serial Hub Mail!",
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "body": (
                        "Welcome to the integrated electronic mail service.\r\n"
                        "Messages sent here are shared between all connected vintage\r\n"
                        "computers and host users. You can also configure external\r\n"
                        "IMAP/SMTP internet email at any time from the Mail menu."
                    ),
                    "read": False,
                }
            ]
            try:
                with open(self.hub_mail_path, "w", encoding="utf-8") as f:
                    json.dump(initial_mail, f, indent=2)
            except Exception:
                pass

        if not self.config_path.exists():
            default_config = {
                "default_mode": "hub",
                "smtp_host": "",
                "smtp_port": 587,
                "smtp_user": "",
                "smtp_pass": "",
                "smtp_tls": True,
                "smtp_ssl": False,
                "from_addr": "",
                "imap_host": "",
                "imap_port": 993,
                "imap_user": "",
                "imap_pass": "",
                "imap_ssl": True,
            }
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
            except Exception:
                pass

    def get_config(self) -> dict:
        self._ensure_files()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"default_mode": "hub"}

    def save_config(self, cfg: dict):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def get_mode(self) -> str:
        return self.get_config().get("default_mode", "hub")

    def toggle_mode(self) -> str:
        cur = self.get_mode()
        new_mode = "internet" if cur == "hub" else "hub"
        cfg = self.get_config()
        cfg["default_mode"] = new_mode
        self.save_config(cfg)
        return new_mode

    # ---------------- Integrated Hub Mail ----------------

    def get_sender_identity(self) -> str:
        """Derive origin machine and connection type from session."""
        if not self.session:
            return "Terminal [Unknown]"
        user = getattr(self.session, "user", None) or "User"
        ctype = getattr(self.session, "client_type", None) or "Client"
        if ctype.lower() == "serial":
            return f"{user} [Serial]"
        elif ctype.lower() == "telnet":
            return f"{user} [Telnet]"
        return f"{user} [{ctype}]"

    def get_hub_messages(self) -> List[dict]:
        self._ensure_files()
        try:
            with open(self.hub_mail_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def get_hub_message(self, mid: int, mark_read: bool = True) -> Optional[dict]:
        msgs = self.get_hub_messages()
        for m in msgs:
            if m.get("id") == mid:
                if mark_read and not m.get("read"):
                    m["read"] = True
                    try:
                        with open(self.hub_mail_path, "w", encoding="utf-8") as f:
                            json.dump(msgs, f, indent=2)
                    except Exception:
                        pass
                return m
        return None

    def send_hub_message(self, to: str, subject: str, body: str, sender: Optional[str] = None) -> dict:
        msgs = self.get_hub_messages()
        next_id = max((m.get("id", 0) for m in msgs), default=0) + 1
        snd = sender or self.get_sender_identity()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        new_msg = {
            "id": next_id,
            "from": snd,
            "to": to or "ALL",
            "subject": subject or "(No Subject)",
            "date": now_str,
            "body": body,
            "read": False,
        }
        msgs.append(new_msg)
        try:
            with open(self.hub_mail_path, "w", encoding="utf-8") as f:
                json.dump(msgs, f, indent=2)
        except Exception:
            pass

        if self.bus:
            self.bus.publish("notify", {
                "sender": snd,
                "message": f"New Hub Mail #{next_id} from {snd}: {subject}",
            })
        return new_msg

    def delete_hub_message(self, mid: int) -> bool:
        msgs = self.get_hub_messages()
        new_msgs = [m for m in msgs if m.get("id") != mid]
        if len(new_msgs) < len(msgs):
            try:
                with open(self.hub_mail_path, "w", encoding="utf-8") as f:
                    json.dump(new_msgs, f, indent=2)
                return True
            except Exception:
                pass
        return False

    def format_hub_inbox(self, columns: int = 80) -> str:
        msgs = self.get_hub_messages()
        if not msgs:
            return "No messages in Integrated Hub Mailbox."

        lines = []
        if columns == 40:
            lines.append("=== INTEGRATED HUB MAIL ===")
            for m in msgs:
                unread = "*" if not m.get("read") else " "
                mid = m.get("id")
                date = m.get("date", "")[:10]
                lines.append(f"[{mid}]{unread} {date} {m.get('subject', '')[:25]}")
                lines.append(f"    From: {m.get('from', '')[:30]}")
        else:
            lines.append("======================== INTEGRATED HUB MAILBOX ========================")
            lines.append(f"{'#':<3} {'Date':<16} {'From':<26} {'Subject'}")
            lines.append("-" * 72)
            for m in msgs:
                unread = "*" if not m.get("read") else " "
                mid = f"{m.get('id')}{unread}"
                date = m.get("date", "")[:16]
                sender = m.get("from", "")[:24]
                subject = m.get("subject", "")[:26]
                lines.append(f"{mid:<3} {date:<16} {sender:<26} {subject}")
            lines.append("=" * 72)
            lines.append("(* denotes unread message)")
        return "\n".join(lines)

    def format_hub_message(self, msg: Any, columns: int = 80) -> str:
        if isinstance(msg, (int, str)):
            try:
                mid = int(msg)
                found = self.get_hub_message(mid, mark_read=True)
                if not found:
                    return f"Hub message #{mid} not found."
                msg = found
            except ValueError:
                return f"Invalid message identifier: {msg}"
        if not isinstance(msg, dict):
            return "Invalid message."
        lines = []
        sep = "=" * (columns - 1)
        lines.append(sep)
        lines.append(f"Message ID: {msg.get('id')}")
        lines.append(f"Date:       {msg.get('date')}")
        lines.append(f"From:       {msg.get('from')}")
        lines.append(f"To:         {msg.get('to')}")
        lines.append(f"Subject:    {msg.get('subject')}")
        lines.append("-" * (columns - 1))
        body = msg.get("body", "")
        for line in body.splitlines():
            lines.append(line)
        lines.append(sep)
        return "\n".join(lines)

    # ---------------- External Internet Email (IMAP/SMTP) ----------------

    def is_internet_configured(self) -> bool:
        cfg = self.get_config()
        return bool(cfg.get("imap_host") and cfg.get("imap_user"))

    def get_internet_inbox(self, count: int = 10, columns: int = 80) -> Tuple[bool, str]:
        cfg = self.get_config()
        host = cfg.get("imap_host")
        user = cfg.get("imap_user")
        pwd = cfg.get("imap_pass")
        port = int(cfg.get("imap_port", 993))
        use_ssl = cfg.get("imap_ssl", True)

        if not host or not user:
            return False, (
                "Internet email is not configured.\n"
                "Use [7] Configure Email to set up your IMAP/SMTP server,\n"
                "or switch to [Integrated Hub Mail] to exchange messages locally."
            )

        try:
            if use_ssl:
                server = imaplib.IMAP4_SSL(host, port, timeout=10)
            else:
                server = imaplib.IMAP4(host, port, timeout=10)
            server.login(user, pwd)
            server.select("INBOX", readonly=True)

            status, msg_nums = server.search(None, "ALL")
            if status != "OK" or not msg_nums or not msg_nums[0]:
                server.logout()
                return True, "Internet Inbox is empty (0 messages)."

            num_list = msg_nums[0].split()
            latest_nums = num_list[-count:]
            latest_nums.reverse()

            lines = []
            if columns == 40:
                lines.append(f"=== INBOX: {user[:25]} ===")
                for seq_id in latest_nums:
                    sid = seq_id.decode()
                    res, data = server.fetch(seq_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                    if res == "OK" and data and isinstance(data[0], tuple):
                        hdr_msg = email.message_from_bytes(data[0][1])
                        subj = _clean_ascii(_decode_header_str(hdr_msg.get("Subject", "(No Subject)")))
                        from_hdr = _clean_ascii(_decode_header_str(hdr_msg.get("From", "Unknown")))
                        date_hdr = hdr_msg.get("Date", "")[:10]
                        lines.append(f"[{sid}] {date_hdr} {subj[:25]}")
                        lines.append(f"    From: {from_hdr[:30]}")
            else:
                lines.append(f"================ INBOX: {user} ================")
                lines.append(f"{'ID':<4} {'Date':<16} {'From':<24} {'Subject'}")
                lines.append("-" * 72)
                for seq_id in latest_nums:
                    sid = seq_id.decode()
                    res, data = server.fetch(seq_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                    if res == "OK" and data and isinstance(data[0], tuple):
                        hdr_msg = email.message_from_bytes(data[0][1])
                        subj = _clean_ascii(_decode_header_str(hdr_msg.get("Subject", "(No Subject)")))[:28]
                        from_hdr = _clean_ascii(_decode_header_str(hdr_msg.get("From", "Unknown")))[:22]
                        date_hdr = hdr_msg.get("Date", "")[:16]
                        lines.append(f"{sid:<4} {date_hdr:<16} {from_hdr:<24} {subj}")
                lines.append("=" * 72)

            server.logout()
            return True, "\n".join(lines)
        except Exception as exc:
            return False, f"IMAP Error: {exc}"

    def read_internet_message(self, msg_id: str, columns: int = 80) -> Tuple[bool, str]:
        cfg = self.get_config()
        host = cfg.get("imap_host")
        user = cfg.get("imap_user")
        pwd = cfg.get("imap_pass")
        port = int(cfg.get("imap_port", 993))
        use_ssl = cfg.get("imap_ssl", True)

        if not host or not user:
            return False, "Internet email not configured."

        try:
            if use_ssl:
                server = imaplib.IMAP4_SSL(host, port, timeout=10)
            else:
                server = imaplib.IMAP4(host, port, timeout=10)
            server.login(user, pwd)
            server.select("INBOX", readonly=True)

            res, data = server.fetch(str(msg_id).encode(), "(RFC822)")
            if res != "OK" or not data or not isinstance(data[0], tuple):
                server.logout()
                return False, f"Message ID {msg_id} not found."

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email, policy=email.policy.default)
            server.logout()

            subject = _clean_ascii(_decode_header_str(msg.get("Subject", "")))
            from_h = _clean_ascii(_decode_header_str(msg.get("From", "")))
            to_h = _clean_ascii(_decode_header_str(msg.get("To", "")))
            date_h = msg.get("Date", "")

            body_content = ""
            try:
                body_part = msg.get_body(preferencelist=("plain",))
                if body_part:
                    body_content = body_part.get_content()
                else:
                    html_part = msg.get_body(preferencelist=("html",))
                    if html_part:
                        import re
                        raw_h = html_part.get_content()
                        body_content = re.sub(r"<[^>]+>", "", raw_h)
                    else:
                        body_content = "(No readable text body found.)"
            except Exception:
                body_content = "(Could not decode message content.)"

            body_content = _clean_ascii(body_content)

            lines = []
            sep = "=" * (columns - 1)
            lines.append(sep)
            lines.append(f"Message ID: {msg_id}")
            lines.append(f"Date:       {date_h}")
            lines.append(f"From:       {from_h}")
            lines.append(f"To:         {to_h}")
            lines.append(f"Subject:    {subject}")
            lines.append("-" * (columns - 1))
            for b_line in body_content.splitlines():
                lines.append(b_line)
            lines.append(sep)
            return True, "\n".join(lines)
        except Exception as exc:
            return False, f"Error reading email: {exc}"

    def send_internet_email(self, to_addr: str, subject: str, body: str) -> Tuple[bool, str]:
        cfg = self.get_config()
        host = cfg.get("smtp_host")
        port = int(cfg.get("smtp_port", 587))
        user = cfg.get("smtp_user")
        pwd = cfg.get("smtp_pass")
        from_addr = cfg.get("from_addr") or user
        use_tls = cfg.get("smtp_tls", True)

        if not host or not user:
            return False, "SMTP is not configured. Use [7] Configure Email."

        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to_addr
            msg.set_content(body)

            with smtplib.SMTP(host, port, timeout=10) as s:
                if use_tls:
                    s.starttls()
                if user and pwd:
                    s.login(user, pwd)
                s.send_message(msg)

            return True, f"Email sent successfully to {to_addr}."
        except Exception as exc:
            return False, f"SMTP send error: {exc}"

    def launch_host_gui_auth(self) -> Tuple[bool, str]:
        """Launch the Tkinter GUI setup window on the host PC desktop."""
        try:
            cmd = [sys.executable, "-m", "retro_os.mail_gui", str(self.config_path)]
            subprocess.Popen(cmd)
            return True, "Opened email configuration window on the host desktop."
        except Exception as exc:
            return False, f"Could not launch host setup window: {exc}"
