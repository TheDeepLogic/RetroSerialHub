# Scheduler recovery

The scheduler previously wrote JSON directly over its saved task file. A partial
write could leave unreadable JSON and lose all saved jobs on restart. A malformed
entry could also prevent an otherwise valid legacy task list from loading, or
terminate the worker when its schedule was inspected.

## Saved tasks

Saves now write a unique temporary file beside the destination, flush and fsync
its contents, close it, then replace the destination atomically. Write or replace
failures log an error and preserve the previous destination. Temporary files are
removed after failures when the filesystem permits it.

As before, a save error leaves changes in memory; they are not durable until a
later save succeeds. Resolve the disk-space or permissions problem, then perform
a scheduler change to trigger another save before restarting the hub. Atomic
replacement prevents partial JSON; it does not coordinate edits from multiple
hub processes or guarantee persistence through every filesystem/power failure.

Both dictionary and legacy list task files remain supported. Each entry must be
an object with a text command and a usable schedule. Invalid entries and duplicate
IDs produce warnings and are skipped individually; valid entries remain available.
Loading alone never rewrites the source file. Back it up before making scheduler
changes if you need to recover skipped entries: the next successful save contains
only the loaded tasks and subsequent changes.

## Timestamp recovery

An invalid next-run timestamp is recalculated from the task's schedule. It is not
executed immediately as a catch-up job. Offset-aware timestamps are converted to
host local time before comparison with the scheduler's local clock. A due job
still executes normally; its next timestamp uses the usual local representation.

## Validation

Run from the repository root:

```text
python -m unittest tests.test_scheduler_reliability -v
python -m unittest discover -s tests -q
```

The targeted tests use temporary directories and injected partial-write and
replacement failures. They verify unchanged destination bytes, temporary-file
cleanup, successful retries, mixed valid/invalid dictionary and legacy-list
loading, duplicate IDs, and one deterministic worker iteration with malformed,
non-text, or offset-aware timestamps alongside another due job. They use no
network, serial hardware, real-time waits, or personal task files.
