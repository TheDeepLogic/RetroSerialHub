"""Core session, shell, event bus, and loadable-module primitives."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import shlex
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

_MODULE_INITIALIZATION_LOCK = threading.RLock()


class EventBus:
    """Thread-safe topic-based event delivery."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable[[Any], Any]]] = {}
        self._lock = threading.RLock()

    def subscribe(self, topic: str, handler: Callable[[Any], Any]):
        if not topic or not callable(handler):
            raise ValueError("A topic and callable handler are required.")
        with self._lock:
            self._subscribers.setdefault(topic, []).append(handler)

        def unsubscribe():
            with self._lock:
                handlers = self._subscribers.get(topic, [])
                if handler in handlers:
                    handlers.remove(handler)

        return unsubscribe

    def publish(self, topic: str, event: Any = None):
        with self._lock:
            handlers = tuple(self._subscribers.get(topic, ()))
        results = []
        for handler in handlers:
            result = handler(event)
            if inspect.isawaitable(result):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(result)
                else:
                    results.append(loop.create_task(result))
            else:
                results.append(result)
        return results

    async def publish_async(self, topic: str, event: Any = None):
        with self._lock:
            handlers = tuple(self._subscribers.get(topic, ()))
        results = []
        for handler in handlers:
            result = handler(event)
            results.append(await result if inspect.isawaitable(result) else result)
        return results


@dataclass
class Session:
    """State scoped to one serial or TCP terminal client."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_type: str = "serial"
    cols: int = 80
    rows: int = 24
    user: str | None = None
    state: str = "connected"
    active_module: str | None = None
    kb_profile: str = "default"
    caps_only: bool = False
    pace_delay: float = 0.0


@dataclass
class ModuleContext:
    session: Session
    fs: dict[str, Path]
    bus: EventBus
    host_env: Any
    activate_module: Callable[[str], Any] | None = None


class Shell:
    """Small shell whose command handlers receive a list of arguments."""

    def __init__(self):
        self._commands: dict[str, Callable[[list[str]], Any]] = {}
        self.register_command("help", lambda _args: self.help())

    def register_command(self, name: str, handler: Callable[[list[str]], Any]):
        key = name.strip().lower()
        if not key or not callable(handler):
            raise ValueError("A command name and callable handler are required.")
        self._commands[key] = handler

    @staticmethod
    def split_line(line: str) -> list[str]:
        lex = shlex.shlex(line, posix=True)
        lex.whitespace_split = True
        lex.commenters = ""
        lex.escape = ""
        return list(lex)

    def execute(self, line: str):
        try:
            parts = self.split_line(line)
        except ValueError as exc:
            return f"Syntax error: {exc}"
        if not parts:
            return ""
        handler = self._commands.get(parts[0].lower())
        if handler is None:
            return f"Unknown command: {parts[0]}. Type 'help' for commands."
        result = handler(parts[1:])
        return "" if result is None else str(result)

    def help(self):
        return "Commands: " + ", ".join(self.command_names())

    def command_names(self) -> tuple[str, ...]:
        """Return the commands currently available in this shell."""
        return tuple(sorted(self._commands))


class ModuleLoader:
    """Initialize application modules and support explicit hot reloads."""

    def __init__(self, context: ModuleContext, shell: Shell):
        self.context = context
        self.shell = shell
        self.menu: list[tuple[str, str]] = []
        self.modules: dict[str, Any] = {}

    def load(self, name: str, *, reload_module: bool = False):
        # Modules expose init/register hooks through shared Python modules.
        # Keep those hooks together while simultaneous terminal sessions start.
        with _MODULE_INITIALIZATION_LOCK:
            return self._load(name, reload_module=reload_module)

    def _load(self, name: str, *, reload_module: bool = False):
        module = importlib.import_module(f"retro_os.modules.{name}")
        if reload_module:
            module = importlib.reload(module)
        for method in ("init", "register_commands", "register_menu", "handle_event"):
            if not callable(getattr(module, method, None)):
                raise TypeError(f"Module {name!r} does not implement {method}().")
        module.init(self.context)
        module.register_commands(self.shell)
        module.register_menu(self.menu)
        self.modules[name] = module
        return module

    def load_all(self, names):
        return [self.load(name) for name in names]

    def dispatch_event(self, event):
        for module in tuple(self.modules.values()):
            module.handle_event(event)
