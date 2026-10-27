# XMODEM wire costs: the byte after a block boundary

A file growing from 128 to 129 bytes nearly doubles its XMODEM traffic. That is
not a retry problem: the extra byte requires another complete 128-byte block.
This note measures the existing [sender](../rsh_transfer.py), rather than assuming
that file size and serial traffic are interchangeable.

## Method

Run `python -m tests.measure_technical_behaviors`. It creates temporary binary
files and calls the production `xsend` function with a memory peer providing
handshake, ACK, and optionally NAK bytes. It counts bytes written by the sender
and read from the peer. These are actual protocol byte counts, not measurements
of a physical serial link or independent validation by another XMODEM program.

The fixtures cover the 128-byte checksum and CRC variants. They do not measure
YMODEM or a 1K-block variant. Responses are preloaded, so the run's elapsed time
would say little about stop-and-wait performance on real hardware.

## Count both directions

A checksum packet is 132 bytes: SOH, block number, complemented block number,
128 payload bytes, and one checksum byte. A CRC packet has two check bytes,
making it 133 bytes. For `n = ceil(file_size / 128)`:

```text
Sender: n * packet_size + 1 EOT
Peer:   1 initial handshake + n ACKs + 1 EOT ACK
Combined checksum: 133*n + 3
Combined CRC:      134*n + 3
```

| File bytes | Blocks | Combined checksum bytes | Combined CRC bytes |
|---:|---:|---:|---:|
| 0 | 0 | 3 | 3 |
| 1 | 1 | 136 | 137 |
| 127 | 1 | 136 | 137 |
| 128 | 1 | 136 | 137 |
| 129 | 2 | 269 | 271 |
| 1,024 | 8 | 1,067 | 1,075 |
| 4,096 | 32 | 4,259 | 4,291 |

All fourteen baseline cases assert these formulas. The zero-length case still
has an initial handshake, EOT, and acknowledgement. At one byte, almost all
traffic is padding and framing; at 4 KiB, CRC framing is about 4.8% above the
file's byte count. CRC's extra check byte costs one byte per block compared with
the checksum variant in these successful exchanges.

The sender pads a short block with `0x1A`. Plain XMODEM does not convey the original
file length. A receiver cannot safely assume trailing SUB bytes are disposable
text padding when the file may be binary. The receive implementation preserves
padding unless it has an exact size; a successful transfer alone does not imply
that the receiver can infer the original length.

## A retry has a measurable price

For a 1,024-byte CRC transfer, injecting one NAK changes combined traffic from
**1,075 to 1,209 bytes**. The extra 134 bytes are a retransmitted 133-byte packet
and one extra peer response. Retries resend a whole block. The implementation's
retry budget is ten attempts per packet, with an EOT completion loop as well.

This fixture exercises one rejection; it does not emulate line noise, delayed
ACKs, or an independently computing receiver CRC. Those belong to the protocol
regression tests and hardware interoperability checks.

## Calculated serial budgets

For 8N1 framing, each byte occupies ten bits. An ideal serialized byte budget is
`10 * combined_bytes / baud`. For the successful 1,024-byte CRC case:

| Baud | Calculated byte-serialization budget |
|---:|---:|
| 300 | 35.83 seconds |
| 2,400 | 4.48 seconds |
| 19,200 | 0.56 seconds |

These are calculated budgets, not stopwatch results or promised transfer times.
They exclude response latency, buffering, software scheduling, negotiation
delays, and retries. XMODEM waits for an acknowledgement after each packet;
raising baud cannot eliminate those gaps.

See [the measurement harness](../tests/measure_technical_behaviors.py) and
[protocol regression tests](../tests/test_v25.py). The useful lesson is to report
payload bytes, wire bytes, and timing separately: each answers a different
question when a transfer feels slow.
