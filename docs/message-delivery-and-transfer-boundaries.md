# Message delivery and transfer boundaries

Reproduce with `python -m tests.measure_technical_behaviors`; inspect `messages`
in [the report](technical-measurements.txt). Implementation:
[`SessionServices`](../rsh_session.py), the protocol guard in
[`rsh_transfer.py`](../rsh_transfer.py), the ASCII send guard in
[`rsh_files.py`](../rsh_files.py), and the Messages UI in
[`RETRO_SERIAL_HUB.py`](../RETRO_SERIAL_HUB.py).

## The original delay was not an inactivity threshold

Messages originally entered a queue that was drained at a CLI command boundary.
An idle recipient at the main menu could therefore get a pending count without
ever seeing the contents. Sending more keystrokes did not solve discoverability:
the items were terminal-session notices, not email.

Arrival now attempts a short notice immediately, independent of the activity
tracker. M at the main menu, or MESSAGES/MSGS at the menu or CLI, opens Messages.
No category or A-H item had to be added to an already crowded menu.

## Announced, unread, and retained are different states

| Event | Notice | Unread state | Stored body |
|---|---|---|---|
| Message arrives during ordinary use | Attempted immediately | Unread | Retained |
| Message arrives during a protected transfer | Deferred | Unread | Retained |
| Outermost transfer finishes | Waiting items announced once | Still unread | Retained |
| User opens an item | No new arrival notice | Read | Retained for the session |
| Connection/session ends | None | Session state ends | Inbox is not persisted |

The inbox keeps up to 100 items. Its unread queue is rebuilt from the retained
records, so evicting an old unread item cannot leave a count for a body that no
longer exists. Reading a message does not delete it. Explicit quiet mode remains
an opt-out; turning it off announces waiting items.

## A file notice should not become an unsolicited file dump

The measured fixture stores a **7,536-character** file message. Its immediate
notice is **116 bytes**, identifies `sample.txt`, restores `Choice: par`, and
contains none of the repeated file-body lines. Reading the item returns the full
body. Notice size depends on the preview and restored prompt; 116 is a fixture
result, not a fixed protocol size.

“Immediate” means no wait for the recipient's next CLI command. A real serial
link still takes time to transmit a notice. For illustration, 116 bytes at 8N1
require 1,160 serialized bits: about 3.87 seconds at 300 baud, 0.48 seconds at
2400, or 0.060 seconds at 19200, before any other delays. These are calculated
serialization budgets, not hardware timings.

The notice restores a bounded text tail of the interrupted line. It is not a
modal dialog and does not consume a keypress to dismiss itself. An application
that immediately repaints its screen can overwrite the banner, but the unread
item remains available in Messages.

## Transfer protection must be a boundary, not a timing guess

Checking “has the user typed recently?” says nothing about whether the next byte
belongs to a packet. Protection is instead a nesting counter managed by a context
manager, using the same reentrant write lock as notification emission.

The measured nested-transfer fixture writes `PACKET`, receives a message inside
an inner transfer, then writes `FINAL ACK` while the outer transfer is still
active. The protected interval contains exactly **15 fixture bytes**, with
**zero notices inside it**. Once the outermost context exits, exactly **one**
waiting-message banner appears, after the final marker. A second announcement
attempt does not repeat that banner.

XMODEM/YMODEM engines use this boundary, and ASCII sends guard their streamed file
bytes as well. File contents are not safe places to insert even a friendly text
notice. A message can be announced after completion or cancellation without
having been marked read merely because it appeared on the screen.

Focused tests: [`test_rsh_messages.py`](../tests/test_rsh_messages.py),
[`test_v25.py`](../tests/test_v25.py), and the idle-recipient file-delivery
integration case in [`test_rsh_host.py`](../tests/test_rsh_host.py).
