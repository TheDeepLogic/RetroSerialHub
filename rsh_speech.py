"""Interruptible eSpeak NG host speech; terminal threads never wait for narration."""
import atexit
import os
from pathlib import Path
import shutil
import subprocess
import threading


def find_espeak(executable=''):
    """Resolve a configured engine, PATH installation, or standard host location."""
    if executable:
        found = shutil.which(executable)
        if found:
            return found
        raise FileNotFoundError('Configured eSpeak NG executable was not found: ' + executable)
    for name in ('espeak-ng', 'espeak'):
        found = shutil.which(name)
        if found:
            return found
    candidates = [Path('/opt/homebrew/bin/espeak-ng'), Path('/usr/local/bin/espeak-ng')]
    if os.name == 'nt':
        for variable in ('ProgramFiles', 'ProgramFiles(x86)'):
            if os.environ.get(variable):
                candidates.append(Path(os.environ[variable]) / 'eSpeak NG' / 'espeak-ng.exe')
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError('Install eSpeak NG and restart the hub, or set WOPR_SPEECH_EXECUTABLE.')


class HostSpeech:
    """One host voice. New speech replaces stale speech instead of building a queue."""

    def __init__(self):
        self.lock = threading.RLock()
        self.process = None
        self.owner = None
        self.generation = 0
        self.speaking = False
        self.error = ''
        atexit.register(self.stop)

    def say(self, owner, text, rate=145, volume=85, voice='en-us', pitch=25, gap=3, executable=''):
        try:
            engine = find_espeak(executable)
        except OSError as exc:
            self.stop(owner)
            self.error = 'Speech unavailable: ' + str(exc)
            return
        command = [engine, '--stdin', '-b', '1', '-v', voice or 'en-us',
                   '-s', str(max(80, min(450, int(rate)))),
                   '-a', str(max(0, min(100, int(volume)))),
                   '-p', str(max(0, min(99, int(pitch)))),
                   '-g', str(max(0, min(100, int(gap))))]
        with self.lock:
            self.stop()
            self.owner = owner
            self.speaking = True
            self.error = ''
            token = self.generation
            threading.Thread(target=self._speak, args=(token, command, text),
                             daemon=True, name='RSH-Joshua-Speech').start()

    def _speak(self, token, command, text):
        process = None
        try:
            with self.lock:
                if token != self.generation:
                    return
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self.process = process
            _, error = process.communicate(text, timeout=120)
            if process.returncode:
                with self.lock:
                    if token == self.generation:
                        self.error = 'Speech unavailable: ' + (error.strip()[-300:] or 'eSpeak NG synthesis failed.')
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()
            with self.lock:
                if token == self.generation:
                    self.error = 'Speech unavailable: ' + str(exc)
        finally:
            with self.lock:
                if token == self.generation:
                    self.speaking = False
                    self.process = None

    def busy(self, owner):
        with self.lock:
            return self.owner is owner and self.speaking

    def stop(self, owner=None):
        with self.lock:
            if owner is not None and self.owner is not owner:
                return
            self.generation += 1
            self.speaking = False
            if self.process is not None and self.process.poll() is None:
                try:
                    self.process.terminate()
                except OSError:
                    pass
            self.process = None
            self.owner = None


SPEECH = HostSpeech()
