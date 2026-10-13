"""Send a local document to the host operating system's print service."""

import pathlib
import platform
import shutil
import subprocess

_context = None


def init(context):
    global _context
    _context = context


def register_commands(registry):
    def print_file(args):
        if len(args) != 1:
            return "Usage: print <file>"
        path = pathlib.Path(args[0]).expanduser().resolve()
        if not path.is_file():
            return f"File not found: {path}"
        if platform.system() == "Windows":
            import os
            os.startfile(str(path), "print")
        else:
            printer = shutil.which("lp") or shutil.which("lpr")
            if not printer:
                raise OSError("No host printing command (lp or lpr) was found.")
            subprocess.Popen([printer, str(path)], close_fds=True)
        return f"Sent {path.name} to the host printer."
    registry.register_command("print", print_file)


def register_menu(menu):
    menu.append(("print", "Print"))


def handle_event(event):
    return None
