# Scheduler reliability

The v2.7a scheduler previously wrote directly over its saved JSON file. A disk
error or failed serialization could leave that file incomplete. It now writes to
an independently named temporary file in the same directory, flushes and syncs
the contents, closes it, and replaces the saved file atomically. Failed saves
are logged and temporary files are cleaned up where possible. In-memory changes
remain available for a later save; they are not durable until a save succeeds.
This does not coordinate concurrent hub processes editing the same task file.

A malformed recurrence could also raise outside the worker's execution handler,
ending the background scheduler and preventing healthy tasks from running.
The worker now checks each enabled recurrence independently. An invalid task is
disabled with an `Invalid schedule` last status and a warning in the host log.
Other due tasks continue. Correct the task's saved schedule before re-enabling
it, or remove and recreate it through `schedule`.

Missing or malformed next-run timestamps are recalculated from the current local
time. Timezone-bearing timestamps are also recalculated because the scheduler
uses local timestamps without timezone offsets. This schedules a future run
rather than immediately replaying an uncertain missed run. Repairs and disabled
states are saved together once per worker pass.

Loading accepts the existing JSON object and legacy list formats. Non-object
entries are skipped; object keys become the canonical string task IDs. A file
that cannot be parsed still logs a warning and starts with an empty task list.

## Validation

Run from the repository root:

```text
python -m unittest discover -s tests -p test_scheduler_reliability.py -v
python -m unittest discover -s tests
```

The regression tests inject replacement and serialization failures, run one
worker pass with both broken and healthy tasks, load malformed entries in both
storage formats, and exercise a timezone-bearing timestamp. They use temporary
files and do not execute external commands, open hardware, or use the network.
