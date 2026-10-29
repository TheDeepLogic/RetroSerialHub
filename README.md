![Retro Serial Hub](images/retroserialhub_banner.jpg)

# Retro Serial Hub v2.7

A multi-port serial hub that connects vintage computers to modern TCP/IP
networks and accepts incoming Telnet-compatible connections. Systems using
dedicated Wi-Fi modems can connect over the LAN and access the same BBS, file
transfer, browser, and other retro-computing services through the hub's menu.

> **AI-Assisted Development Notice**
> 
> Hello, fellow human! My name is Aaron Smith. I've been in the IT field for nearly three decades and have extensive experience as both an engineer and architect. While I've had various projects in the past that have made their way into the public domain, I've always wanted to release more than I could. I write useful utilities all the time that aid me with my vintage computing and hobbyist electronic projects, but rarely publish them. I've had experience in both the public and private sectors and can unfortunately slip into treating each one of these as a fully polished cannonball ready for market. It leads to scope creep and never-ending updates to documentation.
> 
> With that in-mind, I've leveraged GitHub Copilot to create or enhance the code within this repository and, outside of this notice, all related documentation. While I'd love to tell you that I pore over it all and make revisions, that just isn't the case. To prevent my behavior from keeping these tools from seeing the light of day, I've decided to do as little of that as possible! My workflow involves simply stating the need to GitHub Copilot, providing reference material where helpful, running the resulting code, and, if there is an actionable output, validating that it's correct. If I find a change I'd like to make, I describe it to Copilot. I've been leveraging the Agent CLI and it takes care of the core debugging.
>
> The code and documentation are developed with assistance from GitHub Copilot, including its coding agents and tools available in the development environment. The specific agents and models may vary between changes. AI-assisted work can contain mistakes; please report issues or submit a pull request with a correction.

## Features

- **Retro Serial OS Runtime**: Interactive command shell (`cli>` / `OS`) with hot-reloadable module system, event bus pub/sub, multi-client sessions, and keyboard bridge shortcut profiles
- **Accordion Main Menu & Custom Shortcuts**: Fast categorized accordion flyout navigation with user-defined macros, arguments, and automatic flyout
- **Host Terminal / Command Prompt**: Quick launch the host OS shell (`cmd.exe` on Windows, or `$SHELL` on macOS/Linux) with bidirectional console streaming, local echo, and line translation
- **Interactive Host Console & Live Activity**: Run hub commands, send messages, and open menus from the host dashboard, with scrollable output, command history, and live terminal activity
- **Host-Approved Telnet Access**: New source IPs require host keyboard approval or a manual JSON allowlist entry before a session starts; serial connections are exempt
- **Workshop**: Disk-image inspection, hex viewing, checksums, text conversion, BASIC listing preparation, file splitting/joining, hex/Base64 encoding, and file comparison
- **Accessories & Media Tools**: Calendar with reminders, unit and number-base conversions, address book, shared file manager, ZIP archive browser, and host audio player with playlists
- **Real-Time Host System Monitor**: Live CPU load measurement, RAM, disk, and uptime metrics with automatic screen clearing and interactive controls (`top` / `sysinfo live`)
- **Multi-Format Document Viewer**: Text extraction and pagination pipeline for PDF, Word (.docx), Excel (.xlsx / .csv), Markdown, HTML, and web URLs with native Windows path handling
- **Direct File Transfers**: XMODEM, YMODEM, and ASCII transfers callable directly from the shell or menu (`xsend`, `ysend`, `asend`, `xrecv`)
- **Electronic Mail (Hub & Internet)**: Central inter-terminal hub mailbox with auto-detected sender identity, plus IMAP/SMTP internet email and desktop configuration GUI
- **Connected Terminal Messaging**: List active serial/Telnet terminals, send a direct message, or deliver a text file from the Communications menu
- **Terminal Messages**: Immediate message notices, M=Messages session inboxes for messages and received text files, and broadcasts to connected screens
- **Dedicated Retro Games**: Native text-mode Minesweeper, Solitaire (Klondike), Hunt the Wumpus, Lunar Lander, Blackjack, Mastermind, Word Guess, Star Trek, and the WarGames (W.O.P.R.) CLI simulation
- **Ambient Desk Companion**: Live ASCII weather forecasts (`wttr.in`), RSS news feeds (NPR, Hacker News, BBC), automated morning briefings (`briefing`), and interactive article reader (`news <num>`)
- **Background Task Scheduler**: Persistent interval, hourly, daily, weekly, and monthly tasks with broadcast notifications and command chaining. See the [scheduler guide](docs/scheduler-reliability.md) for commands, quoting, and recovery behavior.
- **LOGO Programming**: A line-oriented terminal Logo interpreter with repeat loops, variables, procedures, detailed turtle status, and optional host-side turtle graphics
- **Terminal Hardware Settings**: Saved screen width (40/80 cols) and height (24 rows by default), Caps-Only mode for vintage uppercase-only ROMs (Apple II Plus, PET, TRS-80 Model I), and serial character pacing delays
- **In-Hub Help & User Guide**: 9 built-in guide topics accessible directly from the menu (`HELP` or `?`)
- **Multi-Port Serial Support**: Connect multiple vintage computers simultaneously, each with independent configurations
- **BBS Directory**: Browse, connect to, and manage saved BBS destinations
- **Telnet**: Connect to a host and port directly; manage Telnet bookmarks or add destinations to the BBS directory
- **FTP/FTPS**: Browse FTP servers and save downloads to the hub or transfer them directly to the connected terminal
- **Text Library**: Browse and read text files with pagination; includes starter articles on classic computers
- **Web Browser**: Browse paginated text pages, follow numbered links, and manage bookmarks
- **Notes System**: Create, read, and manage text notes
- **COM Port Bridge**: Bridge between different serial ports for direct computer-to-computer communication
- **Keyboard Bridge**: Type serial input into the focused host application with customizable key profiles
- **AI Assistant**: Optional OpenAI, Gemini, or local Ollama chat accessible from vintage terminals
- **Hot-Reload Modules**: Edit feature modules without restarting the hub
- **ANSI Support**: Automatic detection and handling of ANSI escape codes for compatible terminals

## Requirements

- Python 3.9 or higher
- Dependencies listed in `requirements.txt`
- USB-to-Serial adapters or RS-232 ports for connecting vintage computers
- Optional: AI Assistant uses local Ollama without a key, or an OpenAI/Gemini API key
- Optional: FFmpeg (`ffplay` on PATH) for internet radio and additional audio formats/platforms
- Optional: eSpeak NG installed on the host for WOPR speech

## Installation

1. Clone or download this repository to your computer

2. Install Python dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
   This installs PySerial and, on macOS/Linux, `pynput` for the Keyboard Bridge.
   On macOS, grant the terminal or Python process Accessibility permission.
   On Linux, the bridge requires a supported graphical desktop session; Wayland
   sessions may not permit global keyboard injection.

3. Optional - For AI Assistant functionality:
   ```bash
   python -m pip install openai
   ```

4. Configure your serial ports and BBS list (see Configuration section below)

5. Run the hub:
   ```bash
   python RETRO_SERIAL_HUB.py
   ```

## Main Menu Navigation and Command Shell (CLI)

Retro Serial Hub features an accordion flyout main menu organized into seven categories optimized for 40- and 80-column retro terminals:
- **Sections (0–7)**: Only the selected category is expanded, showing its available actions (`[A]–[H]`, `[+]`, `[-]`), while other categories remain collapsed as headers:
  - `[0] Shortcuts`: User-defined quick shortcuts to commands and tools with custom arguments (e.g., weather feeds, favorite BBS connections, games, calculations). If any shortcuts are populated, this section automatically flies out upon opening the main menu.
  - `[1] Communications`: Bulletin Boards, Telnet Terminal, Web Browser, FTP Client, Electronic Mail, Connected Terminals (messages and file delivery), Session Capture, WOPR
  - `[2] Host Connectivity`: Host Applications, Launch Host App, Keyboard Bridge, COM Port Bridge, Host Terminal / Prompt (cmd/powershell/bash), System Monitor & Media, Host Printing, Serial Diagnostics
  - `[3] Files & Media`: File Manager, File Transfers (XMODEM/YMODEM/ASCII), Archive Browser, Text Library, Document Viewer, ASCII Image Viewer, Audio Player, Find Files
  - `[4] Games`: Dedicated Retro Games (Minesweeper, Solitaire, Hunt the Wumpus, Lunar Lander, Blackjack, Mastermind, Word Guess, Star Trek)
  - `[5] Accessories`: Notepad, Calendar, Calculator, Address Book, Unit Converter, Weather & News, AI Assistant, LOGO
  - `[6] Workshop`: Disk Image Inspector, Hex Viewer, Checksums, Text Converter, BASIC Listing Tools, Split / Join Files, Binary / Text Encoding, Compare Files
  - `[7] System`: Command Shell (CLI), Task Scheduler, Terminal Hardware Settings, Keyboard Profiles, Help & User Guide, Welcome Banner, Host Settings, Disconnect
- **Navigation**: Enter `0`–`7` (or section names such as `GAMES`, `CONNECTIVITY`, `SYS`) to expand that section. Enter the item's letter (`A`–`H` where available), `+`, or `-` to run it within the currently active section.
- **Shortcuts Management**: In the Shortcuts section, press `+` to add a shortcut with custom arguments (saved to `settings/local/user_shortcuts.json`), or `-` to remove an existing shortcut. You can also manage shortcuts from the CLI via `shortcut add <name> <cmd>`, `shortcut list`, `shortcut run <id>`, or `shortcut del <id>`.
- **Help & User Guide**: Comprehensive multi-topic documentation is accessible directly inside the hub by pressing `HELP` or `?` at the main menu, selecting `[E]` under System, or typing `help <topic>` in the CLI.
- **Direct Commands**: You can enter commands directly from the main menu prompt, such as `CLI` (or `OS`), `HELP` (or `?`), `SYSINFO`, `CLIP`, `VOL`, `MEDIA`, `WEATHER`, `NEWS`, `BRIEFING`, `SHORTCUT`, `APPS`, `VIEW`, `FETCH`, `LAUNCH`, `TERMINAL`, `CALC`, `LOGO`, `MAIL`, `MAILTO`, `MINES`, `SOLITAIRE`, `WUMPUS`, `WARGAMES`, `PRINT`, `KB`, `SCHEDULE`, `CAPS`, `PACE`, or `ATM` to return/refresh.

### Command Shell (CLI)

The host dashboard accepts input directly at the active hub prompt, with console
control hints immediately above it. It opens the standard numbered menu on
startup, with its own session and output history.
On the host main menu, status and the ATM/messages hint sit above a blank line,
the console controls, another blank line, and the active prompt. Other tools keep
their output in place; a blank line separates console controls from input.
Enter `CLI` for the command shell.
For example:

```text
terminals
msg to APPLE2 Hello from the host
broadcast Meeting in five minutes
calc 6 * 7
```

Use `terminals` to find exact destination names. Other terminals can reply with
`msg to Host <text>`. `ATM` opens the normal numbered menus; use `CLI` to return
to commands. Interactive tools use the same prompts as serial/Telnet sessions.
Host output stays in the dashboard: PgUp/PgDn browse it, Up/Down recall commands,
and `clear` clears the output pane. PgUp holds the history you are reading while
incoming output continues; the pane title shows `Scrollback - N new lines`.
**End** returns to live output and clears the counter. PgDn also returns live at
the bottom. Resizing reflows the same source text; incoming screen clears do not
discard the held view. Submitting input or explicitly clearing the console returns
to live output. In windows at least 124 columns wide,
the bordered host pane provides exactly 80 output columns on the left. Serial
and network status, connections, active menu selections, approvals, and events
appear on the right. Each active client gets its own activity entry; unused menu
options stay hidden. Taller windows move status and connections across the top
when at least 24 host output rows still fit below, with activity on the right.
Narrower windows stack status above host output.
Blank Enter answers prompts or continues a pause; Ctrl+X is forwarded to the
active host session. The host CLI also works
when inbound Telnet listeners are disabled.

At the console, `host help` (or `console help`) lists dashboard controls; `HELP`
continues to reach the hub. `clear` removes output while retaining the active
prompt. The activity monitor always shows active selections. Approvals and errors
have priority over normal status/activity rows, with overflow counts when space
is limited. The host session appears as `Host`, without adding a serial port or
Telnet connection to the live counts.

Any serial or Telnet terminal can submit a line to the host session by prefixing
it with `HOST`, for example `HOST theme Commodore`, `HOST ATM`, or
`HOST calc 6 * 7`. Bare `HOST` submits a blank Enter. This works at hub command
prompts and nested tool prompts; raw bridges, binary transfers, and remote BBS
streams retain their normal byte handling. The originating terminal stays in its
current tool; the command runs in the host session's current context.

The first `HOST` attempt from each source IP or physical serial port requires
separate host-control approval, even if the Telnet connection was already allowed.
The attempted command is not executed or queued. At the physical host keyboard,
type `allow host <request #>` or `deny host <request #>`. After approval, retry the
`HOST` command. Forwarded commands cannot approve host-control requests.
`pending` lists both Telnet and host-control requests; requests expire after two
minutes. Host-control permissions persist in
`settings/local/host_command_allowlist.json` (`allowed_ips` and
`allowed_serial_ports`); removing an entry revokes it without restarting.
Incoming Telnet connections continue to use `allow <request #>` / `deny <request #>`
and their own `telnet_allowlist.json`. If someone is editing a local host input
line, forwarded input is refused until that line is sent, preserving the draft.

Console appearance commands work at the active host prompt, including while a
submenu is open. Approved terminals can use the same commands with `HOST`:

```text
theme                         List schemes and current settings
theme Windows 3.1             Select a scheme by name (or its list number)
theme background off          Use the terminal background, including transparency
theme background on           Restore the scheme's backgrounds
theme colors off              Use terminal-default foreground and background
theme colors on               Restore scheme colors
```

Schemes are **Ocean** (the default), **Turquoise**, **Emerald City**, **Hot Pink**,
**Light**, **Dark**, **QBasic**, **Commodore**, **Apple IIGS**, **TI-99/4A**, **Windows 95**,
**Windows 3.1**, **Amber Monochrome**, and **Green Monochrome**.
Basic Blue and Windows 3.1 share one scheme; either name selects it. Windows 95
uses a teal desktop, silver-gray panels, and navy title/selection bars.
Light uses the DOS Shell Monochrome-4 Colors
palette (mostly white with black text); Dark uses mostly black with white text.
Background-off makes panel interiors, borders, and unused space transparent while
retaining scheme backgrounds for the title bar, input/status bands, and selection
highlights. The selected scheme and both switches
are saved in `settings/local/console_theme.json`. Selecting a scheme keeps the
background and color switches as chosen. `NO_COLOR` continues to disable colors.
These are dashboard controls; a remote terminal uses the separately approved
`HOST` prefix to access them.

Enter `CLI` at the main menu to open the interactive command shell (`cli>`). Type `help` for commands or `exit` to return to the menu:
- `sysinfo` (aliases `sys`, `top`): Displays host CPU cores, memory load, disk capacity, uptime, and OS platform information formatted cleanly for 40- or 80-column screens.
- `clip [text]` / `copy <text>` / `paste`: Reads the host OS clipboard or copies text to the host clipboard. Notepad also has `P` to save clipboard text as a note and `C<number>` to copy a note to the clipboard.
- `terminals`: Lists connected serial and Telnet terminals. `msg to <terminal> <text>` sends a message to one listed destination; `msg <text>` broadcasts to all.
- `logo`: Opens the interactive Logo prompt. Use `REPEAT 4 (FD 80 RT 90)` (parentheses or square brackets) to draw a square; drawing commands report turtle position and heading.
- `media <play|pause|next|prev|stop>` and `vol <up|down|mute>`: Controls host media playback and volume without leaving your retro terminal.
- `weather [city/zip]`: Fetches current conditions and ASCII weather forecast from wttr.in.
- `news [npr|hn|bbc] [count]` / `news <number>`: Parses and displays clean ASCII news headlines from RSS feeds. Type an article number (e.g. `news 1` or `news 1 full`) to read the article story summary or fetch the complete web article text.
- `briefing [location]`: Generates a complete desk briefing combining weather forecast, top news headlines, and host hardware status.
- `xsend <file>`, `ysend <file>`, `asend <file>`, `xrecv <dest>`: Initiates direct file transfers straight from the shell.
- `caps <on|off>`: Toggles uppercase-only mode (Caps Mode) for vintage computers without lowercase ROMs (Apple II+, early TRS-80, PET 2001).
- `pace <milliseconds>`: Adjusts inter-character serial pacing delay (e.g. `pace 2` for 2ms/char) to prevent buffer overflows on flow-control-less UARTs.
- `terminal [cmd|powershell|bash]`: Opens an interactive bidirectional console session into the host machine's command interpreter.
- `apps [refresh | <letter> | <filter>]`: Scans the host's applications. You can filter by initial letter (e.g., `apps c`) or search term (e.g., `apps note`). Interactive output supports pagination (`Enter`=Next, `Q`=Quit, `A-Z`=Skip to letter).
- `launch <app> [args...]`: Starts a host application by name, stem, or path. On Windows hosts, forward slashes (`/`) typed on Apple II keyboards (which lack a backslash key) are automatically translated to backslashes (`\`). Use `-k` for keyboard bridge mode or `-b` for background execution.
- `view <file/url>`: Extracts text and paginates supported document formats (TXT, PDF, DOC/DOCX, XLS/XLSX, CSV) or downloads and parses web pages.
- `kb profile <name>` and `kb map <key> <action>`: Selects or configures shortcut mappings in `settings/local/keyboard_profiles.json` (e.g., mapping `CTRL+W` to `WIN` or `CTRL+M` to `WIN+R`).
- `calc <expr>`, `mail [inbox|hub|net|read|send|mode|popup|mailto]`, `mines [new|r|f]`, `solitaire [new|draw|auto]`, `wargames`, `print <file/text>`, `ascii <image>`: Access host and retro utilities directly from the CLI.
- Modular feature commands (`notes`, `textlib`, `bbs`, `browser`, `telnet`, `ftp`, `files`, and `ai`) open their interactive module screens. Type `ATM` at any time to return to the main menu.

### Electronic Mail (Hub Mail & Internet Email)

Retro Serial Hub provides a dual-mode electronic mail system accessible from the menu (`1E`) or shell (`mail`):
1. **Integrated Hub Mailbox**: A shared local message spool stored on the hub. Every message is stamped with the originating user name and connection type (e.g. `APPLE2 [Serial]`, `Terminal [Telnet]`, or `Host System [Local]`). Any vintage terminal or host user can compose messages to other machines, read unread messages, and delete notes.
2. **Internet Email (IMAP/SMTP)**: Connect to any standard email provider. Lists and paginates IMAP inboxes on 40- and 80-column screens and delivers outbound messages via secure SMTP (STARTTLS or SSL).
3. **Host Desktop Auth Window**: Launch a GUI configuration window directly on the host PC desktop (`mail popup` or `python -m retro_os.mail_gui`) to configure server hostnames, ports, and app credentials without typing sensitive passwords over unencrypted serial or telnet connections.
4. **Instant Mode Toggle**: Toggle between Hub Mailbox and Internet Email at any time via `mail mode` or option `[4]` in the Mail menu.
5. **Host Mailto Trigger**: Open the host computer's default desktop mail client using `mail mailto <address> [subject]`.

### Dedicated Retro Games

All games feature clean ASCII board rendering optimized for both 40- and 80-column displays:
- **Minesweeper** (`mines`): Text-mode minefield with first-click safety, reveal (`r row col`), flag toggle (`f row col`), and customizable board dimensions.
- **Klondike Solitaire** (`solitaire`): Full card tableau with stock/waste piles, card movement, and automatic foundation moves (`f`).
- **WarGames (W.O.P.R.)** (`wargames`): Interactive NORAD defense computer simulation inspired by the 1983 film.

WOPR opens at an IMSAI-style CP/M prompt with two simulated disks. Explore with
`DIR`, `DIR *.COM`, `TYPE README.TXT`, and `TYPE MODEM.DOC` to discover the software.
`HELP` lists the shell commands. `A:` and `B:` switch disks; `STAT`, `PIP`, `DUMP`,
`REN`, `ERA`, `SAVE`, and `CLS` provide a small working command environment.
For example, `PIP B:=NOTES.TXT` copies notes to the scratch disk, and
`REN B:WORK.TXT=B:NOTES.TXT` renames that copy. `SAVE` creates a simulated memory
image; binary dumps show placeholder bytes. Disk changes last only for the current
WOPR session. `EXIT` or `ATM` returns to the hub.

- **Lunar Lander** (`games lander`): Turn-based descent challenge controlled with numeric engine burns.
- **Hunt the Wumpus** (`games wumpus` in the CLI, or Games section `[D]`): Cave exploration with numbered rooms, danger clues, bats, pits, and three-room arrow shots, designed for line-oriented terminals.
- **Blackjack** (`games blackjack`): Play hit or stand against a dealer with standard ace scoring.
- **Mastermind** (`games mastermind`): Crack a four digit code using exact and misplaced clues in up to ten guesses.
- **Word Guess** (`games wordguess`, or Games section `[G]`): Find a hidden five-letter word in six tries. `G` marks a correct position, `Y` marks a letter elsewhere in the word, and `.` marks a letter that is absent.
- **Star Trek** (`games trek`, or Games section `[H]`): Explore an 8×8 galaxy, scan quadrants and sectors, then destroy Klingons with phasers and photon torpedoes before the mission deadline. Move with `move <course> <warp>`; dock near a starbase to resupply.

### Built-in Help & User Guide

An interactive multi-topic guide is accessible anywhere by typing `HELP` or `?` at the main menu or selecting `[E]` under System. Topics cover hub capabilities, navigation, shell commands, hardware settings, games, and emergency hotkeys with built-in `--More--` paging.

### Accessories and Shared Files

These tools have terminal menus and CLI commands. Quote names and paths containing spaces.

| Menu | Tool | CLI examples |
|---|---|---|
| Accessories B | Calendar | `calendar month`, `calendar add 2026-11-01 09:00 "Retro club"`, `calendar agenda`, `calendar done <id>` |
| Accessories D | Address Book | `contacts add "Retro Friend"`, `contacts set <id> email user@example.org`, `contacts set <id> bbs example.org:23`, `contacts mail <id>`, `contacts connect <id>` |
| Accessories E | Unit Converter | `convert 72 F C`, `convert 1 mi km`, `convert FF hex bin` |
| Files & Media A | File Manager | `fileman ls`, `fileman cd <folder>`, `fileman copy <file> <destination>`, `fileman view <file>`, `fileman send <file> y` |
| Files & Media C | Archive Browser | `archive list`, `archive open software.zip`, `archive members`, `archive extract 2`, `archive extract all unpacked` |
| Files & Media G | Audio Player | `audio list`, `audio play 1`, `audio queue 2`, `audio pause`, `audio next`, `audio volume 70`, `audio save "Retro Mix"`, `audio load "Retro Mix"`, `audio radio <stream URL>` |

Appointments and contacts are shared by terminals and saved in `settings/local/`. Appointment times follow the host's local clock. Due reminders are queued for connected terminals, and today's appointments and overdue items appear when a terminal connects. Mark an appointment done to remove it from the open agenda.

File tools can browse the full host filesystem accessible to the hub process, including drives and paths outside `files/`. Host-to-host copying does not pass the file through the vintage computer. ZIP contents can be extracted individually or together; existing output files are not replaced. Each session keeps its own browsing location.

If ZIP extraction fails, the incomplete member is removed when possible. Completed
members remain available; retry the failed member by number after resolving the
error. See [tool data and recovery](docs/tool-data-reliability.md).

Audio plays through the host speakers with one shared playback queue. Select audio from any accessible host folder; saved M3U playlists go in `files/playlists/`. Windows provides native local playback. Installing FFmpeg with `ffplay` on PATH enables internet radio, additional formats, and playback on other platforms. Playback errors appear in `audio info`.

### Menu map

The terminal menu, host activity monitor, and navigation help share one catalogue.
Each category has at most eight entries, A-H. Workshop is section **6** and System
is now section **7**. Existing command names remain available. Shortcuts show eight entries per page;
use `<` and `>` to change pages.

| Location | New entry |
|---|---|
| Communications G | Session Capture |
| Host Connectivity H | Serial Diagnostics |
| Files & Media H | Find Files |

Workshop's initial tools:

| Key | Tool | What it does |
|---|---|---|
| A | Disk Image Inspector | Image size, size hints, raw sector inspection and extraction |
| B | Hex Viewer | Bounded byte-range view with hex offsets and printable ASCII |
| C | Checksums | SHA-256, SHA-1, MD5, or CRC-32, streamed for large files |
| D | Text Converter | Strict character-set conversion, LF/CRLF/CR, upper/lower case |
| E | BASIC Listing Tools | Validate numbered ASCII listings and renumber common line references |
| F | Split / Join Files | Chunk a file, then verify sizes and SHA-256 before reassembly |
| G | Binary / Text Encoding | Hex or Base64 encoding and decoding |
| H | Compare Files | Stream a comparison and report the first differing byte |

Workshop creates new outputs and refuses to replace existing files. Conversion,
encoding, and BASIC operations accept source files up to 8 MiB; raw sector
extraction is limited to 16 MiB per operation. Hashes, comparisons, splitting, and
joining stream data. Inspecting a disk image does not identify or modify its
filesystem. Raw sector extraction is not ProDOS/CP/M/DOS filesystem extraction.
BASIC preparation works on text listings; it does not tokenize programs or convert
between dialects. Inspect dialect-specific constructs before loading a result.
Split parts need a compatible reassembly tool on the destination machine.

### Browsing and finding files

File Manager, File Transfers, Archive Browser, Document Viewer, and Text Library
use one browser. Audio uses the same directory/filter/favorites model with audio
filtering and playback controls. The current directory and filename filter are
shared within a session; folder favorites persist across sessions. Full host
filesystem access remains available.

- A number opens a directory or a file's action menu.
- D lists drives/root, B opens the parent, H opens the shared folder, G accepts a path.
- P returns to the previous folder; repeat it to switch between two folders.
  The CLI equivalents are `fileman previous` and `fileman cd -`. History belongs
  to the current session; a failed directory change preserves the current folder.
- F changes the filename filter; `*` clears it. The current filter is displayed.
- V manages folder favorites, M manages marked items, O opens other operations.
- A selected file offers relevant view/play/image/ZIP actions, plus copy, move,
  rename, transfer, and marking.
- Copy/move accepts `=` to reuse the remembered destination. Mark multiple items
  to copy/move a batch; conflicting destinations are rejected before starting.
  This includes identically named items marked in different folders; rename an
  item or copy/move those items separately. Rejected batches retain their marks.
- Other operations include folder creation, upload, protocol selection, search,
  opening a web URL, and reading notifications.

Find Files accepts a filename wildcard and a host folder. Plain text searches are
also supported (`manual` matches names containing that text). Searches stop after
200 results or 5 seconds and report that limit, so narrow the folder if needed.
Inaccessible directories are skipped and counted. Results use the same file actions.

Tool screens separate action lists, navigation controls, usage syntax, information,
and input prompts with blank rows. Page budgets reserve those rows so the added
spacing does not push results off the configured screen.

All generic tool menus show at most eight actions per page. N/B changes action
pages when necessary. Q goes back, Enter refreshes ordinary menus, and empty
prompted arguments cancel. ATM unwinds the standard nested tool menus to the
main menu. Reader/game-specific controls are shown on their own screens.

### Reading and notes

The reader supports Enter=next, B=back, F=find, N=next match, M=bookmark,
R=recall bookmark, G=page, H=first page, L=last page, and Q=back. Type a page
number directly to jump without an extra prompt. HOME/FIRST and END/LAST are
also accepted as typed commands. Out-of-range numbers leave the current page
unchanged and show the valid range; Enter or Q cancels the G prompt.
Position and bookmark are saved by file
and terminal width. The Text Library and note selections open this reader.
Files selected for viewing use the host's existing extraction support.
Unreadable or corrupt saved positions no longer prevent reading. The reader starts
at the beginning and shows a notice if it cannot save. Invalid offsets are reset
or clamped to the document; corrupt settings files are preserved for repair.
Search matches ignore case and wrap to the beginning, using constant extra memory
for line-number traversal.

In Notepad, O opens edit, rename, export, and search operations. E<number> edits
an existing note. The line editor accepts `replace <line> <text>`, `append <text>`,
`delete <line>`, `save`, N/B for preview pages, and Q to cancel changes. Quotes in
replacement text are retained. R<number> renames a note, X<number> exports to a new
host path, `F text` searches names and content, and `ALL` resets the search.
If a note was deleted, cannot be read, or is not valid UTF-8, Edit displays an
error and returns to the Notes menu so you can choose another note or quit.
If saving fails while writing or replacing the temporary file, the original note
and your in-memory edits remain intact so you can retry `save`. Failed saves also
clean up their temporary file when filesystem permissions allow it.
Large content searches inspect note text up to 1 MiB, while filenames are always searched.
Content search skips notes that cannot be read or disappear during the search,
reports the skipped count, and continues returning the other matches.
Clipboard creation/copy and the original read/create/delete operations remain.

### Audio

The player stays compact. Queue/playlists opens queue editing (remove/reorder),
repeat, shuffle, and Radio / Music Folder. Save radio stations by name and save a
preferred music folder. Browse Files opens the saved music folder when one exists.
Stop playback before removing or reordering the current track;
shuffle preserves that track and randomizes the upcoming queue.

CLI examples:

```text
audio station add "Retro Radio" "https://example.org/stream"
audio station play "Retro Radio"
audio musicfolder "F:/Music"
audio remove 3
audio reorder 4 2
audio repeat on
audio shuffle
```

### Capture, diagnostics, messages

Session Capture records readable outgoing terminal text, including locally echoed
conversation, to `hub_tools/captures/`. Control sequences are translated/removed;
raw binary transfers and secret input/output are excluded. Captures can be stopped,
listed, viewed, and exported. It does not replay captured keystrokes or commands.

Serial Diagnostics lists connected sessions, byte counters, last-input age,
settings and modem signals where supported, recent ASCII/hex traffic, and active
transfer progress. The host can request cancellation using
`diagnostics cancel <terminal-name-or-port>`. It never opens a second connection
to a busy port or toggles modem control lines automatically.

Terminal messages, reminders, scheduled broadcasts, and received text files now
announce themselves immediately, even while the terminal is idle or at a prompt.
Only active file transfers automatically defer notices; deferred notices appear
when the transfer finishes. A short banner identifies the message and restores
the current input line. Long files stay in Messages instead of flooding the screen.

Press **M** at the main menu when **M=Messages** appears, or type `MESSAGES` / `MSGS`
at the main menu or CLI. This opens the session inbox with unread markers, paging,
individual messages, and read-all-unread. Received files are here, separate from
Electronic Mail. Read messages remain available for the session; the inbox keeps
up to 100 items and resets on disconnect. Connected Terminals also has M=Messages
(the old N shortcut remains accepted).

Explicit quiet mode remains an opt-out: `messages quiet on/off` (or the older
`notifications quiet on/off`) changes it for this session. `machine quiet on/off`
saves the default. Turning quiet off announces any waiting messages.
Connected Terminals shows input age
and queued counts. The host status panel shows transfer byte/retry progress.

### Transfers

XMODEM supports checksum and CRC send negotiation, fragmented reads, duplicate
block acknowledgment, bounded waits/retries, and host-requested cancellation.
YMODEM sends CRC headers/data and completes the end-of-batch handshake. Progress
is host-side and is excluded from the protocol byte stream.

XMODEM does not carry the original length. Received final-block padding is
preserved by default; trailing 0x1A bytes are never blindly removed. For an exact
binary length, use:

```text
xrecv "F:/Incoming/program.bin" 12345
```

A completed receive is published to its destination only after successful receipt.
Failed receives keep a uniquely named `.part` file; inspect or remove it yourself.
Existing destination files are not replaced. Hardware testing with your vintage
terminal software is still necessary alongside the automated protocol tests.

### Machine preferences and launch presets

Terminal Settings includes transfer protocol, starting screen, reconnect behavior,
and idle timeout. Host Settings > Machine Preferences exposes all saved settings.
Width, uppercase mode, character pacing, and ANSI preferences remain available.

```text
machine list
machine pace_ms 5
machine caps on
machine columns 40
machine protocol YMODEM
machine start menu
machine reconnect menu
machine idle_seconds 300
machine clear_sequence 1b76
```

Clear sequences are hex bytes. `reconnect resume` retains the active screen;
`reconnect menu` returns to a fresh menu on input after the serial idle timeout.
An idle timeout is inferred inactivity, not proof that a cable was disconnected.
Starting-screen changes apply on the next session. Preferences live in
`settings/local/machine_preferences.json` and are separate from the existing width/ANSI
preference files; setting width through the menus/CLI keeps them in agreement.

Host Applications > Launch Presets saves a name, application, working directory,
and background/terminal/keyboard launch mode. The CLI also accepts arguments:

```text
presets add "Build BASIC" terminal "F:/Retro/Project" python build.py
presets run "Build BASIC"
```

New preparation/session tools use Python's standard library. Existing optional
viewer, audio, keyboard, and speech dependencies remain unchanged.


### Terminal height, stable menu footers, and console borders

System (7) > Terminal Settings (C) > Screen Size (1) has width and height controls.
Height defaults to **24 rows** and is saved per profile. Set it to the actual
terminal height (16-100); the hub does not guess a vintage terminal's dimensions.
The CLI equivalents are `machine rows 25` or `height 25`. `rows: 24` can also be
supplied in `serial_profiles` in `settings/local/hub_config.json` before a saved preference exists.

At both 40 and 80 columns, the main menu retains a blank row between the version
and Shortcuts. Its footer ends at the configured last row, with padding above the
status line so selecting a short category does not move the prompt. At both widths
there is a blank row between the ATM note and the input prompt. On a 24-row
screen, the status/ATM/prompt rows are 21/22/24 at both widths (row 23 is blank). Shorter screens page active entries
using `<` and `>` when needed. Submenu entry/redraw uses the configured clearing
sequence before displaying new work.

The modern host dashboard uses Unicode box borders when stdout's encoding can
represent them. This is independent of the vintage terminal's character set;
serial/Telnet menus retain their existing ASCII output. Windows, macOS, and Linux
Unicode-capable terminals need a font with box-drawing glyphs. An incompatible
output encoding automatically uses ASCII borders. Set `RSH_ASCII_BORDERS=1`
before starting the hub to force the old borders if your font or terminal needs it.

## Configuration

Core settings are in **settings/local/hub_config.json**. There is no `config.py`.
Use the host console's **config** menu to add a computer, or edit the JSON while
the hub is stopped. New installations start with APPLE2 on COM1 and C64 on COM2;
inbound Telnet is disabled until configured. These are starter assignments, so
select the ports actually present on your computer.

On the first interactive launch, the console opens the configuration menu
automatically. Serial workers and inbound listeners wait until you leave setup,
so starter assignments do not produce connection failures while you configure
them. Use **5 Edit existing profile** to adjust the starter computers, or add
another. **Q Return to hub** finishes setup, reloads saved settings, and starts
the configured profiles. This also acknowledges unchanged starter defaults.
Completion is saved locally as `configuration_completed: true`; later launches
open normally. Your existing local setup is already marked complete. Without an
interactive console, the hub uses the JSON settings directly.

### Host configuration wizard

At the physical host console, type `config` (or `host config`). Its separate menu
offers Add Profile, Edit Profile, List Profiles, Hub Defaults, and WOPR Speech.

Add Profile walks through a unique name, a scanned serial-port selection, baud,
data bits, parity, stop bits, software/hardware flow control, ANSI menus and
translation, screen-clear hex bytes, cursor-home clearing, width (40/80), height
(16-100), inactivity timeout, and optional inbound Telnet bind address and port.
The port step shows eight detected devices per page: use Next/Prev, R to rescan,
or type a device name manually for an offline device or a Unix serial path.

Enter accepts a displayed default; Back revisits a field. Cancel discards the
draft and returns to the configuration menu, and Q exits that menu. A review
screen requires **yes** before writing anything. Duplicate serial assignments,
conflicting listener ports, invalid values, and settings changed by another
writer are rejected without overwriting the saved configuration.

Newly saved profiles start their serial worker and optional Telnet listener
immediately, without restarting existing connections. Missing hardware is shown
by the normal connection status; saving does not guarantee a port can be opened.
If activation fails, the saved profile remains available for the next launch.
Outside first setup, hub-default, speech, and existing-profile changes require a
restart, as do manual JSON edits. Use **5 Edit existing profile** for an existing
computer; remove profiles in JSON while stopped. Remote HOST commands cannot
open or operate this menu, even after host-control approval.

### JSON settings and personal data

Configuration and application data live under **settings/**:

- **settings/defaults/** contains version-controlled, public starter templates,
  including the supplied web/FTP bookmarks and keyboard profiles. The AI template
  contains a placeholder key and the Telnet allowlist starts empty. `hub_config.json`
  supplies two example computers; `bbs_directory.json` supplies structured BBS entries.
- **settings/local/** contains live JSON: credentials, mail, bookmarks, contacts,
  appointments, shortcuts, scheduler tasks, terminal preferences, reading
  positions, and other saved settings. Missing starter files are copied here;
  other files are generated when their features need them. Editing live settings
  never changes the public templates.
- On first use, existing JSON files from the project root, `mail/`, `hub_tools/`,
  and the former `retro_os/` storage location move into `settings/local/`.
  Existing local files take priority; differing old copies are preserved under
  `settings/local/legacy/`. Identical duplicate copies are removed. No existing
  settings are replaced by templates. JSON migration leaves non-JSON content,
  such as session captures in `hub_tools/captures/`, in place.

Back up `settings/local/` privately. It may contain passwords, API keys, mail,
addresses, and personal paths. Git ignores that directory and JSON outside the
explicit public-defaults location, including legacy JSON locations. Only put
reviewed, sanitized starter content in `settings/defaults/`; do not copy live
files there wholesale or force-add ignored personal files. To publish a new
bookmark default, add the intended public entry to its template separately.
Template changes affect missing local files, never existing personal copies.
Moving a previously tracked file does not erase it from older Git history.

The hub JSON contains `schema_version: 1`, `serial_profiles`, `telnet_listeners`,
`welcome_banner`, `serial_idle_timeout_seconds`, and `wopr_speech`. WOPR speech
uses `enabled`, `rate`, `volume`, `voice`, `pitch`, `gap`, and `executable` (empty
means auto-detect). The general timeout uses seconds, with 0 disabling it;
profiles can override it using `idle_timeout_seconds`. JSON uses numeric serial
settings (8 data bits, parity `"N"`, 1 stop bit), not Python constants.

Specialized stores remain separate: AI credentials, BBS directory, approvals,
console appearance, terminal/machine preferences, and the welcome-banner override.
Saved terminal width/translation/machine preferences and the saved welcome banner
continue to override profile/global defaults. Changing those defaults does not
erase an existing terminal preference or banner override.

### Serial Port Configuration

Each entry in `serial_profiles` represents one vintage computer or device.
For example, this is a fragment of `hub_config.json`:

```json
{
    "serial_profiles": {
        "APPLE2": {
            "port": "COM1",
            "baud": 19200,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "xonxoff": false,
            "rtscts": false,
            "ansi": false,
            "translate_ansi": true,
            "clear_sequence_hex": "1b76",
            "ansi_home_clears_screen": true,
            "columns": 80,
            "rows": 24
        }
    }
}
```

Set `columns` independently for each machine profile to `40` or `80`. This is
the profile's default width; the main-menu **System → Terminal Settings → Screen Size** option can
switch and save that profile's preference. The saved selection is stored in
`settings/local/terminal_columns.json` and takes precedence over the profile default. At 40 columns,
menus use a compact layout, browser pages wrap to the configured width, long
labels are shortened to fit, and ANSI translation uses the configured terminal
width. The included defaults use 80 columns for APPLE2 and 40 for C64;
profiles without this setting default to 80.

Common baud rates for vintage systems:
- Apple II with Super Serial Card: 300, 1200, 2400, 9600, 19200, or 115200
- Commodore 64: 300, 1200, 2400
- IBM PC/XT/AT: 300, 1200, 2400, 9600
- TRS-80: 300, 1200, 2400, 9600

#### Optional translation for non-ANSI terminals

ANSI translation is useful with any terminal or display that cannot interpret
the control sequences sent by a remote system. It is configured independently
in each `serial_profiles` entry and affects **incoming BBS/Telnet data** on that
serial profile. It does not affect the serial-to-serial COM Port Bridge or
other configured ports. Hub menu screens use `ansi` for native ANSI
clear/home controls; when ANSI translation is enabled, they use
`clear_sequence_hex` to clear the terminal.

```json
{
    "ansi": false,
    "translate_ansi": true,
    "clear_sequence_hex": "0c",
    "ansi_home_clears_screen": false
}
```

- `translate_ansi` enables the lossy ANSI/VT100-to-text translator. It strips
  color and unsupported control sequences, approximates common CP437
  line-drawing characters, and linearizes supported cursor positioning. It is
  not a complete terminal emulator; applications using complex screen
  addressing or terminal queries may not display correctly.
- `clear_sequence_hex` represents the bytes sent to the terminal for a
  supported erase-in-display/reset request, incoming form-feed (`0x0C`), or a
  Hub menu screen clear when `translate_ansi` is enabled.
  Set this to the clear-screen control sequence expected by the receiving
  terminal or its software. The default when omitted is form feed
  (hex `"0c"`). For ESC-v, use `"1b76"`; no Python byte literal is needed.
- `ansi_home_clears_screen` defaults to `False`. Set it to `True` when an
  application redraws a screen by returning the cursor home and the configured
  clear sequence is suitable. This can be useful for refreshed or animated
  interfaces; cursor-home is then treated as a clear rather than merely
  repositioning the cursor.

The clear sequence can be any byte sequence understood by the terminal or its
software. Some terminal emulators can map a custom sequence to a screen action.
Leave translation disabled for terminals that already interpret the remote
system's control sequences.

### BBS Directory

Both the numbered menu and CLI load `settings/local/bbs_directory.json`, a list
of objects containing `name`, `host`, and numeric `port`. There are no parallel
name/host/port lists to edit. On first use the supplied 64-entry directory is
copied from `settings/defaults/bbs_directory.json`; existing local entries win.
Changes made with **Bulletin Boards → M=Manage directory** update the local file.
Delete it while stopped to restore the public template on the next launch.

```json
[
    {"name": "Example BBS", "host": "bbs.example.org", "port": 23}
]
```

In the **Telnet** option, enter a hostname/IP and port for a direct TCP terminal
connection. Choose whether to save that destination in Telnet bookmarks, add it
to the Bulletin Boards directory, or connect without saving. Telnet bookmarks
are stored separately in `settings/local/telnet_bookmarks.json`; select a saved destination by
number or use `D` to delete it. Both connection types support `ATH` to hang up
and `ATM` to return to the main menu. Incoming data uses the same configured
ANSI translation and screen-clear behavior.

### Inbound Telnet-Compatible Server (Optional)

Retro Serial Hub can also accept incoming TCP terminal connections. Add a
`telnet_listeners` entry in `settings/local/hub_config.json` for each profile you want
to expose, using a distinct port for each profile:

```json
{
    "telnet_listeners": {
        "APPLE2": {"host": "0.0.0.0", "port": 6400},
        "C64": {"host": "0.0.0.0", "port": 6401}
    }
}
```

The keys must match entries in `serial_profiles`. Set `host` to `0.0.0.0` to
accept connections from other devices on the LAN, or `127.0.0.1` for local
connections only. Start the hub, then connect a TCP terminal or Wi-Fi modem to
the hub computer's IP address and the configured port (for example,
`192.168.1.20:6400`). The selected profile controls the menu's ANSI behavior;
the server works even if that profile's serial port is not connected.
When a listener starts, the hub prints detected LAN IPv4 address(es) and ports
to use for connecting.

Incoming Telnet clients must be listed in `settings/local/telnet_allowlist.json`. The hub
creates this file with an empty `allowed_ips` array on its first network-enabled
start; no address, including loopback, is automatically trusted. Serial
connections do not use this approval process.

An unknown address waits for up to 120 seconds while the host dashboard shows
its request number, source IP, and requested machine profile. At the **host
computer's console**, type `allow 1` or `deny 1` (using the displayed request
number), then press Enter. `pending` lists pending requests. Approval is saved
before the waiting client receives a hub session. Future connections from that
IP can enter any machine profile without another prompt. Input sent by an
unapproved client is discarded and cannot approve its own connection.

You can also edit the JSON manually, using individual IP addresses:

```json
{
  "allowed_ips": ["192.168.1.13", "192.168.1.14"]
}
```

See `settings/defaults/telnet_allowlist.example.json` for an empty template. Manual additions apply
to waiting clients and new connections without a restart. Removing an address
blocks its next connection; it does not end an existing approved session.
Missing files mean no addresses are approved. Invalid JSON, invalid entries,
or a failed approval save never grant access. Without an interactive host console
(for example, a background service), unknown connections are refused; add their
addresses manually and reconnect. Pending approvals are limited to 16, with one
per source IP, and unanswered requests expire.

This trusts source IPs, not hardware identities. DHCP reservations help keep
entries assigned to the intended devices; devices behind the same NAT or proxy
can share an approved address. Approved clients still have the hub's full host
capabilities. Telnet remains unencrypted: restrict access with your firewall and
do not forward these ports from the Internet. The listener is disabled when
`telnet_listeners` is empty, as in the public starter configuration.

### AI Assistant Configuration (Optional)

The assistant supports **OpenAI**, **Google Gemini**, and **local Ollama** from
Accessories G. All three use the same terminal chat interface and the optional
client library: `python -m pip install openai`. Using that library with another
provider does not send requests to OpenAI.

Choose one provider in `settings/local/ai_config.json`. Configuration is managed
on the host; the terminal displays the selected provider and model.

#### Local Ollama: no API key or token charges

Install [Ollama](https://ollama.com/download) on the hub computer, start it, and
run `ollama pull llama3.2:3b` once to download the example model. Use:

```json
{
    "provider": "ollama",
    "model": "llama3.2:3b"
}
```

The hub connects to `http://localhost:11434/v1/`. No API key, paid account, or
cloud service is needed for a downloaded local model. Model speed and capacity
depend on the host's hardware. Use `ollama list` to see installed model names.
For an Ollama server on another host, set `base_url` to its full HTTP(S) address
ending in `/v1/`, or set `OLLAMA_BASE_URL`. See
[Ollama compatibility](https://docs.ollama.com/api/openai-compatibility).

#### Google Gemini: hosted free-tier option

Get a key from [Google AI Studio](https://aistudio.google.com/apikey), then use:

```json
{
    "provider": "gemini",
    "model": "gemini-3.8-flash",
    "api_key": "your-gemini-api-key"
}
```

You can omit `api_key` and set `GEMINI_API_KEY` instead. Gemini offers a free tier
for eligible models, accounts, and regions, with quotas and rate limits. A key
alone does not guarantee free usage: keep the project on the free tier if that
is your intent. Free-tier content may be used to improve Google's products.
Check [current pricing and terms](https://ai.google.dev/gemini-api/docs/pricing).
Gemini uses the model's default thinking settings unless `reasoning_effort` is
explicitly configured. Available levels depend on the model; the hub accepts
`minimal`, `low`, `medium`, or `high` as explicit overrides. Use `default` or
remove the setting if Gemini rejects a thinking level. See
[Gemini compatibility](https://ai.google.dev/gemini-api/docs/openai).

#### OpenAI: existing configuration remains supported

```json
{
    "provider": "openai",
    "model": "gpt-5.6-terra",
    "api_key": "your-openai-api-key"
}
```

Omitting `provider` keeps the existing OpenAI behavior. `OPENAI_API_KEY` can
supply the key instead. OpenAI API usage is billed separately from a ChatGPT
subscription; this option does not provide free ChatGPT access.
The existing default model and OpenAI reasoning settings are preserved.

#### Overrides, conversation settings, and troubleshooting

- `AI_PROVIDER` overrides `provider`: `openai`, `gemini`, or `ollama`.
- `AI_MODEL` overrides the model for the selected provider. Next in precedence
  are `OPENAI_MODEL`, `GEMINI_MODEL`, or `OLLAMA_MODEL`, respectively, then JSON
  `model`, then that provider's default.
- Provider-specific key environment variables override JSON `api_key`. Switching
  providers through `AI_PROVIDER` does not reuse another provider's JSON key,
  model, token budget, or reasoning settings.
- `max_tokens` in JSON sets the response budget (1-8192; default 500). Reasoning
  models can consume part of that budget before producing visible text; increase
  it or choose another model if replies are empty or cut short.
- For OpenAI, `reasoning_effort` in JSON or `OPENAI_REASONING_EFFORT` controls
  reasoning. The default OpenAI model uses `none`; custom models omit the field
  unless configured. `default` omits it for any OpenAI model. Ollama omits the
  reasoning field; choose a suitable local model.
- Reopen the assistant after changing configuration. An active conversation keeps
  its provider, model, credentials, and options. N clears its history while keeping
  those settings; Q exits. Configuration is never written by terminal chat.
- Requests have a 60-second timeout and no automatic retries. A quota, connection,
  or model error stays with the selected provider; there is no automatic fallback
  to a potentially paid service. Failed requests leave conversation history ready
  to retry. For Ollama connection/model errors, check the service and `ollama list`.

## Usage

### Starting the Hub

Run the hub from the command line:

```bash
python RETRO_SERIAL_HUB.py
```

The startup console shows each profile's serial-port and inbound TCP-listener
status, connection addresses, and active remote-client counts. In an interactive
terminal, the status dashboard updates live and uses color when supported.
Serial ports that are not present are marked unavailable; enabled TCP listeners
continue to run independently. When output is redirected, status changes and
errors are printed as ordinary text without ANSI color codes.

### Connecting Your Vintage Computer

1. Connect your vintage computer to the USB-to-Serial adapter
2. Start your terminal software on the vintage computer
3. Configure the terminal to match its JSON profile (baud rate, data bits, parity, stop bits)
4. Press Enter to see the main menu. Type `ATM` at any time to return to it.

### Main Menu

The main menu features an interactive accordion flyout layout designed for vintage 40- and 80-column terminals:

- **[0] Shortcuts**: User-defined command macros with custom arguments. Automatically flies out when populated. Press `+` to add a shortcut or `-` to remove one.
- **[1] Communications**: `A` Bulletin Boards, `B` Telnet, `C` Web Browser, `D` FTP, `E` Electronic Mail (Hub & Internet), `F` Connected Terminals (list, message, or send a text file), `G` Session Capture, and `H` WOPR.
- **[2] Host Connectivity**: `A` Host Applications, `B` Launch with Keyboard Bridge, `C` Keyboard Bridge Profiles, `D` Serial COM Port Bridge, `E` Host Terminal / Prompt (`cmd.exe`/`powershell`/unix shell), `F` System Monitor & Media Controls, `G` Host Printing, and `H` Serial Diagnostics.
- **[3] Files & Media**: `A` File Manager, `B` File Transfers (XMODEM, YMODEM, ASCII), `C` Archive Browser, `D` Text Library, `E` Document Viewer (PDF, DOCX, XLSX, CSV, Markdown, Web), `F` ASCII Image Viewer, `G` Audio Player, and `H` Find Files.
- **[4] Games**: Dedicated retro text games: `A` Minesweeper, `B` Solitaire (Klondike), `C` Lunar Lander, `D` Hunt the Wumpus, `E` Blackjack, `F` Mastermind, `G` Word Guess, and `H` Star Trek.
- **[5] Accessories**: `A` Notepad, `B` Calendar, `C` Calculator, `D` Address Book, `E` Unit Converter, `F` Weather & News, `G` AI Assistant, and `H` LOGO. Logo accepts commands in the terminal and reports turtle position and heading after drawing; when Tkinter is available, it also opens a host-side turtle window.
- **[6] Workshop**: `A` Disk Image Inspector, `B` Hex Viewer, `C` Checksums, `D` Text Converter, `E` BASIC Listing Tools, `F` Split / Join Files, `G` Binary / Text Encoding, and `H` Compare Files.
- **[7] System**: `A` Command Shell (`cli>` / `OS`), `B` Task Scheduler, `C` Terminal Settings (40/80 cols, Caps-Only, Serial Pacing, ANSI), `D` Keyboard Profiles, `E` Help & User Guide, `F` Welcome Banner, and `G` Host Settings. Remote TCP clients also see `H` Disconnect at the bottom.

Enter a section number (`0`-`7`) or name (`GAMES`, `SYS`, `HOST`, etc.) to expand it, then enter the letter (`A`-`H`) to activate an option. You can also switch between the accordion flyout and the legacy numbered menu layout.

### LOGO

Select **Accessories > H > LOGO**, or type `LOGO` at the main menu. At the `Logo>` prompt, try `REPEAT 4 (FD 80 RT 90)` to draw a square; square brackets work too. Use `STATUS` to inspect turtle state and `HELP` to see the supported commands. Variables (`MAKE "side 60`), arithmetic words, and user procedures (`TO SQUARE :side`, then commands, then `END`) are supported. Type `BYE` to return to the hub. Drawing output is always described in the terminal; the graphical turtle window is optional and requires a working Tkinter display.

The Keyboard option types into the focused host application. Enter, Tab,
Backspace, and Escape are supported. The configured Ctrl+letter exit binding
defaults to **Ctrl+X** and can be changed under **System > Host Settings**.
This uses Windows' native input API on Windows and
`pynput` on macOS/Linux. Keep the intended application focused while using this
mode.

The ANSI Translation option toggles translating incoming ANSI/VT100 BBS output
for the connected machine. Its setting is saved per machine profile and applies
to later connections as well.

Welcome Banner sets a persistent main-menu banner. The `welcome_banner` value
in `hub_config.json` is the default; a banner set here is saved separately and takes
precedence until an empty entry resets it to the configured default.

The main menu status line shows the current local time, the number of open
serial ports, and the number of connected remote Telnet clients.

Type `ATM` at any time to return to the main menu and disconnect an active
network or serial bridge session.

Use `N` and `P` to scroll, `G` to jump to a page number, `F` to return to
the first page, and enter a displayed link number (such as `3` or `[3]`) to
follow it. `B` goes back, `U` enters another address, and `Q` returns to the
main menu. `A` saves the current page as a bookmark; `M` opens saved
bookmarks, where you can enter a number to open it or `D` followed by a
number to delete it. HTML search inputs appear as `I<number>`; choose one,
enter the value, then use `S<number>` to submit its form. Press Backspace to
edit the current input line. Bookmarks are stored in `settings/local/browser_bookmarks.json`
beside the hub. The browser includes starter bookmarks for retro-computing
resources. It displays text and numbered links; JavaScript and images are not
supported. HTML GET/POST forms are supported when their fields
are standard text controls. HTML and plain-text responses are limited to 1 MiB.

### FTP Downloads

Select **FTP**, enter the server hostname and port (default 21), choose regular
FTP or explicit FTPS, and provide credentials. Press Enter at the username
prompt for anonymous login. The client uses passive mode and displays files and
directories; use `C<number>` to open a directory, `U` to go up, and `R` to
refresh. Enter `A` to bookmark the current site; `M` opens saved FTP sites,
where a number opens a site and `D<number>` deletes a bookmark. Bookmarks retain
the hostname, port, FTP/FTPS selection, and username, but never the password;
the password is prompted for when opening a saved site. They are stored in
`settings/local/ftp_bookmarks.json`.
The file includes starter FTP sites.

Selecting a file prompts for **Host** or **Direct**:

- **Host** saves the file in `files/`, where it appears in **File Transfers**
  the next time that menu is opened.
- **Direct** downloads to a temporary host file and immediately sends it using
  XMODEM, YMODEM, or ASCII. The temporary copy is removed after transfer.

Press `Q` to disconnect and return to the main menu. `ATM` also returns to the
main menu. Explicit FTPS encrypts the connection; ordinary FTP does not encrypt
credentials or data.

### Special Commands

- **ATM**: Return to main menu from anywhere (like the old modem "AT" commands)
- **ATH**: Hang up / disconnect from a BBS or Telnet host
- **Q**: Quit from most sub-menus

### File Transfers

The hub supports multiple file transfer protocols:

- **XMODEM**: Classic 128-byte blocks with checksum or CRC negotiation
- **YMODEM**: 1024-byte block protocol for faster transfers
- **ASCII**: Plain text streaming (no error correction)

Open Files & Media > File Transfers and browse to any accessible host folder.
`D` opens drives/root, `B` the parent, `H` the shared folder, and `G` a typed
path. Select a file and its Send action, choose XMODEM/YMODEM/ASCII, then start
the matching receive function on the vintage computer. Other operations (`O`)
contains upload and protocol controls; uploads use the current folder.

For receive completion, exact XMODEM lengths, and partial files, see Transfers
above. Host-to-host copies are available directly in File Manager.

### Directory Structure

```
Retro-Serial-Hub/
├── RETRO_SERIAL_HUB.py    # Main hub program
├── rsh_config.py           # Validated core JSON configuration store
├── rsh_config_wizard.py    # Host-only configuration menu and profile wizard
├── requirements.txt       # Python dependencies
├── docs/                  # Engineering notes and reproducible measurements
├── rsh_ai.py              # AI Assistant module
├── rsh_bbs.py             # BBS directory and management module
├── rsh_directory.py       # Persistent BBS directory storage
├── rsh_telnet.py          # Direct TCP terminal connections and bookmarks
├── rsh_ftp.py             # FTP/FTPS browser and downloads
├── rsh_browser.py         # Text-first web browser and bookmarks
├── rsh_bridge.py          # COM port bridge module
├── rsh_files.py           # File transfer interface
├── rsh_transfer.py        # XMODEM/YMODEM protocol engines
├── rsh_storage.py         # Central JSON paths, defaults, and upgrade migration
├── rsh_session.py         # Session capture, notifications, and diagnostics
├── rsh_preferences.py     # Saved machine preferences
├── rsh_keyboard.py        # Host keyboard bridge
├── rsh_access.py          # Telnet admission and host approval queue
├── rsh_host.py            # Local host-console terminal session
├── rsh_console.py         # Adaptive dashboard, host input, and scrollback
├── rsh_console_theme.py   # Console schemes and saved appearance settings
├── rsh_host_screen.py     # Isolated host text screen and cursor controls
├── rsh_host_access.py     # First-use HOST command approval by IP/serial port
├── rsh_cpm.py             # WOPR session-local CP/M disks and commands
├── rsh_notes.py           # Notes module
├── rsh_terminal.py        # ANSI translation and screen clearing
├── rsh_text.py            # Text library module
├── rsh_wargames.py        # WarGames module
├── rsh_welcome.py         # Persistent welcome banner
├── retro_os/              # Retro Serial OS core, runtime, shell, and services
│   ├── core.py            # Shell, EventBus, Session model, ModuleLoader
│   ├── runtime.py         # Runtime initialization and built-in command handlers
│   ├── host_env.py        # Host OS integration, app scanner, clipboard, sysinfo
│   ├── toolkit.py         # Calendar, conversion, contacts, files, and ZIP tools
│   ├── audio_player.py    # Shared audio playback and playlists
│   ├── menu.py            # Accordion flyout menu engine
│   ├── menu_data.py       # Shared terminal/dashboard menu catalogue
│   ├── menu_layout.py     # Screen-height-aware menu layout
│   ├── file_browser.py    # Shared host file navigation and actions
│   ├── reader.py          # Searchable reader with saved positions
│   ├── workshop.py        # File preparation and inspection tools
│   ├── session_tools.py   # Capture, diagnostics, presets, and preferences
│   ├── shortcuts.py       # User-defined command shortcuts manager
│   ├── scheduler.py       # Background periodic task scheduler
│   ├── mail_service.py    # Hub mailbox and internet email backend
│   ├── viewer.py          # Multi-format document text extraction pipeline
│   ├── news.py            # RSS news headlines
│   ├── weather_news.py    # Live weather and combined desk briefings
│   ├── help_data.py       # In-hub help system and user guide
│   └── modules/           # Built-in OS modules (calc, games, mail, print, etc.)
├── files/                 # File transfer storage
├── text/                  # Text library files, README, and starter articles
├── notes/                 # Notes storage
├── settings/              # Central JSON storage
│   ├── defaults/          # Publishable starter templates
│   └── local/             # Ignored personal settings and data
├── hub_tools/             # Session captures (not committed)
└── tests/                 # Unit tests
```

## Module Development

The hub uses a modular architecture. Each feature is implemented in a separate `rsh_*.py` module that can be edited without restarting the hub. Modules are automatically reloaded when accessed.

Each module implements a standard interface:

```python
def create_session(ser, use_ansi=True, **kwargs):
    """Initialize and return a session object"""
    pass

def handle_input(session, line_str, ser, use_ansi=True):
    """Handle user input. Returns (consumed, action) tuple"""
    pass
```

This design allows you to customize or extend features without modifying the core hub.

## Troubleshooting

### Port Won't Open

- Check that the COM port in `settings/local/hub_config.json` matches your system
- On Windows, use Device Manager to verify COM port numbers
- On Linux/Mac, ports are typically `/dev/ttyUSB0`, `/dev/ttyACM0`, etc.
- Ensure no other program is using the port
- Check cable connections

### Connection Issues with Vintage Computer

- Verify baud rate matches between hub and terminal software
- Check data bits, parity, and stop bits settings
- Try disabling hardware flow control (rtscts) if connections are unreliable
- Some vintage systems require null-modem adapters

### BBS Won't Connect

- Verify the hostname/IP and port in the BBS directory or Telnet bookmark
- Check your internet connection
- Some BBSs may be offline; try a different one
- Firewall may be blocking outbound Telnet connections

### Garbled Text

- Check baud rate settings
- Verify data bits setting (usually 8)
- Disable ANSI support for terminals that don't support it
- Try a different cable

## Technical Notes

The [engineering field notes](docs/README.md) explain measured behavior and the
implementation lessons behind the console, terminal layout, screen controls,
scrollback, messaging, host approvals, file transfers, and Notepad recovery.
Each note links to the relevant code and tests. The index includes reproduction
commands and recorded measurements, distinguishing simulated cases and calculated
serial timing from hardware measurements.

## Release Notes

### v2.7

- **Previous Folder**: Added P to the shared file browser and `fileman previous`
  / `fileman cd -` to switch between the current and previous folders. History
  stays within each session, and failed directory changes keep the current folder.
- **Reader Navigation**: Added H/L for first/last page and direct page-number
  entry. Invalid pages report the valid range without moving; G prompts can be
  cancelled with Enter or Q. Existing bookmarks and saved positions still work.
- **Download Integrity**: `fetch` now streams downloads in 64 KiB chunks to unique
  temporary files, verifies a supplied content length, and replaces the
  destination only after completion. Failed transfers preserve the previous file.
- **Event Delivery Recovery**: Event listeners and module hooks now log individual
  failures and continue delivery to later listeners, including async listeners.
- **Batch Destination Checks**: Copy/move checks duplicate destination names before
  making changes, preventing partial batches caused by same-named marked items.
  See [failure prevention notes](docs/failure-prevention.md) for validation details.
- **Shared Tool Data**: Contacts, calendar entries, folder preferences, launch presets,
  and other record stores now use unique, synced temporary files with atomic
  replacement and failure cleanup. Existing saved data survives failed saves.
- **ZIP Retry Recovery**: Failed member reads, copies, or output closes remove the
  incomplete member when possible; completed members and existing files are kept.
  See [tool data and recovery](docs/tool-data-reliability.md) for retry steps and
  regression coverage.
- **Scheduler Review**: Enable/disable commands now set the requested state,
  quoted command chains and URL semicolons are preserved, invalid schedules are
  rejected, and concurrent runs of the same task are prevented. Added
  `schedule details <id>` for next/last run and status diagnostics.
- **Reader Recovery and Search**: Unreadable/corrupt position files and invalid
  saved offsets no longer block reading. Failed saves display a notice and retry
  on later pages. Search avoids allocating a full list of line numbers; a
  100,001-line benchmark reduced temporary allocation from 4,393,192 to 676 bytes.
- **Notepad Rename and Export Recovery**: Rename/export prompts now accept
  filenames such as N, B, and O without triggering menu navigation. Export reads
  the source before creating its destination, removes incomplete exports after
  write failures when possible, and preserves existing destination files. Added
  regression coverage for recovery and retry; see
  [Notepad recovery notes](docs/notepad-edit-recovery.md).
- **Scheduler Reliability**: Task saves now use a unique temporary file and atomic
  replacement to preserve the last saved tasks on write failure. Malformed task
  entries no longer prevent valid tasks from loading, invalid recurrences are
  disabled without stopping other tasks, and broken next-run timestamps are
  repaired. See [scheduler reliability notes](docs/scheduler-reliability.md)
  for recovery behavior and regression tests.
- **Settings Failure Recovery**: Failed starter-settings copies now remove partial
  live files so the next attempt can seed them again; unreadable templates no
  longer create empty live settings. Machine-preference saves use unique temporary
  files, clean up failed writes/replacements, and preserve the last saved settings.
  Regression tests cover partial writes, permission errors, and successful retries;
  see [settings recovery notes](docs/settings-recovery.md).
- **Receive and COM Bridge Recovery**: Failed XMODEM destination copies now
  remove the incomplete destination so a retry can use the same filename, while
  retaining the diagnostic `.part` file and preserving files created by other
  writers. COM bridge raw forwarding preserves bytes exactly, including CR/LF
  split across reads; line-oriented forwarding converts each newline only once.
  Added fault-injection and byte-preservation regressions; see the
  [transfer reliability notes](docs/transfer-reliability.md) and
  [COM bridge reliability notes](docs/com-bridge-reliability.md).
- **Telnet and Input Reliability**: Failed Telnet bookmark saves/deletions now
  preserve the current list and offer a retry; Q cancels deletion, and N connects
  without saving after an add failure. Saves use unique temporary files. Inbound
  Telnet polling yields during continuous protocol-only traffic. Interactive
  prompts drain buffered input immediately instead of delaying every character.
  Regression tests also run on the documented Python 3.9 minimum; see the
  [Telnet and input reliability notes](docs/telnet-input-reliability.md).
- **Transfer Failure Recovery**: XMODEM/YMODEM fragmented reads now enforce the
  overall read deadline even when a peer keeps sending small fragments. A failed
  cancellation write on a disconnected transport preserves the original transfer
  error. Added deterministic regression tests; see
  [transfer reliability notes](docs/transfer-reliability.md) for timeout limits
  and validation details.
- **JSON Hub Configuration**: Removed `config.py` and moved serial/Telnet profiles,
  welcome text, serial inactivity defaults, and WOPR speech to validated
  `settings/local/hub_config.json`. Preserved the current local hardware settings;
  public defaults now contain only APPLE2 on COM1 and C64 on COM2, with no inbound
  listeners. BBS defaults are 64 structured JSON entries shared by menu and CLI.
- **Host Configuration Wizard**: Type `config` at the physical console for a
  separate menu and guided profile setup with scanned serial ports, serial framing,
  flow control, ANSI/clear behavior, width/height, timeouts, and optional Telnet.
  Review/confirm before atomic save, cancel/back navigation, conflict validation,
  and remote-input blocking protect the draft. New profiles start immediately;
  global and speech changes are saved for restart.
- **First-Launch Setup**: Fresh installations open configuration automatically and
  defer serial/Telnet workers until setup finishes. Edit the two starter profiles
  or add a computer, then Q starts the saved configuration. Completion is remembered
  locally; existing setups keep their normal startup. Existing-profile edits use
  the same wizard and take effect at first-setup completion or after a restart.
- **Gemini Thinking Compatibility**: Removed the automatic `minimal` reasoning
  setting that caused HTTP 400 errors on models rejecting that thinking level.
  Gemini now chooses its own thinking defaults unless explicitly configured.
  Added a simulated provider rejection to the SDK request test and coverage for
  omitted, explicit, and `default` reasoning settings.
- **AI Provider Choice**: Added Google Gemini and local Ollama alongside OpenAI.
  Local models need no API key or token billing; Gemini supports a hosted free-tier
  setup subject to provider limits. Existing OpenAI configurations remain valid.
  Provider/model headers, host configuration and environment overrides, isolated
  per-conversation clients, configurable response budgets, and provider-specific
  request options keep the terminal interface consistent. Added setup instructions,
  quota/connection guidance, and SDK-level tests; errors never switch providers or
  fall back to a paid service automatically.
- **Resilient Note Search**: An unreadable or disappearing note no longer aborts
  content search. Continue searching other notes and report the skipped count.
  Filename matches require no content read, and the 1 MiB content-search limit
  remains in place. Regression coverage exercises metadata and read failures,
  successful retries, filename-only matches, and oversized files.
- **Notepad Save Recovery**: Clean up temporary files after failed writes or file
  replacements, including partially written saves. Keep the original note and
  unsaved editor contents intact so `save` can be retried without reopening the
  note. Regression coverage injects both a disk-write failure and a replacement
  permission error, verifies cleanup and unchanged source bytes, then retries
  successfully.
- **Notepad Edit Recovery**: Fixed editing notes that were deleted, cannot be read,
  or contain invalid UTF-8. Failed reads leave the menu usable without entering a
  partially initialized editor or changing the source file. Merged from the
  experiment branch in [PR #1](https://github.com/TheDeepLogic/RetroSerialHub/pull/1).
- **Engineering Field Notes**: Added six technical writeups covering terminal layout
  budgets, screen controls and frozen scrollback, transfer-safe message delivery,
  host-control approval boundaries, XMODEM wire costs, and Notepad recovery. Includes
  a repeatable assertion-based measurement harness and recorded results. See the
  [technical documentation index](docs/README.md).
- **Release Version**: Updated the displayed application version, bundled guide,
  and web-viewer user agent to 2.7. Terminal banners and HTTP requests now share
  one version constant. All 450 tests passed.

### v2.6

- **Adaptive Console Layout**: Reworked the dashboard around a bordered 80-column host
  pane, serial/network status, and an active-only activity monitor. Narrow windows stack
  the panels; taller windows move status and connections across the top. Approvals
  remain visible, errors sit below activity, and overflow counts identify hidden items.
- **Direct Host Input**: The host opens the standard numbered menu on startup and edits
  directly at the active hub prompt. Main-menu status and ATM/messages hints sit above
  separated console controls near the bottom. Screen clears, cursor movement, and erase
  commands update the host pane correctly.
- **Console Themes**: Added fourteen saved DOS Shell and vintage-system schemes,
  including Ocean, Apple IIGS, Commodore, TI-99/4A, Windows 95, and Windows 3.1.
  Background-off supports terminal transparency while retaining title and highlight
  colors; colors-off uses terminal defaults. Colored bands extend across the pane,
  including the input separator.
- **Stable Scrollback**: PgUp holds the text being read while output continues, with a
  new-line counter and End to resume live output. Resizing, incoming screen clears, and
  live-history eviction preserve the held view.
- **Efficient Redrawing**: Only changed rows are repainted; unchanged refreshes emit
  nothing. Resizes and appearance changes still trigger a full repaint. See [redraw
  measurements](docs/console-redraw-measurements.md) for measured terminal-traffic
  reductions.
- **Terminal Messages**: Messages and received text files announce themselves
  immediately, including at idle prompts, with notices deferred during file transfers.
  M=Messages opens a session inbox with unread counts, paging, and read history,
  separate from email. MESSAGES and MSGS also work at the menu or CLI.
- **Approved Host Control**: Serial and Telnet terminals can submit `HOST <text>` to the
  host session. First use requires approval typed at the physical console, remembered
  per source IP or physical serial port in a separate allowlist. Forwarded commands
  cannot approve host-control requests.
- **CP/M Exploration**: Expanded WOPR's IMSAI shell with session-local A/B disks,
  discoverable documentation, directory filters, text viewing, copy/rename/erase
  commands, disk statistics, simulated memory images, and native screen clearing.
  Communications programs are discovered by exploring the disk.
- **Console Help**: Added host help for dashboard controls while HELP continues to reach
  the hub. Retired monitor-collapse behavior and refreshed the README, in-menu guide,
  hotkeys, and regression coverage.

### v2.5

- **Star Trek Guide**: Star Trek now shows a quick-start command guide on launch, with
  examples, course directions, combat, and resupply instructions; terminal output pages
  to the configured screen size.
- **Settings Storage**: Consolidated JSON settings and application data under
  `settings/`: publishable starter defaults are separate from ignored personal files,
  with automatic migration from earlier locations and preservation of existing
  bookmarks.
- **Workshop Tools**: Added Workshop as category 6 with disk-image inspection, hex
  viewing, checksums, text conversion, BASIC listing preparation, split/join, hex/Base64
  encoding, and file comparison. System moves to category 7; categories retain at most
  eight A–H entries.
- **Host File Browsing**: Unified host-file browsing across file tools, with
  drives/root, parent folders, direct paths, favorites, filters, marking, and batch
  copy/move. Audio can select files anywhere the host can access. Added Find Files under
  Files & Media H.
- **Reading and Notes**: Added searchable, resumable reading and bookmarks, plus note
  editing, renaming, exporting, and content search.
- **Audio Player**: Simplified the audio player menu; added queue editing,
  repeat/shuffle, named radio stations, and a remembered music folder.
- **Capture and Diagnostics**: Added Session Capture under Communications G and Serial
  Diagnostics under Host Connectivity H, including transfer progress and host
  cancellation.
- **Transfer Reliability**: Improved XMODEM/YMODEM negotiation, retries, fragmented
  reads, and completion handling. Receives preserve binary padding, avoid overwriting
  files, and publish completed files only after success.
- **Session Activity**: Added serial inactivity timeouts and cleared stale menu
  selections when a port becomes active again. Queued notifications keep messages out of
  prompts and transfer streams, with optional quiet mode.
- **Machine Preferences**: Added saved machine preferences and host application launch
  presets. Terminal height defaults to 24 rows per profile; menus keep the footer
  stable, clear submenus, and reserve readable spacing in 40- and 80-column layouts.
- **Host Dashboard**: Updated the host dashboard with Unicode borders and ASCII
  fallback, a single color-coded Connections list, and an activity monitor that
  collapses during host interaction to give output more room. `clear` restores the
  expanded layout unless `monitor collapse` pins it compact; `monitor auto` restores
  automatic behavior.
- **WOPR Interaction**: Enhanced the WOPR/Joshua interaction while retaining the
  IMSAI/CP/M dialer, with movie-style displays, gentler pacing, and optional
  synchronized host speech. Open it from Communications H or `wargames`.

### v2.4

- **AI Model Compatibility**: Replaced the retired GPT-3.5 Turbo default with GPT-5.6
  Terra, updated completion parameters, and added configurable model and reasoning
  settings with actionable errors when a model is unavailable.
- **Interactive Host Console**: The host keyboard now runs the hub's CLI and interactive
  menus. Added host-to-terminal messaging and replies to `Host`, scrollable command
  output, command history, and masked FTP password input.
- **Telnet Source Approval**: Unknown source IPs wait for `allow <request #>` or `deny
  <request #>` at the host keyboard. Approvals persist in a manually editable JSON
  allowlist. Missing/invalid policies and failed saves never grant access; pending
  requests expire and the queue is bounded. Serial connections are exempt.
- **Six New Tools**: Added Calendar with persistent reminders, Unit Converter, Address
  Book with mail/BBS shortcuts, File Manager, ZIP Archive Browser, and Audio Player with
  host playback controls, M3U playlists, and optional internet radio through FFmpeg.
- **More Terminal Games**: Added Word Guess and a Star Trek adaptation inspired by the
  supplied Apple II BASIC listing, with quadrant exploration, scans, phasers, photon
  torpedoes, shields, starbase resupply, and a mission deadline.
- **Host Settings**: Added a host preferences menu with a saved keyboard bridge exit
  binding, defaulting to Ctrl+X. Escape is forwarded to the host application.
- **Menus and Status Formatting**: Reordered Files & Media and Accessories, shortened
  Calendar and Weather & News labels, and placed Disconnect last in System. Active and
  waiting profile rows share field order and indentation; active rows stay green under a
  gray divider without redundant terminal text.
- **Stable Console Redrawing**: Fixed cursor drift after host input and approval
  changes. Redraws use fixed screen positions, fit the viewport, and retain the host
  prompt when the full dashboard will not fit.
- **Session Reliability**: Kept game, Logo, and mail context tied to the correct
  terminal, serialized module initialization, and shared one scheduler per task file so
  adding a host session does not duplicate scheduled jobs.
- **Documentation and Tests**: Updated the README, in-hub help, text-library guide, and
  regression coverage. Private allowlists and saved tool data remain local to the
  installation.

### v2.3

- **Terminal Logo Programming**: Added the LOGO accessory and CLI launcher, with
  movement, pen controls, repeat groups using brackets or parentheses, variables,
  arithmetic, user procedures, terminal turtle status, and optional host graphics.
- **Connected Terminal Tools**: Added a Communications menu for listing active
  terminals, messaging a selected terminal, and delivering a text file over ASCII; the
  CLI also supports `terminals` and `msg to <terminal> <text>`.
- **Expanded Terminal Games**: Added Lunar Lander, Hunt the Wumpus, Blackjack, and
  Mastermind to Games. WarGames remains available through the CLI. Game prompts now show
  the single-letter keys that activate each action.
- **Menu and Notes Updates**: Moved Host Printing to Host Connectivity, renamed the
  Notes menu item to Notepad, added host clipboard capture/copy workflows, corrected
  dashboard section activity numbering, and normalized menu spacing.
- **Documentation**: Updated both user guides and incremented the application version to
  v2.3.

### v2.2

- **Scheduler Commands**: Added resilient command chaining, dynamic command discovery,
  broadcast command guidance, and menu support for URL tasks. Current syntax and
  examples are maintained in the [scheduler guide](docs/scheduler-reliability.md).
- **Release Version**: Incremented application version to v2.2.

### v2.1

- **Document Viewer Windows Path Resolution**: Fixed an issue where Windows backslashes
  were stripped during shell argument parsing (causing duplicated or corrupted paths
  such as `OneDriveSoftware...`), allowing documents, images, and local files to load
  seamlessly from local drives.
- **Interactive News Article Reader**: Added interactive headline article selection to
  Weather & News, allowing vintage terminals to type an article number directly to read
  the complete summary and download full web article contents (`F` / `news <num> full`).
- **Dedicated News Task Scheduler Option**: Added news and weather command scheduling to
  the background task scheduler (`schedule add <name> <minutes> news ...`), listing them under
  `schedule modules`.
- **Console Pseudo Interface & Connected User Highlighting**: Enhanced the live host
  console dashboard with an interactive pseudo interface layout displaying connected
  client activity and highlighting active menu items in real time.
- **Updated Copyright Notices**: Updated all system banners, headers, and documentation
  to 2025-2026.
- **Release Version**: Incremented application version to v2.1.

### v2.0

- **Retro Serial OS Runtime**: Full host-side operating system extension with an
  interactive command prompt (`cli>` / `OS`), hot-reloadable module system, event bus
  publish/subscribe architecture, multi-client session tracking, and programmable
  keyboard bridge shortcut profiles.
- **Accordion Main Menu & Custom Shortcuts**: Fast categorized accordion flyout menu
  layout optimized for 40- and 80-column terminals, complete with a user-defined command
  shortcut macro system with automatic flyout.
- **Host Terminal & Quick Shell**: Bidirectional streaming console session to the host
  OS (`cmd.exe`, `powershell`, or unix shells) with configurable local echo, newline
  translation, and interactive parameters.
- **Real-Time Host System Monitor**: Live CPU load measurement, memory, disk, and uptime
  monitor with continuous screen clearing, pause/resume, and adjustable refresh rates
  (`top` / `sysinfo live`).
- **Modern Document Viewer Pipeline**: Automatic text extraction and pagination for
  modern file formats including PDF, Word (.docx), Excel (.xlsx / .csv), plain text,
  Markdown, HTML, and web URLs.
- **Integrated Hub Mail & Internet Email**: Central inter-terminal hub mailbox
  identifying senders by hardware/connection, along with full IMAP/SMTP internet email
  support and host desktop configuration GUI.
- **Dedicated Retro Games**: Native text-mode Minesweeper, Solitaire (Klondike), and
  WarGames (W.O.P.R.) simulation.
- **Ambient Desk Companion**: Live ASCII weather forecasts (`wttr.in`), RSS news feeds
  (NPR, Hacker News, BBC), and automated morning briefings (`briefing`).
- **Background Task Scheduler**: Automated periodic task execution with terminal
  broadcast notifications and cron-like intervals. Weather and news commands can be
  scheduled directly (for example, `weather Austin` or `news npr 6`) and are listed by
  `schedule modules`.
- **Terminal Hardware Settings & In-Hub Help**: Caps-Only mode for vintage
  uppercase-only ROMs (Apple II Plus, Commodore PET, TRS-80 Model I), serial character
  pacing delays (1-3ms), and 9 comprehensive in-hub help guide topics.
- **Release Version**: Incremented application version to v2.0.

### v1.5

- Added a persistent, per-machine ANSI translation toggle in the System menu
  (option 12), and moved the terminal-width toggle to option 13.
- Added File Transfers directory browsing, drive/root selection, direct path
  entry, and shortcuts to move to the parent or return to the `files/` home.
- Expanded Text Library reader pages to use the available 24 terminal rows at
  40 and 80 columns.
- Incremented the application version to v1.5.

### v1.4

- Fixed text-library pagination to account for wrapped lines, terminal width,
  the continuation prompt, and the echoed Enter key so the first displayed
  lines remain visible on 40- and 80-column terminals.
- Added plain-text versions of this README and short vintage-computer articles
  on the Apple II, Commodore 64, TRS-80, IBM PC, and Altair 8800 to the Text
  Library.
- Added starter browser bookmarks for retro-computing resources and anonymous
  FTP bookmarks for three public file archives.
- Set saved terminal-column defaults to match the bundled machine profiles
  and reordered the System menu so option 12 switches column width and option
  13 opens Welcome Banner.
- Included the recent menu-routing and Notes workflow fixes, incoming
  Telnet-compatible Wi-Fi modem documentation, Keyboard Bridge feature listing,
  and Aaron Smith copyright notice.
- Updated the application version to v1.4.

### v1.3

- Fixed main-menu routing after the Accessories/Files reorder and restored
  Notes creation, cancellation, and deletion workflows.
- Fixed returning to the Notes menu after reading a note.
- Documented incoming Telnet-compatible Wi-Fi modem access and the Keyboard
  Bridge; set the default C64 terminal width to 40 columns.
- Added the project copyright notice and incremented the application version.

### v1.2

- Added optional per-machine inbound TCP terminal servers for Wi-Fi modems and
  other remote terminals, plus startup connection addresses and a live,
  colorized console dashboard with serial, listener, and client status.
- Added a remote-session-only **Disconnect** menu option and a main-menu status
  line showing local time and active connections.
- Added per-machine 40/80-column layouts with a persistent width toggle,
  reorganized and renumbered the menu sections, and adapted browser pages and
  other feature menus to the configured terminal width.
- Added bracketed, consistent menu section headings and improved startup and
  menu spacing for both display widths.
- Centralized the displayed application version and updated it to v1.2.

### v1.1

- Replaced the former URL Reader with a text-first Web Browser supporting
  paginated pages, numbered links, standard HTML forms, history, and bookmarks.
- Added direct Telnet connections with persistent Telnet bookmarks and the
  option to add destinations to the Bulletin Boards directory.
- Added persistent BBS directory management for adding, editing, and deleting
  configured and user-added entries.
- Added FTP/explicit-FTPS directory browsing, saved site bookmarks, and
  downloads to the hub's file library or directly to the terminal using
  XMODEM, YMODEM, or ASCII.
- Added a cross-platform Keyboard Bridge (Windows native input; macOS/Linux
  through `pynput`), plus Ctrl+X as an exit shortcut.
- Added persistent welcome-banner customization, main-menu and submenu screen
  clearing, and improved ANSI translation for non-ANSI terminals.
- Migrated the AI Assistant to the current OpenAI Python client interface.
- Reordered the main menu, added the FTP option, shortened the banner option
  label to **Welcome Banner**, and documented `ATM` as the menu return command.

## Hardware Recommendations

- **USB-to-Serial Adapters**: Look for adapters with FTDI chipsets for best compatibility
- **Cables**: DB9 or DB25 cables depending on your vintage computer
- **Null-Modem Adapters**: Required for some vintage systems
- **RS-232 Level Shifters**: May be needed for some single-board computers

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is provided as-is for use by the retro computing community. Feel free to modify and distribute.

## Acknowledgments

- Inspired by classic BBS systems and the retro computing community
- Special thanks to the maintainers of the various BBSs listed in the default configuration
- Built with the assistance of GitHub Copilot and AI coding agents

## Support

For questions or issues, please open a GitHub issue or contact the retro computing community forums.

---

**Happy retro computing!** 🖥️📞

Third-party component credits and license information: [Third-party notices](THIRD_PARTY_NOTICES.md).
