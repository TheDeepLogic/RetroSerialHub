"""Task scheduler module for Retro Serial OS."""

from __future__ import annotations
from rsh_storage import settings_dir, settings_path

import re
from typing import Any

from retro_os.scheduler import MODULE_USAGE_INFO, TaskScheduler

_context = None
_scheduler: TaskScheduler | None = None
_schedulers_by_path = {}


def init(context):
    global _context, _scheduler
    _context = context
    tasks_file = context.fs.get("tasks")
    if not tasks_file:
        tasks_file = settings_path("scheduled_tasks.json", context.fs.get("files", context.fs.get("notes")).parent)
    key = str(tasks_file.resolve())
    if key in _schedulers_by_path:
        context.host_env.scheduler = _schedulers_by_path[key]

    # Check if a scheduler is already created on host_env or create one
    if not hasattr(context.host_env, "scheduler") or context.host_env.scheduler is None:
        def execute_scheduled_command(command: str) -> str:
            commands = [
                item.strip()
                for item in re.split(r"\s+:\s+|\s*;\s*", command)
                if item.strip()
            ]
            outputs = []
            for item in commands:
                try:
                    cmd_to_run = f"view {item}" if item.startswith(("http://", "https://")) else item
                    res = context.host_env.shell.execute(cmd_to_run)
                    if res is not None and str(res).strip():
                        outputs.append(str(res).strip())
                except Exception as exc:
                    outputs.append(f"[{item}] Error: {exc}")
            return "\n\n".join(outputs)

        context.host_env.scheduler = TaskScheduler(
            filepath=tasks_file,
            executor=execute_scheduled_command,
            broadcaster=lambda task, out: context.bus.publish(
                "scheduler.broadcast", {"task": task, "output": out}
            ),
            bus=context.bus,
        )
        context.host_env.scheduler.start()
    _schedulers_by_path[key] = context.host_env.scheduler
    _scheduler = context.host_env.scheduler


def register_commands(registry):
    context = _context

    def schedule_cmd(args):
        scheduler = getattr(context.host_env, "scheduler", None)
        if scheduler is None:
            return "Scheduler is not initialized."

        if not args or args[0].lower() in ("list", "show"):
            tasks = scheduler.list_tasks()
            if not tasks:
                return "No scheduled tasks found. Use 'schedule add' or menu to create one."
            lines = [f"{'ID':<3} {'NAME':<16} {'SCHEDULE':<18} {'STATUS':<8} {'BCAST':<5} {'COMMAND'}"]
            lines.append("-" * min(context.session.cols, 78))
            for t in tasks:
                st = t.get("schedule_type", "")
                p = t.get("params", {})
                if st == "interval":
                    sched_str = f"every {p.get('every', 1)}m"
                elif st == "hourly":
                    sched_str = f"hourly at :{p.get('minute', 0):02d}"
                elif st == "daily":
                    sched_str = f"daily {p.get('time', '00:00')}"
                elif st == "weekly":
                    sched_str = f"weekly {p.get('weekday', 'Mon')} {p.get('time', '00:00')}"
                elif st == "monthly":
                    sched_str = f"monthly d{p.get('day', 1)} {p.get('time', '00:00')}"
                else:
                    sched_str = st
                status = "Active" if t.get("enabled", True) else "Off"
                bcast = "Yes" if t.get("broadcast", True) else "No"
                cmd = t.get("command", "")
                lines.append(f"{t.get('id', ''):<3} {t.get('name', '')[:16]:<16} {sched_str:<18} {status:<8} {bcast:<5} {cmd}")
            return "\n".join(lines)

        sub = args[0].lower()
        if sub in ("modules", "mods"):
            lines = ["Available CLI Commands for Scheduling:"]
            for command_name in context.host_env.shell.command_names():
                info = MODULE_USAGE_INFO.get(command_name)
                description = info["description"] if info else "CLI command"
                lines.append(f"  {command_name:<14} - {description}")
            lines.append("\nAny command shown by 'help' can be scheduled.")
            lines.append("Type 'schedule info <command>' for usage and examples.")
            return "\n".join(lines)

        if sub in ("info", "usage") and len(args) > 1:
            mod_name = args[1].lower()
            if mod_name not in context.host_env.shell.command_names():
                return f"Command '{mod_name}' not found. Type 'schedule modules' for list."
            info = MODULE_USAGE_INFO.get(mod_name)
            if not info:
                return (
                    f"Command: {mod_name}\n"
                    "Description: CLI command available in the current runtime.\n"
                    f"Usage:       {mod_name} [arguments...]"
                )
            lines = [
                f"Command: {mod_name}",
                f"Description: {info['description']}",
                f"Usage:       {info['usage']}",
                "Examples:",
            ]
            for ex in info.get("examples", []):
                lines.append(f"  {ex}")
            lines.append("Chain scheduled commands with ' : ' (for example: news : weather Austin).")
            return "\n".join(lines)

        if sub in ("run", "exec") and len(args) > 1:
            task_id = args[1]
            return scheduler.run_task_now(task_id)

        if sub in ("toggle", "enable", "disable") and len(args) > 1:
            task_id = args[1]
            res = scheduler.toggle_task(task_id)
            if res is None:
                return f"Task ID {task_id} not found."
            return f"Task {task_id} is now {'enabled' if res else 'disabled'}."

        if sub in ("delete", "remove", "rm") and len(args) > 1:
            task_id = args[1]
            if scheduler.remove_task(task_id):
                return f"Removed task {task_id}."
            return f"Task ID {task_id} not found."

        if sub == "add":
            if len(args) < 4:
                return (
                    "Usage: schedule add <name> <interval_minutes> <command...>\n"
                    "Chain commands with ' : '.\n"
                    "Example: schedule add MorningUpdate 15 news : weather Austin : broadcast Update complete"
                )
            name = args[1]
            try:
                every = int(args[2])
            except ValueError:
                return "Interval minutes must be a number."
            cmd = " ".join(args[3:])
            task = scheduler.add_task(
                name=name,
                command=cmd,
                schedule_type="interval",
                params={"every": every},
                broadcast=True,
                show_output=True,
            )
            return f"Scheduled task '{name}' (ID {task['id']}) every {every} minutes."

        return (
            "Usage: schedule [list] | schedule modules | schedule info <mod> | "
            "schedule run <id> | schedule toggle <id> | schedule delete <id> | "
            "schedule add <name> <minutes> <command...>\n"
            "Chain scheduled commands with ' : '."
        )

    registry.register_command("schedule", schedule_cmd)
    registry.register_command("scheduler", schedule_cmd)


def register_menu(menu):
    menu.append(("scheduler", "Task Scheduler"))


def handle_event(event):
    return None
