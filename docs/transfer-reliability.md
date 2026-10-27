# Transfer deadlines and error recovery

During the v2.7a stability review, two failure paths were identified in the shared
XMODEM/YMODEM engine:

- Fragmented reads checked the deadline only after an empty read. A continuous
  trickle of bytes could therefore exceed the overall timeout for a packet.
- When reporting a transfer failure, writing cancellation bytes could itself fail
  on a disconnected transport and replace the original diagnostic.

The reader now checks its monotonic deadline before every read, including reads
following a nonempty fragment. Cancellation remains best effort: transport write
errors do not replace the original exception, and transfer progress is cleared.
The protocol's existing retries and CRC/checksum negotiation remain in effect.

The deadline is checked between transport reads. It cannot interrupt a blocking
transport read; the transport must have a finite read timeout or return promptly,
as the hub's serial and socket adapters do. These tests simulate transports and
do not establish timing or interoperability on physical vintage hardware.

Run the focused regressions and existing transfer/session integration tests from
the repository root:

```text
python -m unittest discover -s tests -p test_rsh_transfer.py -v
python -m unittest discover -s tests -p test_v25.py -v
```

The new tests simulate a monotonic clock and continuous fragments to prove the
read terminates at its deadline, verify successful fragmented reads, and inject
a cancellation write failure to verify the original error and progress cleanup.

Validation on 2026-10-27 with Windows Python 3.9: all 3 new regressions and all
29 existing v2.5 transfer/session tests passed, as did compilation. Running the
new regressions against the original engine reproduced both defects. Full-suite
discovery ran 377 tests with the same 29 errors and one failure seen in the
374-test baseline. Of those errors, 28 use `TestCase.enterContext`, which requires
Python 3.11 or newer; the remaining error involves a subprocess mock during
Windows platform detection. The failure is a host-menu integration timeout.
These existing test issues remain unresolved; physical serial testing was not
performed.
