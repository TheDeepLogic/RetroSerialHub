# Telnet and interactive input reliability

The v2.7a stability review found three reproducible problems:

- Telnet bookmark additions and deletions changed the session list before saving.
  A disk error could leave memory inconsistent with disk and disconnect the menu.
- A peer sending only Telnet control sequences could keep a single input poll
  running indefinitely, preventing the session loop from doing other work.
- Interactive prompts slept 20 ms after every character, including queued host
  input. A 100-character paste added about two seconds of artificial delay.

Bookmark changes now save a proposed list before replacing the session list.
Filesystem errors leave the current prompt active and display the error. Retry T
or B when adding, or choose N to connect without saving. Deletion retains the
original bookmark after a failed save; retry its number or enter Q to cancel.
Each save writes a unique temporary file beside the destination and replaces the
destination only after writing completes. Failed replacements clean up that
temporary file. This prevents simultaneous saves from sharing a temporary path;
it does not merge concurrent edits (the last successful save still wins).

Inbound socket polling processes at most 16 chunks of up to 4096 bytes per call.
Telnet parser state persists across polls, so fragmented negotiations and escaped
binary bytes continue to work. This bounds receive work per poll; it does not
impose a socket write timeout or rate limit on clients.

Interactive line input now sleeps only when no input is available. Output pacing
configured for vintage serial hardware remains separate from this input change.

## Validation

```text
python -m unittest tests.test_rsh_telnet tests.test_rsh_server tests.test_rsh_host -v
python -m unittest discover -s tests
python -m compileall -q .
```

Tests inject disk-full and permission errors, verify disk and memory preservation,
retry without duplicate bookmarks, cancel deletion, and exercise the BBS fallback.
A synthetic continuously readable socket proves that protocol-only input yields;
socket-pair tests cover fragmented negotiation and binary escaping. A queued host
path asserts that buffered input causes no sleeps, and the existing host workflow
exercises file search and workshop menus end to end.

The test suite uses cleanup-managed context stacks instead of the Python 3.11-only
`TestCase.enterContext`. The Windows launcher test explicitly mocks the platform,
so OS discovery cannot accidentally invoke its mocked subprocess launcher.
These checks use temporary files and simulated terminals, without vintage hardware.
