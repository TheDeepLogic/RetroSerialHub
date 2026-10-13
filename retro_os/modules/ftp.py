from ._adapter import handle, setup


def init(context):
    global _context
    _context = context


def register_commands(registry):
    setup("ftp", _context, registry)


def register_menu(menu):
    menu.append(("ftp", "ftp"))


def handle_event(event):
    handle(event)

