"""Shared host audio playback with local playlists and optional ffplay streams."""

from __future__ import annotations

import atexit
import ctypes
import os
import pathlib
import queue
import shutil
import signal
import subprocess
import threading
import time
from concurrent.futures import Future
from urllib.parse import urlparse


def is_stream(value):
    text = str(value)
    if any(character.isspace() for character in text):
        return False
    parsed = urlparse(text)
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


class AudioPlayer:
    """One playback queue for the host; all terminal commands share its lock."""

    def __init__(self):
        self.lock = threading.RLock()
        self.tracks = []
        self.index = 0
        self.volume = 70
        self.paused = False
        self.process = None
        self.native = False
        self.started = 0.0
        self.offset = 0.0
        self.pause_position = 0.0
        self.error = ""
        self._monitor_started = False
        self._mci_requests = None
        atexit.register(self.stop)

    def _mci(self, command):
        # MCI devices belong to the thread that opened them. Route every native
        # operation through one daemon, including monitor and other sessions.
        if self._mci_requests is None:
            self._mci_requests = queue.Queue()
            def worker():
                while True:
                    text, future = self._mci_requests.get()
                    try:
                        future.set_result(self._mci_direct(text))
                    except Exception as exc:
                        future.set_exception(exc)
            threading.Thread(target=worker, daemon=True, name="RSH-Audio-Native").start()
        future = Future()
        self._mci_requests.put((command, future))
        return future.result(timeout=10)

    def _mci_direct(self, command):
        library = ctypes.WinDLL("winmm")
        send = library.mciSendStringW
        send.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        send.restype = ctypes.c_uint
        output = ctypes.create_unicode_buffer(512)
        code = send(command, output, len(output), None)
        if code:
            error = ctypes.create_unicode_buffer(256)
            library.mciGetErrorStringW(code, error, len(error))
            raise OSError(error.value or f"Audio error {code}")
        return output.value

    def _close(self):
        if self.process is not None:
            if self.paused and self.process.poll() is None:
                self._suspend(False)
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
            self.process = None
        if self.native:
            self._mci("close rsh_audio")
            self.native = False
        self.paused = False

    def _start(self, position=0):
        self._close()
        track = self.tracks[self.index]
        ffplay = shutil.which("ffplay")
        if ffplay:
            command = [ffplay, "-nodisp", "-autoexit", "-loglevel", "error", "-volume", str(self.volume)]
            if position and not is_stream(track):
                command.extend(["-ss", str(position)])
            command.extend(["-i", str(track)])
            self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.offset = position if not is_stream(track) else 0.0
        elif os.name == "nt" and not is_stream(track):
            if '"' in str(track):
                raise ValueError("Audio filename contains an unsupported quote.")
            self._mci(f'open "{track}" type mpegvideo alias rsh_audio')
            self.native = True
            self._mci("set rsh_audio time format milliseconds")
            self._mci(f"setaudio rsh_audio volume to {self.volume * 10}")
            self._mci(f"play rsh_audio from {int(position * 1000)}")
            self.offset = position
        else:
            raise OSError("Install FFmpeg (ffplay) for audio playback and internet radio on this host.")
        self.started = time.monotonic()
        self.paused = False
        self.error = ""

    def play(self, tracks):
        if not tracks:
            raise ValueError("The playback queue is empty.")
        with self.lock:
            self.tracks, self.index = list(tracks), 0
            self._start()
            if not self._monitor_started:
                self._monitor_started = True
                threading.Thread(target=self._monitor, daemon=True, name="RSH-Audio").start()
            return self.status()

    def _monitor(self):
        while True:
            time.sleep(0.5)
            with self.lock:
                if self.paused:
                    continue
                try:
                    ended = (self.process is not None and self.process.poll() is not None) or (self.native and self._mci("status rsh_audio mode") == "stopped")
                    if ended:
                        if self.process is not None and self.process.returncode:
                            self.error = "Playback failed; check the file format or radio URL."
                            self._close()
                        elif self.index + 1 < len(self.tracks):
                            self.index += 1
                            self._start()
                        else:
                            self._close()
                except (OSError, ValueError) as exc:
                    self.error = str(exc)
                    try:
                        self._close()
                    except OSError:
                        pass

    def _suspend(self, suspend):
        if os.name != "nt":
            os.kill(self.process.pid, signal.SIGSTOP if suspend else signal.SIGCONT)
            return
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x0800, False, self.process.pid)
        if not handle:
            raise OSError("Could not control the audio process.")
        try:
            function = getattr(ctypes.WinDLL("ntdll"), "NtSuspendProcess" if suspend else "NtResumeProcess")
            function.argtypes = [ctypes.c_void_p]
            function.restype = ctypes.c_long
            if function(handle) != 0:
                raise OSError("Could not pause or resume playback.")
        finally:
            kernel.CloseHandle(handle)

    def control(self, action, value=None):
        with self.lock:
            active = self.native or (self.process is not None and self.process.poll() is None)
            if action == "volume":
                volume = int(value)
                if not 0 <= volume <= 100:
                    raise ValueError("Volume must be from 0 to 100.")
                position = self.position()
                was_paused = self.paused
                self.volume = volume
                if self.native:
                    self._mci(f"setaudio rsh_audio volume to {volume * 10}")
                elif active:
                    self._start(position)
                    if was_paused:
                        self.control("pause")
                return self.status()
            if action in ("next", "prev"):
                next_index = self.index + (1 if action == "next" else -1)
                if not self.tracks or not 0 <= next_index < len(self.tracks):
                    raise ValueError("No track in that direction.")
                self.index = next_index
                self._start()
            elif action in ("pause", "resume"):
                if not active:
                    raise ValueError("Nothing is playing.")
                suspend = action == "pause"
                if suspend != self.paused:
                    if suspend:
                        self.pause_position = self.position()
                    if self.native:
                        self._mci(("pause" if suspend else "resume") + " rsh_audio")
                    else:
                        self._suspend(suspend)
                    if not suspend:
                        self.offset = self.pause_position
                        self.started = time.monotonic()
                    self.paused = suspend
            elif action == "stop":
                self._close()
            else:
                raise ValueError("Audio controls: pause, resume, stop, next, prev, volume.")
            return self.status()

    def position(self):
        if self.paused:
            return self.pause_position
        return self.offset + time.monotonic() - self.started if self.native or self.process is not None else 0.0

    def status(self):
        with self.lock:
            state = "paused" if self.paused else "playing" if self.native or self.process is not None else "stopped"
            track = str(self.tracks[self.index]) if self.tracks else "(none)"
            position = int(self.position())
            duration = ""
            if self.native:
                duration = f" / {int(self._mci('status rsh_audio length')) // 1000}s"
            return f"Audio: {state} | Volume {self.volume}%\nTrack {self.index + 1 if self.tracks else 0}/{len(self.tracks)}: {track}\nPosition: {position}s{duration}" + (f"\n{self.error}" if self.error else "")

    def stop(self):
        with self.lock:
            self._close()


_PLAYER = AudioPlayer()


class AudioTool:
    EXTENSIONS = {".mp3", ".wav", ".wma", ".flac", ".ogg", ".m4a", ".aac", ".aiff"}
    HELP = ("audio [list | play <file/#/URL> | queue <file/#/URL> | radio <URL> | "
            "pause | resume | stop | next | prev | volume <0-100> | info | tracks | "
            "save <playlist> | load <playlist> | playlists]\n"
            "Playback uses the host speakers. FFmpeg (ffplay) enables internet radio and extra formats.")

    def __init__(self, files, player=None):
        self.files = files
        self.player = player or _PLAYER
        self.entries = []

    def target(self, value):
        if is_stream(value):
            return value
        if value.isdigit() and 1 <= int(value) <= len(self.entries):
            path = self.entries[int(value) - 1]
        else:
            path = self.files.path(value, numbered=False)
        path = self.files.path(str(path), numbered=False)
        if not path.is_file() or path.suffix.lower() not in self.EXTENSIONS:
            raise ValueError("Choose an audio file in shared files, or an HTTP(S) radio URL.")
        return str(path)

    def command(self, args):
        action = args[0].lower() if args else "list"
        if action == "help":
            return self.HELP
        if action == "list":
            self.entries = sorted(p for p in self.files.root.rglob('*') if p.is_file() and p.suffix.lower() in self.EXTENSIONS and p.resolve().is_relative_to(self.files.root))
            return "\n".join(f"{i}. {p.relative_to(self.files.root)}" for i, p in enumerate(self.entries, 1)) or "No audio files in shared files."
        if action == "play" and len(args) == 1:
            with self.player.lock:
                tracks = list(self.player.tracks)
            return self.player.play(tracks)
        if action in ("play", "queue", "radio") and len(args) == 2:
            if action == "radio" and not is_stream(args[1]):
                raise ValueError("Enter an HTTP(S) radio stream URL.")
            target = self.target(args[1])
            if action == "queue":
                with self.player.lock:
                    self.player.tracks.append(target)
                return "Queued: " + target
            return self.player.play([target])
        if action in ("pause", "resume", "stop", "next", "prev"):
            return self.player.control(action)
        if action == "volume" and len(args) == 2:
            return self.player.control("volume", args[1])
        if action == "info":
            return self.player.status()
        if action == "tracks":
            with self.player.lock:
                return "\n".join(f"{i}. {track}" for i, track in enumerate(self.player.tracks, 1)) or "Playback queue is empty."
        playlist_root = self.files.path(str(self.files.root / "playlists"), numbered=False)
        if action == "playlists":
            return "\n".join(p.stem for p in sorted(playlist_root.glob("*.m3u"))) or "No saved playlists."
        if action in ("save", "load") and len(args) == 2:
            name = args[1]
            if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- " for c in name):
                raise ValueError("Playlist names may contain letters, numbers, spaces, - and _.")
            path = self.files.path(str(playlist_root / (name + ".m3u")), numbered=False)
            if action == "save":
                with self.player.lock:
                    tracks = list(self.player.tracks)
                if not tracks:
                    raise ValueError("Queue some tracks before saving a playlist.")
                playlist_root.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8") as output:
                    output.write("#EXTM3U\n" + "\n".join(tracks) + "\n")
                return "Playlist saved: " + name
            entries = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]
            return self.player.play([self.target(entry) for entry in entries])
        return self.HELP
