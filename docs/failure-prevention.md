# Failure prevention change notes

Reviewed October 28, 2026, during v2.7a alpha development. These changes address
three failure paths found by code inspection, rather than reported production
incidents.

## Download integrity and memory use

Previously, `fetch` read the entire response into memory and then wrote directly
to its final destination. Large files required equally large byte buffers, and
a disk-write failure could truncate an existing local copy. Reading a response
in chunks also needs an explicit length check to detect an early EOF.

`fetch <url> [destination_filename]` now streams in 64 KiB chunks into a unique
temporary file beside the destination. When the server supplies a valid
nonnegative `Content-Length`, the received byte count must match. The file is
flushed, synced, and closed; the HTTP response also closes before the temporary
file atomically replaces the destination. A successful fetch retains the existing
behavior of replacing a same-named file.

Network read errors, length mismatches, output write/sync/close failures, response
close failures, and replacement errors leave the previous destination intact.
A failed new download does not publish a partial final file. Temporary files are
removed when possible, with cleanup failures logged. The CLI reports `Fetch error`
and can retry the same command after the underlying error is resolved.

The streaming buffer stays bounded as files grow. No total-size cap is added;
downloads still need enough disk space. Responses without a usable length are
accepted on EOF, so truncation cannot be inferred from a missing header. This
change applies to `fetch`; document extraction through `view`/`fetchview` still
loads response contents for parsing. Forced termination can leave a temporary
file, and filesystem synchronization does not guarantee survival of every
possible storage failure.

## Event listener isolation

Previously, an exception from one event listener prevented later listeners from
receiving the event. A failed module hook could similarly stop dispatch through
the remaining modules. For example, an optional hook failing during a `notify`
event could prevent a healthy delivery hook from seeing the notification.

The event bus now treats delivery as best effort. Each ordinary listener
exception is logged with the topic, listener, and traceback; delivery continues
to later listeners. Module hooks receive the same individual isolation. Failed
callbacks return `None` in the result list; successful callbacks retain their
results. Event payloads are not added to the error log.

`publish_async` awaits asynchronous listeners and isolates their exceptions.
Synchronous `publish` runs asynchronous listeners when no event loop exists and
returns their results. Inside a running loop it returns tasks for asynchronous
listeners; those tasks log failures and resolve to `None`. Existing awaitable
objects, including futures, are supported. Cancellation and other control-flow
exceptions are not suppressed.

Delivery remains ordered for synchronous/awaited callbacks. This is not a retry
queue or a transaction: failed callbacks are not automatically replayed, partial
side effects are not rolled back, and a blocking callback can still delay later
callbacks. Background tasks returned by `publish` require the event loop to keep
running until completion.

## Batch copy/move destination collisions

Marked items can come from different folders. Previously, selecting
`first/game.dsk` and `second/game.dsk` passed destination preflight when neither
output existed yet. The first operation succeeded, then the second failed because
both targeted the same output filename. A batch move could therefore leave its
source set partly relocated.

Preflight now checks the destination of every marked item against the other
planned destinations, using the host platform's path comparison. Duplicate names
are rejected before any copy/move begins. Existing checks for missing sources,
existing destinations, linked directory contents, and overlapping sources remain.
Marks are retained after rejection, so the user can unmark a conflicting item or
copy/move the items separately. Ordinary batches with distinct names still work.

This prevents the identified predictable collision. Batch operations are not
atomic: a later disk error or concurrent filesystem change can still interrupt
a batch after some operations have completed.

## Validation

Run from the repository root:

```text
python -m unittest discover -s tests -p test_failure_prevention.py -v
python -m unittest discover -s tests
```

The focused tests cover sync and async listener failures, futures, cancellation,
module-hook isolation, bounded download reads, truncation, network failures,
partial disk writes, sync/replacement/response-close failures, cleanup and retry,
automatic filenames, duplicate batch names, unchanged source files, retained
marks, and successful ordinary copy/move batches. HTTP responses are simulated;
all filesystem tests use temporary directories. No live servers or serial
hardware are used.
