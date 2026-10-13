"""Host application index and launcher command."""

_context = None


def init(context):
    global _context
    _context = context


def register_commands(registry):
    context = _context

    def list_apps(args):
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

        context.host_env.launch_app(app_name, app_args)
        return f"Started {app_name}."

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

    registry.register_command("apps", list_apps)
    registry.register_command("launch", launch)
    registry.register_command("terminal", terminal_cmd)
    registry.register_command("cmd", terminal_cmd)
    registry.register_command("hostcmd", terminal_cmd)
    registry.register_command("hostsh", terminal_cmd)


def register_menu(menu):
    menu.append(("apps", "apps"))


def handle_event(event):
    return None
