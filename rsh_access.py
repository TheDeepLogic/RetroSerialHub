"""Host-approved IP allowlist for inbound Telnet sessions."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import select
import socket
import tempfile
import threading
import time


def canonical_ip(value):
    if not isinstance(value, str) or "%" in value:
        raise ValueError("Allowlist entries must be individual IP addresses.")
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return str(address)


class IPAllowlist:
    """Read on admission so manual additions and removals need no restart."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def ensure_exists(self):
        with self._lock:
            try:
                with self.path.open("x", encoding="utf-8") as output:
                    output.write('{"allowed_ips": []}\n')
            except FileExistsError:
                pass

    def allowed(self):
        with self._lock:
            try:
                with self.path.open("r", encoding="utf-8") as source:
                    text = source.read(65537)
            except FileNotFoundError:
                return set()
            if len(text) > 65536:
                raise ValueError("Telnet allowlist exceeds 64 KiB.")
            data = json.loads(text)
            if not isinstance(data, dict) or not isinstance(data.get("allowed_ips"), list):
                raise ValueError('Telnet allowlist must contain an "allowed_ips" array.')
            return {canonical_ip(value) for value in data["allowed_ips"]}

    def approve(self, address):
        address = canonical_ip(address)
        with self._lock:
            addresses = self.allowed()
            addresses.add(address)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                                 prefix=self.path.name + ".", suffix=".tmp", delete=False) as output:
                    temporary = Path(output.name)
                    json.dump({"allowed_ips": sorted(addresses)}, output, indent=2)
                    output.write("\n")
                    output.flush()
                    os.fsync(output.fileno())
                temporary.replace(self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


@dataclass
class PendingTelnet:
    id: int
    profile: str
    config: dict
    client: socket.socket
    address: tuple
    ip: str
    deadline: float


class TelnetAccess:
    """Hold a bounded number of sockets without starting any hub session."""

    def __init__(self, path, admit, notify, *, interactive=False, timeout=120,
                 max_pending=16, clock=time.monotonic):
        self.store = IPAllowlist(path)
        self.admit = admit
        self.notify = notify
        self.interactive = interactive
        self.timeout = timeout
        self.max_pending = max_pending
        self.clock = clock
        self._lock = threading.RLock()
        self._poll_lock = threading.Lock()
        self._pending = {}
        self._next_id = 1
        self._last_error = float("-inf")
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        try:
            self.store.ensure_exists()
            self.store.allowed()
        except (OSError, ValueError) as exc:
            self.notify(f"Telnet allowlist error; new connections will be refused: {exc}", "red")
        self._thread = threading.Thread(target=self._monitor, name="telnet-approvals", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for request in pending:
            self._reject(request.client, "Host shutting down.")

    def pending(self):
        with self._lock:
            return [{"id": row.id, "ip": row.ip, "profile": row.profile,
                     "seconds_left": max(0, int(row.deadline - self.clock()))}
                    for row in self._pending.values()]

    def _error(self, message):
        # Refusals must not let a connection flood overwhelm the host display.
        with self._lock:
            if self.clock() - self._last_error < 5:
                return
            self._last_error = self.clock()
        self.notify(message, "yellow")

    @staticmethod
    def _reject(client, reason):
        try:
            client.settimeout(.2)
            client.sendall((reason + "\r\n").encode("ascii", errors="replace"))
        except OSError:
            pass
        finally:
            client.close()

    def accept(self, profile, config, client, address):
        if self._stop.is_set():
            self._reject(client, "Host shutting down.")
            return
        try:
            ip = canonical_ip(address[0])
            allowed = self.store.allowed()
        except (OSError, ValueError) as exc:
            self._reject(client, "Access denied: host allowlist unavailable.")
            self._error(f"Telnet access denied; allowlist error: {exc}")
            return
        if ip in allowed:
            self._admit(profile, config, client, address)
            return
        if not self.interactive:
            self._reject(client, "Host approval required. Ask the host operator to update the allowlist.")
            self._error(f"Telnet {ip} -> {profile} refused: no interactive host console. Edit {self.store.path.name} to approve.")
            return
        reason = None
        with self._lock:
            if self._stop.is_set():
                reason = "Host shutting down."
            elif any(row.ip == ip for row in self._pending.values()):
                reason = "This address already has an approval request pending."
            elif len(self._pending) >= self.max_pending:
                reason = "Host approval queue is full. Please try again later."
            else:
                identifier = self._next_id
                self._next_id += 1
                request = PendingTelnet(identifier, profile, config, client, address, ip, self.clock() + self.timeout)
                # Send the waiting notice before making the request approvable.
                try:
                    client.settimeout(.2)
                    client.sendall(f"Waiting for approval at the host console ({self.timeout}s).\r\n".encode("ascii"))
                except OSError:
                    client.close()
                    return
                self._pending[identifier] = request
        if reason:
            self._reject(client, reason)
            return
        self.notify(f"TELNET APPROVAL #{identifier}: {ip} -> {profile}. Host: allow {identifier} or deny {identifier}, then Enter.", "yellow")

    def allow(self, identifier):
        if not self.interactive:
            raise ValueError("Approval requires an interactive host console; edit the JSON file instead.")
        with self._lock:
            request = self._pending.get(identifier)
            if request is None or request.deadline <= self.clock():
                raise ValueError("That approval request is missing or expired.")
            # Persistence must succeed before a session can be admitted.
            self.store.approve(request.ip)
        self.notify(f"Approved Telnet address {request.ip}; saved in {self.store.path.name}.", "green")
        self.poll()

    def deny(self, identifier):
        request = self._take(identifier)
        if request is None:
            raise ValueError("That approval request is no longer pending.")
        self._reject(request.client, "Connection denied by the host operator.")
        self.notify(f"Denied Telnet address {request.ip} (request #{identifier}).", "yellow")

    def _take(self, identifier):
        with self._lock:
            return self._pending.pop(identifier, None)

    def _admit(self, profile, config, client, address):
        if self._stop.is_set():
            self._reject(client, "Host shutting down.")
            return
        try:
            client.settimeout(None)
            self.admit(profile, config, client, address)
        except Exception as exc:
            client.close()
            self._error(f"Could not start approved Telnet session: {exc}")

    def poll(self):
        with self._poll_lock:
            self._poll_pending()

    def _poll_pending(self):
        with self._lock:
            pending = list(self._pending.values())
        if not pending:
            return
        try:
            allowed = self.store.allowed()
        except (OSError, ValueError) as exc:
            allowed = None
            self._error(f"Telnet approval paused; allowlist error: {exc}")
        for request in pending:
            try:
                # Unapproved input is discarded, never sent to a hub command parser.
                if select.select([request.client], [], [], 0)[0]:
                    if not request.client.recv(4096):
                        if self._take(request.id):
                            request.client.close()
                        continue
                if self.clock() >= request.deadline:
                    if self._take(request.id):
                        self._reject(request.client, "Host approval timed out. Reconnect to request approval again.")
                    continue
                if allowed is None or request.ip not in allowed:
                    continue
                if not self._take(request.id):
                    continue
                # Flush buffered pre-approval keystrokes before handing off the socket.
                for _ in range(16):
                    if not select.select([request.client], [], [], 0)[0]:
                        break
                    if not request.client.recv(4096):
                        request.client.close()
                        break
                else:
                    self._reject(request.client, "Too much input while awaiting approval; reconnect.")
                    continue
                if request.client.fileno() < 0:
                    continue
                request.client.sendall(b"Host approved this address. Opening Retro Serial Hub.\r\n")
                self._admit(request.profile, request.config, request.client, request.address)
            except (OSError, ValueError):
                self._take(request.id)
                request.client.close()

    def _monitor(self):
        while not self._stop.wait(.25):
            self.poll()
