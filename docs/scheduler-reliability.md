# Scheduler reliability

## Using scheduled tasks

Open **System > Task Scheduler** to create interval, hourly, daily, weekly, or
monthly tasks. All times use the host's local clock. Monthly tasks on the 29th,
30th, or 31st run on the month's last day when necessary. Intervals must be
positive; invalid times, weekdays, month days, and recurrence types are rejected.

The CLI creates interval tasks and manages all saved schedules:

```text
schedule add MorningBriefing 30 news : weather Austin : broadcast Briefing complete
schedule list
schedule details 1
schedule run 1
schedule disable 1
schedule enable 1
schedule toggle 1
schedule delete 1
schedule modules
schedule info weather
```

`details` shows the command, recurrence, enabled state, next run, last run, last
status, and broadcast/output settings. Repeating `enable` or `disable` keeps the
requested state; enabling an already enabled task preserves its next run.
Re-enabling a disabled task calculates a future run. `run` also runs disabled
tasks on demand and reschedules their next run without enabling them.

Chain commands with ` : ` or `;` outside quotes. Quote paths and arguments that
contain spaces or literal delimiters, for example:

```text
schedule add Reminder 60 broadcast "Check cables; power : ready" : calc 2 + 2
```

Quotes and Windows backslashes are retained when saving CLI tasks. Semicolons
inside URL tokens are preserved; put whitespace before a semicolon when using
it to separate a URL from another command. Bare HTTP/HTTPS URLs are executed
through `view`. Both the menu and CLI use the same execution-time chain parser.
An individual command failure does not prevent later commands from running.
The combined text reports command errors; last status records executor-level
exceptions, so `OK` alone does not guarantee that each command succeeded.

The worker runs tasks sequentially. A second invocation of a task already running
returns an `already running` message. Deleted or disabled tasks waiting behind
another job are skipped. Stop wakes an idle worker immediately; a restart cannot
create another worker while the old one is still executing. Running commands are
not cancelled. A stopped worker must finish before it can be started again.
Overdue tasks run once after restart, then calculate a future run; missed periods
are not replayed individually.

## Persistence and malformed tasks

The scheduler previously wrote directly over its saved JSON file. A disk
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
Coverage also includes calendar rollovers, schedule validation, quoted chains,
CLI diagnostics and enable/disable behavior, overlapping manual runs, and worker
stop/restart. Runtime integration tests cover command discovery, resilient
chaining, news/weather output, and broadcast delivery.
