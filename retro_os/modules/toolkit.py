"""Menu and CLI entry points for the hub's accessories and media tools."""

import zipfile
import threading

from retro_os.audio_player import AudioTool
from retro_os.toolkit import CalendarTool, ContactsTool, Converter, FileTools

_context = threading.local()

# Label, command arguments, and prompted arguments. Empty inputs cancel an action.
TOOL_MENUS = {
    "calendar": ("CALENDAR", "month", [
        ("This Month", ["month"], []),
        ("Another Month", ["month"], ["Month (YYYY-MM)"]),
        ("Appointment List", ["agenda"], []),
        ("Add Appointment", ["add"], ["Date (YYYY-MM-DD)", "Time (HH:MM, host local time)", "Title"]),
        ("Complete Appointment", ["done"], ["Appointment ID"]),
        ("Delete Appointment", ["delete"], ["Appointment ID"]),
    ]),
    "convert": ("UNIT CONVERTER", "help", [
        ("Convert Units or Number Bases", [], ["Value", "From unit/base", "To unit/base"]),
        ("Show Supported Units", ["help"], []),
    ]),
    "contacts": ("ADDRESS BOOK", "list", [
        ("List Contacts", ["list"], []),
        ("Search Contacts", ["list"], ["Search text"]),
        ("Show Contact", ["show"], ["Contact ID"]),
        ("Add Contact", ["add"], ["Name"]),
        ("Edit Contact Field", ["set"], ["Contact ID", "Field (name/email/phone/bbs/notes)", "Value"]),
        ("Delete Contact", ["delete"], ["Contact ID"]),
        ("Compose Mail on Host", ["mail"], ["Contact ID"]),
        ("Connect to Contact's BBS", ["connect"], ["Contact ID"]),
    ]),
    "fileman": ("FILE MANAGER", "ls", [
        ("List Directory", ["ls"], []),
        ("Change Directory", ["cd"], ["Folder name/# (.. for parent)"]),
        ("File Information", ["info"], ["File name/#"]),
        ("Create Folder", ["mkdir"], ["Folder name"]),
        ("Rename", ["rename"], ["Source name/#", "New name/path"]),
        ("Copy", ["copy"], ["Source name/#", "Destination path"]),
        ("Move", ["move"], ["Source name/#", "Destination path"]),
        ("View File", ["view"], ["File name/#"]),
        ("Transfer File", ["send"], ["File name/#", "Protocol (x/y/ascii)"]),
    ]),
    "archive": ("ARCHIVE BROWSER", "list", [
        ("List ZIP Archives", ["list"], []),
        ("Open ZIP Archive", ["open"], ["ZIP path in shared files"]),
        ("List Archive Contents", ["members"], []),
        ("Extract Files", ["extract"], ["Member number or all"]),
        ("Extract to Selected Folder", ["extract"], ["Member number or all", "Destination folder"]),
    ]),
    "audio": ("AUDIO PLAYER", "list", [
        ("Browse Audio Files", ["list"], []),
        ("Play File", ["play"], ["Audio file name/#"]),
        ("Add Track to Queue", ["queue"], ["Audio file name/#"]),
        ("Pause", ["pause"], []),
        ("Resume", ["resume"], []),
        ("Stop", ["stop"], []),
        ("Next Track", ["next"], []),
        ("Previous Track", ["prev"], []),
        ("Set Volume", ["volume"], ["Volume (0-100)"]),
        ("Track Information", ["info"], []),
        ("Show Queue", ["tracks"], []),
        ("Save Playlist", ["save"], ["Playlist name"]),
        ("Saved Playlists", ["playlists"], []),
        ("Load and Play Playlist", ["load"], ["Playlist name"]),
        ("Internet Radio", ["radio"], ["HTTP(S) radio stream URL"]),
        ("Play Queued Tracks", ["play"], []),
    ]),
}


def init(context):
    _context.value = context


def register_commands(registry):
    context = _context.value
    root = context.fs.get("files")
    if root is None:
        raise ValueError("The tools require a shared files directory.")
    data = context.fs.get("tool_data", root.parent / "hub_tools")
    context.host_env.calendar_tool = CalendarTool(data / "appointments.json")
    files = FileTools(root, context)
    archives = FileTools(root, context)
    handlers = {
        "calendar": context.host_env.calendar_tool.command,
        "convert": Converter.command,
        "contacts": ContactsTool(data / "contacts.json", context).command,
        "fileman": files.command,
        "archive": archives.archive_command,
        "audio": AudioTool(FileTools(root, context)).command,
    }

    def guarded(handler):
        def invoke(args):
            try:
                return handler(args)
            except (OSError, ValueError, KeyError, RuntimeError, EOFError, zipfile.BadZipFile) as exc:
                return f"Could not complete command: {exc}"
        return invoke

    for name, handler in handlers.items():
        registry.register_command(name, guarded(handler))
    for alias, name in {"cal": "calendar", "units": "convert", "addressbook": "contacts", "fm": "fileman", "zip": "archive", "player": "audio"}.items():
        registry.register_command(alias, guarded(handlers[name]))


def register_menu(menu):
    menu.extend((name, title) for name, (title, _, _) in TOOL_MENUS.items())


def handle_event(event):
    return None
