# Notepad edit recovery: read before committing state

[PR #1, Fix Notepad editing errors for unreadable notes](https://github.com/TheDeepLogic/RetroSerialHub/pull/1),
merged from `experiment`, is the first tracked fix for v2.7a alpha development.
Its implementation commit is `145de76`; the merge is `e86a96e`.

The interesting part is not just catching an exception. It is choosing when an
operation becomes an editor session.

## A listed note is not necessarily readable

Notepad lists files and later accepts `E<number>`. Between those two operations,
a file can disappear, access can fail, or its contents can turn out not to be
valid UTF-8. A directory listing cannot guarantee that the later read succeeds.

Previously, setting the editing flag before reading the file could leave a
partially initialized editor when that read failed. Subsequent input then went
to a state that had no complete original text. The fix in
[rsh_notes.py](../rsh_notes.py) reads into a local `original` value first.
Only after success does it assign `editing`, `edit_original`, `edit_lines`,
and `edit_page`.

```text
Select note -> read and decode -> initialize all editor state -> accept edits
                       |
                       +-> report failure, redraw menu, keep accepting commands
```

This is a small transaction boundary. The failure path returns `(True, None)`
to keep the module active and leaves the command prompt usable. It catches
`OSError` and `UnicodeError`; it does not hide every possible programming error.

## Reproduce the three failures

Run `python -m tests.measure_technical_behaviors`. The Notepad fixture starts
with a listed temporary note, then changes the conditions before requesting edit:

| Condition | How it is produced | Result |
|---|---|---|
| Missing note | Delete the listed file | Menu remains usable; no partial editor state |
| Unreadable note | Inject `PermissionError` at the read | Same recovery; source bytes unchanged |
| Invalid UTF-8 | Write bytes `FF FE` | Same recovery; invalid bytes remain unchanged |

All three cases check that none of the four editor-state keys has been committed,
that the failing operation changes no source bytes, and that repairing the file
allows a subsequent edit to succeed. The permission fixture is fault injection,
not an actual Windows ACL experiment. Strict decoding matters: silently replacing
invalid characters could make an apparently normal edit overwrite original bytes
that the user never saw accurately.

The PR also adds one regression test with three subcases in
[test_rsh_notes.py](../tests/test_rsh_notes.py). These are three failure scenarios,
not three separately counted unittest tests.

## What this establishes

The fix prevents a failed initial read from entering an incomplete editor. It
does not repair missing files or permissions, and it does not establish that
every other Notepad filesystem operation can recover from every I/O failure.

The reusable lesson is concrete: when initialization depends on external data,
obtain and validate that data before publishing the state that routes future
input. Testing a retry after failure is especially useful; an error message by
itself does not prove the application remains usable.

## Rename and export recovery

Pending rename/export input is now handled before menu navigation. Names such as
`N`, `B`, and `O` are treated as filenames at those prompts. `Q` still cancels,
and an empty reply returns to the menu. Rename adds `.txt` when needed.

Export reads the complete source before exclusively creating the destination.
An unreadable or missing source therefore leaves no empty destination, and an
existing destination is never overwritten. If writing or closing the new export
fails, the hub attempts to remove the incomplete output after closing it. If
filesystem permissions also prevent cleanup, that incomplete file may remain;
choose another output path or remove it before retrying. The source is unchanged.
After a reported failure, select `X<number>` again to retry the export.

Run `python -m unittest tests.test_rsh_notes -v` for temporary-file regression
coverage of command-letter rename targets, source-read failure followed by a
successful retry, preservation of an existing export, and a partial write failure
that leaves the menu usable. Filesystem errors are injected; these checks do not
require serial hardware.
