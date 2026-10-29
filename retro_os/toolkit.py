"""Persistent accessories and shared-file tools, scoped to a terminal session."""

from __future__ import annotations
from rsh_storage import settings_dir, settings_path

import calendar
import fnmatch
import copy
import datetime as dt
import json
import logging
import math
import os
import pathlib
import shlex
import shutil
import stat
import threading
import tempfile
import uuid
import zipfile

_DATA_LOCK = threading.RLock()
_REMINDER_SERVICES = {}
logger = logging.getLogger(__name__)


def start_calendar_reminders(calendar_tool, notify):
    """Start one reminder clock per shared data file, across terminal sessions."""
    key = calendar_tool.store.path.resolve()
    with _DATA_LOCK:
        if key in _REMINDER_SERVICES:
            return
        stop = threading.Event()
        _REMINDER_SERVICES[key] = stop

    def poll():
        while not stop.wait(15):
            try:
                notice = calendar_tool.due()
                if notice:
                    notify("\r\n" + notice + "\r\n")
            except (OSError, ValueError, KeyError):
                # A bad data file must not terminate the host's serial workers.
                continue
    threading.Thread(target=poll, name="RSH-Reminders", daemon=True).start()


class JsonRecords:
    def __init__(self, path):
        self.path = pathlib.Path(path)

    def load(self):
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError(f"Invalid records in {self.path.name}.")
        return data

    def save(self, rows):
        with _DATA_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode='w', encoding='utf-8', dir=self.path.parent,
                    prefix=self.path.name + '.', suffix='.tmp', delete=False,
                ) as output:
                    temporary = pathlib.Path(output.name)
                    json.dump(rows, output, indent=2)
                    output.write('\n')
                    output.flush()
                    os.fsync(output.fileno())
                temporary.replace(self.path)
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError as exc:
                        logger.warning('Could not remove temporary records file %s: %s', temporary, exc)

    def change(self, operation):
        with _DATA_LOCK:
            rows = self.load()
            before = copy.deepcopy(rows)
            result = operation(rows)
            if rows != before:
                self.save(rows)
            return result


def record_by_id(rows, identifier):
    found = next((row for row in rows if row["id"] == identifier), None)
    if found is None:
        raise ValueError(f"Record {identifier} not found.")
    return found


class CalendarTool:
    HELP = ("calendar [month [YYYY-MM] | agenda | add YYYY-MM-DD HH:MM <title> | "
            "done <id> | delete <id>]\nTimes use the host's local clock.")

    def __init__(self, path):
        self.store = JsonRecords(path)

    def command(self, args):
        action = args[0].lower() if args else "month"
        if action == "help":
            return self.HELP
        if action == "month":
            today = dt.date.today()
            selected = dt.datetime.strptime(args[1], "%Y-%m").date() if len(args) == 2 else today
            # TextCalendar is 20 columns wide and works on 40-column terminals.
            return calendar.TextCalendar().formatmonth(selected.year, selected.month).rstrip() + "\n" + self.agenda(selected.year, selected.month)
        if action == "agenda":
            return self.agenda()
        if action == "due":
            return self.due()
        if action == "add" and len(args) >= 4:
            when = dt.datetime.strptime(args[1] + " " + args[2], "%Y-%m-%d %H:%M")
            title = " ".join(args[3:]).strip()
            if not title:
                raise ValueError("An appointment title is required.")
            row = {"id": uuid.uuid4().hex[:8], "when": when.isoformat(timespec="minutes"),
                   "title": title, "done": False, "notified": False}
            self.store.change(lambda rows: rows.append(row))
            return f"Appointment {row['id']} saved for {when:%Y-%m-%d %H:%M}: {title}"
        if action in ("done", "delete") and len(args) == 2:
            def change(rows):
                row = record_by_id(rows, args[1])
                if action == "delete":
                    rows.remove(row)
                else:
                    row["done"] = True
            self.store.change(change)
            return "Appointment deleted." if action == "delete" else "Appointment completed."
        return self.HELP

    def agenda(self, year=None, month=None):
        with _DATA_LOCK:
            rows = sorted(self.store.load(), key=lambda row: row["when"])
        lines = []
        for row in rows:
            when = dt.datetime.fromisoformat(row["when"])
            if row.get("done") or (year is not None and (when.year, when.month) != (year, month)):
                continue
            lines.append(f"{row['id']} {when:%Y-%m-%d %H:%M}\n  {row['title']}")
        return "\n".join(lines) or "No open appointments."

    def connection_reminders(self):
        today = dt.date.today()
        with _DATA_LOCK:
            rows = self.store.load()
        due = [row for row in rows if not row.get("done") and dt.datetime.fromisoformat(row["when"]).date() <= today]
        return "\n".join(f"Reminder {row['when'].replace('T', ' ')}: {row['title']}" for row in sorted(due, key=lambda row: row["when"]))

    def due(self):
        now = dt.datetime.now()
        def notify(rows):
            messages = []
            for row in rows:
                if not row.get("done") and not row.get("notified") and dt.datetime.fromisoformat(row["when"]) <= now:
                    messages.append(f"REMINDER: {row['title']} ({row['when'].replace('T', ' ')})")
                    row["notified"] = True
            return "\n".join(messages)
        # Avoid creating a data file just by checking for reminders.
        return self.store.change(notify) if self.store.path.exists() else ""


class Converter:
    # Each entry maps a unit to a dimension and its SI multiplier.
    UNITS = {
        "mm": ("length", .001), "cm": ("length", .01), "m": ("length", 1),
        "km": ("length", 1000), "in": ("length", .0254), "ft": ("length", .3048),
        "yd": ("length", .9144), "mi": ("length", 1609.344),
        "mg": ("mass", .000001), "g": ("mass", .001), "kg": ("mass", 1),
        "oz": ("mass", .028349523125), "lb": ("mass", .45359237),
        "ml": ("volume", .001), "l": ("volume", 1), "tsp": ("volume", .00492892159375),
        "tbsp": ("volume", .01478676478125), "floz": ("volume", .0295735295625),
        "cup": ("volume", .2365882365), "pt": ("volume", .473176473),
        "qt": ("volume", .946352946), "gal": ("volume", 3.785411784),
    }
    BASES = {"bin": 2, "binary": 2, "oct": 8, "dec": 10, "decimal": 10, "hex": 16}
    HELP = ("convert <value> <from> <to>\n"
            "Length: mm cm m km in ft yd mi\nMass: mg g kg oz lb\n"
            "Volume: ml l tsp tbsp floz cup pt qt gal (US)\n"
            "Temperature: C F K\nNumber bases: bin oct dec hex\n"
            "Examples: convert 72 F C; convert FF hex bin")

    @classmethod
    def command(cls, args):
        if len(args) != 3:
            return cls.HELP
        raw, source, target = args[0], args[1].lower(), args[2].lower()
        if source in cls.BASES and target in cls.BASES:
            value = int(raw, cls.BASES[source])
            base = cls.BASES[target]
            result = str(value) if base == 10 else format(value, {2: "b", 8: "o", 16: "X"}[base])
            return f"{raw} ({source}) = {result} ({target})"
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("Enter a finite number.")
        if source in ("c", "f", "k") and target in ("c", "f", "k"):
            celsius = (value - 32) * 5 / 9 if source == "f" else value - 273.15 if source == "k" else value
            if celsius < -273.15 - 1e-9:
                raise ValueError("Temperature is below absolute zero.")
            result = celsius * 9 / 5 + 32 if target == "f" else celsius + 273.15 if target == "k" else celsius
        else:
            if source not in cls.UNITS or target not in cls.UNITS:
                raise ValueError("Unknown unit. Type help for the unit list.")
            dimension, scale = cls.UNITS[source]
            other_dimension, other_scale = cls.UNITS[target]
            if dimension != other_dimension:
                raise ValueError("Choose units of the same kind.")
            result = value * scale / other_scale
        if not math.isfinite(result):
            raise ValueError("The converted value is too large.")
        return f"{raw} {source} = {result:.12g} {target}"


class ContactsTool:
    FIELDS = ("name", "email", "phone", "bbs", "notes")
    HELP = ("contacts [list [search] | show <id> | add <name> | "
            "set <id> <name|email|phone|bbs|notes> <value> | delete <id> | "
            "mail <id> [subject] | connect <id>]\nBBS format: host:port (default port 23)")

    def __init__(self, path, context):
        self.store, self.context = JsonRecords(path), context

    def command(self, args):
        action = args[0].lower() if args else "list"
        if action == "help":
            return self.HELP
        with _DATA_LOCK:
            rows = self.store.load()
        if action == "list":
            search = " ".join(args[1:]).casefold()
            return "\n".join(f"{row['id']} {row['name']}\n  {row.get('email', '')} {row.get('phone', '')}" for row in sorted(rows, key=lambda row: row["name"].casefold()) if search in " ".join(str(v) for v in row.values()).casefold()) or "No matching contacts."
        if action == "add" and len(args) >= 2:
            row = dict.fromkeys(self.FIELDS, "")
            row.update(id=uuid.uuid4().hex[:8], name=" ".join(args[1:]))
            self.store.change(lambda records: records.append(row))
            return f"Contact {row['id']} created: {row['name']}"
        if len(args) < 2:
            return self.HELP
        if action in ("set", "delete"):
            def update(records):
                row = record_by_id(records, args[1])
                if action == "delete":
                    records.remove(row)
                elif len(args) >= 4 and args[2].lower() in self.FIELDS:
                    value = " ".join(args[3:])
                    if args[2].lower() == "bbs":
                        self.bbs_address(value)
                    row[args[2].lower()] = value
                else:
                    raise ValueError(self.HELP)
            self.store.change(update)
            return "Contact deleted." if action == "delete" else "Contact updated."
        row = record_by_id(rows, args[1])
        if action == "show":
            return "\n".join(f"{field.title()}: {row.get(field, '')}" for field in self.FIELDS)
        if action == "mail":
            if not row.get("email"):
                raise ValueError("This contact has no email address.")
            # Open a draft using the hub's existing host-mail integration.
            return self.context.host_env.shell.execute(shlex.join(["mail", "mailto", row["email"], *args[2:]]))
        if action == "connect":
            host, port = self.bbs_address(row.get("bbs", ""))
            if self.context.activate_module:
                self.context.activate_module(("bbs_connect", host, port))
            return f"Connecting to {row['name']}: {host}:{port}"
        return self.HELP

    @staticmethod
    def bbs_address(value):
        host, separator, port = value.strip().rpartition(":")
        if not separator:
            host, port = value.strip(), "23"
        if not host or not port.isdigit() or not 1 <= int(port) <= 65535 or any(c.isspace() for c in host):
            raise ValueError("Use a BBS hostname and optional port, such as bbs.example.org:23.")
        return host, int(port)


class FileTools:
    HELP = ("fileman [ls | d/drives | b/parent | h/home | cd <folder/#> | info <file/#> | mkdir <folder> | "
            "rename <file/#> <name> | copy <file/#> <destination> | move <file/#> <destination> | "
            "view <file/#> | send <file/#> [x|y|ascii] | filter <pattern> | favorites | "
            "favorite add/go/delete <name> | mark <file/#> | unmark | copy/move marked <folder>]\nHost paths supported. D=drives/root, B=parent, H=shared files.")
    ARCHIVE_HELP = ("archive [list | open <ZIP file> | members | extract <member #|all> [folder]]\n"
                    "Extraction creates files without replacing existing files.")

    def __init__(self, root, context, allow_host=True):
        self.allow_host = allow_host
        self.root = pathlib.Path(root).resolve()
        self.cwd, self.context = self.root, context
        self.entries = []
        self.archive = None
        self.filter_pattern = '*'
        self.marked = set()
        self.browser_store = JsonRecords(context.fs.get('tool_data', settings_dir(self.root.parent)) / 'browser_preferences.json')
        self.last_destination = next((r['path'] for r in self.browser_store.load() if r.get('kind') == 'destination'), '')

    def path(self, value, numbered=True):
        if numbered and value.isdigit() and 1 <= int(value) <= len(self.entries):
            target = self.entries[int(value) - 1]
        else:
            target = self.cwd / pathlib.Path(value).expanduser()
        resolved = target.resolve()
        if not self.allow_host and not resolved.is_relative_to(self.root):
            raise ValueError("Choose a path inside the shared files folder.")
        return resolved

    def browse_entries(self, extensions=None):
        self.root.mkdir(parents=True, exist_ok=True)
        entries = []
        for path in self.cwd.iterdir():
            try:
                if path.is_dir() or (path.is_file() and (extensions is None or path.suffix.lower() in extensions)
                                     and fnmatch.fnmatchcase(path.name.casefold(), self.filter_pattern.casefold())):
                    entries.append(path)
            except OSError:
                continue
        self.entries = sorted(entries, key=lambda p: (not p.is_dir(), p.name.casefold()))
        return self.entries

    def listing(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.browse_entries()
        lines = [f"Directory: {self.cwd}", f"Filter: {self.filter_pattern}"]
        for index, path in enumerate(self.entries, 1):
            kind = "<DIR>" if path.is_dir() else f"{path.stat().st_size} B"
            lines.append(f"{index:3} {kind:>10} {path.name}" + (" [marked]" if path in self.marked else ""))
        return "\n".join(lines + ([] if self.entries else ["(empty)"]))

    def command(self, args):
        action = args[0].lower() if args else "ls"
        if action == 'filter':
            self.filter_pattern = args[1] if len(args) > 1 and args[1] else '*'
            return self.listing()
        if action == 'mark' and len(args) == 2:
            path = self.path(args[1])
            if path in self.marked:
                self.marked.remove(path)
            else:
                self.marked.add(path)
            return self.listing()
        if action == 'unmark':
            self.marked.clear()
            return self.listing()
        if action in ('favorites', 'favorite'):
            rows = [r for r in self.browser_store.load() if r.get('kind') == 'favorite']
            if len(args) == 1:
                return '\n'.join(f"{r['name']}: {r['path']}" for r in rows) or 'No folder favorites.'
            operation = args[1].lower()
            if operation == 'add' and len(args) >= 3:
                path = self.path(args[3], numbered=False) if len(args) > 3 else self.cwd
                if not path.is_dir():
                    raise ValueError('Choose a directory.')
                def save(records):
                    records[:] = [r for r in records if not (r.get('kind') == 'favorite' and r['name'].casefold() == args[2].casefold())]
                    records.append({'kind':'favorite','name':args[2],'path':str(path)})
                self.browser_store.change(save)
                return 'Folder favorite saved.'
            if operation in ('go','delete') and len(args) == 3:
                row = next((r for r in rows if r['name'].casefold() == args[2].casefold()), None)
                if row is None:
                    raise ValueError('Favorite not found.')
                if operation == 'go':
                    return self.command(['cd', row['path']])
                self.browser_store.change(lambda records: records.remove(row))
                return 'Favorite deleted.'
            return 'favorite [add <name> [folder] | go <name> | delete <name>]'
        if action in ('copy','move') and len(args) >= 2 and args[1] == 'marked':
            if not self.marked:
                raise ValueError('Mark at least one item first.')
            destination = args[2] if len(args) > 2 else self.last_destination
            if not destination or not self.path(destination, numbered=False).is_dir():
                raise ValueError('Choose a destination directory.')
            folder = self.path(destination, numbered=False)
            paths = sorted(self.marked)
            for path in paths:
                if not path.exists():
                    raise ValueError("A marked item no longer exists; refresh and mark it again.")
                if action == "copy" and path.is_dir() and any(p.is_symlink() or (hasattr(p,"is_junction") and p.is_junction()) for p in path.rglob("*")):
                    raise ValueError("A marked directory contains linked entries; copy individual files instead.")
                if path == self.root or path == pathlib.Path(path.anchor) or (folder / path.name).exists() or folder.is_relative_to(path):
                    raise ValueError('Batch destination conflicts with a source or existing item.')
                if any(other != path and path.is_relative_to(other) for other in paths):
                    raise ValueError('Do not mark both a folder and its contents.')
            for path in paths:
                self.command([action, str(path), str(folder)])
            self.marked.clear()
            return self.listing()
        if action in ('copy','move') and len(args) == 2 and self.last_destination:
            args = [*args, self.last_destination]
        if action in ("d", "drives"):
            from rsh_files import _root_directories
            self.entries = _root_directories()
            return "Drives / filesystem roots:\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(self.entries, 1)) + "\nUse cd <number> to open."
        if action in ("b", "parent"):
            return self.command(["cd", ".."])
        if action in ("h", "home"):
            return self.command(["cd", str(self.root)])
        if action in ("ls", "list"):
            return self.listing()
        if action == "help":
            return self.HELP
        if len(args) < 2:
            return self.HELP
        target = self.path(args[1], numbered=action != "mkdir")
        if action == "cd":
            if not target.is_dir():
                raise ValueError("Choose a directory.")
            self.cwd = target
            return self.listing()
        if action == "mkdir":
            target.mkdir(parents=True, exist_ok=False)
            return self.listing()
        if action == "info":
            data = target.stat()
            return f"{target}\nType: {'Directory' if target.is_dir() else 'File'}\nSize: {data.st_size} bytes\nModified: {dt.datetime.fromtimestamp(data.st_mtime):%Y-%m-%d %H:%M:%S}"
        if action in ("rename", "copy", "move") and len(args) == 3:
            if target == self.root or target == pathlib.Path(target.anchor):
                raise ValueError("Choose an item other than the shared folder or filesystem root.")
            destination = self.path(args[2], numbered=False)
            remembered_destination = destination if destination.is_dir() else destination.parent
            if action != "rename" and destination.is_dir():
                destination = destination / target.name
            if destination.exists():
                raise ValueError("Destination already exists; choose another name.")
            if destination.is_relative_to(target):
                raise ValueError("An item cannot be placed inside itself.")
            if action == "copy":
                if target.is_dir():
                    # Do not copy linked entries that escape the shared folder.
                    if any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()) for p in target.rglob('*')):
                        raise ValueError("Directory contains linked entries; copy individual files instead.")
                    shutil.copytree(target, destination)
                else:
                    shutil.copy2(target, destination)
            else:
                shutil.move(str(target), str(destination))
                if target in self.marked:
                    self.marked.remove(target)
                    self.marked.add(destination)
                if self.cwd.is_relative_to(target):
                    self.cwd = destination / self.cwd.relative_to(target)
            self.last_destination = str(remembered_destination)
            def remember(records):
                records[:] = [r for r in records if r.get('kind') != 'destination']
                records.append({'kind':'destination','path':self.last_destination})
            self.browser_store.change(remember)
            return self.listing()
        if action in ("view", "send"):
            if not target.is_file():
                raise ValueError("Choose a file.")
            if action == "view":
                command = "view"
            else:
                preferred = getattr(getattr(self.context.host_env,'terminal',None),'_rsh_transfer_mode','XMODEM')
                protocol = args[2].lower() if len(args) > 2 else {'XMODEM':'x','YMODEM':'y','ASCII':'ascii'}.get(preferred,'x')
                if protocol not in ("x", "y", "ascii"):
                    raise ValueError("Transfer protocol: x, y, or ascii.")
                command = {"x": "xsend", "y": "ysend", "ascii": "asend"}[protocol]
            return self.context.host_env.shell.execute(shlex.join([command, str(target)]))
        return self.HELP

    def archive_command(self, args):
        action = args[0].lower() if args else "list"
        if action == "help":
            return self.ARCHIVE_HELP
        if action == "list":
            self.root.mkdir(parents=True, exist_ok=True)
            archives = sorted(p for p in self.root.rglob('*') if p.suffix.lower() == '.zip' and p.is_file() and p.resolve().is_relative_to(self.root))
            return "\n".join(str(p.relative_to(self.root)) for p in archives) or "No ZIP archives in shared files."
        if action == "open" and len(args) == 2:
            candidate = self.path(args[1])
            with zipfile.ZipFile(candidate) as archive:
                archive.infolist()
            self.archive = candidate
            return self.archive_command(["members"])
        if self.archive is None:
            return "Open a ZIP file first: archive open <file.zip>"
        with zipfile.ZipFile(self.archive) as archive:
            members = archive.infolist()
            if action == "members":
                return f"ZIP: {self.archive.name}\n" + "\n".join(f"{i:3} {item.file_size:>10} B {item.filename}" for i, item in enumerate(members, 1))
            if action == "extract" and len(args) in (2, 3):
                if args[1].lower() == "all":
                    selected = members
                elif args[1].isdigit() and 1 <= int(args[1]) <= len(members):
                    selected = [members[int(args[1]) - 1]]
                else:
                    raise ValueError("Choose a member number or all.")
                destination = self.path(args[2], numbered=False) if len(args) == 3 else self.path(self.archive.stem + "_extracted", numbered=False)
                if sum(item.file_size for item in selected) > 512 * 1024 * 1024:
                    raise ValueError("Selected contents exceed 512 MiB; extract a smaller selection.")
                targets = []
                seen = set()
                for item in selected:
                    member_path = pathlib.PurePosixPath(item.filename.replace('\\', '/'))
                    if member_path.is_absolute() or '..' in member_path.parts or ':' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                        raise ValueError(f"Unsafe ZIP entry: {item.filename}")
                    target = (destination / str(member_path)).resolve()
                    if not target.is_relative_to(destination) or (not self.allow_host and not target.is_relative_to(self.root)):
                        raise ValueError(f"ZIP entry escapes destination: {item.filename}")
                    if target in seen or (target.exists() and not (item.is_dir() and target.is_dir())):
                        raise ValueError(f"Destination already exists or is duplicated: {item.filename}")
                    seen.add(target)
                    targets.append((item, target))
                file_targets = {target for item, target in targets if not item.is_dir()}
                for _, target in targets:
                    if any(parent in file_targets or (parent.exists() and not parent.is_dir()) for parent in target.parents if parent.is_relative_to(destination)):
                        raise ValueError("ZIP entries conflict with a file used as a directory.")
                for item, target in targets:
                    if item.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        # Only remove a file this extraction created. Opening
                        # exclusively also preserves files created after preflight.
                        output = target.open('xb')
                        try:
                            with output, archive.open(item) as source:
                                shutil.copyfileobj(source, output)
                        except Exception:
                            try:
                                target.unlink()
                            except OSError as exc:
                                logger.warning('Could not remove incomplete ZIP member %s: %s', target, exc)
                            raise
                return f"Extracted {len(selected)} entries into {destination}."
        return self.ARCHIVE_HELP
