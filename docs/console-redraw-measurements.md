# Console redraw measurements

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
