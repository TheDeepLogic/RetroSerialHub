# Console redraw measurements

This historical before/after comparison was recorded during v2.6 development.
See the [engineering index](README.md) for the v2.7a measurement suite.

Measured before and after row caching in the same development session. Fixture:
150 columns by 40 rows, Ocean colors, four listening profiles with open serial
ports, 30 output lines, and a `cli>` prompt. The clock is fixed except during the
clock-tick test. Byte counts include UTF-8 borders and ANSI controls.

| Workload | Full redraw bytes | Cached redraw bytes | Rows repainted before / after |
|---|---:|---:|---:|
| Initial paint | 17,618 | 17,625 | 40 / 40 |
| 100 unchanged refreshes | 1,761,800 | 0 | 4,000 / 0 |
| Typing `calc 123456789 + 987654321` (26 keys) | 458,092 | 10,914 | 1,040 / 23 |
| Clock advances one second | 17,619 | 345 | 40 / 1 |
| One serial profile changes to missing | 17,618 | 930 | 40 / 2 |

Repeat the current implementation's measurements from the repository root:

```text
python -m tests.benchmark_console_redraw
```

This measures generated terminal traffic, not terminal rendering latency. Elapsed
times are also printed but vary by machine and are not regression thresholds.
Resizes, theme/background changes, output-stream changes, and explicit forced
redraws still repaint the viewport. Failed writes invalidate the cache.

## v2.7a alpha verification

Rerun on 2026-10-27, Windows, Python 3.14.2, working tree based on `bae0ea4`:

| Workload | Current bytes | Rows repainted |
|---|---:|---:|
| Initial paint | 17,689 | 40 |
| 100 unchanged refreshes | 0 | 0 |
| Typing the same 26 keys | 10,914 | 23 |
| Clock advances one second | 345 | 1 |
| One serial profile changes to missing | 930 | 2 |

The current initial frame differs from the historical fixture output above.
The historical full-redraw numbers have not been remeasured against today's
frame content; they remain the original before/after record. The important
regression check is that unchanged frames still emit nothing and small updates
still repaint only the affected rows. Runtime measurements vary and are omitted
here deliberately; byte and row counts are the repeatable results.
