"""Factory for a session-scoped Retro Serial OS shell and module set."""

from __future__ import annotations

import pathlib

from .core import EventBus, ModuleContext, ModuleLoader, Session, Shell
from .host_env import HostEnvironment


FEATURE_MODULES = (
    "apps",
    "browser",
    "telnet",
    "ftp",
    "notes",
    "textlib",
    "files",
    "bbs",
    "ai",
    "calc",
    "mail",
    "print",
    "games",
    "ascii_viewer",
    "scheduler",
    "shortcut",
)


def create_runtime(fs, *, session=None, activate_module=None, profiles_path=None, shortcuts_path=None):
    """Build a complete shell, event bus, host facade, and module registry."""
    session = session or Session()
    bus = EventBus()
    shortcuts_file = shortcuts_path or fs.get("shortcuts")
    host_env = HostEnvironment(profiles_path, shortcuts_path=shortcuts_file)
    context = ModuleContext(
        session=session,
        fs={name: pathlib.Path(path) for name, path in fs.items()},
        bus=bus,
        host_env=host_env,
        activate_module=activate_module,
    )
    shell = Shell()
    host_env.shell = shell
    loader = ModuleLoader(context, shell)
    loader.load_all(FEATURE_MODULES)
    install_core_commands(shell, context, loader)
    for topic in ("session.connected", "session.disconnected", "kb.shortcut", "file.open", "notify"):
        bus.subscribe(topic, loader.dispatch_event)
    bus.subscribe(
        "scheduler.exec",
        lambda evt: shell.execute(evt.get("command", "")) if isinstance(evt, dict) else "",
    )
    bus.publish("session.connected", session)
    return session, bus, host_env, shell, loader


def install_core_commands(shell, context, loader):
    """Register the commands shared by all application modules."""

    def apps(args):
        refresh = False
        pattern = None
        if args:
            if len(args) == 1 and args[0].lower() == "refresh":
                refresh = True
            else:
                pattern = " ".join(args).strip()
        index = context.host_env.list_apps(refresh=refresh)
        if pattern:
            p_lower = pattern.casefold()
            if len(pattern) == 1:
                index = {k: v for k, v in index.items() if k.casefold().startswith(p_lower)}
            else:
                index = {k: v for k, v in index.items() if p_lower in k.casefold()}
        if not index:
            if pattern:
                return f"No host applications matched '{pattern}'."
            return "No host applications were found."
        return "\n".join(f"{name} - {path}" for name, path in index.items())

    def launch(args):
        if not args:
            return (
                "Usage: launch [-i | -k] <app> [args...]\n"
                "  -i, -t: Interactive terminal (grab keyboard & stream app output)\n"
                "  -k:     Keyboard bridge (launch and type into host window)\n"
                "  (none): Run app in background on host"
            )
        mode = "bg"
        clean_args = list(args)
        if clean_args[0].lower() in ("-i", "-t", "--interactive", "--terminal"):
            mode = "interactive"
            clean_args.pop(0)
        elif clean_args[0].lower() in ("-k", "--keyboard", "--bridge"):
            mode = "keyboard"
            clean_args.pop(0)
        elif clean_args[0].lower() in ("-b", "--background"):
            mode = "bg"
            clean_args.pop(0)

        if not clean_args:
            return "Usage: launch [-i | -k] <app> [args...]"

        app_name = clean_args[0]
        app_args = clean_args[1:]

        if mode == "interactive" and context.activate_module:
            context.session.active_module = "launch"
            context.activate_module(("app_interactive", app_name, app_args))
            return f"Opening interactive terminal session for {app_name}..."

        if mode == "keyboard" and context.activate_module:
            context.session.active_module = "launch"
            context.activate_module(("app_keyboard", app_name, app_args))
            return f"Launching {app_name} with Keyboard Bridge..."

        process = context.host_env.launch_app(app_name, app_args)
        return f"Started {app_name}."

    def view(args):
        if not args:
            return "Usage: view <file_or_url>"
        target = args[0]
        full_candidate = " ".join(args)
        if len(args) > 1 and not pathlib.Path(target).exists() and pathlib.Path(full_candidate).exists():
            target = full_candidate
        target = target.strip("'\"")
        from .viewer import extract_text, extract_text_from_url, paginate_text
        if target.lower().startswith(("http://", "https://")):
            try:
                text = extract_text_from_url(target)
                pages = paginate_text(text, context.session.cols)
                return "\n\f\n".join("\n".join(page) for page in pages)
            except Exception as exc:
                return f"Error downloading/viewing URL: {exc}"

        path = pathlib.Path(target).expanduser()
        if not path.is_absolute():
            candidates = [pathlib.Path.cwd() / path]
            candidates.extend(root / path for root in context.fs.values())
            path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])

        if path.is_file():
            context.bus.publish("file.open", {"session": context.session, "path": path})
            pages = paginate_text(extract_text(path), context.session.cols)
            return "\n\f\n".join("\n".join(page) for page in pages)

        t_lower = target.lower()
        if t_lower.startswith("www.") or any(
            t_lower.endswith(tld) or f"{tld}/" in t_lower
            for tld in (".com", ".org", ".net", ".edu", ".gov", ".io", ".info", ".co", ".me", ".tv")
        ):
            target_url = "https://" + target
            try:
                text = extract_text_from_url(target_url)
                pages = paginate_text(text, context.session.cols)
                return "\n\f\n".join("\n".join(page) for page in pages)
            except Exception as exc:
                return f"Error downloading/viewing URL: {exc}"

        return f"File not found: {path}"

    def fetch(args):
        if not args:
            return "Usage: fetch <url> [destination_filename]"
        url = args[0]
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        dest_name = args[1] if len(args) > 1 else None
        from .viewer import fetch_url
        try:
            target_dir = context.fs.get("files", pathlib.Path.cwd())
            dest_path, size = fetch_url(url, dest_dir=target_dir, dest_name=dest_name)
            return f"Downloaded {dest_path.name} ({size} bytes) to {dest_path}."
        except Exception as exc:
            return f"Fetch error: {exc}"

    def fetchview(args):
        if not args:
            return "Usage: fetchview <url>"
        url = args[0]
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        return view([url, *args[1:]])

    def kb(args):
        profiles = context.host_env.keyboard_profiles
        if len(args) == 2 and args[0].lower() == "profile":
            profile = args[1]
            profiles.get(profile)
            context.session.kb_profile = profile
            return f"Keyboard profile: {profile}"
        if len(args) == 3 and args[0].lower() == "map":
            mappings = profiles.set_mapping(
                context.session.kb_profile, args[1], args[2]
            )
            return "\n".join(f"{key} = {value}" for key, value in sorted(mappings.items()))
        if len(args) == 1 and args[0].lower() == "profiles":
            return "Profiles: " + ", ".join(profiles.names)
        return "Usage: kb profile <name> | kb map <key> <action> | kb profiles"

    def notify_cmd(args):
        if not args:
            return "Usage: msg <text> | notify <text> | alert <text> | echo <text>"
        message = " ".join(args).strip()
        context.bus.publish("notify", {
            "session": context.session,
            "message": message,
            "sender": getattr(context.session, "user", "Host"),
        })
        return message

    def send_cmd(args):
        if not args:
            return "Usage: send <keystrokes> (e.g. 'send guest{ENTER}' or 'send text{WAIT:1}more')"
        raw_text = " ".join(args)
        context.bus.publish("session.send_keys", {
            "session": context.session,
            "text": raw_text,
        })
        return f"Sent: {raw_text}"

    def terminal_cmd(args):
        shell_info = context.host_env.get_host_shell()
        target = shell_info["default_shell"]
        target_args = list(shell_info["default_args"])
        if args:
            first = args[0].lower()
            if first in ("powershell", "ps") and shell_info.get("alt_shell"):
                target = shell_info["alt_shell"]
                target_args = list(shell_info.get("alt_args", []))
            elif first in ("cmd", "cmd.exe"):
                target = "cmd.exe"
                target_args = ["/q"]
            elif first in ("bash", "sh", "zsh"):
                target = args[0]
                target_args = list(args[1:])
            else:
                target = args[0]
                target_args = list(args[1:])

        if context.activate_module:
            context.session.active_module = "launch"
            context.activate_module(("host_terminal", target, target_args))
            return f"Opening host terminal session for {target}..."
        return f"Host terminal: {target}"

    def sysinfo_cmd(args):
        cols = getattr(context.session, "cols", 80)
        if args and args[0].lower() in ("live", "watch", "-w", "-l", "realtime", "rt"):
            if context.activate_module:
                context.session.active_module = "sysinfo"
                context.activate_module(("sysinfo_live",))
                return "Entering real-time host system monitor..."
        return context.host_env.format_sysinfo(cols=cols)

    def top_cmd(args):
        cols = getattr(context.session, "cols", 80)
        if args and args[0].lower() in ("static", "snap", "snapshot", "-s"):
            return context.host_env.format_sysinfo(cols=cols)
        if context.activate_module:
            context.session.active_module = "sysinfo"
            context.activate_module(("sysinfo_live",))
            return "Entering real-time host system monitor..."
        return context.host_env.format_sysinfo(cols=cols)

    def clip_cmd(args):
        if not args:
            text = context.host_env.get_clipboard()
            if not text:
                return "(Host clipboard is empty)"
            return f"Host Clipboard:\n{text}"
        new_text = " ".join(args)
        ok = context.host_env.set_clipboard(new_text)
        return f"Copied {len(new_text)} characters to host clipboard." if ok else "Failed to set host clipboard."

    def copy_cmd(args):
        if not args:
            return "Usage: copy <text to copy to host clipboard>"
        new_text = " ".join(args)
        ok = context.host_env.set_clipboard(new_text)
        return f"Copied {len(new_text)} characters to host clipboard." if ok else "Failed to set host clipboard."

    def media_cmd(args):
        if not args:
            return "Usage: media play | pause | next | prev | stop"
        return context.host_env.media_control(args[0])

    def vol_cmd(args):
        if not args:
            return "Usage: vol up | down | mute"
        action = args[0].lower()
        if action in ("up", "+"):
            return context.host_env.media_control("vol_up")
        elif action in ("down", "-"):
            return context.host_env.media_control("vol_down")
        elif action in ("mute", "m"):
            return context.host_env.media_control("mute")
        return "Usage: vol up | down | mute"

    def weather_cmd(args):
        from .weather_news import get_weather
        loc = " ".join(args).strip() if args else None
        return get_weather(loc)

    def news_cmd(args):
        from .news import (
            get_news,
            get_article_by_index,
            get_full_article_by_index,
        )
        if not args:
            return get_news("npr", count=5)
        arg0 = args[0].strip().lower()
        if arg0.isdigit():
            idx = int(arg0)
            full = len(args) > 1 and args[1].lower() in ("full", "-f", "--full")
            if full:
                return get_full_article_by_index(idx)
            return get_article_by_index(idx)
        if arg0 == "read" and len(args) > 1 and args[1].isdigit():
            idx = int(args[1])
            full = len(args) > 2 and args[2].lower() in ("full", "-f", "--full")
            if full:
                return get_full_article_by_index(idx)
            return get_article_by_index(idx)
        src = args[0]
        count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
        return get_news(src, count=count)

    def briefing_cmd(args):
        from .weather_news import get_briefing
        loc = " ".join(args).strip() if args else None
        cols = getattr(context.session, "cols", 80)
        return get_briefing(loc, columns=cols)

    def xsend_cmd(args):
        if not args:
            return "Usage: xsend <filename>"
        fname = args[0]
        if context.activate_module:
            context.session.active_module = "files"
            context.activate_module(("file_transfer", "XMODEM_SEND", fname))
            return f"Starting XMODEM send for {fname}..."
        return f"XMODEM send: {fname}"

    def ysend_cmd(args):
        if not args:
            return "Usage: ysend <filename>"
        fname = args[0]
        if context.activate_module:
            context.session.active_module = "files"
            context.activate_module(("file_transfer", "YMODEM_SEND", fname))
            return f"Starting YMODEM send for {fname}..."
        return f"YMODEM send: {fname}"

    def asend_cmd(args):
        if not args:
            return "Usage: asend <filename>"
        fname = args[0]
        if context.activate_module:
            context.session.active_module = "files"
            context.activate_module(("file_transfer", "ASCII_SEND", fname))
            return f"Starting ASCII send for {fname}..."
        return f"ASCII send: {fname}"

    def xrecv_cmd(args):
        if not args:
            return "Usage: xrecv <destination_filename>"
        fname = args[0]
        if context.activate_module:
            context.session.active_module = "files"
            context.activate_module(("file_transfer", "XMODEM_RECV", fname))
            return f"Starting XMODEM receive for {fname}..."
        return f"XMODEM receive: {fname}"

    def caps_cmd(args):
        if not args:
            cur = getattr(context.session, "caps_only", False)
            return f"Caps mode: {'ON' if cur else 'OFF'} (Usage: caps on | off)"
        setting = args[0].lower() in ("1", "on", "yes", "true")
        context.session.caps_only = setting
        if context.activate_module:
            context.activate_module(("set_caps", setting))
        return f"Caps mode set to {'ON' if setting else 'OFF'}."

    def pace_cmd(args):
        if not args:
            cur = getattr(context.session, "pace_delay", 0.0)
            return f"Pacing delay: {int(cur * 1000)} ms/char (Usage: pace <ms>)"
        try:
            ms = float(args[0])
            sec = max(0.0, ms / 1000.0)
            context.session.pace_delay = sec
            if context.activate_module:
                context.activate_module(("set_pace", sec))
            return f"Character pacing set to {int(ms)} ms/character."
        except ValueError:
            return "Usage: pace <milliseconds> (e.g. 'pace 2' or 'pace 0' for off)"

    def cols_cmd(args):
        if not args:
            return f"Current width: {context.session.cols} columns. (Usage: cols 40 | cols 80)"
        val = args[0]
        if val in ("40", "80"):
            target_cols = int(val)
            context.session.cols = target_cols
            if context.activate_module:
                context.activate_module(("set_columns", target_cols))
            return f"Terminal columns set to {target_cols}."
        return "Usage: cols 40 | cols 80"

    def ansi_cmd(args):
        if not args:
            return "Usage: ansi on | off"
        setting = args[0].lower() in ("1", "on", "yes", "true")
        if context.activate_module:
            context.activate_module(("set_ansi", setting))
        return f"ANSI translation set to {'ON' if setting else 'OFF'}."

    shell.register_command("apps", apps)
    shell.register_command("launch", launch)
    shell.register_command("terminal", terminal_cmd)
    shell.register_command("cmd", terminal_cmd)
    shell.register_command("hostcmd", terminal_cmd)
    shell.register_command("hostsh", terminal_cmd)
    shell.register_command("sysinfo", sysinfo_cmd)
    shell.register_command("sys", sysinfo_cmd)
    shell.register_command("top", top_cmd)
    shell.register_command("clip", clip_cmd)
    shell.register_command("paste", clip_cmd)
    shell.register_command("copy", copy_cmd)
    shell.register_command("media", media_cmd)
    shell.register_command("vol", vol_cmd)
    shell.register_command("volume", vol_cmd)
    shell.register_command("weather", weather_cmd)
    shell.register_command("news", news_cmd)
    shell.register_command("briefing", briefing_cmd)
    shell.register_command("xsend", xsend_cmd)
    shell.register_command("ysend", ysend_cmd)
    shell.register_command("asend", asend_cmd)
    shell.register_command("xrecv", xrecv_cmd)
    shell.register_command("caps", caps_cmd)
    shell.register_command("pace", pace_cmd)
    shell.register_command("cols", cols_cmd)
    shell.register_command("ansi", ansi_cmd)
    shell.register_command("view", view)
    shell.register_command("fetch", fetch)
    shell.register_command("download", fetch)
    shell.register_command("fetchview", fetchview)
    shell.register_command("kb", kb)
    shell.register_command("msg", notify_cmd)
    shell.register_command("notify", notify_cmd)
    shell.register_command("alert", notify_cmd)
    shell.register_command("echo", notify_cmd)
    shell.register_command("broadcast", notify_cmd)
    shell.register_command("send", send_cmd)
    shell.register_command("sendkeys", send_cmd)
    shell.register_command("reload", lambda args: _reload_module(loader, args))


def parse_and_chunk_keystrokes(raw_text):
    """Parse keystroke string into list of ('send', bytes) and ('wait', seconds)."""
    import re
    tokens = re.split(r'(\{WAIT:[0-9.]+\}|\{ENTER\}|\{ESC\}|\{TAB\})', raw_text, flags=re.IGNORECASE)
    actions = []
    has_explicit_enter = False
    for token in tokens:
        if not token:
            continue
        token_upper = token.upper()
        if token_upper.startswith('{WAIT:') and token_upper.endswith('}'):
            try:
                sec = float(token[6:-1])
                actions.append(('wait', sec))
            except ValueError:
                pass
        elif token_upper == '{ENTER}':
            actions.append(('send', b'\r\n'))
            has_explicit_enter = True
        elif token_upper == '{ESC}':
            actions.append(('send', b'\x1b'))
        elif token_upper == '{TAB}':
            actions.append(('send', b'\t'))
        else:
            cleaned = token.replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t')
            if '\r' in cleaned or '\n' in cleaned:
                has_explicit_enter = True
            actions.append(('send', cleaned.encode('utf-8', errors='replace')))
    if not has_explicit_enter:
        actions.append(('send', b'\r\n'))
    return actions


def _reload_module(loader, args):
    if len(args) != 1:
        return "Usage: reload <module>"
    loader.load(args[0], reload_module=True)
    return f"Reloaded module: {args[0]}"
