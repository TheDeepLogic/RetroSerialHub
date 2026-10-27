"""Menu and CLI entry points for the hub's accessories and media tools."""

from rsh_storage import settings_dir, settings_path
import zipfile
import threading

from retro_os.audio_player import AudioTool
from retro_os.toolkit import CalendarTool, ContactsTool, Converter, FileTools
from retro_os.session_tools import SessionTools
from retro_os.workshop import Workshop

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
        ("Change Directory", ["cd"], ["Folder name/# or host path (.. for parent)"]),
        ("File Information", ["info"], ["File name/#"]),
        ("Create Folder", ["mkdir"], ["Folder name"]),
        ("Rename", ["rename"], ["Source name/#", "New name/path"]),
        ("Copy", ["copy"], ["Source name/#", "Destination path"]),
        ("Move", ["move"], ["Source name/#", "Destination path"]),
        ("View File", ["view"], ["File name/#"]),
        ("Transfer File", ["send"], ["File name/#", "Protocol (x/y/ascii)"]),
        ("Drives / Root (D)", ["drives"], []),
        ("Parent Directory (B)", ["parent"], []),
        ("Shared Files Home (H)", ["home"], []),
    ]),
    "archive": ("ARCHIVE BROWSER", "list", [
        ("List ZIP Archives", ["list"], []),
        ("Open ZIP Archive", ["open"], ["ZIP path in shared files"]),
        ("List Archive Contents", ["members"], []),
        ("Extract Files", ["extract"], ["Member number or all"]),
        ("Extract to Selected Folder", ["extract"], ["Member number or all", "Destination folder"]),
    ]),
    "audio": ("AUDIO PLAYER", "info", [
        ("Browse Audio Files", ["list"], []),
        ("Play Queue", ["play"], []),
        ("Pause / Resume", ["toggle"], []),
        ("Stop", ["stop"], []),
        ("Next Track", ["next"], []),
        ("Previous Track", ["prev"], []),
        ("Set Volume", ["volume"], ["Volume (0-100)"]),
        ("Queue / Playlists", ["tracks"], []),
    ]),
}


TOOL_MENUS.update({
    'capture': ('SESSION CAPTURE', 'status', [
        ('Start Capture', ['start'], ['New capture name']), ('Stop Capture', ['stop'], []),
        ('List Captures', ['list'], []), ('View Capture', ['view'], ['Capture name']),
        ('Export Capture', ['export'], ['Capture name','New output path'])]),
    'diagnostics': ('SERIAL DIAGNOSTICS', 'list', [
        ('All Sessions', ['list'], []), ('Line Settings / Signals', ['info'], ['Terminal name or port']),
        ('Recent ASCII / Hex Traffic', ['hex'], ['Terminal name or port']),
        ('Cancel Transfer (Host)', ['cancel'], ['Terminal name or port'])]),
    'findfiles': ('FIND FILES', 'help', [('Search Host Files', [], ['Filename pattern','Search folder'])]),
    'machine': ('MACHINE PREFERENCES', 'list', [('Change Setting', [], ['Setting name','Value'])]),
    'presets': ('LAUNCH PRESETS', 'list', [('Launch Preset', ['run'], ['Name']),
        ('Add Preset', ['add-menu'], ['Name','Mode (background/terminal/keyboard)','Working directory','Application','Arguments (quote spaced values; - for none)']),
        ('Delete Preset', ['delete'], ['Name'])]),
    'notifications': ('MESSAGES', '', [('Read Unread', [], []),
        ('Quiet On', ['quiet','on'], []), ('Quiet Off', ['quiet','off'], [])]),
    'diskinfo': ('DISK IMAGE INSPECTOR', '', [('Inspect Sector', [], ['Image path','Sector size (128/256/512/1024)','Sector number']),
        ('Extract Raw Sectors', ['extract'], ['Image path','New output','Sector size','First sector','Sector count'])]),
    'hexview': ('HEX VIEWER', '', [('View Bytes', [], ['File path','Offset (decimal/0x)','Byte count (up to 4096)'])]),
    'checksum': ('CHECKSUMS', '', [('Calculate', [], ['File path','Algorithm (sha256/sha1/md5/crc32)'])]),
    'textconvert': ('TEXT CONVERTER', '', [('Convert to New File', [], ['Source','New output','Line endings (lf/crlf/cr)','Case (keep/upper/lower)','Source encoding','Output encoding'])]),
    'basicprep': ('BASIC LISTING TOOLS', '', [('Validate', [], ['Listing path']),
        ('Renumber to New File', [], ['Listing path','New output','Start number','Step'])]),
    'chunks': ('SPLIT / JOIN FILES', '', [('Split', ['split'], ['Source','New output folder','Chunk bytes']),
        ('Verified Join', ['join'], ['Manifest path','New output'])]),
    'encoding': ('BINARY / TEXT ENCODING', '', [('Encode', ['encode'], ['Format (hex/base64)','Source','New output']),
        ('Decode', ['decode'], ['Format (hex/base64)','Source','New output'])]),
    'compare': ('COMPARE FILES', '', [('Compare', [], ['First file','Second file'])]),
})


def init(context):
    _context.value = context


def register_commands(registry):
    context = _context.value
    root = context.fs.get("files")
    if root is None:
        raise ValueError("The tools require a shared files directory.")
    data = context.fs.get("tool_data", settings_dir(root.parent))
    context.host_env.calendar_tool = CalendarTool(data / "appointments.json")
    files = FileTools(root, context)
    archives = files
    context.host_env.file_tools = files
    extras = SessionTools(context, files)
    context.host_env.session_tools = extras
    workshop = Workshop()
    handlers = {
        "calendar": context.host_env.calendar_tool.command,
        "convert": Converter.command,
        "contacts": ContactsTool(data / "contacts.json", context).command,
        "fileman": files.command,
        "archive": archives.archive_command,
        "audio": AudioTool(files).command,
        "capture": extras.capture,
        "diagnostics": extras.diagnostics,
        "findfiles": extras.find,
        "notifications": extras.notifications,
        "messages": extras.notifications,
        "msgs": extras.notifications,
        "machine": extras.machine,
        "height": lambda args: extras.machine(["rows",args[0]]) if args else extras.machine([]),
        "presets": extras.preset,
        "workshop": workshop.command,
    }

    for name, operation in {'diskinfo':'disk','hexview':'hex','checksum':'hash','textconvert':'text',
                            'basicprep':'basic','compare':'compare'}.items():
        handlers[name] = lambda args, op=operation: workshop.command([op,*args])
    handlers['diskinfo'] = lambda args: workshop.command(['diskextract',*args[1:]]) if args and args[0] == 'extract' else workshop.command(['disk',*args])
    handlers['chunks'] = lambda args: workshop.command(args if args else ['split'])
    handlers['encoding'] = lambda args: workshop.command([args[0],*args[1:]]) if args else workshop.command(['encode'])

    def read_document(args):
        if not args:
            return 'read <file/URL>'
        target = args[0]
        if not target.lower().startswith(('http://','https://')):
            target = str(files.path(target, numbered=False))
        if context.activate_module:
            context.activate_module(('reader',target))
            return 'Opening reader...'
        return context.host_env.shell.execute(__import__('shlex').join(['view',target]))
    handlers['read'] = read_document

    def guarded(handler):
        def invoke(args):
            try:
                return handler(args)
            except (OSError, ValueError, KeyError, RuntimeError, EOFError, LookupError, zipfile.BadZipFile) as exc:
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
