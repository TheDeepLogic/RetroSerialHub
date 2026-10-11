"""Colorized, live console dashboard for hub runtime status."""

from collections import deque
import os
import shutil
import sys
import threading
import time

VERSION = "1.5"


class ConsoleDashboard:
    def __init__(self, profiles, refresh_interval=1.0):
        self.profiles = profiles
        self.refresh_interval = refresh_interval
        self._lock = threading.RLock()
        self._events = deque(maxlen=4)
        self._clients = {}
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

    def _paint(self, text, color):
        if not self._color:
            return text
        colors = {
            "info": "\x1b[36m",
            "green": "\x1b[32m",
            "yellow": "\x1b[33m",
            "red": "\x1b[31m",
            "cyan": "\x1b[36m",
            "dim": "\x1b[2m",
            "bold": "\x1b[1m",
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
            client = self._clients.pop(client_id, None)
            if self._tty and self._running:
                self._draw_frame()
            elif not self._tty and client:
                name, _ = client
                self._print_profile(name)
                self._print_status_line()

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
        for message, level in self._events:
            rows.append((f"Event: {message}", level))
        while len(rows) < len(self.profiles) + 6:
            rows.append(("", ""))
        width = max(40, shutil.get_terminal_size(fallback=(120, 24)).columns - 1)
        return [
            self._paint(row[:width], color) if color else row[:width]
            for row, color in rows
        ]

    def _draw_frame(self):
        rows = self._frame()
        if self._frame_lines:
            sys.stdout.write(f"\x1b[{self._frame_lines}A")
        for row in rows:
            sys.stdout.write("\r\x1b[2K" + row + "\r\n")
        sys.stdout.flush()
        self._frame_lines = len(rows)

    def _refresh_loop(self):
        while self._running:
            time.sleep(self.refresh_interval)
            with self._lock:
                if self._running:
                    self._draw_frame()
