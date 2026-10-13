"""Electronic mail module: Integrated Hub Mailbox, Internet Email (IMAP/SMTP), and Host Mailto."""

import email
import email.policy
import pathlib
import urllib.parse
from ..mail_service import MailManager

_context = None
_manager = None


def get_mail_manager():
    global _manager
    if _manager is None and _context is not None:
        mail_dir = _context.fs.get("mail", pathlib.Path.home() / "RetroSerialHub" / "mail")
        _manager = MailManager(
            mail_dir=mail_dir,
            bus=_context.bus,
            session=_context.session,
        )
    return _manager


def init(context):
    global _context, _manager
    _context = context
    _context.fs.setdefault("mail", pathlib.Path.home() / "RetroSerialHub" / "mail")
    _manager = MailManager(
        mail_dir=_context.fs["mail"],
        bus=_context.bus,
        session=_context.session,
    )


def register_commands(registry):
    context = _context

    def mail_command(args):
        mgr = get_mail_manager()
        cols = getattr(context.session, "cols", 80) if context and context.session else 80
        root = context.fs["mail"]
        root.mkdir(parents=True, exist_ok=True)

        if not args or args[0].lower() in ("inbox", "list"):
            mode = mgr.get_mode()
            if mode == "internet":
                ok, output = mgr.get_internet_inbox(count=10, columns=cols)
                return output
            else:
                return mgr.format_hub_inbox(columns=cols)

        sub = args[0].lower()

        if sub == "hub":
            return mgr.format_hub_inbox(columns=cols)

        if sub in ("net", "imap", "internet"):
            ok, output = mgr.get_internet_inbox(count=10, columns=cols)
            return output

        if sub == "mode":
            if len(args) > 1:
                target_mode = args[1].lower()
                if target_mode in ("hub", "local"):
                    cfg = mgr.get_config()
                    cfg["default_mode"] = "hub"
                    mgr.save_config(cfg)
                    return "Default mail mode set to: Integrated Hub Mailbox."
                elif target_mode in ("net", "internet", "imap", "smtp"):
                    cfg = mgr.get_config()
                    cfg["default_mode"] = "internet"
                    mgr.save_config(cfg)
                    return "Default mail mode set to: Internet Email (IMAP/SMTP)."
            cur = mgr.toggle_mode()
            return f"Toggled default mail mode to: {'Integrated Hub Mail' if cur == 'hub' else 'Internet Email (IMAP/SMTP)'}."

        if sub in ("popup", "gui", "auth"):
            ok, msg = mgr.launch_host_gui_auth()
            return msg

        if sub == "config":
            cfg = mgr.get_config()
            cur_mode = mgr.get_mode()
            return (
                f"Mail Mode:   {'Integrated Hub Mailbox' if cur_mode == 'hub' else 'Internet Email (IMAP/SMTP)'}\n"
                f"IMAP Server: {cfg.get('imap_host', '(not configured)')}:{cfg.get('imap_port', 993)}\n"
                f"IMAP User:   {cfg.get('imap_user', '(not configured)')}\n"
                f"SMTP Server: {cfg.get('smtp_host', '(not configured)')}:{cfg.get('smtp_port', 587)}\n"
                f"SMTP User:   {cfg.get('smtp_user', '(not configured)')}"
            )

        if sub == "mailto":
            if len(args) < 2:
                return "Usage: mail mailto <address> [subject]"
            address = args[1]
            subject = " ".join(args[2:])
            url = "mailto:" + urllib.parse.quote(address, safe="@.+-")
            if subject:
                url += "?subject=" + urllib.parse.quote(subject)
            if context and context.host_env:
                context.host_env.open_url(url)
            return f"Opened the host mail application for {address}."

        if sub == "delete":
            if len(args) < 2:
                return "Usage: mail delete <message_id>"
            try:
                mid = int(args[1])
                ok = mgr.delete_hub_message(mid)
                return f"Message #{mid} deleted." if ok else f"Message #{mid} not found."
            except ValueError:
                return f"Invalid message ID: {args[1]}"

        if sub == "send":
            if len(args) < 2:
                return "Usage: mail send <address> <subject> [| body]"
            target = args[1]
            rest = " ".join(args[2:])
            if "|" in rest:
                subj, body = rest.split("|", 1)
                subj = subj.strip()
                body = body.strip()
            else:
                subj = rest.strip()
                body = ""

            mode = mgr.get_mode()
            # If target has @ and SMTP configured, or in internet mode
            if ("@" in target and mgr.is_internet_configured()) or mode == "internet":
                ok, res = mgr.send_internet_email(target, subj, body)
                return res
            else:
                # Integrated Hub mail
                new_msg = mgr.send_hub_message(target, subj, body)
                return f"Message #{new_msg['id']} sent to Hub Mailbox from {new_msg['from']}."

        if sub in ("read", "open"):
            if len(args) < 2:
                return mail_command(["inbox"])
            target = args[1]

            # Try hub mail by numeric ID first
            if target.isdigit():
                hub_m = mgr.get_hub_message(int(target))
                if hub_m:
                    return mgr.format_hub_message(hub_m, columns=cols)
                # If internet mode is active, try reading via IMAP
                if mgr.get_mode() == "internet" and mgr.is_internet_configured():
                    ok, res = mgr.read_internet_message(target, columns=cols)
                    if ok:
                        return res

            # Check local file or legacy .eml
            path = root / target
            if not path.is_file():
                names = sorted(path.name for path in root.iterdir() if path.suffix.lower() in (".eml", ".txt"))
                if target.isdigit() and 1 <= int(target) <= len(names):
                    path = root / names[int(target) - 1]
            if path.is_file() and path.parent.resolve() == root.resolve():
                if path.suffix.lower() == ".eml":
                    message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
                    body = message.get_body(preferencelist=("plain",))
                    content = body.get_content() if body else "(No plain-text body.)"
                    return f"From: {message.get('From', '')}\nSubject: {message.get('Subject', '')}\n\n{content}"
                return path.read_text(encoding="utf-8", errors="replace")

            return f"Mail message not found: {args[1]}"

        return "Usage: mail [inbox] | mail hub | mail net | mail read <id> | mail send <to> <subj> | mail delete <id> | mail mode [hub|net] | mail popup | mail mailto <addr>"

    registry.register_command("mail", mail_command)


def register_menu(menu):
    menu.append(("mail", "Electronic Mail"))


def handle_event(event):
    return None
