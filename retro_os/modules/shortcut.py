"""Shortcut module for Retro Serial OS."""

from __future__ import annotations

import shlex

_context = None


def init(context):
    global _context
    _context = context


def register_commands(registry):
    context = _context

    def shortcut_cmd(args):
        mgr = getattr(context.host_env, "shortcuts_manager", None)
        if not mgr:
            return "Shortcuts manager not available."

        if not args or args[0].lower() in ("list", "show"):
            shortcuts = mgr.list_shortcuts()
            if not shortcuts:
                return "No shortcuts configured. Use 'shortcut add <name> <command>' to create one."
            lines = ["Configured Shortcuts:"]
            for idx, sc in enumerate(shortcuts):
                letter = chr(ord("A") + idx)
                lines.append(f"[{letter} / {sc['id']}] {sc['name']}: {sc['command']}")
            lines.append("\nRun shortcut via 'shortcut run <letter_or_id>' or from Main Menu [0] Shortcuts.")
            return "\n".join(lines)

        sub = args[0].lower()
        if sub in ("add", "new", "create"):
            if len(args) < 3:
                return "Usage: shortcut add <name> <command with args...>"
            name = args[1]
            cmd = " ".join(args[2:])
            sc = mgr.add_shortcut(name, cmd)
            return f"Shortcut '{sc['name']}' added (runs '{sc['command']}')."

        if sub in ("del", "delete", "remove", "rm"):
            if len(args) < 2:
                return "Usage: shortcut del <letter_or_id_or_name>"
            target = args[1]
            if mgr.delete_shortcut(target):
                return f"Shortcut '{target}' deleted."
            return f"Shortcut '{target}' not found."

        if sub in ("run", "exec"):
            if len(args) < 2:
                return "Usage: shortcut run <letter_or_id_or_name>"
            target = args[1]
            sc = mgr.get_shortcut(target)
            if not sc:
                return f"Shortcut '{target}' not found."
            cmd = sc["command"]
            shell = getattr(context.host_env, "shell", None)
            if shell:
                return shell.execute(cmd)
            return f"Running shortcut: {cmd}"

        # If user ran `shortcut <letter_or_id>` directly
        sc = mgr.get_shortcut(args[0])
        if sc:
            shell = getattr(context.host_env, "shell", None)
            if shell:
                return shell.execute(sc["command"])
            return f"Running shortcut: {sc['command']}"

        return "Usage: shortcut [list | add <name> <command> | del <target> | run <target>]"

    registry.register_command("shortcut", shortcut_cmd)
    registry.register_command("shortcuts", shortcut_cmd)


def register_menu(menu):
    menu.append(("shortcut", "shortcut"))


def handle_event(event):
    return None
