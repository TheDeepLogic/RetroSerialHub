# COM bridge byte preservation (v2.7)

The bridge exposes both raw forwarding and a line-oriented input handler.
Previously, both used chained replacements that expanded LF into CR/LF and
then expanded the newly inserted CR again. An existing CR/LF pair became
CR/LF/CR/LF/LF, introducing blank lines and changing transmitted bytes.

Raw forwarding now writes the supplied bytes unchanged. This preserves binary
values and treats a CR/LF pair identically whether it arrives together or in
separate reads. Raw callers supply any required line endings themselves.

The line-oriented handler still appends its CR/LF line terminator. When supplied
raw line content, it first collapses CR/LF and standalone CR to LF, then expands
each LF to exactly one CR/LF. Other bytes remain unchanged. The existing text
fallback and bridge command handling are retained.

Run the regressions from the repository root:

```text
python -m unittest discover -s tests -p test_rsh_bridge.py -v
```

Tests cover all 256 byte values, CR/LF split across calls, mixed newline forms
in line mode, and closing a disconnected bridge after a failed write. These use
mock transports; physical serial hardware compatibility has not been tested.

Validation on 2026-10-27, Windows Python 3.9.13: all four bridge tests and the
full 389-test suite passed. Loading the original bridge implementation in memory
reproduced three failures in the byte and newline tests; its disconnect cleanup
test already passed.
