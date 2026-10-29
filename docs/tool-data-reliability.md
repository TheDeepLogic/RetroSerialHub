# Tool data, reader recovery, and ZIP retries

## Shared record saves

`JsonRecords` stores contacts, appointments, folder preferences, launch presets,
reading positions, and other tool records. Saves now create a unique temporary
file beside the destination, serialize the records, flush Python's buffer, sync
the file, close it, and atomically replace the saved file. If serialization,
writing, syncing, or replacement fails, the previous saved file remains intact.
Temporary files are removed when possible; cleanup failures are logged without
hiding the original error. A caller can retry the change after resolving the
underlying filesystem error.

The existing process-wide lock also covers direct saves. Read/modify/write
operations through `change` remain serialized across terminal sessions in one
hub process. Unique temporary files prevent filename collisions but do not
coordinate edits made by separate hub processes. A successful file sync is not
a guarantee against every kind of power loss or filesystem failure.

## Document reader recovery and search

If saved reading positions cannot be loaded because of a filesystem error,
invalid JSON, or an invalid record-list shape, the document still opens at its
first page. The reader displays `Reading position not saved.` when persistence
fails and retries through the normal save path on later pages. It does not
replace an unparseable settings file with empty data. Back up and repair that
file before expecting positions to persist again.

Records missing a document path are ignored when finding the current document.
Invalid numeric offsets reset to zero; negative offsets cannot select pages
from the end. Offsets beyond a shortened document are clamped to its last page.
Legacy page-based positions and bookmarks remain supported. Saving the current
document preserves unrelated records.

F searches for text, and N finds the next matching line, wrapping once to the
beginning. Unicode case-insensitive comparisons still use `casefold`. Search
now folds the query once and walks two ranges instead of constructing and
concatenating lists of every line number. The traversal uses constant extra
memory; loading and wrapping the document still require memory proportional to
the document, and search remains linear in the number of lines examined.

Measured on Windows with Python 3.10.11 on October 28, 2026, using a synthetic
100,001-line document with its match at the end, median of five searches:

| Search | Peak temporary allocation | Time with allocation tracing enabled |
|---|---:|---:|
| Previous algorithm | 4,393,192 bytes | 103.2 ms |
| Current algorithm | 676 bytes | 61.6 ms |

These measurements cover searching only. They exclude document loading,
wrapping, terminal output, and position storage. Timing varies by host; the
benchmark checks that both algorithms return the same matching line.

## Retrying ZIP extraction

Archive extraction still validates selected paths before writing and creates
output files exclusively, preserving existing files. If a member cannot be
opened, fails CRC verification while reading, cannot be copied, or fails while
closing its output, the newly created incomplete member is removed when
possible. The error still reaches the caller. If removal also fails, the host
log names the incomplete file for manual inspection.

Completed members and directories remain in place. After resolving the error,
use `archive members` to find the failed member's number, then retry it:

```text
archive open software.zip
archive members
archive extract 2 unpacked
```

Repeating `extract all` into a partly completed directory will still reject
completed files because existing output is never replaced. Select the remaining
members individually or choose a different destination. Extraction is not an
archive-wide transaction; forced process termination can still leave partial
output.

## Validation

From the repository root:

```text
python -m unittest discover -s tests -p test_tool_reliability.py -v
python -m unittest discover -s tests
python docs/measure_reader_search.py
```

Tests use temporary files and injected failures. They check failed replacements,
serialization and sync errors, cleanup and retry, unrelated temporary files,
corrupt/unreadable reader state, bad offsets, legacy bookmarks, Unicode search
wraparound, partial ZIP copies, failed member opens, and preservation of files
created after extraction preflight. The existing concurrent-contact test also
checks that changes from multiple terminal sessions are retained. No hardware
or external services are needed for these checks.
