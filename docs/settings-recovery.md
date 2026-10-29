# Settings failure recovery

The v2.7 storage review found two failure paths that normal successful-save
tests did not exercise.

## Starter settings

[Settings storage](../rsh_storage.py) seeds missing live JSON files from the public
defaults. Previously, a copy error could leave a truncated live file. Subsequent
calls saw that file as existing settings and never tried the default again.
Opening the destination before an unreadable template could also leave an empty
live file.

The template now opens first. A failed copy or output close removes the newly
created destination before propagating the error. A later call can retry seeding.
Exclusive destination creation still preserves existing local settings, including
a file created by another process between the existence check and file creation.
Legacy migration and conflict backups retain their existing behavior.

This is cleanup after an exception, not an atomic publication or power-loss
guarantee. Another process could observe a copy in progress, and forced termination
can still leave a partial file. Existing corrupt settings are not automatically
overwritten. Back up and inspect affected local files before manually removing one
to restore its starter default.

## Machine preferences

[Machine preferences](../rsh_preferences.py) previously used a fixed temporary
filename. A failed write or replacement left it behind, and separate hub processes
could use the same path.

Each save now writes a unique temporary file beside the destination, closes it,
and replaces the live file only after writing succeeds. A `finally` block removes
the temporary file after failures. The original settings remain available, and
the caller can retry the same change. Existing validation and the process-local
lock remain in place.

Unique temporary files prevent temporary-path collisions; they do not coordinate
read-modify-write operations across processes. Concurrent processes can still
overwrite each other's edits, with the last successful replacement winning. These
saves do not add filesystem synchronization for power-loss durability. Cleanup
also depends on filesystem permission to remove the temporary file.

## Validation

```text
python -m unittest tests.test_rsh_storage tests.test_rsh_preferences -v
python -m unittest discover -s tests
python -m compileall -q .
```

Tests use temporary directories and injected errors. They verify a partial default
copy is removed, an unreadable template leaves no empty live file, failed
preference writes and replacements preserve the original bytes, temporary files
are removed, unrelated temporary files are untouched, and retries succeed. They
do not access personal settings, open serial ports, or simulate power loss.
