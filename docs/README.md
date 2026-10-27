# Engineering field notes

These are measured behaviors and implementation lessons from building Retro Serial
Hub, especially the console work that took several iterations in v2.6. The notes
were added during v2.7a alpha development; they do not imply that every described behavior
is new in v2.7a.

| Note | What it explains |
|---|---|
| [Transfer reliability](transfer-reliability.md) | Overall fragmented-read deadlines, disconnected cancellation recovery, and deterministic regression tests. |
| [Console redraw measurements](console-redraw-measurements.md) | Why 100 unchanged refreshes went from 1,761,800 bytes to zero, and which changes still require a full paint. |
| [Terminal layout and cursor budgets](terminal-layout-and-cursor-budgets.md) | Why an 80-column host pane needs a 124-column window for side-by-side status, and why the last cell matters. |
| [Host screen controls and frozen scrollback](host-screen-and-scrollback.md) | Why a screen is not a log, why erase is not home, and why a relative scroll offset cannot hold a view still. |
| [Message delivery and transfer boundaries](message-delivery-and-transfer-boundaries.md) | Immediate notice versus unread state, partial input restoration, and preventing notices from entering file bytes. |
| [Host-control approval boundaries](host-approval-boundaries.md) | Separate Telnet/host permissions, physical-port identities, failed saves, request expiry, and retry semantics. |
| [XMODEM wire costs](xmodem-wire-costs.md) | Actual bytes emitted by the sender, padding cliffs, CRC/checksum overhead, retries, and calculated serial budgets. |
| [Notepad edit recovery](notepad-edit-recovery.md) | The merged experiment-branch fix and the importance of reading a file before committing editor state. |

## Reproduce the measurements

From the repository root, using the project's Python environment:

```text
python -m tests.measure_technical_behaviors
python -m tests.benchmark_console_redraw
python -m unittest discover -s tests -v
```

The first command asserts its invariants and prints a JSON report. Its recorded
output is [technical-measurements.txt](technical-measurements.txt). The `.txt`
extension keeps this public fixture report separate from the repository's ignored
personal JSON settings; its contents are still JSON.

Recorded on **2026-10-27**, Windows, Python **3.14.2**, with application version
**2.7a** in a working tree based on `bae0ea4`. Fixtures use memory terminals,
synthetic addresses, temporary files, a simulated clock for approval expiry, and
injected filesystem errors. They open no serial ports or network connections and
do not inspect personal notes, settings, or allowlists.

Byte counts, row counts, state transitions, and assertions are measured. Serial
timing estimates are explicitly calculated, not stopwatch results from vintage
hardware. The virtual viewport is a deliberately small test model, not proof of
compatibility with every terminal emulator or ROM.
