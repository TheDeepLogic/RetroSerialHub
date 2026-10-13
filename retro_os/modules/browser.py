from ._adapter import handle, setup


def init(context):
    global _context
    _context = context


def register_commands(registry):
    setup("browser", _context, registry)


def register_menu(menu):
    menu.append(("browser", "browser"))


def handle_event(event):
    handle(event)

