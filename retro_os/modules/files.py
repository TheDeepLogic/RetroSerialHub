from ._adapter import handle, setup


def init(context):
    global _context
    _context = context


def register_commands(registry):
    setup("files", _context, registry)


def register_menu(menu):
    menu.append(("files", "files"))


def handle_event(event):
    handle(event)

