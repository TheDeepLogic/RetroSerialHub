# Terminal layout and cursor budgets

Reproduce with `python -m tests.measure_technical_behaviors`; see the `layout`
section of [the report](technical-measurements.txt). The relevant implementation is
[`OSFlyoutMenu.render`](../retro_os/menu.py),
[`ConsoleDashboard._frame`](../rsh_console.py), and
[`_host_pane`](../rsh_console.py).

## The last printable cell is not free space

The native menu uses `columns - 1`, so a 40-column terminal receives lines no
longer than 39 characters, and an 80-column terminal receives at most 79. Filling
the final cell can leave a terminal poised to wrap; at the bottom of the screen,
the next printable character can scroll the entire menu.

The native menu therefore emits exactly the configured number of rows, with no
trailing newline after its final prompt. The host dashboard similarly clips each
physical row to `terminal_columns - 1` and uses absolute cursor placement instead
of newline-driven painting. Tests check both the text dimensions and the virtual
viewport's scroll counter: a plausible-looking string is not sufficient evidence
that drawing it stays inside the screen.

## Where the menu rows go

The flyout menu reserves three header rows, one Shortcuts header, seven category
headers, and four footer rows. That leaves:

```text
action capacity = max(1, min(8, configured_rows - 15))
```

| Configured rows | Measured action capacity |
|---:|---:|
| 16 | 1 |
| 20 | 5 |
| 24 | 8 |
| 25 | 8 |
| 30 | 8 |
| 43 | 8 |

More than eight actions are never displayed together because item keys are A-H.
Short screens page the actions rather than letting the footer drift below the
viewport. Shortcut editing has an additional row-budget constraint; it is not
simply another eight-item category.

The native sweep exercised **1,536 menus**:

```text
2 widths x 6 heights x 4 shortcut counts x 8 selected sections
         x 2 connection types x 2 unread-message states
```

Every case had the expected row count, fit within the guarded width, ended its
cursor on the final configured row, and produced **zero virtual scrolls**.

## Why side-by-side mode starts at 124 columns

The dashboard budget is:

```text
80 host text cells + 2 host borders + 1 gutter + 40 status cells
                  + 1 terminal wrap-guard cell = 124 columns
```

A 123-column window has only 122 usable cells and takes the stacked layout.
At 124 columns, the 80-column host interior fits beside the minimum status width.
The host interior still allows all 80 cells because its final text cell is
followed by a border and additional dashboard columns, not the terminal's edge.

The host sweep covered **168 cases**: eight widths from 20 through 200, seven
heights from 5 through 50, and empty, four-profile, and crowded scenarios. The
crowded scenario adds 40 active selections, 20 pending Telnet requests, and an
error. Observed layouts were **114 stacked**, **36 side-by-side**, and **18 with
status above**. All retained a visible `cli>` prompt and stayed within the
viewport without scrolling. This does not mean every detail fits in five rows;
summaries and clipping remain necessary there.

## Semantic spacing versus terminal-height padding

An early host capture retained blank padding that native terminals need to anchor
their footer. The dashboard then added its own footer and pushed the menu heading
into scrollback. Removing every blank row fixed that problem but also removed a
useful separator. These are different kinds of whitespace.

The host now compacts terminal-height padding while recognizing the real main
menu's footer explicitly. It places status and the ATM/messages hint near the
bottom, then a blank row, console controls, another blank row, and the actual
prompt. Other tools do not get their status-looking text relocated.

For an 80-column main menu showing eight actions, the host can account for 19
menu-body rows, two status/hint rows, three control rows when Telnet is enabled,
two blank separators, one prompt row, and two borders: **29 pane rows**. A wrapped
prompt or narrower control hints needs more. The tall-layout condition reserves
at least 30 host-pane rows after the title and full-width status block; simply
assuming “24 rows means a whole host console” would miss these additions.

Further coverage:
[`test_terminal_layout.py`](../tests/test_terminal_layout.py),
[`test_rsh_console.py`](../tests/test_rsh_console.py), and
[`test_rsh_host.py`](../tests/test_rsh_host.py).
