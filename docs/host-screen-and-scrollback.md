# A host screen is not an append-only log

Reproduce with `python -m tests.measure_technical_behaviors`; inspect
`screen_controls` and `scrollback` in [the report](technical-measurements.txt).
The core pieces are [`HostScreen`](../rsh_host_screen.py) and the dashboard's
capture, body extraction, and scrollback methods in [`rsh_console.py`](../rsh_console.py).

## Shorter progress updates leave a suffix unless erased

Consider this byte stream:

```text
Downloading 100 percent\rDone\x1b[K
```

Carriage return moves the cursor back; it does not remove the old characters.
Writing `Done` replaces only four positions. The erase-to-end-of-line command
removes the remaining suffix. The measured resulting screen is exactly `Done`,
with the cursor at zero-based `(0, 4)`.

Stripping every escape sequence turns a screen into a misleading log. Passing
those sequences straight through is also wrong: a submenu clear could erase the
dashboard's status panels. The host therefore interprets controls inside its own
bounded text screen and lets the outer renderer paint the resulting cells.

## Erase and home are different operations

The supported `CSI 2 J` operation erases the screen but preserves the cursor's
position within it. `CSI H` moves the cursor home. The normal hub clear sends both
in sequence. `CSI 0 J` erases from the cursor onward; `CSI 3 J` discards old
scrollback rows while retaining the current modeled viewport.

This distinction matters when a program erases part of a display, restores a
saved cursor, or starts writing before another home command. Restoring a saved
position into rows that an erase removed must re-create those rows safely.

The model also handles common relative/absolute cursor moves, line erase modes,
save/restore, and character insertion/deletion/erase. Session SGR styling is
ignored so dashboard themes own the colors. OSC/control strings are consumed
rather than being allowed to rename or control the containing terminal.

This is a small text-screen model, not a complete xterm/VT emulator. The measured
fixtures are ASCII; byte capture uses ASCII replacement. Alternate screens,
arbitrary terminal modes, and complex Unicode-cell editing are not covered by
these measurements.

## A write boundary is not a control-sequence boundary

Serial reads and program writes can split an escape sequence between any two
characters. Four fixtures cover suffix erasure, clear/home, saved-cursor editing,
and OSC plus SGR handling. Replaying all **140 possible two-chunk partitions**,
plus **four byte-at-a-time runs**, produced **zero screen mismatches**.

The exact-width test writes 80 characters followed by CR/LF. It produces **one**
line event, not an automatic wrap followed by a second empty line. The model waits
until another printable character actually needs the next row before wrapping.

## Why adding to a scroll offset was not enough

If the view ends `N` rows before the newest output, new output moves the reference
point. Cursor-addressed output is harder still: old rows can be overwritten or
cleared without appending anything.

PgUp now takes a bounded snapshot of the history being browsed. Its anchor is a
source-row index and character offset, not a distance from the live tail. A resize
reflows the same source text. The active input prompt remains live below it.

Measured sequence:

| Step | Observed state |
|---|---|
| Emit 100 original rows, then PgUp in a 150x40 viewport | 100 logical rows retained in the held history; 30 original rows visible |
| Clear the live screen and emit 700 new rows | The same 30 original rows remain visible |
| Inspect the live buffer | 500 rows retained, its configured capacity |
| Inspect the held-view indicator | 700 new lines |
| Press End | Live output includes row 699; the counter returns to zero |

The counter records emitted newlines and automatic wraps, not write calls or
arbitrary screen updates. A carriage-return progress update can change live cells
without adding a new line. Native screen clears do not discard the held view;
an explicit console clear or host-command submission resumes live operation.
PgDn also resumes live at the bottom.

Both buffers are bounded in logical rows. At 80 columns, 500 rows represent at
most 40,000 character positions per buffer, but that is not a Python heap-size
measurement: strings may be shared and object overhead is additional.

Focused tests: [`test_rsh_host_screen.py`](../tests/test_rsh_host_screen.py) and
[`test_rsh_scrollback.py`](../tests/test_rsh_scrollback.py).
