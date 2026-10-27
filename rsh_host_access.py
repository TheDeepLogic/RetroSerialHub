"""Separate, locally approved permission to submit HOST commands."""

import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time

from rsh_access import canonical_ip


def serial_identity(port):
    if not isinstance(port, str) or not port.strip() or len(port) > 256:
        raise ValueError("Cannot identify the physical serial port.")
    port = port.strip()
    match = re.fullmatch(r"(?:\\\\\.\\)?COM([0-9]+)", port, re.IGNORECASE)
    return "COM" + str(int(match[1])) if match else port


class HostCommandAccess:
    def __init__(self, path=None, *, clock=time.monotonic, timeout=120, max_pending=16):
        self.path = Path(path) if path is not None else None
        self.clock, self.timeout, self.max_pending = clock, timeout, max_pending
        self._lock = threading.RLock()
        self._allowed = {"allowed_ips": [], "allowed_serial_ports": []}
        self._pending = {}
        self._next_id = 1

    def _load(self):
        if self.path is None:
            return {key: list(values) for key, values in self._allowed.items()}
        try:
            with self.path.open(encoding="utf-8") as source:
                text = source.read(65537)
        except FileNotFoundError:
            return {"allowed_ips": [], "allowed_serial_ports": []}
        if len(text) > 65536:
            raise ValueError("Host-control allowlist exceeds 64 KiB.")
        data = json.loads(text)
        if not isinstance(data, dict) or any(not isinstance(data.get(key), list) for key in self._allowed):
            raise ValueError("Host-control allowlist requires allowed_ips and allowed_serial_ports arrays.")
        return {"allowed_ips": sorted({canonical_ip(value) for value in data["allowed_ips"]}),
                "allowed_serial_ports": sorted({serial_identity(value) for value in data["allowed_serial_ports"]})}

    def _save(self, data):
        if self.path is None:
            self._allowed = data
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             delete=False) as output:
                temporary = output.name
                json.dump(data, output, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def _expire(self):
        for identifier, request in list(self._pending.items()):
            if request["deadline"] <= self.clock():
                del self._pending[identifier]

    def request(self, terminal):
        address = getattr(terminal, "_remote_address", None)
        if isinstance(address, tuple) and address:
            key, source = "allowed_ips", canonical_ip(address[0])
        else:
            key, source = "allowed_serial_ports", serial_identity(getattr(terminal, "port", None))
        with self._lock:
            allowed = self._load()
            if source in allowed[key]:
                return True, "", False
            self._expire()
            request = next((row for row in self._pending.values()
                            if row["key"] == key and row["source"] == source), None)
            new = request is None
            if new:
                if len(self._pending) >= self.max_pending:
                    return False, "Host-control approval queue is full; try again later.", False
                identifier = self._next_id
                self._next_id += 1
                request = {"id": identifier, "key": key, "source": source,
                           "deadline": self.clock() + self.timeout}
                self._pending[identifier] = request
            return False, (f"Host-control request #{request['id']} for {source}. "
                           f"At the local console type: allow host {request['id']}. "
                           "Then retry your HOST command; it has not been executed."), new

    def pending(self):
        with self._lock:
            self._expire()
            return [{"id": row["id"], "source": row["source"],
                     "seconds_left": max(0, int(row["deadline"] - self.clock()))}
                    for row in self._pending.values()]

    def decide(self, identifier, allow):
        """The caller must enforce that this came from the physical console."""
        with self._lock:
            self._expire()
            request = self._pending.get(identifier)
            if request is None:
                raise ValueError("That host-control request is missing or expired.")
            if allow:
                data = self._load()
                data[request["key"]] = sorted(set(data[request["key"]]) | {request["source"]})
                self._save(data)
            del self._pending[identifier]
            return request["source"]
