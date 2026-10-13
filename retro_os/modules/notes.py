from ._adapter import handle, setup


def init(context):
    global _context
    _context = context


def register_commands(registry):
    setup("notes", _context, registry)


def register_menu(menu):
    menu.append(("notes", "notes"))


def handle_event(event):
    handle(event)

