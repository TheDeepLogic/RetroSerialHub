"""Terminal Logo programming accessory."""

_context = None


def init(context):
    global _context
    _context = context


def register_commands(registry):
    def logo(args):
        from ..logo import LogoInterpreter

        if args and args[0].lower() in ("help", "?"):
            return LogoInterpreter.help_text()
        if _context.activate_module:
            _context.activate_module("logo")
            return "Starting Logo. Enter commands at the Logo prompt."
        return "Open LOGO from Accessories to start the Logo prompt."

    registry.register_command("logo", logo)


def register_menu(menu):
    menu.append(("logo", "LOGO"))


def handle_event(event):
    return None
