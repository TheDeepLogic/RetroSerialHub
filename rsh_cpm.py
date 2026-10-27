"""Small, session-local CP/M command environment for the IMSAI simulation."""

import re
from rsh_terminal import clear_terminal_screen, terminal_columns


def _text(text):
    return {"text": text, "size": len(text.encode("ascii"))}


def new_disks():
    files = {
        "CPM.SYS": {"size": 8192},
        "README.TXT": _text("IMSAI PERSONAL DISK\r\n\r\n"
            "DIR lists files. TYPE displays a text file.\r\n"
            "Run a COM program by entering its name without the extension.\r\n"
            "The communications programs are described in MODEM.DOC.\r\n"
            "Drive B is a scratch disk. Changes last until this session ends.\r\n"),
        "MODEM.DOC": _text("COMMUNICATIONS SOFTWARE\r\n\r\n"
            "DIALER.COM searches an area code or prefix for carrier tones.\r\n"
            "TERM.COM connects to a number or a saved system.\r\n"
            "Example: run DIALER, scan 311, then run TERM.\r\n"
            "All calls and remote systems are local simulations.\r\n"),
        "NOTES.TXT": _text("TO DO\r\n\r\nFinish homework.\r\n"
            "Check the modem cable.\r\nTry the new numbers after dinner.\r\n"),
        "PHONE.LST": _text("MODEM TEST PREFIXES\r\n311\r\n311767\r\n"),
    }
    for program, size in (("STAT", 5248), ("PIP", 7424), ("DUMP", 512),
                          ("HELP", 768), ("CLS", 256), ("DIALER", 4096), ("TERM", 6144)):
        files[program + ".COM"] = {"program": program, "size": size}
    return {"A": files, "B": {}}


def write(ser, text):
    ser.write(text.encode("ascii", errors="replace"))


def prompt(session, ser):
    write(ser, session.get("cpm_drive", "A") + ">")


def _spec(session, value, wildcard=False):
    value = value.upper().strip()
    drive = session["cpm_drive"]
    if len(value) >= 2 and value[1] == ":":
        drive, value = value[0], value[2:]
    if drive not in session["cpm_disks"]:
        raise ValueError("BDOS ERR: " + drive + ": SELECT")
    if not value and wildcard:
        value = "*.*"
    allowed = r"[A-Z0-9_$#@!*?\-]" if wildcard else r"[A-Z0-9_$#@!\-]"
    if not re.fullmatch(allowed + r"{1,8}(?:\." + allowed + r"{0,3})?", value):
        raise ValueError("BAD FILE NAME")
    return drive, value.rstrip(".")


def _matches(name, pattern):
    # CP/M matches the name and extension as separate padded fields. A missing
    # extension is blank, while *.* includes extensionless files as well.
    def fields(value):
        return (value.split(".", 1) + [""])[:2]
    def match(value, expression, length):
        if "*" in expression:
            prefix = expression.split("*", 1)[0]
            expression = prefix + "?" * (length - len(prefix))
        return len(expression) <= length and all(p == "?" or p == c
            for p, c in zip(expression.ljust(length), value.ljust(length)))
    return all(match(value, expression, length) for value, expression, length
               in zip(fields(name), fields(pattern), (8, 3)))


def handle(session, command, ser, use_ansi=True):
    """Return a selected program name, MENU, or None after a CP/M command."""
    session.setdefault("cpm_drive", "A")
    if "cpm_disks" not in session:
        session["cpm_disks"] = new_disks()
    command = command.strip().upper()
    if not command:
        prompt(session, ser)
        return None
    write(ser, "\r\n")
    parts = command.split(None, 1)
    verb, tail = parts[0], parts[1].strip() if len(parts) > 1 else ""
    if verb == "?":
        verb = "A:HELP"
    try:
        if command in ("EXIT", "QUIT"):
            return "MENU"
        if re.fullmatch(r"[A-Z]:", command):
            drive = command[0]
            if drive not in session["cpm_disks"]:
                raise ValueError("BDOS ERR: " + drive + ": SELECT")
            session["cpm_drive"] = drive
        elif verb in ("DIR", "ERA"):
            if verb == "ERA" and not tail:
                raise ValueError("ERA filename.typ")
            drive, pattern = _spec(session, tail, wildcard=True)
            disk = session["cpm_disks"][drive]
            names = sorted(name for name in disk if _matches(name, pattern))
            if not names:
                write(ser, "NO FILE\r\n")
            elif verb == "ERA":
                for name in names:
                    del disk[name]
            else:
                columns = 2 if terminal_columns(ser) == 40 else 4
                cells = [f"{name.partition('.')[0]:<8} {name.partition('.')[2]:<3}" for name in names]
                for start in range(0, len(cells), columns):
                    write(ser, drive + ": " + " : ".join(cells[start:start + columns]) + "\r\n")
        elif verb in ("TYPE", "REN", "SAVE"):
            if verb == "REN":
                if tail.count("=") != 1:
                    raise ValueError("REN newname.typ=oldname.typ")
                new, old = tail.split("=", 1)
                drive, old = _spec(session, old)
                destination, new = _spec({**session, "cpm_drive": drive}, new)
                if destination != drive:
                    raise ValueError("REN CANNOT CHANGE DRIVES")
                disk = session["cpm_disks"][drive]
                if old not in disk:
                    raise ValueError("NO FILE")
                if new in disk:
                    raise ValueError("FILE EXISTS")
                disk[new] = disk.pop(old)
            elif verb == "TYPE":
                drive, name = _spec(session, tail)
                entry = session["cpm_disks"][drive].get(name)
                if entry is None:
                    raise ValueError("NO FILE")
                write(ser, entry.get("text", "NOT A TEXT FILE\r\n"))
            else:
                fields = tail.split()
                if len(fields) != 2 or not fields[0].isdigit() or not 1 <= int(fields[0]) <= 128:
                    raise ValueError("SAVE pages filename.typ (1-128 pages)")
                drive, name = _spec(session, fields[1])
                session["cpm_disks"][drive][name] = {"size": int(fields[0]) * 256}
                write(ser, "SIMULATED MEMORY IMAGE SAVED\r\n")
        else:
            drive, name = _spec(session, verb)
            if "." not in name:
                name += ".COM"
            entry = session["cpm_disks"][drive].get(name, {})
            program = entry.get("program") if name.endswith(".COM") else None
            if program in ("DIALER", "TERM"):
                return program
            if program == "HELP" or verb == "?":
                write(ser, "DIR [d:pattern]   TYPE d:file.typ\r\n"
                      "REN new=old      ERA d:pattern\r\n"
                      "SAVE n file      A: / B:\r\n"
                      "STAT [d:]        PIP dest=source\r\n"
                      "DUMP file        CLS\r\n"
                      "TYPE README.TXT for disk notes.\r\n"
                      "EXIT or ATM returns to the hub.\r\n")
            elif program == "CLS":
                clear_terminal_screen(ser, use_ansi)
            elif program == "STAT":
                drive = tail[:1] if re.fullmatch(r"[AB]:", tail) else session["cpm_drive"]
                if tail and not re.fullmatch(r"[AB]:", tail):
                    raise ValueError("STAT [A: or B:]")
                disk = session["cpm_disks"][drive]
                used = sum((entry["size"] + 1023) // 1024 for entry in disk.values())
                write(ser, f"{drive}: R/W, {len(disk)} FILES\r\nBYTES REMAINING ON {drive}: {max(0, 241-used)}K\r\n")
            elif program == "PIP":
                if tail.count("=") != 1:
                    raise ValueError("PIP destination=source")
                destination, source = tail.split("=", 1)
                drive, source = _spec(session, source)
                entry = session["cpm_disks"][drive].get(source)
                if entry is None:
                    raise ValueError("NO FILE")
                if re.fullmatch(r"[AB]:", destination):
                    destination += source
                target, name = _spec(session, destination)
                session["cpm_disks"][target][name] = dict(entry)
            elif program == "DUMP":
                drive, name = _spec(session, tail)
                entry = session["cpm_disks"][drive].get(name)
                if entry is None:
                    raise ValueError("NO FILE")
                data = entry.get("text", "").encode("ascii") or bytes(min(256, entry["size"]))
                for offset in range(0, min(len(data), 256), 8):
                    write(ser, f"{offset:04X} " + " ".join(f"{byte:02X}" for byte in data[offset:offset+8]) + "\r\n")
                if entry["size"] > 256:
                    write(ser, "FIRST 0100H BYTES SHOWN\r\n")
            else:
                write(ser, verb + "?\r\n")
    except ValueError as exc:
        write(ser, str(exc) + "\r\n")
    prompt(session, ser)
    return None
