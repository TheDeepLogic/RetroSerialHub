"""Persistent, multi-frequency task scheduler for Retro Serial OS."""

from __future__ import annotations

import calendar
import datetime
import json
import logging
import os
import pathlib
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("retro_os.scheduler")

MODULE_USAGE_INFO: Dict[str, Dict[str, Any]] = {
    "weather": {
        "description": "Fetch current weather conditions and forecasts.",
        "usage": "weather [location]",
        "examples": ["weather", "weather Austin", "weather 90210"],
    },
    "news": {
        "description": "Fetch current headlines or read news articles (NPR, Hacker News, BBC).",
        "usage": "news [npr|hn|bbc] [count] | news <number>",
        "examples": ["news", "news npr 6", "news 1", "news bbc 6"],
    },
    "mail": {
        "description": "Host email sending and reading of local saved messages.",
        "usage": "mail inbox | mail read <message_number_or_name> | mail send <address> [subject]",
        "examples": ["mail inbox", "mail read 1", "mail send user@example.com Alert"],
    },
    "apps": {
        "description": "Host application scanner and search.",
        "usage": "apps [refresh | <letter> | <filter>]",
        "examples": ["apps refresh", "apps c", "apps note"],
    },
    "launch": {
        "description": "Launch a host application by name, stem, or path.",
        "usage": "launch <app> [args...]",
        "examples": ["launch notepad", "launch calc"],
    },
    "view": {
        "description": "Extract text and view documents (PDF, DOCX, XLSX, TXT, CSV, or Web URLs).",
        "usage": "view <file_path_or_url>",
        "examples": ["view sample.txt", "view report.pdf", "view https://wttr.in/Austin?format=3", "view https://example.com/news.txt"],
    },
    "fetch": {
        "description": "Download a file or web document from the internet to the hub files directory.",
        "usage": "fetch <url> [destination_filename]",
        "examples": ["fetch https://example.com/news.txt", "fetch https://example.com/bulletin.pdf daily.pdf"],
    },
    "fetchview": {
        "description": "Download a web document or file and immediately display its text to the terminal.",
        "usage": "fetchview <url>",
        "examples": ["fetchview https://wttr.in/NewYork?format=4", "fetchview https://example.com/daily.txt"],
    },
    "calc": {
        "description": "Evaluate an arithmetic expression.",
        "usage": "calc <expression>",
        "examples": ["calc 15 * 24", "calc 2 ** 10", "calc (50+25)/3"],
    },
    "print": {
        "description": "Send a file or document to the host operating system printer.",
        "usage": "print <file_path>",
        "examples": ["print memo.txt", "print C:/notes/todo.txt"],
    },
    "games": {
        "description": "Text-mode retro games (Minesweeper and Solitaire).",
        "usage": "games minesweeper new [rows cols mines] | games solitaire [new|draw|move <src> <dst>]",
        "examples": ["games minesweeper new 8 8 10", "games solitaire new"],
    },
    "ascii_viewer": {
        "description": "Image-to-ASCII preview generator for retro terminals.",
        "usage": "ascii_viewer <image_file>",
        "examples": ["ascii_viewer logo.png", "ascii_viewer photo.jpg"],
    },
    "kb": {
        "description": "Manage keyboard bridge profiles and shortcut mappings.",
        "usage": "kb profiles | kb profile <name> | kb map <key> <action>",
        "examples": ["kb profiles", "kb profile apple2", "kb map CTRL+W WIN"],
    },
    "notes": {
        "description": "Notes system commands.",
        "usage": "notes (interactive notes module)",
        "examples": ["notes"],
    },
    "textlib": {
        "description": "Text library document browser.",
        "usage": "textlib (interactive text library)",
        "examples": ["textlib"],
    },
    "bbs": {
        "description": "Bulletin Board System directory and dialer.",
        "usage": "bbs (interactive BBS directory)",
        "examples": ["bbs"],
    },
    "browser": {
        "description": "Web browser module.",
        "usage": "browser (interactive web browser)",
        "examples": ["browser"],
    },
    "telnet": {
        "description": "Telnet client module.",
        "usage": "telnet [host [port]]",
        "examples": ["telnet telehack.com 23"],
    },
    "ftp": {
        "description": "FTP file transfer client.",
        "usage": "ftp (interactive FTP client)",
        "examples": ["ftp"],
    },
    "ai": {
        "description": "ChatGPT AI assistant for vintage terminals.",
        "usage": "ai (interactive AI assistant)",
        "examples": ["ai"],
    },
    "shortcut": {
        "description": "Run, add, list, or delete custom user shortcuts.",
        "usage": "shortcut [list | add <name> <command...> | del <id> | run <id>]",
        "examples": ["shortcut list", "shortcut run 1", "shortcut add Weather view https://wttr.in/?0"],
    },
    "broadcast": {
        "description": "Send a real-time message or alert to all connected terminals.",
        "usage": "broadcast <message> | msg <message> | alert <message>",
        "examples": [
            "broadcast System update complete",
            "news : weather Austin : broadcast Morning briefing complete",
        ],
    },
    "notify": {
        "description": "Send a real-time notification to connected terminals.",
        "usage": "notify <message>",
        "examples": ["notify System backup starting"],
    },
    "msg": {
        "description": "Send a real-time message to connected terminals.",
        "usage": "msg <message>",
        "examples": ["msg Hello terminals"],
    },
    "alert": {
        "description": "Send a real-time alert to connected terminals.",
        "usage": "alert <message>",
        "examples": ["alert Scheduled maintenance in 5 minutes"],
    },
}


def calculate_next_run(
    schedule_type: str,
    params: Dict[str, Any],
    from_time: Optional[datetime.datetime] = None,
) -> datetime.datetime:
    """Calculate the next execution timestamp based on schedule type and parameters."""
    base = from_time or datetime.datetime.now()
    st = schedule_type.lower()
    if st == "interval":
        minutes = max(1, int(params.get("every", 1)))
        return base + datetime.timedelta(minutes=minutes)
    elif st == "hourly":
        target_min = int(params.get("minute", 0)) % 60
        candidate = base.replace(minute=target_min, second=0, microsecond=0)
        if candidate <= base:
            candidate += datetime.timedelta(hours=1)
        return candidate
    elif st == "daily":
        time_str = params.get("time", "00:00")
        parts = time_str.split(":")
        hh = int(parts[0]) % 24
        mm = int(parts[1]) % 60 if len(parts) > 1 else 0
        candidate = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if candidate <= base:
            candidate += datetime.timedelta(days=1)
        return candidate
    elif st == "weekly":
        time_str = params.get("time", "00:00")
        parts = time_str.split(":")
        hh = int(parts[0]) % 24
        mm = int(parts[1]) % 60 if len(parts) > 1 else 0
        target_day = params.get("weekday", 0)
        if isinstance(target_day, str):
            day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            target_day = next((i for i, d in enumerate(day_names) if d in target_day.lower()), 0)
        days_ahead = (target_day - base.weekday()) % 7
        candidate = (base + datetime.timedelta(days=days_ahead)).replace(
            hour=hh, minute=mm, second=0, microsecond=0
        )
        if candidate <= base:
            candidate += datetime.timedelta(days=7)
        return candidate
    elif st == "monthly":
        time_str = params.get("time", "00:00")
        parts = time_str.split(":")
        hh = int(parts[0]) % 24
        mm = int(parts[1]) % 60 if len(parts) > 1 else 0
        target_day = max(1, min(31, int(params.get("day", 1))))
        year = base.year
        month = base.month
        max_day = calendar.monthrange(year, month)[1]
        day = min(target_day, max_day)
        candidate = base.replace(day=day, hour=hh, minute=mm, second=0, microsecond=0)
        if candidate <= base:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            max_day = calendar.monthrange(year, month)[1]
            day = min(target_day, max_day)
            candidate = datetime.datetime(year, month, day, hh, mm, 0)
        return candidate
    return base + datetime.timedelta(minutes=60)


class TaskScheduler:
    """Thread-safe persistent task scheduler with broadcast capability."""

    def __init__(
        self,
        filepath: pathlib.Path | str,
        executor: Optional[Callable[[str], str]] = None,
        broadcaster: Optional[Callable[[Dict[str, Any], str], None]] = None,
        bus: Any = None,
    ):
        self.filepath = pathlib.Path(filepath)
        self.executor = executor
        self.broadcaster = broadcaster
        self.bus = bus
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.load()

    def load(self):
        with self._lock:
            if self.filepath.is_file():
                try:
                    data = json.loads(self.filepath.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        entries = data.items()
                    elif isinstance(data, list):
                        entries = ((str(idx), item) for idx, item in enumerate(data, 1))
                    else:
                        raise ValueError("Tasks must be a JSON object or list.")
                    self._tasks = {}
                    for key, item in entries:
                        try:
                            if not isinstance(item, dict):
                                raise ValueError("Task must be an object.")
                            if not isinstance(item.get("command"), str):
                                raise ValueError("Task command must be text.")
                            # Validate each schedule independently so one damaged
                            # entry cannot stop every background job.
                            calculate_next_run(item["schedule_type"], item.get("params", {}))
                            task_id = str(item.get("id", key))
                            if task_id in self._tasks:
                                raise ValueError("Duplicate task ID.")
                            self._tasks[task_id] = dict(item, id=task_id)
                        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
                            logger.warning("Skipping invalid task %s in %s: %s", key, self.filepath, exc)
                except Exception as exc:
                    logger.warning("Failed to load tasks from %s: %s", self.filepath, exc)
                    self._tasks = {}
            else:
                self._tasks = {}

    def save(self):
        with self._lock:
            temporary_path = None
            try:
                self.filepath.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.filepath.parent,
                    prefix=self.filepath.name + ".", suffix=".tmp", delete=False,
                ) as output:
                    temporary_path = pathlib.Path(output.name)
                    json.dump(self._tasks, output, indent=2)
                    output.write("\n")
                    output.flush()
                    os.fsync(output.fileno())
                temporary_path.replace(self.filepath)
            except Exception as exc:
                logger.error("Failed to save tasks to %s: %s", self.filepath, exc)
            finally:
                if temporary_path is not None:
                    try:
                        temporary_path.unlink(missing_ok=True)
                    except OSError as exc:
                        logger.warning("Failed to remove temporary task file %s: %s", temporary_path, exc)

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: str(t.get("id", "")))

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._tasks.get(str(task_id))

    def add_task(
        self,
        name: str,
        command: str,
        schedule_type: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        broadcast: bool = True,
        show_output: bool = True,
        enabled: bool = True,
        frequency: Optional[str] = None,
        interval_minutes: Optional[int] = None,
        run_time: Optional[str] = None,
        day_of_week: Optional[Any] = None,
        day_of_month: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        with self._lock:
            if frequency is not None and schedule_type is None:
                freq_lower = str(frequency).lower()
                if freq_lower in ("minute", "minutes", "interval"):
                    schedule_type = "interval"
                    params = {"every": interval_minutes or 15}
                elif freq_lower == "hourly":
                    schedule_type = "hourly"
                    minute = 0
                    if run_time and ":" in run_time:
                        try:
                            minute = int(run_time.split(":")[1])
                        except ValueError:
                            pass
                    params = {"minute": minute}
                elif freq_lower == "daily":
                    schedule_type = "daily"
                    params = {"time": run_time or "08:00"}
                elif freq_lower == "weekly":
                    schedule_type = "weekly"
                    params = {"time": run_time or "08:00", "weekday": day_of_week or "mon"}
                elif freq_lower == "monthly":
                    schedule_type = "monthly"
                    params = {"time": run_time or "08:00", "day": day_of_month or 1}
                else:
                    schedule_type = "interval"
                    params = {"every": interval_minutes or 15}

            schedule_type = schedule_type or "interval"
            params = params or {}

            next_id = 1
            existing_ids = [int(k) for k in self._tasks.keys() if k.isdigit()]
            if existing_ids:
                next_id = max(existing_ids) + 1
            task_id = str(next_id)

            next_run_dt = calculate_next_run(schedule_type, params)
            task = {
                "id": task_id,
                "name": name,
                "command": command,
                "schedule_type": schedule_type,
                "params": params,
                "broadcast": broadcast,
                "show_output": show_output,
                "enabled": enabled,
                "last_run": None,
                "next_run": next_run_dt.isoformat(),
                "last_status": "Pending",
            }
            self._tasks[task_id] = task
            self.save()
            return task

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            s_id = str(task_id)
            if s_id in self._tasks:
                del self._tasks[s_id]
                self.save()
                return True
            return False

    def toggle_task(self, task_id: str) -> Optional[bool]:
        with self._lock:
            s_id = str(task_id)
            task = self._tasks.get(s_id)
            if task is not None:
                task["enabled"] = not task.get("enabled", True)
                if task["enabled"]:
                    task["next_run"] = calculate_next_run(
                        task["schedule_type"], task.get("params", {})
                    ).isoformat()
                self.save()
                return task["enabled"]
            return None

    def execute_task(self, task: Dict[str, Any]) -> str:
        command = task.get("command", "")
        output = ""
        status = "OK"
        if self.executor:
            try:
                output = self.executor(command)
                status = "OK"
            except Exception as exc:
                output = f"Execution error: {exc}"
                status = f"Error: {exc}"
        else:
            output = f"(No executor configured) Command: {command}"

        with self._lock:
            task["last_run"] = datetime.datetime.now().isoformat()
            task["last_status"] = status
            next_dt = calculate_next_run(task["schedule_type"], task.get("params", {}))
            task["next_run"] = next_dt.isoformat()
            self.save()

        if self.bus:
            try:
                self.bus.publish("scheduler.run", {"task": task, "output": output})
            except Exception:
                pass

        if task.get("broadcast") and self.broadcaster:
            try:
                self.broadcaster(task, output)
            except Exception as exc:
                logger.warning("Broadcaster error for task %s: %s", task.get("id"), exc)

        return output

    def run_task_now(self, task_id: str) -> str:
        with self._lock:
            task = self._tasks.get(str(task_id))
            if task is None:
                return f"Task ID {task_id} not found."
        return self.execute_task(task)

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._worker_loop, name="retro-os-scheduler", daemon=True
            )
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False

    def _worker_loop(self):
        while self._running:
            now = datetime.datetime.now()
            due_tasks = []
            with self._lock:
                for task in self._tasks.values():
                    if not task.get("enabled", True):
                        continue
                    next_run_str = task.get("next_run")
                    if not next_run_str:
                        next_dt = calculate_next_run(task["schedule_type"], task.get("params", {}))
                        task["next_run"] = next_dt.isoformat()
                        continue
                    try:
                        next_dt = datetime.datetime.fromisoformat(next_run_str)
                        # Persisted times use the host's local, naive clock.
                        # An edited offset-aware value cannot be compared to it.
                        if next_dt.tzinfo is not None:
                            next_dt = next_dt.astimezone().replace(tzinfo=None)
                    except (TypeError, ValueError, OverflowError):
                        next_dt = calculate_next_run(task["schedule_type"], task.get("params", {}))
                        task["next_run"] = next_dt.isoformat()
                    if now >= next_dt:
                        due_tasks.append(task)

            for task in due_tasks:
                try:
                    self.execute_task(task)
                except Exception as exc:
                    logger.error("Error executing task %s: %s", task.get("id"), exc)

            time.sleep(1.0)
