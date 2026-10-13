"""Colorized, live console dashboard for hub runtime status."""

from collections import deque
import os
import re
import shutil
import sys
import threading
import time

_ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

VERSION = "2.2"

MENU_SECTIONS = [
    (
        "1",
        "COMMUNICATIONS",
        [
            ("A", "Bulletin Boards", "BBS", "bbs"),
            ("B", "Telnet Terminal", "Telnet", "telnet"),
            ("C", "Web Browser", "Browser", "browser"),
            ("D", "FTP Client", "FTP", "ftp"),
            ("E", "Electronic Mail", "Mail", "mail"),
        ],
    ),
    (
        "2",
        "HOST CONNECTIVITY",
        [
            ("A", "Host Applications", "Apps", "apps"),
            ("B", "Launch Host App", "Launch", "launch"),
            ("C", "Keyboard Bridge", "Keyboard", "keyboard"),
            ("D", "COM Port Bridge", "COM Bridge", "com_bridge"),
            ("E", "Host Terminal", "Terminal", "host_terminal"),
            ("F", "Sys Monitor & Media", "Sys/Media", "host_media"),
        ],
    ),
    (
        "3",
        "FILES & MEDIA",
        [
            ("A", "File Transfers", "Transfers", "files"),
            ("B", "Document Viewer", "Viewer", "view"),
            ("C", "Text Library", "TextLib", "text"),
            ("D", "ASCII Image Viewer", "ASCII Art", "ascii_viewer"),
        ],
    ),
    (
        "4",
        "GAMES",
        [
            ("A", "Minesweeper", "Mines", "mines"),
            ("B", "Solitaire", "Solitaire", "solitaire"),
            ("C", "WarGames (W.O.P.R.)", "WarGames", "wargames"),
        ],
    ),
    (
        "5",
        "ACCESSORIES",
        [
            ("A", "Notepad (Notes)", "Notes", "notes"),
            ("B", "Calculator", "Calculator", "calc"),
            ("C", "Live Weather & News", "Weather/News", "weather_news"),
            ("D", "AI Assistant", "AI Chat", "ai"),
            ("E", "Host Printing", "Print", "print"),
        ],
    ),
    (
        "6",
        "SYSTEM",
        [
            ("A", "Command Shell (CLI)", "Shell (CLI)", "cli"),
            ("B", "Task Scheduler", "Scheduler", "scheduler"),
            ("C", "Terminal Settings", "Settings", "terminal_settings"),
            ("D", "Keyboard Profiles", "KB Profiles", "kb"),
            ("E", "Help & User Guide", "Help/Guide", "help_menu"),
            ("F", "Welcome Banner", "Banner", "welcome_banner"),
        ],
    ),
]

ACTION_ALIASES = {
    "menu": "menu",
    "main_menu": "menu",
    "shortcuts": "shortcuts",
    "shortcut": "shortcuts",
    "shortcut_add": "shortcuts",
    "shortcut_del": "shortcuts",
    "bbs": "bbs",
    "telnet": "telnet",
    "browser": "browser",
    "web": "browser",
    "ftp": "ftp",
    "mail": "mail",
    "email": "mail",
    "mailto": "mail",
    "apps": "apps",
    "launch": "launch",
    "keyboard": "keyboard",
    "kb_bridge": "keyboard",
    "com_bridge": "com_bridge",
    "bridge": "com_bridge",
    "host_terminal": "host_terminal",
    "terminal": "host_terminal",
    "cmd": "host_terminal",
    "hostcmd": "host_terminal",
    "hostsh": "host_terminal",
    "host_media": "host_media",
    "media": "host_media",
    "vol": "host_media",
    "volume": "host_media",
    "sysinfo": "host_media",
    "sys": "host_media",
    "top": "host_media",
    "files": "files",
    "direct_transfer": "files",
    "xsend": "files",
    "ysend": "files",
    "asend": "files",
    "xrecv": "files",
    "view": "view",
    "text": "text",
    "textlib": "text",
    "library": "text",
    "ascii_viewer": "ascii_viewer",
    "ascii": "ascii_viewer",
    "mines": "mines",
    "minesweeper": "mines",
    "solitaire": "solitaire",
    "sol": "solitaire",
    "wargames": "wargames",
    "games": "wargames",
    "notes": "notes",
    "calc": "calc",
    "calculator": "calc",
    "weather_news": "weather_news",
    "weather": "weather_news",
    "news": "weather_news",
    "briefing": "weather_news",
    "ai": "ai",
    "chat": "ai",
    "print": "print",
    "printer": "print",
    "cli": "cli",
    "shell": "cli",
    "os": "cli",
    "scheduler": "scheduler",
    "schedule": "scheduler",
    "tasks": "scheduler",
    "cron": "scheduler",
    "terminal_settings": "terminal_settings",
    "columns": "terminal_settings",
    "translate_ansi": "terminal_settings",
    "caps": "terminal_settings",
    "pace": "terminal_settings",
    "kb": "kb",
    "help_menu": "help_menu",
    "help": "help_menu",
    "welcome_banner": "welcome_banner",
    "disconnect": "disconnect",
}


def normalize_action(action):
    if not action:
        return "menu"
    act = str(action).strip().lower()
    if act in ("0", "1", "2", "3", "4", "5", "6"):
        return f"section:{act}"
    if act.startswith("section:"):
        sec_num = act.split(":", 1)[1].strip()
        if sec_num in ("0", "1", "2", "3", "4", "5", "6"):
            return f"section:{sec_num}"
    if act.startswith("section_"):
        sec_num = act.split("_", 1)[1].strip()
        if sec_num in ("0", "1", "2", "3", "4", "5", "6"):
            return f"section:{sec_num}"
    if act.startswith("sec_"):
        sec_num = act.split("_", 1)[1].strip()
        if sec_num in ("0", "1", "2", "3", "4", "5", "6"):
            return f"section:{sec_num}"
    if act in ("main_menu", "root", "home"):
        return "section:0"
    if act.startswith("shortcut_run:"):
        sub = act.split(":", 1)[1].strip()
        cmd0 = sub.split()[0] if sub else ""
        return ACTION_ALIASES.get(cmd0, "shortcuts")
    return ACTION_ALIASES.get(act, act)


class ConsoleDashboard:
    normalize_action = staticmethod(normalize_action)
    def __init__(self, profiles, refresh_interval=1.0):
        self.profiles = profiles
        self.refresh_interval = refresh_interval
        self._lock = threading.RLock()
        self._events = deque(maxlen=4)
        self._clients = {}
        self._user_activities = {}
        self._running = False
        self._thread = None
        self._frame_lines = 0
        self._tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
        self._color = self._tty and "NO_COLOR" not in os.environ
        self._enable_windows_ansi()

    def _enable_windows_ansi(self):
        if os.name != "nt" or not self._tty:
            return
        try:
            import ctypes

            handle = ctypes.windll.kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint()
            if (
                ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode))
                and ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)
            ):
                return
            self._color = False
        except (AttributeError, OSError):
            self._color = False

    def _paint(self, text, color, force_color=False):
        if not self._color and not force_color:
            return text
        colors = {
            "info": "\x1b[36m",
            "green": "\x1b[32m",
            "yellow": "\x1b[33m",
            "red": "\x1b[31m",
            "cyan": "\x1b[36m",
            "dim": "\x1b[2m",
            "bold": "\x1b[1m",
            "highlight": "\x1b[1;32m",
            "active_header": "\x1b[1;33m",
            "reset": "\x1b[0m",
        }
        return f"{colors.get(color, '')}{text}{colors['reset'] if color in colors else ''}"

    def start(self):
        with self._lock:
            self._running = True
            if not self._tty:
                print(f"Retro Serial Hub v{VERSION}")
                for line in self._profile_lines():
                    print(line)
                self._print_status_line()
                return
            self._draw_frame()
            self._thread = threading.Thread(
                target=self._refresh_loop,
                name="console-dashboard",
                daemon=True,
            )
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
            if self._tty:
                sys.stdout.write("\r\n")
                sys.stdout.flush()

    def log(self, message, level="info"):
        with self._lock:
            if not self._tty:
                print(message)
                return
            self._events.append((str(message), level))
            self._draw_frame()

    def update_profile(self, name, *, serial=None, tcp=None):
        with self._lock:
            profile = self.profiles.get(name)
            if profile is None:
                return
            if serial is not None:
                profile["serial_status"] = serial
            if tcp is not None:
                profile["tcp_status"] = tcp
            if self._tty and self._running:
                self._draw_frame()
            elif not self._tty:
                status = self._profile_lines()
                for line in status:
                    if line.startswith(f"{name:<8} |"):
                        print(line)
                        break

    def add_client(self, client_id, name, address):
        with self._lock:
            self._clients[client_id] = (name, address)
            if self._tty and self._running:
                self._draw_frame()
            elif not self._tty:
                self._print_profile(name)
                self._print_status_line()

    def remove_client(self, client_id):
        with self._lock:
            self._user_activities.pop(client_id, None)
            client = self._clients.pop(client_id, None)
            if self._tty and self._running:
                self._draw_frame()
            elif not self._tty and client:
                name, _ = client
                self._print_profile(name)
                self._print_status_line()

    @staticmethod
    def _strip_ansi(text):
        return _ANSI_REGEX.sub("", text)

    def set_user_activity(self, user_id, action, user_label=None):
        with self._lock:
            if not user_label:
                client = self._clients.get(user_id)
                if client:
                    if isinstance(client, tuple):
                        name, addr = client
                        user_label = f"{name}@{addr[0]}" if addr else name
                    elif isinstance(client, dict):
                        user_label = client.get("label", client.get("profile", str(user_id)))
                    else:
                        user_label = str(client)
                else:
                    user_label = str(user_id)
            self._user_activities[user_id] = {
                "action": str(action) if action else "menu",
                "user": str(user_label),
            }
            if self._tty and self._running:
                self._draw_frame()

    def clear_user_activity(self, user_id):
        with self._lock:
            if user_id in self._user_activities:
                del self._user_activities[user_id]
                if self._tty and self._running:
                    self._draw_frame()

    def get_user_activities(self):
        with self._lock:
            return dict(self._user_activities)

    def _users_for_action(self, target_action):
        users = []
        target = normalize_action(target_action)
        for u_info in self._user_activities.values():
            act = normalize_action(u_info.get("action", ""))
            if act == target:
                users.append(u_info.get("user", u_info.get("name", "User")))
        return sorted(list(dict.fromkeys(users)))

    def _users_for_section(self, sec_num):
        users = []
        sec_targets = (f"section:{sec_num}", f"section_{sec_num}", f"sec_{sec_num}", str(sec_num))
        for u_info in self._user_activities.values():
            raw_act = str(u_info.get("action", "")).lower()
            act = normalize_action(raw_act)
            if act in sec_targets or act == f"section:{sec_num}":
                users.append(u_info.get("user", u_info.get("name", "User")))
        return sorted(list(dict.fromkeys(users)))

    def _make_user_tag(self, users, avail_space):
        if not users or avail_space <= 0:
            return ""
        full_tag = f" [{','.join(users)}]"
        if len(full_tag) <= avail_space:
            return full_tag
        short_tag = f" [{users[0]}+{len(users)-1}]"
        if len(short_tag) <= avail_space:
            return short_tag
        very_short = f" [*{len(users)}]"
        if len(very_short) <= avail_space:
            return very_short
        return ""

    def _format_cell(
        self,
        key,
        full_label,
        short_label,
        action,
        col_width,
        is_sec=False,
        sec_num=None,
        force_color=False,
    ):
        if is_sec:
            users = self._users_for_section(sec_num)
        else:
            users = self._users_for_action(action)
        is_active = len(users) > 0
        prefix = "*[" if is_active else " ["
        if is_sec:
            tag = self._make_user_tag(users, col_width - len(prefix) - len(sec_num) - 2)
            avail = col_width - len(prefix) - len(sec_num) - 2 - len(tag)
            name = full_label[:avail].rstrip() if len(full_label) > avail and avail > 2 else full_label
            raw_txt = f"{prefix}{sec_num}] {name}{tag}"
            color = "active_header" if is_active else "cyan"
        else:
            label = full_label if col_width >= 30 else short_label
            tag = self._make_user_tag(users, col_width - len(prefix) - len(key) - 2)
            avail = col_width - len(prefix) - len(key) - 2 - len(tag)
            name = label[:avail].rstrip() if len(label) > avail and avail > 2 else label
            raw_txt = f"{prefix}{key}] {name}{tag}"
            color = "highlight" if is_active else None
        raw_cell = raw_txt[:col_width].ljust(col_width)
        colored_cell = self._paint(raw_cell, color, force_color=force_color) if color else raw_cell
        return raw_cell, colored_cell

    def _interface_rows(self, width=None, force_color=False):
        if width is None:
            width = max(40, shutil.get_terminal_size(fallback=(120, 24)).columns - 1)
        box_width = max(40, min(width, 118))
        inner_width = box_width - 4

        rows = []
        title = " Retro Serial Hub Interface "
        if box_width < len(title) + 6:
            title = " RSH Menu "
        dash_len = max(0, box_width - 2 - len(title))
        left_dash = 2
        right_dash = max(0, dash_len - left_dash)
        top_border = "+" + ("-" * left_dash) + title + ("-" * right_dash) + "+"
        rows.append((self._paint(top_border, "dim", force_color=force_color), "raw"))

        # Main Menu row
        mm_users = self._users_for_action("menu") + self._users_for_action("shortcuts")
        mm_users = sorted(list(dict.fromkeys(mm_users)))
        mm_active = len(mm_users) > 0
        mm_tag = self._make_user_tag(mm_users, inner_width - 28)
        mm_pfx = "*[0] " if mm_active else " [0] "
        mm_raw = f"{mm_pfx}MAIN MENU / SHORTCUTS{mm_tag}"
        mm_padded = mm_raw[:inner_width].ljust(inner_width)
        mm_colored = self._paint(mm_padded, "highlight" if mm_active else "bold", force_color=force_color)
        rows.append((self._paint("| ", "dim", force_color=force_color) + mm_colored + self._paint(" |", "dim", force_color=force_color), "raw"))

        if inner_width >= 70:
            col_width = (inner_width - 2) // 3
            # Top half: Sec 1, 2, 3
            sec1, sec2, sec3 = MENU_SECTIONS[0], MENU_SECTIONS[1], MENU_SECTIONS[2]
            h1_raw, h1 = self._format_cell("", sec1[1], sec1[1], "", col_width, True, sec1[0], force_color=force_color)
            h2_raw, h2 = self._format_cell("", sec2[1], sec2[1], "", col_width, True, sec2[0], force_color=force_color)
            h3_raw, h3 = self._format_cell("", sec3[1], sec3[1], "", col_width, True, sec3[0], force_color=force_color)
            top_line = f"{h1} {h2} {h3}"
            raw_len = len(h1_raw) + 1 + len(h2_raw) + 1 + len(h3_raw)
            pad = " " * max(0, inner_width - raw_len)
            rows.append((self._paint("| ", "dim", force_color=force_color) + top_line + pad + self._paint(" |", "dim", force_color=force_color), "raw"))

            max_top = max(len(sec1[2]), len(sec2[2]), len(sec3[2]))
            for i in range(max_top):
                c1_raw, c1 = self._format_cell(*sec1[2][i], col_width=col_width, force_color=force_color) if i < len(sec1[2]) else (" " * col_width, " " * col_width)
                c2_raw, c2 = self._format_cell(*sec2[2][i], col_width=col_width, force_color=force_color) if i < len(sec2[2]) else (" " * col_width, " " * col_width)
                c3_raw, c3 = self._format_cell(*sec3[2][i], col_width=col_width, force_color=force_color) if i < len(sec3[2]) else (" " * col_width, " " * col_width)
                row_raw_len = len(c1_raw) + 1 + len(c2_raw) + 1 + len(c3_raw)
                pad = " " * max(0, inner_width - row_raw_len)
                rows.append((self._paint("| ", "dim", force_color=force_color) + f"{c1} {c2} {c3}" + pad + self._paint(" |", "dim", force_color=force_color), "raw"))

            # Bottom half: Sec 4, 5, 6
            sec4, sec5, sec6 = MENU_SECTIONS[3], MENU_SECTIONS[4], MENU_SECTIONS[5]
            h4_raw, h4 = self._format_cell("", sec4[1], sec4[1], "", col_width, True, sec4[0], force_color=force_color)
            h5_raw, h5 = self._format_cell("", sec5[1], sec5[1], "", col_width, True, sec5[0], force_color=force_color)
            h6_raw, h6 = self._format_cell("", sec6[1], sec6[1], "", col_width, True, sec6[0], force_color=force_color)
            bot_line = f"{h4} {h5} {h6}"
            raw_len = len(h4_raw) + 1 + len(h5_raw) + 1 + len(h6_raw)
            pad = " " * max(0, inner_width - raw_len)
            rows.append((self._paint("| ", "dim", force_color=force_color) + bot_line + pad + self._paint(" |", "dim", force_color=force_color), "raw"))

            max_bot = max(len(sec4[2]), len(sec5[2]), len(sec6[2]))
            for i in range(max_bot):
                c4_raw, c4 = self._format_cell(*sec4[2][i], col_width=col_width, force_color=force_color) if i < len(sec4[2]) else (" " * col_width, " " * col_width)
                c5_raw, c5 = self._format_cell(*sec5[2][i], col_width=col_width, force_color=force_color) if i < len(sec5[2]) else (" " * col_width, " " * col_width)
                c6_raw, c6 = self._format_cell(*sec6[2][i], col_width=col_width, force_color=force_color) if i < len(sec6[2]) else (" " * col_width, " " * col_width)
                row_raw_len = len(c4_raw) + 1 + len(c5_raw) + 1 + len(c6_raw)
                pad = " " * max(0, inner_width - row_raw_len)
                rows.append((self._paint("| ", "dim", force_color=force_color) + f"{c4} {c5} {c6}" + pad + self._paint(" |", "dim", force_color=force_color), "raw"))

        elif inner_width >= 46:
            col_width = (inner_width - 1) // 2
            col0_cells = []
            for s_idx in (0, 2, 4):
                sec = MENU_SECTIONS[s_idx]
                col0_cells.append(self._format_cell("", sec[1], sec[1], "", col_width, True, sec[0], force_color=force_color))
                for it in sec[2]:
                    col0_cells.append(self._format_cell(*it, col_width=col_width, force_color=force_color))
            col1_cells = []
            for s_idx in (1, 3, 5):
                sec = MENU_SECTIONS[s_idx]
                col1_cells.append(self._format_cell("", sec[1], sec[1], "", col_width, True, sec[0], force_color=force_color))
                for it in sec[2]:
                    col1_cells.append(self._format_cell(*it, col_width=col_width, force_color=force_color))
            max_rows = max(len(col0_cells), len(col1_cells))
            for i in range(max_rows):
                c0_raw, c0 = col0_cells[i] if i < len(col0_cells) else (" " * col_width, " " * col_width)
                c1_raw, c1 = col1_cells[i] if i < len(col1_cells) else (" " * col_width, " " * col_width)
                row_raw_len = len(c0_raw) + 1 + len(c1_raw)
                pad = " " * max(0, inner_width - row_raw_len)
                rows.append((self._paint("| ", "dim", force_color=force_color) + f"{c0} {c1}" + pad + self._paint(" |", "dim", force_color=force_color), "raw"))
        else:
            col_width = inner_width
            for sec in MENU_SECTIONS:
                h_raw, h = self._format_cell("", sec[1], sec[1], "", col_width, True, sec[0], force_color=force_color)
                pad = " " * max(0, inner_width - len(h_raw))
                rows.append((self._paint("| ", "dim", force_color=force_color) + h + pad + self._paint(" |", "dim", force_color=force_color), "raw"))
                for it in sec[2]:
                    c_raw, c = self._format_cell(*it, col_width=col_width, force_color=force_color)
                    pad = " " * max(0, inner_width - len(c_raw))
                    rows.append((self._paint("| ", "dim", force_color=force_color) + c + pad + self._paint(" |", "dim", force_color=force_color), "raw"))

        bot_border = "+" + ("-" * (box_width - 2)) + "+"
        rows.append((self._paint(bot_border, "dim", force_color=force_color), "raw"))
        return rows

    def render_interface(self, width=None, inner_width=None, use_color=None):
        with self._lock:
            target_width = inner_width if inner_width is not None else width
            force_color = bool(use_color) if use_color is not None else self._color
            rows = self._interface_rows(width=target_width, force_color=force_color)
            result = []
            for r, _ in rows:
                if use_color is False:
                    result.append(self._strip_ansi(r))
                elif use_color is True:
                    result.append(r)
                else:
                    result.append(r if self._color else self._strip_ansi(r))
            return result

    def _print_profile(self, name):
        prefix = f"{name:<8} |"
        for line in self._profile_lines():
            if line.startswith(prefix):
                print(line)
                break

    def _status_color(self, status):
        if status in ("OPEN", "LISTENING"):
            return "green"
        if status in ("MISSING", "ERROR", "DISABLED"):
            return "red" if status != "DISABLED" else "dim"
        return "yellow"

    def _profile_lines(self):
        lines = []
        for name, profile in self.profiles.items():
            serial_status = profile.get("serial_status", "STARTING")
            tcp_status = profile.get("tcp_status", "DISABLED")
            port = profile.get("tcp_port")
            client_count = sum(
                client_name == name
                for client_name, _ in self._clients.values()
            )
            serial_label = f"Serial {profile.get('serial_port', '—')}: {serial_status}"
            if profile.get("baud"):
                serial_label += f" {profile['baud']}"
            tcp_label = (
                f"TCP {port}: {tcp_status} ({client_count})"
                if port
                else "TCP: DISABLED"
            )
            endpoint = profile.get("endpoint")
            line = f"{name:<8} | {serial_label} | {tcp_label}"
            if endpoint:
                line += f" | Connect {endpoint}"
            lines.append(line)
        return lines

    def _status_line(self):
        total_clients = len(self._clients)
        open_serial = sum(
            profile.get("serial_status") == "OPEN"
            for profile in self.profiles.values()
        )
        total_sessions = open_serial + total_clients
        return (
            f"Live | Serial ports open: {open_serial} | "
            f"Telnet clients: {total_clients} | Active connections: {total_sessions}"
        )

    def _print_status_line(self):
        status = self._status_line()
        print(self._paint(status, "cyan"))

    def _frame(self):
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        rows = [(f"Retro Serial Hub v{VERSION}  |  {now}", "bold")]
        rows.extend(
            (
                line,
                self._status_color(
                    self.profiles[name].get("serial_status", "STARTING")
                ),
            )
            for name, line in zip(self.profiles, self._profile_lines())
        )
        rows.append((self._status_line(), "cyan"))
        rows.extend(self._interface_rows())
        for message, level in self._events:
            rows.append((f"Event: {message}", level))
        width = max(40, shutil.get_terminal_size(fallback=(120, 24)).columns - 1)
        final_rows = []
        for row, color in rows:
            if color == "raw":
                final_rows.append(row)
            else:
                visible = row[:width]
                final_rows.append(self._paint(visible, color) if color else visible)
        return final_rows

    def _draw_frame(self):
        rows = self._frame()
        if self._frame_lines:
            sys.stdout.write(f"\x1b[{self._frame_lines}A")
        for row in rows:
            sys.stdout.write("\r\x1b[2K" + row + "\r\n")
        if len(rows) < self._frame_lines:
            sys.stdout.write("\x1b[J")
        sys.stdout.flush()
        self._frame_lines = len(rows)

    def _refresh_loop(self):
        while self._running:
            time.sleep(self.refresh_interval)
            with self._lock:
                if self._running:
                    self._draw_frame()
