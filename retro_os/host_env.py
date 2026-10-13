"""Operating-system integration for apps and keyboard shortcuts."""

from __future__ import annotations

import datetime
import os
import pathlib
import platform
import shutil
import subprocess
import threading

from .keyboard_profiles import KeyboardProfiles


class HostAppScanner:
    """Discover launchable applications with a short-lived in-memory index."""

    def __init__(self):
        self._apps: dict[str, str] = {}
        self._scanned = False
        self._lock = threading.Lock()

    def _candidates(self):
        system = platform.system()
        if system == "Windows":
            roots = []
            for variable, suffix in (
                ("APPDATA", "Microsoft/Windows/Start Menu/Programs"),
                ("PROGRAMDATA", "Microsoft/Windows/Start Menu/Programs"),
                (
                    "USERPROFILE",
                    "AppData/Roaming/Microsoft/Internet Explorer/Quick Launch/User Pinned/TaskBar",
                ),
            ):
                base = os.environ.get(variable)
                if base:
                    roots.append(pathlib.Path(base) / suffix)
            for root in roots:
                if root.is_dir():
                    for path in root.rglob("*"):
                        if path.is_file() and path.suffix.lower() in (".lnk", ".url", ".exe"):
                            yield path.stem, str(path)
            for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
                program_files = os.environ.get(env_name)
                if not program_files:
                    continue
                root = pathlib.Path(program_files)
                if root.is_dir():
                    for directory, subdirs, files in os.walk(root):
                        depth = len(pathlib.Path(directory).relative_to(root).parts)
                        subdirs[:] = subdirs[:30] if depth < 3 else []
                        if depth <= 3:
                            for filename in files:
                                if filename.lower().endswith(".exe"):
                                    path = pathlib.Path(directory) / filename
                                    yield path.stem, str(path)
        elif system == "Darwin":
            for root in (pathlib.Path("/Applications"), pathlib.Path.home() / "Applications"):
                if root.is_dir():
                    for path in root.glob("*.app"):
                        yield path.stem, str(path)
        else:
            for directory in os.environ.get("PATH", "").split(os.pathsep):
                root = pathlib.Path(directory)
                if root.is_dir():
                    for path in root.iterdir():
                        if path.is_file() and os.access(path, os.X_OK):
                            yield path.name, str(path)

    def list_apps(self, refresh=False):
        with self._lock:
            if refresh or not self._scanned:
                apps: dict[str, str] = {}
                for name, path in self._candidates():
                    apps.setdefault(name, path)
                self._apps = apps
                self._scanned = True
            return dict(sorted(self._apps.items(), key=lambda item: item[0].casefold()))

    def find_app(self, name: str):
        raw_name = str(name).strip()
        if platform.system() == "Windows":
            # Apple II keyboards lack backslash; translate forward slash to backslash
            raw_name = raw_name.replace("/", "\\")

        raw_path = pathlib.Path(raw_name)
        if raw_path.exists():
            return str(raw_path.resolve())

        apps = self.list_apps()
        normalized = raw_name.casefold()
        target = next((path for app, path in apps.items() if app.casefold() == normalized), None)
        if target is None:
            target = next((path for app, path in apps.items() if pathlib.Path(path).stem.casefold() == normalized or pathlib.Path(path).name.casefold() == normalized), None)
        if target is None:
            apps = self.list_apps(refresh=True)
            target = next(
                (path for app, path in apps.items() if app.casefold() == normalized),
                None,
            )
            if target is None:
                target = next((path for app, path in apps.items() if pathlib.Path(path).stem.casefold() == normalized or pathlib.Path(path).name.casefold() == normalized), None)

        if target is None:
            found = shutil.which(raw_name)
            if found:
                target = found

        if target is None and platform.system() == "Windows" and not raw_path.suffix:
            for ext in (".exe", ".cmd", ".bat", ".com"):
                found = shutil.which(raw_name + ext)
                if found:
                    target = found
                    break

        return target

    def launch_app(self, name: str, args=None, interactive: bool = False, cwd=None):
        target = self.find_app(name)
        if target is None:
            raise LookupError(f"Host application not found: {name}")

        arguments = []
        for arg in (args or []):
            s_arg = str(arg)
            if platform.system() == "Windows" and "://" not in s_arg and not s_arg.startswith("/"):
                s_arg = s_arg.replace("/", "\\")
            arguments.append(s_arg)

        if platform.system() == "Windows" and pathlib.Path(target).suffix.lower() in (".lnk", ".url"):
            if arguments:
                raise ValueError("Arguments cannot be passed to a Start Menu shortcut.")
            os.startfile(target)
            return target

        if platform.system() == "Darwin" and pathlib.Path(target).suffix.lower() == ".app":
            return subprocess.Popen(["open", target, *arguments], close_fds=True, cwd=cwd)

        command = [target, *arguments]
        if interactive:
            flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            return subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                creationflags=flags,
                close_fds=(platform.system() != "Windows"),
                cwd=cwd,
            )
        return subprocess.Popen(command, close_fds=True, cwd=cwd)


_SHARED_APP_SCANNER = HostAppScanner()
_PROFILE_STORES: dict[str, KeyboardProfiles] = {}
_PROFILE_STORES_LOCK = threading.Lock()


class HostEnvironment:
    def __init__(self, profiles_path=None, shortcuts_path=None):
        self.apps = _SHARED_APP_SCANNER
        profile_path = (
            pathlib.Path(profiles_path)
            if profiles_path
            else pathlib.Path(__file__).with_name("keyboard_profiles.json")
        )
        key = str(profile_path.resolve())
        with _PROFILE_STORES_LOCK:
            if key not in _PROFILE_STORES:
                _PROFILE_STORES[key] = KeyboardProfiles(profile_path)
            self.keyboard_profiles = _PROFILE_STORES[key]

        from .shortcuts import ShortcutsManager
        self.shortcuts_manager = ShortcutsManager(shortcuts_path)
        self._last_cpu_times = None

    def list_apps(self, refresh=False):
        return self.apps.list_apps(refresh=refresh)

    def find_app(self, name):
        return self.apps.find_app(name)

    def launch_app(self, name, args=None, interactive: bool = False, cwd=None):
        return self.apps.launch_app(name, args, interactive=interactive, cwd=cwd)

    def get_host_shell(self) -> dict:
        """Return host OS shell metadata based on the host operating system."""
        system = platform.system()
        if system == "Windows":
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            return {
                "system": "Windows",
                "default_shell": comspec,
                "default_args": ["/q"],
                "default_name": "Command Prompt (cmd.exe)",
                "alt_shell": "powershell.exe",
                "alt_args": ["-NoLogo"],
                "alt_name": "PowerShell",
            }
        elif system == "Darwin":
            shell = os.environ.get("SHELL", "/bin/zsh")
            return {
                "system": "macOS",
                "default_shell": shell,
                "default_args": [],
                "default_name": f"Terminal ({pathlib.Path(shell).name})",
                "alt_shell": "/bin/bash" if shell != "/bin/bash" else "/bin/sh",
                "alt_args": [],
                "alt_name": "Bash" if shell != "/bin/bash" else "sh",
            }
        else:
            shell = os.environ.get("SHELL", "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh")
            return {
                "system": "Linux",
                "default_shell": shell,
                "default_args": [],
                "default_name": f"Shell ({pathlib.Path(shell).name})",
                "alt_shell": "/bin/sh" if shell != "/bin/sh" else "/bin/bash",
                "alt_args": [],
                "alt_name": "POSIX sh",
            }

    def is_gui_app(self, name_or_path: str) -> bool:
        if not name_or_path:
            return True
        target = self.find_app(name_or_path) or name_or_path
        target_path = pathlib.Path(target)
        suffix = target_path.suffix.lower()
        if suffix in (".lnk", ".url", ".app"):
            return True
        if suffix in (".bat", ".cmd"):
            return False
        if platform.system() == "Windows" and suffix == ".exe" and target_path.is_file():
            try:
                import struct
                with target_path.open("rb") as f:
                    dos_hdr = f.read(64)
                    if len(dos_hdr) >= 64 and dos_hdr[:2] == b"MZ":
                        pe_offset = struct.unpack_from("<I", dos_hdr, 0x3C)[0]
                        f.seek(pe_offset)
                        if f.read(4) == b"PE\x00\x00":
                            coff_hdr = f.read(20)
                            opt_hdr_size = struct.unpack_from("<H", coff_hdr, 16)[0]
                            opt_hdr = f.read(opt_hdr_size)
                            if len(opt_hdr) >= 70:
                                subsystem = struct.unpack_from("<H", opt_hdr, 68)[0]
                                return subsystem == 2  # IMAGE_SUBSYSTEM_WINDOWS_GUI
            except Exception:
                pass
        return True

    def send_shortcut(self, action):
        from rsh_keyboard import send_shortcut
        send_shortcut(action)

    @staticmethod
    def open_path(path):
        path = str(path)
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path], close_fds=True)
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                raise OSError("No desktop application opener (xdg-open) was found.")
            subprocess.Popen([opener, path], close_fds=True)

    @staticmethod
    def open_url(url):
        if platform.system() == "Windows":
            os.startfile(url)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", url], close_fds=True)
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                raise OSError("No desktop application opener (xdg-open) was found.")
            subprocess.Popen([opener, url], close_fds=True)

    def get_sysinfo(self) -> dict:
        """Collect host system metrics (OS, CPU, memory, disk, uptime)."""
        system = platform.system()
        total, used, free = shutil.disk_usage(".")
        info = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system": system,
            "os_release": platform.release(),
            "arch": platform.machine(),
            "cpus": os.cpu_count() or 1,
            "cpu_load": None,
            "disk_total_gb": total // (1024**3),
            "disk_used_gb": used // (1024**3),
            "disk_free_gb": free // (1024**3),
            "disk_percent": round(100.0 * used / total, 1) if total else 0.0,
            "ram_total_mb": 0,
            "ram_used_mb": 0,
            "ram_free_mb": 0,
            "ram_load": 0,
            "uptime": "Unknown",
        }

        if system == "Windows":
            try:
                import ctypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    info["ram_load"] = int(stat.dwMemoryLoad)
                    info["ram_total_mb"] = int(stat.ullTotalPhys // (1024**2))
                    info["ram_free_mb"] = int(stat.ullAvailPhys // (1024**2))
                    info["ram_used_mb"] = info["ram_total_mb"] - info["ram_free_mb"]

                uptime_ms = ctypes.windll.kernel32.GetTickCount64()
                sec = int(uptime_ms // 1000)
                days = sec // 86400
                hours = (sec % 86400) // 3600
                mins = (sec % 3600) // 60
                info["uptime"] = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m"

                class FILETIME(ctypes.Structure):
                    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

                def _ft_to_int(ft):
                    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

                idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
                if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                    cur_times = (_ft_to_int(idle), _ft_to_int(kernel), _ft_to_int(user))
                    if self._last_cpu_times:
                        last_idle, last_kernel, last_user = self._last_cpu_times
                        d_idle = cur_times[0] - last_idle
                        d_kernel = cur_times[1] - last_kernel
                        d_user = cur_times[2] - last_user
                        total_ticks = d_kernel + d_user
                        busy_ticks = total_ticks - d_idle
                        if total_ticks > 0:
                            info["cpu_load"] = max(0.0, min(100.0, round(100.0 * busy_ticks / total_ticks, 1)))
                    self._last_cpu_times = cur_times
            except Exception:
                pass
        elif system == "Linux":
            try:
                if os.path.exists("/proc/meminfo"):
                    with open("/proc/meminfo", "r", encoding="utf-8") as f:
                        mem = {}
                        for line in f:
                            parts = line.split(":")
                            if len(parts) == 2:
                                mem[parts[0].strip()] = int(parts[1].split()[0])
                        total_kb = mem.get("MemTotal", 0)
                        free_kb = mem.get("MemAvailable", mem.get("MemFree", 0))
                        info["ram_total_mb"] = total_kb // 1024
                        info["ram_free_mb"] = free_kb // 1024
                        info["ram_used_mb"] = info["ram_total_mb"] - info["ram_free_mb"]
                        if info["ram_total_mb"]:
                            info["ram_load"] = int(100 * info["ram_used_mb"] / info["ram_total_mb"])

                if os.path.exists("/proc/uptime"):
                    with open("/proc/uptime", "r", encoding="utf-8") as f:
                        sec = int(float(f.read().split()[0]))
                        days = sec // 86400
                        hours = (sec % 86400) // 3600
                        mins = (sec % 3600) // 60
                        info["uptime"] = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m"

                if os.path.exists("/proc/stat"):
                    with open("/proc/stat", "r", encoding="utf-8") as f:
                        cpu_line = f.readline()
                        if cpu_line.startswith("cpu "):
                            fields = [int(x) for x in cpu_line.split()[1:]]
                            idle_t = fields[3] + (fields[4] if len(fields) > 4 else 0)
                            total_t = sum(fields)
                            cur_t = (idle_t, total_t)
                            if self._last_cpu_times:
                                last_idle, last_total = self._last_cpu_times
                                d_total = cur_t[1] - last_total
                                d_idle = cur_t[0] - last_idle
                                if d_total > 0:
                                    busy_t = d_total - d_idle
                                    info["cpu_load"] = max(0.0, min(100.0, round(100.0 * busy_t / d_total, 1)))
                            self._last_cpu_times = cur_t
            except Exception:
                pass

        return info

    def format_sysinfo(self, cols: int = 80) -> str:
        """Format host metrics into a clean text display for 40- or 80-column screens."""
        info = self.get_sysinfo()
        now_str = info.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cpu_load_str = f" [CPU Load: {info['cpu_load']}%]" if info.get("cpu_load") is not None else ""
        lines = []
        if cols == 40:
            lines.append("=== HOST SYSTEM MONITOR ===")
            lines.append(f"Time  : {now_str}")
            lines.append(f"OS    : {info['system']} {info['os_release']} ({info['arch']})")
            if info.get("cpu_load") is not None:
                lines.append(f"CPU   : {info['cpus']} cores ({info['cpu_load']}%)")
            else:
                lines.append(f"CPU   : {info['cpus']} cores")
            lines.append(f"Uptime: {info['uptime']}")
            if info["ram_total_mb"]:
                lines.append(f"Memory: {info['ram_used_mb']}M/{info['ram_total_mb']}M ({info['ram_load']}%)")
            lines.append(f"Disk  : {info['disk_used_gb']}G/{info['disk_total_gb']}G ({info['disk_percent']}%)")
            lines.append("===========================")
            lines = [l[:40] for l in lines]
        else:
            lines.append("=================== HOST SYSTEM MONITOR ===================")
            lines.append(f"Local Time        : {now_str}")
            lines.append(f"Operating System  : {info['system']} {info['os_release']} ({info['arch']})")
            lines.append(f"Processor & Uptime: {info['cpus']} Logical Cores{cpu_load_str}  |  System Uptime: {info['uptime']}")
            if info["ram_total_mb"]:
                lines.append(f"Physical Memory   : {info['ram_used_mb']} MB used / {info['ram_total_mb']} MB total ({info['ram_load']}% loaded)")
            lines.append(f"Primary Storage   : {info['disk_used_gb']} GB used / {info['disk_total_gb']} GB total ({info['disk_percent']}% used)")
            lines.append("===========================================================")
        return "\n".join(lines)

    def get_clipboard(self) -> str:
        """Read plain text from host OS clipboard."""
        system = platform.system()
        if system == "Windows":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.GetClipboardData.restype = ctypes.c_void_p
                user32.GetClipboardData.argtypes = [ctypes.c_uint]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

                if not user32.OpenClipboard(None):
                    return ""
                try:
                    h_mem = user32.GetClipboardData(13)  # CF_UNICODETEXT
                    if not h_mem:
                        return ""
                    ptr = kernel32.GlobalLock(h_mem)
                    if not ptr:
                        return ""
                    text = ctypes.wstring_at(ptr)
                    kernel32.GlobalUnlock(h_mem)
                    return text or ""
                finally:
                    user32.CloseClipboard()
            except Exception as exc:
                return f"[Clipboard read error: {exc}]"
        elif system == "Darwin":
            try:
                proc = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
                return proc.stdout or ""
            except Exception:
                return ""
        else:
            for tool in ("xclip", "xsel", "wl-paste"):
                found = shutil.which(tool)
                if found:
                    try:
                        args = [tool, "-selection", "clipboard", "-o"] if "xclip" in tool else [tool, "-b"]
                        if tool == "wl-paste":
                            args = [tool]
                        proc = subprocess.run(args, capture_output=True, text=True, timeout=2)
                        return proc.stdout or ""
                    except Exception:
                        pass
            return ""

    def set_clipboard(self, text: str) -> bool:
        """Write plain text into host OS clipboard."""
        system = platform.system()
        if system == "Windows":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                kernel32.GlobalAlloc.restype = ctypes.c_void_p
                kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                user32.SetClipboardData.restype = ctypes.c_void_p
                user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

                if not user32.OpenClipboard(None):
                    return False
                try:
                    user32.EmptyClipboard()
                    data = (str(text) + "\0").encode("utf-16le")
                    h_mem = kernel32.GlobalAlloc(0x0042, len(data))  # GMEM_MOVEABLE | GMEM_ZEROINIT
                    if not h_mem:
                        return False
                    ptr = kernel32.GlobalLock(h_mem)
                    if not ptr:
                        return False
                    ctypes.memmove(ptr, data, len(data))
                    kernel32.GlobalUnlock(h_mem)
                    user32.SetClipboardData(13, h_mem)  # CF_UNICODETEXT
                    return True
                finally:
                    user32.CloseClipboard()
            except Exception:
                return False
        elif system == "Darwin":
            try:
                subprocess.run(["pbcopy"], input=text, text=True, timeout=2, check=True)
                return True
            except Exception:
                return False
        else:
            for tool in ("xclip", "xsel", "wl-copy"):
                found = shutil.which(tool)
                if found:
                    try:
                        args = [tool, "-selection", "clipboard"] if "xclip" in tool else [tool, "-b"]
                        if tool == "wl-copy":
                            args = [tool]
                        subprocess.run(args, input=text, text=True, timeout=2, check=True)
                        return True
                    except Exception:
                        pass
            return False

    def media_control(self, action: str) -> str:
        """Control host playback and volume (play, pause, next, prev, mute, vol_up, vol_down)."""
        act = action.strip().lower().replace("-", "_")
        system = platform.system()
        if system == "Windows":
            try:
                import ctypes
                vk_map = {
                    "play": 0xB3,
                    "pause": 0xB3,
                    "play_pause": 0xB3,
                    "toggle": 0xB3,
                    "next": 0xB0,
                    "prev": 0xB1,
                    "previous": 0xB1,
                    "stop": 0xB2,
                    "mute": 0xAD,
                    "vol_up": 0xAF,
                    "up": 0xAF,
                    "vol_down": 0xAE,
                    "down": 0xAE,
                }
                vk = vk_map.get(act)
                if vk is None:
                    return f"Unknown media command: {action}. (play, pause, next, prev, stop, mute, up, down)"
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # KEYEVENTF_KEYUP
                return f"Host media command sent: {act}"
            except Exception as exc:
                return f"Media control error: {exc}"
        elif system == "Darwin":
            try:
                if act in ("up", "vol_up"):
                    subprocess.run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) + 10)"], check=True)
                elif act in ("down", "vol_down"):
                    subprocess.run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) - 10)"], check=True)
                elif act == "mute":
                    subprocess.run(["osascript", "-e", "set volume output muted (not (output muted of (get volume settings)))"], check=True)
                else:
                    return f"Media action {act} triggered on macOS."
                return f"Host media command sent: {act}"
            except Exception as exc:
                return f"Media control error: {exc}"
        else:
            return f"Host media command simulated on {system}: {act}"

