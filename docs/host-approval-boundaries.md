# Host-control approval boundaries

Letting a terminal use the hub and letting it control the host console are two
different decisions. Telnet admission lives in [rsh_access.py](../rsh_access.py);
`HOST <text>` permission lives in [rsh_host_access.py](../rsh_host_access.py).
An admitted Telnet client still needs host-control approval. A physical serial
connection needs it too.

## First use requests permission; it does not queue a command

The first unauthorized command creates an approval request and returns without
executing the text. The person at the console types `allow host <number>`;
the terminal then retries its command. Requests store source metadata rather
than a command to execute later. This avoids a surprising delayed action when
someone approves a request after the original context has changed.

The console dispatcher rejects approval attempts submitted through remote HOST
control. The access manager handles identities and persistence; the console
enforces which input path may make the decision. These are separate boundaries,
so testing the manager alone would not establish the console routing rule.

## Permission follows the source

| Input | Remembered identity | Consequence |
|---|---|---|
| Serial `COM02` | Canonical `COM2` | Reconnecting the same physical port retains permission. |
| Serial `\\.\COM2` | Canonical `COM2` | Windows device-path notation does not create another identity. |
| Telnet `192.0.2.7`, any source port | Source IP | A new socket from that IP retains permission. |
| Another IP | Another source | It needs its own approval. |

Profile display names are not identities. Conversely, clients sharing an IP
share its grant: this is source-based permission, not an account login or a
cryptographic identity. That follows directly from the requested per-IP model.

## Measure failure paths, not just a successful allow

Run `python -m tests.measure_technical_behaviors`. The approval fixture uses
temporary storage, synthetic IPs, and a controlled clock:

| Probe | Result |
|---|---|
| Unapproved serial and Telnet sources | Both initially denied |
| Repeat the same pending request | One request row |
| Fill a deliberately two-entry queue | Third distinct source rejected |
| Inject an allowlist-save `OSError` | Zero grants committed |
| Save approvals and construct a new manager | Both source grants restored |
| Reconnect approved IP with another socket port | Allowed |
| Try another IP | Denied |
| Advance clock beyond the 120-second request lifetime | Expired approval rejected |

The production queue limit is **16**, not the fixture's two. Request numbers
increase rather than being recycled when requests expire. A bounded queue and
deduplication keep repeated first-use attempts from producing an unbounded list.

Saving is part of approving: the implementation writes a temporary file, flushes
and synchronizes it, and replaces the allowlist before removing the pending
request. A failed save must not leave a permission that appears granted only in
memory. The fixture injects a save error; it does not simulate a disk filling up
or a power failure. Reloading the allowlist also makes manual revocation take
effect on subsequent requests.

## Why this needed separate tests

An ordinary successful-command test would miss three distinct mistakes: using
the Telnet-admission grant for host control, using a friendly profile label in
place of a source identity, or allowing already-authorized remote control to
approve another source. Persistence failure adds a fourth boundary between
"the operator said yes" and "the permission was actually recorded."

See [the console dispatcher](../rsh_console.py),
[access tests](../tests/test_rsh_host_access.py), and
[the measurement harness](../tests/measure_technical_behaviors.py).
