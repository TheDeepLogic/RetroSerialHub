"""Colorized, live console dashboard for hub runtime status."""

from collections import deque
from rsh_host_screen import HostScreen
from rsh_host_access import HostCommandAccess
from rsh_console_theme import ConsoleTheme, THEMES, THEME_ALIASES
import os
import re
import shutil
import sys
import threading
import textwrap
import time
import unicodedata

_ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

VERSION = "2.6"

from retro_os.menu_data import console_sections

MENU_SECTIONS = console_sections()

ACTION_ALIASES = {
    "calendar": "calendar", "cal": "calendar",
    "convert": "convert", "units": "convert",
    "contacts": "contacts", "addressbook": "contacts",
    "fileman": "fileman", "fm": "fileman",
    "archive": "archive", "zip": "archive",
    "audio": "audio", "player": "audio",
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
    "terminals": "terminals",
    "connected_terminals": "terminals",
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
    "lander": "lander",
    "lunarlander": "lander",
    "wumpus": "wumpus",
    "hunt": "wumpus",
    "blackjack": "blackjack",
    "21": "blackjack",
    "mastermind": "mastermind",
    "codebreaker": "mastermind",
    "wordguess": "wordguess",
    "wordle": "wordguess",
    "trek": "trek",
    "startrek": "trek",
    "star_trek": "trek",
    "wargames": "wargames",
    "wopr": "wargames",
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
    "host_settings": "host_settings",
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
    if act in ("0", "1", "2", "3", "4", "5", "6", "7"):
        return f"section:{act}"
    if act.startswith("section:"):
        sec_num = act.split(":", 1)[1].strip()
        if sec_num in ("0", "1", "2", "3", "4", "5", "6", "7"):
            return f"section:{sec_num}"
    if act.startswith("section_"):
        sec_num = act.split("_", 1)[1].strip()
        if sec_num in ("0", "1", "2", "3", "4", "5", "6", "7"):
            return f"section:{sec_num}"
    if act.startswith("sec_"):
        sec_num = act.split("_", 1)[1].strip()
        if sec_num in ("0", "1", "2", "3", "4", "5", "6", "7"):
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
    def __init__(self, profiles, refresh_interval=1.0, theme_path=None, host_access_path=None):
        self._theme = ConsoleTheme(theme_path)
        self._host_access = HostCommandAccess(host_access_path)
        self.profiles = profiles
        self.refresh_interval = refresh_interval
        self._lock = threading.RLock()
        self._events = deque(maxlen=4)
        self._clients = {}
        self._user_activities = {}
        self._activity_ports = {}
        self._running = False
        self._thread = None
        self._input_thread = None
        self._host_command = ""
        self._telnet_access = None
        self._host_terminal = None
        self._screen = HostScreen()
        self._host_output_offset = 0
        self._output_page_size = 8
        self._host_body_width = 80
        self._scrollback = None
        self._scrollback_top = (0, 0)
        self._scrollback_started_lines = 0
        self._console_message = []
        self._frame_cursor = None
        self._frame_input_rows = set()
        self._command_history = deque(maxlen=50)
        self._history_index = None
        self._history_draft = ""
        self._frame_lines = 0
        self._painted_rows = []
        self._painted_cursor = None
        self._painted_context = None
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
        if not self._theme.colors:
            return text
        return self._theme.ansi(color) + text + "\x1b[0m"

    def start(self):
        with self._lock:
            self._running = True
            if not self._tty:
                print(f"Retro Serial Hub v{VERSION}")
                for line in self._profile_lines():
                    print(line)
                self._print_status_line()
                return
            self._draw_frame(force=True)
            self._thread = threading.Thread(
                target=self._refresh_loop,
                name="console-dashboard",
                daemon=True,
            )
            self._thread.start()
            if (self._telnet_access is not None or self._host_terminal is not None) and self.host_input_available():
                self._input_thread = threading.Thread(
                    target=self._host_input_loop, name="host-console-input", daemon=True,
                )
                self._input_thread.start()

    def stop(self):
        with self._lock:
            self._running = False
        if self._input_thread is not None:
            self._input_thread.join(timeout=1)
        with self._lock:
            if self._tty:
                sys.stdout.write("\x1b[0m\x1b[?25h\r\n")
                sys.stdout.flush()
                self._painted_context = None

    def host_input_available(self):
        return self._tty and bool(getattr(sys.stdin, "isatty", lambda: False)())

    def set_telnet_access(self, access):
        self._telnet_access = access

    def set_host_terminal(self, terminal):
        self._host_terminal = terminal

    @property
    def _host_output(self):
        return [line.rstrip() for line in self._screen.lines[:self._screen.row]]

    @property
    def _host_output_line(self):
        return self._screen.lines[self._screen.row]

    @property
    def _host_output_column(self):
        return self._screen.column

    def append_host_output(self, data):
        """Interpret host screen controls inside an isolated, bounded screen."""
        text = data.decode("ascii", errors="replace") if isinstance(data, bytes) else str(data)
        with self._lock:
            rows = getattr(self._host_terminal, "_rsh_rows", None)
            columns = getattr(self._host_terminal, "_rsh_columns", None)
            if type(rows) is int and 16 <= rows <= 100:
                self._screen.height = rows
            if type(columns) is int and columns in (40, 80):
                self._screen.columns = columns
            generation = self._screen.generation
            self._screen.feed(text)
            if self._screen.generation != generation and self._scrollback is None:
                self._host_output_offset = 0
            if text:
                self._console_message = []

    def _reset_host_screen(self):
        self._screen.clear()
        self._resume_live()
        self._console_message = []

    def _resume_live(self):
        self._scrollback = None
        self._scrollback_top = (0, 0)
        self._host_output_offset = 0

    @property
    def _scrollback_new_lines(self):
        return max(0, self._screen.line_events - self._scrollback_started_lines) if self._scrollback is not None else 0

    def _host_body(self):
        if self._console_message:
            return list(self._console_message)
        if self._host_terminal is None:
            return []
        screen = self._screen
        after = list(screen.lines[screen.row + 1:])
        while after and not after[-1].strip():
            after.pop()
        body = [(line.rstrip(), None) for line in screen.lines[:screen.row] + after]
        footer = self._main_menu_footer()
        if footer:
            for index in range(len(body) - 2, -1, -1):
                if [body[index][0], body[index + 1][0]] == footer:
                    del body[index:index + 2]
                    break
            while body and not body[-1][0].strip():
                body.pop()
        return body

    def _main_menu_footer(self):
        """Only the real main-menu prompt opts into a pinned session footer."""
        footer = getattr(self._host_terminal, '_rsh_main_menu_footer', None)
        if (isinstance(footer, tuple) and len(footer) == 3
                and all(isinstance(line, str) for line in footer)
                and self._host_output_line == footer[2]):
            return [line.rstrip() for line in footer[:2]]
        return []

    @staticmethod
    def _wrap_host_body(body, width):
        wrapped, positions = [], []
        for index, (line, color) in enumerate(body):
            for column in range(0, max(1, len(line)), width):
                wrapped.append((line[column:column + width], color))
                positions.append((index, column))
        return wrapped, positions

    def _scrollback_index(self, positions):
        # Anchor to the source line and column, so a resize reflows the same text.
        return max((index for index, position in enumerate(positions)
                    if position <= self._scrollback_top), default=0)

    def _scroll_page(self, direction):
        page = self._output_page_size
        if self._scrollback is None:
            if direction > 0:
                return
            body = self._host_body()
            wrapped, positions = self._wrap_host_body(body, self._host_body_width)
            if not wrapped:
                return
            # Freeze bounded screen history, including rows that later screen
            # controls overwrite or evict. Live output and the prompt keep running.
            self._scrollback = body
            self._scrollback_started_lines = self._screen.line_events
            top = max(0, len(wrapped) - page)
        else:
            wrapped, positions = self._wrap_host_body(self._scrollback, self._host_body_width)
            top = self._scrollback_index(positions)
        top = max(0, top + direction * page)
        if direction > 0 and top >= max(0, len(wrapped) - page):
            self._resume_live()
            return
        top = min(top, len(positions) - 1)
        self._scrollback_top = positions[top]
        self._host_output_offset = max(0, len(wrapped) - top - page)

    def clear_host_output(self):
        with self._lock:
            prompt, column = self._host_output_line, self._host_output_column
            self._reset_host_screen()
            if self._host_terminal is not None:
                self._screen.lines = [prompt]
                self._screen.column = column

    def _host_special_key(self, action):
        with self._lock:
            if action == "end":
                self._resume_live()
            elif action in ("page_up", "page_down"):
                self._scroll_page(-1 if action == "page_up" else 1)
            elif action in ("history_up", "history_down") and self._command_history:
                if getattr(self._host_terminal, "secret_input", False) is True:
                    return
                history = list(self._command_history)
                if self._history_index is None:
                    self._history_draft = self._host_command
                    self._history_index = len(history)
                self._history_index = max(0, min(len(history), self._history_index + (-1 if action == "history_up" else 1)))
                self._host_command = history[self._history_index] if self._history_index < len(history) else self._history_draft
            if self._running and self._tty:
                self._draw_frame()

    def _theme_command(self, arguments, remote=False):
        if not self._can_input(remote):
            raise ValueError("Theme controls require the local interactive console.")
        names = list(THEMES)
        if not arguments or arguments == ["list"]:
            lines = ["Console color schemes (host only):"]
            lines.extend(f"  {index}. {name}" for index, name in enumerate(names, 1))
            lines.extend((f"Current: {self._theme.name}; backgrounds {'on' if self._theme.background else 'off'}; colors {'on' if self._theme.colors else 'off'}",
                          "theme <name or number> | theme background on/off | theme colors on/off"))
            self._console_message = [(line, None) for line in lines]
            return
        previous = (self._theme.name, self._theme.background, self._theme.colors)
        if arguments[0] in ("background", "backgrounds", "colors"):
            if len(arguments) != 2 or arguments[1] not in ("on", "off"):
                raise ValueError("Use theme background on/off or theme colors on/off.")
            key = "colors" if arguments[0] == "colors" else "background"
            setattr(self._theme, key, arguments[1] == "on")
        else:
            requested = " ".join(arguments)
            requested = THEME_ALIASES.get(requested, requested).casefold()
            name = next((name for name in names if name.casefold() == requested), None)
            if requested.isdigit() and 1 <= int(requested) <= len(names):
                name = names[int(requested) - 1]
            if name is None:
                raise ValueError("Unknown console scheme. Type theme to list available schemes.")
            self._theme.name = name
        try:
            self._theme.save()
        except OSError:
            self._theme.name, self._theme.background, self._theme.colors = previous
            raise
        self.log(f"Console theme: {self._theme.name}; backgrounds {'on' if self._theme.background else 'off'}; colors {'on' if self._theme.colors else 'off'}")

    def _can_input(self, remote=False):
        return (self._running and self._host_terminal is not None
                and getattr(self._host_terminal, "closed", False) is not True) if remote else self.host_input_available()

    def submit_remote_command(self, command, terminal):
        """Submit a complete line from a connected terminal without replacing a local draft."""
        with self._lock:
            if not self._can_input(True):
                return False, "Host console session is unavailable."
            try:
                allowed, message, new = self._host_access.request(terminal)
            except (OSError, ValueError) as exc:
                return False, f"Host control denied: {exc}"
            if not allowed:
                if new:
                    self.log(message)
                return False, message
            if self._host_command:
                return False, "Host input is being edited locally; try again after it is sent."
            secret = getattr(self._host_terminal, "secret_input", False) is True
            ok = self._dispatch_host_command(command, remote=True)
            if ok and command and not secret and (not self._command_history or self._command_history[-1] != command):
                self._command_history.append(command)
            return ok, "Sent to Host." if ok else self._command_error

    def handle_host_command(self, command):
        with self._lock:
            return self._dispatch_host_command(command)

    def _dispatch_host_command(self, command, remote=False):
        if self._telnet_access is None and self._host_terminal is None:
            self._command_error = "Host console session is unavailable."
            return False
        parts = command.strip().lower().split()
        self._resume_live()
        self._console_message = []
        try:
            if not self._can_input(remote):
                raise ValueError("Host commands require an available host console.")
            if getattr(self._host_terminal, "secret_input", False) is True:
                self._host_terminal.submit(command)
            elif parts in (["host", "help"], ["console", "help"]):
                self._console_message = [(line, None) for line in (
                    "HOST CONSOLE CONTROLS",
                    "Type directly at the active hub prompt; HELP is the hub's help.",
                    "host help / console help  Show these console controls",
                    "theme [name or number]    List or select console schemes",
                    "theme background on/off  Toggle panel backgrounds",
                    "theme colors on/off      Toggle all console colors",
                    "allow <#> / deny <#>      Answer incoming Telnet requests",
                    "allow host <#> / deny host <#>  Approve first HOST use by IP/port",
                    "pending                  List requests waiting for approval",
                    "clear                    Clear the host screen",
                    "PgUp/PgDn                Browse fixed scrollback; End returns live",
                    "Up/Down                  Recall previous input",
                    "ATM                      Return the host session to the main menu",
                    "From any hub terminal: HOST <text> submits a line to this session.")]
            elif parts and parts[0] == "theme":
                self._theme_command(parts[1:], remote=remote)
            elif parts == ["pending"]:
                pending = self._telnet_access.pending() if self._telnet_access is not None else []
                requests = [f"Telnet #{row['id']} {row['ip']} -> {row['profile']}" for row in pending]
                requests += [f"Host-control #{row['id']} {row['source']}" for row in self._host_access.pending()]
                self._console_message = [(line, None) for line in (requests or ["No approvals pending."])]
            elif len(parts) >= 2 and parts[0] in ("allow", "deny") and parts[1] == "host":
                if remote:
                    raise ValueError("Host-control approval must be typed at the local console.")
                if len(parts) != 3 or not parts[2].isdigit():
                    raise ValueError("Use allow host <request #> or deny host <request #>.")
                source = self._host_access.decide(int(parts[2]), parts[0] == "allow")
                self.log(f"Host control {'approved' if parts[0] == 'allow' else 'denied'} for {source}.", "green")
            elif parts and parts[0] in ("allow", "deny"):
                if self._telnet_access is None:
                    raise ValueError("Telnet listeners are disabled.")
                if len(parts) != 2 or not parts[1].isdigit():
                    raise ValueError("Use allow <request #> or deny <request #>.")
                getattr(self._telnet_access, parts[0])(int(parts[1]))
            elif parts and parts[0] == "monitor":
                self.log("The activity monitor always shows active selections. Use host help for console controls.")
            elif parts == ["clear"]:
                self.clear_host_output()
            elif self._host_terminal is not None:
                self._host_output_offset = 0
                self._host_terminal.submit(command)
            else:
                raise ValueError("No hub session is attached. Use host help for console controls.")
            self._command_error = ""
            return True
        except (OSError, ValueError) as exc:
            self._command_error = str(exc)
            self.log(f"Host command failed: {exc}", level="red")
            return False

    def _host_key(self, key):
        if key in ("\r", "\n"):
            with self._lock:
                command, self._host_command = self._host_command, ""
                if command and getattr(self._host_terminal, "secret_input", False) is not True and (not self._command_history or self._command_history[-1] != command):
                    self._command_history.append(command)
                self._history_index = None
            self.handle_host_command(command)
        elif key not in ("\x08", "\x7f") and len(key) == 1 and ord(key) < 32 and self._host_terminal is not None:
            try:
                self._host_terminal.send_key(key)
            except (OSError, ValueError) as exc:
                self.log(f"Host input failed: {exc}", level="red")
        else:
            with self._lock:
                if key in ("\x08", "\x7f"):
                    self._host_command = self._host_command[:-1]
                elif key.isascii() and key.isprintable() and len(self._host_command) < 1024:
                    self._host_command += key
        with self._lock:
            if self._running and self._tty:
                self._draw_frame()

    def _host_input_loop(self):
        try:
            if os.name == "nt":
                import msvcrt
                while self._running:
                    if not msvcrt.kbhit():
                        time.sleep(.05)
                        continue
                    key = msvcrt.getwch()
                    if key in ("\x00", "\xe0"):
                        action = {"H": "history_up", "P": "history_down", "I": "page_up", "Q": "page_down", "O": "end"}.get(msvcrt.getwch())
                        if action:
                            self._host_special_key(action)
                        continue
                    self._host_key(key)
            else:
                import select
                import termios
                import tty
                descriptor = sys.stdin.fileno()
                previous = termios.tcgetattr(descriptor)
                try:
                    tty.setcbreak(descriptor)
                    while self._running:
                        if select.select([descriptor], [], [], .1)[0]:
                            key = os.read(descriptor, 1)
                            if not key:
                                return
                            if key == b"\x1b":
                                while len(key) < 8 and select.select([descriptor], [], [], .02)[0]:
                                    key += os.read(descriptor, 1)
                                    if len(key) > 2 and (key[-1:] == b"~" or key[-1:].isalpha()):
                                        break
                                action = {b"\x1b[A": "history_up", b"\x1b[B": "history_down", b"\x1b[5~": "page_up", b"\x1b[6~": "page_down", b"\x1b[F": "end", b"\x1bOF": "end", b"\x1b[4~": "end", b"\x1b[8~": "end"}.get(key)
                                if action:
                                    self._host_special_key(action)
                                    continue
                            self._host_key(key.decode("ascii", errors="ignore"))
                finally:
                    termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)
        except (OSError, ValueError) as exc:
            self.log(f"Host console keyboard unavailable: {exc}", level="yellow")

    def log(self, message, level="info"):
        with self._lock:
            if not self._tty:
                print(message)
                return
            self._events.append((str(message), level))
            self._draw_frame()

    def update_profile(self, name, *, serial=None, tcp=None, terminal=None):
        with self._lock:
            profile = self.profiles.get(name)
            if profile is None:
                return
            if serial is not None:
                profile["serial_status"] = serial
                if serial == "OPEN":
                    profile["terminal_status"] = "WAITING"
                elif serial != "OPEN":
                    profile["terminal_status"] = "OFFLINE"
            if tcp is not None:
                profile["tcp_status"] = tcp
            if terminal is not None:
                profile["terminal_status"] = terminal
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
            self._activity_ports.pop(client_id, None)
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

    def _serial_activity_port(self, user_id, user_label=None):
        if user_id in self._clients:
            return None
        if user_id in self._activity_ports:
            return self._activity_ports[user_id]
        if isinstance(user_id,str) and user_id.lower().startswith('serial:'):
            profile=user_id.split(':',1)[1]
            return str(self.profiles.get(profile,{}).get('serial_port') or profile).strip().casefold()
        if user_label in self.profiles:
            port=self.profiles[user_label].get('serial_port')
            if port:
                return str(port).strip().casefold()
        return None

    def set_user_activity(self, user_id, action, user_label=None, serial_port=None):
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
            port=(str(serial_port).strip().casefold() if serial_port else self._serial_activity_port(user_id,user_label))
            if port is not None:
                for previous,activity in list(self._user_activities.items()):
                    previous_port=self._serial_activity_port(previous,activity.get('user'))
                    legacy_same_label=(previous_port is None and previous not in self._clients and activity.get('user') == str(user_label))
                    if previous != user_id and (previous_port == port or legacy_same_label):
                        self._user_activities.pop(previous,None)
                        self._activity_ports.pop(previous,None)
                self._activity_ports[user_id]=port
            self._user_activities[user_id] = {
                "action": str(action) if action else "menu",
                "user": str(user_label),
            }
            if self._tty and self._running:
                self._draw_frame()

    def clear_user_activity(self, user_id):
        with self._lock:
            self._activity_ports.pop(user_id,None)
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

    def _box_style(self, rows):
        if os.environ.get('RSH_ASCII_BORDERS') == '1':
            return rows
        try:
            '┌┐└┘─│'.encode(getattr(sys.stdout,'encoding',None) or 'utf-8')
        except (UnicodeError,LookupError):
            return rows
        styled=[]
        for index,(row,color) in enumerate(rows):
            plain=self._strip_ansi(row)
            if plain.startswith('+') and plain.endswith('+'):
                left,right=('┌','┐') if index == 0 else ('└','┘')
                row=row.replace('+',left,1)
                prefix,_,suffix=row.rpartition('+')
                row=(prefix+right+suffix).replace('-','─')
            elif plain.startswith('|-- ') and plain.endswith('|'):
                row=row.replace('|','├',1)
                prefix,_,suffix=row.rpartition('|')
                row=(prefix+'┤'+suffix).replace('-','─')
            elif plain.startswith('|') and plain.endswith('|'):
                row=row.replace('|','│',1)
                prefix,_,suffix=row.rpartition('|')
                row=prefix+'│'+suffix
            styled.append((row,color))
        return styled

    def _interface_rows(self, width=None, force_color=False):
        if width is None:
            width = max(40, shutil.get_terminal_size(fallback=(120, 24)).columns - 1)
        box_width = max(40, min(width, 118))
        inner_width = box_width - 5

        rows = []
        title = " Connected Terminal Activity Monitor "
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
        rows.append((self._paint("|  ", "dim", force_color=force_color) + mm_colored + self._paint(" |", "dim", force_color=force_color), "raw"))

        columns=4 if inner_width >= 100 else 3 if inner_width >= 70 else 2 if inner_width >= 46 else 1
        col_width=(inner_width-columns+1)//columns
        for start in range(0,len(MENU_SECTIONS),columns):
            group=MENU_SECTIONS[start:start+columns]
            def append_cells(cells):
                content=' '.join(cells)
                pad=' '*max(0,inner_width-len(self._strip_ansi(content)))
                rows.append((self._paint('|  ','dim',force_color=force_color)+content+pad+self._paint(' |','dim',force_color=force_color),'raw'))
            append_cells([self._format_cell('',section[1],section[1],'',col_width,True,section[0],force_color=force_color)[1] for section in group])
            for index in range(max(len(section[2]) for section in group)):
                append_cells([self._format_cell(*section[2][index],col_width,force_color=force_color)[1] if index<len(section[2]) else ' '*col_width for section in group])
            if start+columns < len(MENU_SECTIONS):
                append_cells([' '*col_width for _ in group])

        bot_border = "+" + ("-" * (box_width - 2)) + "+"
        rows.append((self._paint(bot_border, "dim", force_color=force_color), "raw"))
        return self._box_style(rows)

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
            terminal_status = profile.get("terminal_status")
            serial_label = f"Serial {profile.get('serial_port', '—')}: {serial_status}"
            if profile.get("baud"):
                serial_label += f" {profile['baud']}"
            if serial_status == "OPEN" and terminal_status == "ACTIVE":
                serial_label += f" | Terminal: {terminal_status}"
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
        active_serial = sum(
            profile.get("terminal_status") == "ACTIVE"
            for profile in self.profiles.values()
        )
        total_sessions = active_serial + total_clients
        return (
            f"Live | Serial ports open: {open_serial} | "
            f"Telnet clients: {total_clients} | Active connections: {total_sessions}"
        )

    def _print_status_line(self):
        status = self._status_line()
        print(self._paint(status, "cyan"))

    def _status_panel_rows(self, width, force_color=False):
        """Render profile and live-count status in a box matching the menu."""
        box_width = max(8, width)
        inner_width = box_width - 4
        title = " Serial & Network Status "
        top = "+--" + title + ("-" * max(0, box_width - len(title) - 4)) + "+"
        bottom = "+" + ("-" * (box_width - 2)) + "+"
        rows = [(self._paint(top, "dim", force_color=force_color), "raw")]

        connections = []
        for name, profile in self.profiles.items():
            client_count = sum(
                client_name == name
                for client_name, _ in self._clients.values()
            )
            is_active = profile.get("terminal_status") == "ACTIVE" or client_count > 0
            endpoint = profile.get("endpoint")
            serial_status = profile.get("serial_status", "STARTING")
            tcp_status = profile.get("tcp_status", "DISABLED")
            tcp_port = profile.get("tcp_port")
            serial = f"Serial {profile.get('serial_port', '—')}: {serial_status}"
            if profile.get("baud"):
                serial += f" {profile['baud']}"
            tcp = (
                f"TCP {tcp_port}: {tcp_status} ({client_count})"
                if tcp_port
                else "TCP: DISABLED"
            )
            transfer_detail=''
            from rsh_session import services
            for service in services():
                if getattr(service.terminal,'_profile_name',None)==name and service.progress:
                    progress=service.progress
                    transfer_detail=f" | {progress['direction']} {progress['bytes']}/{progress['total'] or '?'} B retries {progress['retries']}"
                    break
            if is_active:
                line = f"{name} | {serial} | {tcp}" + transfer_detail
                if endpoint:
                    line += f" | Connect {endpoint}"
                if client_count:
                    line += f" | Clients: {client_count}"
                connections.append((f"  {line}", "green"))
            else:
                line = f"{name} | {serial} | {tcp}"
                if endpoint:
                    line += f" | Connect {endpoint}"
                connections.append((f"  {line}", self._profile_status_color(name)))

        content = [(f"  {self._status_line()}", "cyan")]
        if connections:
            content.append(("Connections", "dim"))
            content.extend(connections)
        for line, color in content:
            if line == "Connections":
                divider_prefix = f"|-- {line} "
                divider = divider_prefix + ("-" * max(0, box_width - len(divider_prefix) - 1)) + "|"
                rows.append((self._paint(divider, "dim", force_color=force_color), "raw"))
                continue
            wrapped = textwrap.wrap(
                line,
                width=inner_width,
                subsequent_indent="  ",
                break_long_words=True,
                break_on_hyphens=False,
            ) or [""]
            for part in wrapped:
                padded = part.ljust(inner_width)
                border = self._paint("| ", "dim", force_color=force_color)
                end = self._paint(" |", "dim", force_color=force_color)
                value = self._paint(padded, color, force_color=force_color)
                rows.append((border + value + end, "raw"))
        rows.append((self._paint(bottom, "dim", force_color=force_color), "raw"))
        return self._box_style(rows)

    def _profile_status_color(self, name):
        profile = self.profiles[name]
        if (
            profile.get("serial_status") == "OPEN"
            and profile.get("terminal_status", "WAITING") == "WAITING"
        ):
            return "yellow"
        return self._status_color(profile.get("serial_status", "STARTING"))

    def _pane_rows(self, title, content, width):
        """One border and padding implementation for every dashboard pane."""
        inner = max(1, width - 2)
        heading = ("-- " + title + " ")[:inner]
        rows = [(self._paint("+" + heading.ljust(inner, "-") + "+", "dim"), "raw")]
        for text, color in content:
            clipped = self._clip_screen_row(text, inner)
            cells = sum(0 if unicodedata.combining(c) else
                        2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
                        for c in self._strip_ansi(clipped))
            padded = clipped + " " * max(0, inner - cells)
            value = self._paint(padded, color) if color and color != "raw" else padded
            rows.append((self._paint("|", "dim") + value
                         + self._paint("|", "dim"), "raw"))
        rows.append((self._paint("+" + "-" * inner + "+", "dim"), "raw"))
        return self._box_style(rows)

    def _active_monitor_rows(self, width, height=None):
        labels = {action: label for _, _, items in MENU_SECTIONS
                  for _, _, label, action in items}
        labels.update(menu="Main Menu", shortcuts="Shortcuts")
        groups = []
        for activity in self._user_activities.values():
            action = normalize_action(activity["action"])
            label = labels.get(action, action.replace("section:", "Section "))
            groups.append(textwrap.wrap(f"{activity['user']}: {label}", max(1, width - 4)))
        limit = max(1, height - 2) if height is not None else sum(map(len, groups)) + 1
        content = []
        truncated = sum(map(len, groups)) > limit
        shown = 0
        for group in groups:
            if len(content) + len(group) > limit - int(truncated):
                break
            content.extend((" " + line, "highlight") for line in group)
            shown += 1
        if shown < len(groups):
            content.append((f"+{len(groups) - shown} more active sessions", "yellow"))
        if not groups:
            content.append((" No active selections", "dim"))
        return self._pane_rows("Activity Monitor", content, width)

    def _priority_rows(self, width, budget):
        """Approvals and errors are allocated space before ordinary panels."""
        if budget <= 0:
            return []
        pending = self._telnet_access.pending() if self._telnet_access is not None else []
        errors = [(message, level) for message, level in self._events if level in ("red", "yellow")]
        requests = [(f"APPROVAL #{r['id']} {r['ip']} -> {r['profile']} ({r['seconds_left']}s)", "yellow", "approval")
                    for r in pending]
        host_requests = self._host_access.pending()
        requests = [(f"HOST APPROVAL #{r['id']} {r['source']} | allow host {r['id']} ({r['seconds_left']}s)", "yellow", "approval")
                    for r in host_requests] + requests
        pending_count = len(requests)
        failures = [(f"{'ERROR' if level == 'red' else 'NOTICE'}: {message}", level, "error")
                    for message, level in reversed(errors)]
        # Preserve the first request and the latest error before additional items.
        entries = requests[:1] + failures[:1] + requests[1:] + failures[1:]
        if len(entries) > budget:
            if budget == 1:
                entries = [(f"{pending_count} approvals | {len(errors)} errors/notices", "yellow", "summary")]
            else:
                shown = entries[:budget - 1]
                shown_requests = sum(kind == "approval" for _, _, kind in shown)
                shown_errors = sum(kind == "error" for _, _, kind in shown)
                entries = shown + [(f"+{pending_count-shown_requests} approvals; +{len(errors)-shown_errors} errors/notices", "yellow", "summary")]
        return [(self._paint(self._clip_screen_row(text, width), color), "raw", kind)
                for text, color, kind in entries]

    def _fit_status(self, width, height):
        if height <= 0:
            return []
        if height < 3 or width < 30:
            return [(self._paint(self._clip_screen_row(self._status_line(), width), "cyan"), "raw")]
        rows = self._status_panel_rows(width, force_color=self._color)
        if len(rows) > height:
            omitted = len(rows) - height + 1
            summary = self._pane_rows("", [(f"+{omitted} more status rows", "dim")], width)[1]
            rows = rows[:height - 2] + [summary, rows[-1]]
        return rows

    def _dashboard_rows(self, width, height, include_status=True):
        if height <= 0:
            return []
        priority = self._priority_rows(width, max(1, min(6, height - 5)))
        rows = [(text, color) for text, color, kind in priority if kind == "approval"]
        notices = [(text, color) for text, color, kind in priority if kind != "approval"]
        available = height - len(priority)
        if available >= 3:
            desired_activity = len(self._active_monitor_rows(width))
            activity_height = min(desired_activity, max(3, available // 3)) if include_status else available
            status_height = available - activity_height if include_status else 0
            if status_height and status_height < 3:
                activity_height, status_height = 3, available - 3
            rows += self._fit_status(width, status_height)
            rows += self._active_monitor_rows(width, activity_height)
        elif available:
            rows += self._fit_status(width, available) if include_status else []
        rows += notices
        for message, level in reversed(self._events):
            if len(rows) >= height:
                break
            if level not in ("red", "yellow"):
                rows.append((self._paint(self._clip_screen_row("Event: " + message, width), level), "raw"))
        return rows[:height]

    def _host_hints(self):
        hints = ["Host: allow host <#> / deny host <#> / pending"]
        if self._telnet_access is not None:
            hints.append("Telnet: allow <#> / deny <#>")
        hints.append("Hub: HELP | ATM | host help | theme | clear | PgUp/PgDn | End=Live | Up/Down")
        return hints

    def _host_pane(self, width, height):
        """Draw history and place the line editor at the actual session cursor."""
        bordered = width >= 4 and height >= 3
        border = int(bordered)
        inner = max(1, width - border * 2)
        input_width = min(inner, self._screen.columns) if self._host_terminal is not None else inner
        inner_height = max(1, height - border * 2)
        if self._host_terminal is not None:
            screen = self._screen
            prompt, position = screen.lines[screen.row], screen.column
        else:
            prompt, position = "Host> ", 6
        draft = self._host_command
        if getattr(self._host_terminal, "secret_input", False) is True:
            draft = "*" * len(draft)
        prompt = prompt.ljust(position)
        edited = prompt[:position] + draft + prompt[position + len(draft):]
        cursor = position + len(draft)
        cursor_line, cursor_column = divmod(cursor, input_width)
        prompt_lines = [edited[start:start + input_width] for start in range(0, len(edited), input_width)] or [""]
        while len(prompt_lines) <= cursor_line:
            prompt_lines.append("")
        hints = []
        for line in self._main_menu_footer():
            hints.extend((part, None) for part in (textwrap.wrap(line, inner) or [""]))
        if hints:
            hints.append(("", None))
        for hint in self._host_hints():
            hints.extend((part, "dim") for part in textwrap.wrap(hint, inner))
        # One blank row separates the control hints from the live input prompt.
        available_hints = max(0, inner_height - 1)
        if available_hints >= 2:
            hints = hints[:available_hints - 1] + [("", "dim")]
        else:
            hints = hints[:available_hints]
        if inner_height - len(hints) == 1 and cursor_line:
            # A one-line input region scrolls horizontally rather than hiding
            # most of a word on the previous wrapped line.
            offset = max(0, cursor - input_width + 1)
            prompt_lines = [edited[offset:offset + input_width]]
            cursor_line, cursor_column = 0, cursor - offset
        prompt_count = min(3, max(1, inner_height - len(hints)), cursor_line + 1)
        start = max(0, cursor_line - prompt_count + 1)
        visible_prompt = prompt_lines[start:cursor_line + 1]
        body_height = max(0, inner_height - len(hints) - len(visible_prompt))
        self._output_page_size = max(1, body_height)
        self._host_body_width = inner
        body = self._scrollback if self._scrollback is not None else self._host_body()
        wrapped, positions = self._wrap_host_body(body, inner)
        if self._scrollback is not None:
            top = self._scrollback_index(positions)
            self._host_output_offset = max(0, len(wrapped) - top - body_height)
        else:
            top = max(0, len(wrapped) - body_height)
            self._host_output_offset = 0
        visible = wrapped[top:top + body_height] if body_height else []
        content = visible + [("", None)] * (body_height - len(visible))
        content += hints
        input_start = border + len(content)
        content += [(line, "cyan") for line in visible_prompt]
        local_cursor = (input_start + cursor_line - start, border + cursor_column)
        input_rows = set(range(input_start, input_start + len(visible_prompt)))
        if bordered:
            count = self._scrollback_new_lines
            title = f"Scrollback - {count} new {'line' if count == 1 else 'lines'}" if self._scrollback is not None else "Host Console / PgUp/PgDn"
            rows = self._pane_rows(title, content, width)
        else:
            rows = [(self._paint(self._clip_screen_row(text, width), color) if color else
                     self._clip_screen_row(text, width), "raw") for text, color in content]
        return rows[:height], local_cursor, input_rows

    def _frame(self, height=None, terminal_size=None):
        size = terminal_size or shutil.get_terminal_size(fallback=(120, 24))
        height = max(1, height if height is not None else size.lines)
        width = max(1, size.columns - 1)
        self._frame_cursor = None
        self._frame_input_rows = set()
        title = (f"Retro Serial Hub v{VERSION}  |  " + time.strftime("%Y-%m-%d %H:%M:%S"), "bold")
        if height == 1:
            return [self._paint(self._clip_screen_row(title[0], width), title[1])]
        split = width >= 123 and height >= 8
        top = [title]
        if split:
            full_status = self._status_panel_rows(width, force_color=self._color)
            above = height >= len(full_status) + 31
            if above:
                top += full_status
            body_height = height - len(top)
            right = self._dashboard_rows(width - 83, body_height, include_status=not above)
            left, cursor, inputs = self._host_pane(82, body_height)
            rows = top + [(line + self._paint(" ", "desktop") + (right[index][0] if index < len(right) else ""), "raw")
                          for index, (line, _) in enumerate(left)]
        else:
            available = height - 1
            required_host = max(24, self._screen.height) + len(self._host_hints()) + 2
            host_height = required_host if available >= required_host + 6 else max(1, available * 2 // 3)
            dashboard_height = available - host_height
            # On tiny screens keep the prompt and one urgent status row.
            dashboard = self._dashboard_rows(width, dashboard_height)
            top += dashboard
            host_height = height - len(top)
            left, cursor, inputs = self._host_pane(width, host_height)
            rows = top + left
        self._frame_cursor = (len(top) + cursor[0] + 1, min(width, cursor[1] + 1))
        self._frame_input_rows = {len(top) + index for index in inputs}
        return [text if color == "raw" else self._paint(self._clip_screen_row(text, width), color)
                for text, color in rows[:height]]

    @staticmethod
    def _clip_screen_row(row, width):
        """Keep ANSI colors without letting text wrap or move the cursor."""
        output = []
        columns = 0
        colored = False
        for match in re.finditer(r"\x1b\[[0-9;]*[a-zA-Z]|.", row, re.DOTALL):
            token = match.group()
            if token.startswith("\x1b["):
                if token.endswith("m"):
                    output.append(token)
                    colored = True
                continue
            if not token.isprintable() and not unicodedata.combining(token):
                token = " "
            cells = 0 if unicodedata.combining(token) else 2 if unicodedata.east_asian_width(token) in ("W", "F") else 1
            if columns + cells > width:
                break
            output.append(token)
            columns += cells
        if colored:
            output.append("\x1b[0m")
        return "".join(output)

    def _draw_frame(self, force=False):
        size = shutil.get_terminal_size(fallback=(120, 24))
        rows = self._frame(height=max(1, size.lines), terminal_size=size)
        base = self._theme.ansi() if self._color else ""
        desktop = self._theme.ansi("desktop") if self._color else ""
        context = (sys.stdout, size.columns, size.lines, self._color,
                   self._theme.name, self._theme.colors, self._theme.background)
        repaint = force or context != self._painted_context
        prepared = []
        for index, row in enumerate(rows):
            if self._color:
                if index == 0:
                    title = self._strip_ansi(row)[:max(0, size.columns - 1)]
                    row = self._paint(title.center(max(0, size.columns - 1)), "title")
                row = row.replace("\x1b[0m", base)
            prepared.append(self._clip_screen_row(row, max(0, size.columns - 1)))
        changed = [index for index, row in enumerate(prepared)
                   if repaint or index >= len(self._painted_rows) or row != self._painted_rows[index]]
        stale = [] if repaint else list(range(len(prepared), len(self._painted_rows)))
        self._frame_lines = len(prepared)
        if not changed and not stale and self._frame_cursor == self._painted_cursor and not repaint:
            return

        output = ["\x1b[?25l"]
        if repaint:
            # A resized terminal can reflow old content anywhere in its viewport.
            # Reset the background and paint once before trusting row comparisons.
            output.append(desktop + "\x1b[H\x1b[2J")
        for index in changed:
            output.append(f"\x1b[{index + 1};1H" + desktop + "\x1b[2K" + base
                          + prepared[index] + desktop)
        for index in stale:
            output.append(f"\x1b[{index + 1};1H" + desktop + "\x1b[2K")
        if self._frame_cursor is not None:
            row, column = self._frame_cursor
            output.append(f"\x1b[{row};{column}H\x1b[?25h")
        try:
            sys.stdout.write("".join(output))
            sys.stdout.flush()
        except (OSError, ValueError):
            self._painted_context = None
            raise
        self._painted_rows = prepared
        self._painted_cursor = self._frame_cursor
        self._painted_context = context

    def _refresh_loop(self):
        while self._running:
            time.sleep(self.refresh_interval)
            with self._lock:
                if self._running:
                    self._draw_frame()
