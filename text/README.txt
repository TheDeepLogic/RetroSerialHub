Image: Retro Serial Hub

Retro Serial Hub v2.5

A multi-port serial hub that connects vintage computers to modern TCP/IP
networks and accepts incoming Telnet-compatible connections. Systems using
dedicated Wi-Fi modems can connect over the LAN and access the same BBS,
file
transfer, browser, and other retro-computing services through the hub's
menu.

Image: Retro Serial Hub Screenshot

AI-Assisted Development Notice

Hello, fellow human! My name is Aaron Smith. I've been in the IT field for
nearly three decades and have extensive experience as both an engineer and
architect. While I've had various projects in the past that have made their
way into the public domain, I've always wanted to release more than I could.
I write useful utilities all the time that aid me with my vintage computing
and hobbyist electronic projects, but rarely publish them. I've had
experience in both the public and private sectors and can unfortunately slip
into treating each one of these as a fully polished cannonball ready for
market. It leads to scope creep and never-ending updates to documentation.

With that in-mind, I've leveraged GitHub Copilot to create or enhance the
code within this repository and, outside of this notice, all related
documentation. While I'd love to tell you that I pore over it all and make
revisions, that just isn't the case. To prevent my behavior from keeping
these tools from seeing the light of day, I've decided to do as little of
that as possible! My workflow involves simply stating the need to GitHub
Copilot, providing reference material where helpful, running the resulting
code, and, if there is an actionable output, validating that it's correct.
If I find a change I'd like to make, I describe it to Copilot. I've been
leveraging the Agent CLI and it takes care of the core debugging.

The code and documentation are developed with assistance from GitHub
Copilot, including its coding agents and tools available in the development
environment. The specific agents and models may vary between changes.
AI-assisted work can contain mistakes; please report issues or submit a pull
request with a correction.

Features

* Retro Serial OS Runtime: Interactive command shell (cli> / OS) with hot-reloadable module system, event bus pub/sub, multi-client sessions, and keyboard bridge shortcut profiles
* Accordion Main Menu & Custom Shortcuts: Fast categorized accordion flyout navigation with user-defined macros, arguments, and automatic flyout
* Host Terminal / Command Prompt: Quick launch the host OS shell (cmd.exe on Windows, or $SHELL on macOS/Linux) with bidirectional console streaming, local echo, and line translation
* Console Pseudo Interface & Live User Activity: Host console dashboard displays an interactive pseudo-interface view highlighting the menu items connected retro users are currently browsing in real time
* Real-Time Host System Monitor: Live CPU load measurement, RAM, disk, and uptime metrics with automatic screen clearing and interactive controls (top / sysinfo live)
* Multi-Format Document Viewer: Text extraction and pagination pipeline for PDF, Word (.docx), Excel (.xlsx / .csv), Markdown, HTML, and web URLs with native Windows path handling
* Direct File Transfers: XMODEM, YMODEM, and ASCII transfers callable directly from the shell or menu (xsend, ysend, asend, xrecv)
* Electronic Mail (Hub & Internet): Central inter-terminal hub mailbox with auto-detected sender identity, plus IMAP/SMTP internet email and desktop configuration GUI
* Connected Terminal Messaging: List active serial/Telnet terminals, message a selected terminal, or deliver a text file from the Communications menu
* Dedicated Retro Games: Native text-mode Minesweeper, Solitaire (Klondike), Hunt the Wumpus, Lunar Lander, Blackjack, Mastermind, Word Guess, and Star Trek, plus WarGames (W.O.P.R.) from the CLI
* LOGO Programming: Terminal Logo interpreter with repeat loops, variables, procedures, turtle state feedback, and optional host graphics
* Ambient Desk Companion: Live ASCII weather forecasts (wttr.in), RSS news feeds (NPR, Hacker News, BBC), automated morning briefings (briefing), and interactive article reader (news <num>)
* Background Task Scheduler: Automated periodic task execution with broadcast notifications, cron-like intervals, and multi-command chaining (e.g. news : weather Austin : broadcast Morning briefing complete)
* Terminal Hardware Settings: Screen width (40/80 cols), Caps-Only mode for vintage uppercase-only ROMs (Apple II Plus, PET, TRS-80 Model I), and serial character pacing delays
* In-Hub Help & User Guide: 9 built-in guide topics accessible directly from the menu (HELP or ?)
* Multi-Port Serial Support: Connect multiple vintage computers simultaneously, each with independent configurations
* BBS Directory: Browse, connect to, and manage saved BBS destinations
* Telnet: Connect to a host and port directly; manage Telnet bookmarks or add destinations to the BBS directory
* FTP/FTPS: Browse FTP servers and save downloads to the hub or transfer them directly to the connected terminal
* Text Library: Browse and read text files with pagination; includes starter
  articles on classic computers
* Web Browser: Browse paginated text pages, follow numbered links, and manage bookmarks
* Notes System: Create, read, and manage text notes, including host clipboard capture and copy
* COM Port Bridge: Bridge between different serial ports for direct computer-to-computer communication
* Keyboard Bridge: Type serial input into the focused host application
* Lunar Lander, Hunt the Wumpus, Blackjack, Mastermind, Word Guess, and Star Trek: Terminal-first games in the Games menu
* WarGames Mode: Nostalgic WarGames movie-inspired interface, available from the CLI
* Notepad clipboard actions: Save host clipboard text as a note, or copy a note to the host clipboard
* AI Assistant: Optional ChatGPT-powered assistant accessible from vintage terminals
* Hot-Reload Modules: Edit feature modules without restarting the hub
* ANSI Support: Automatic detection and handling of ANSI escape codes for compatible terminals

Requirements

* Python 3.9 or higher
* Dependencies listed in requirements.txt
* USB-to-Serial adapters or RS-232 ports for connecting vintage computers
* Optional: OpenAI API key for AI Assistant feature

Installation

1. Clone or download this repository to your computer

2. Install Python dependencies:
   python -m pip install -r requirements.txt
   This installs PySerial and, on macOS/Linux, pynput for the Keyboard
   Bridge.
   On macOS, grant the terminal or Python process Accessibility permission.
   On Linux, the bridge requires a supported graphical desktop session;
   Wayland
   sessions may not permit global keyboard injection.

3. Optional - For AI Assistant functionality:
   python -m pip install openai

4. Configure your serial ports and BBS list (see Configuration section below)

5. Run the hub:
   python RETRO_SERIAL_HUB.py

v2.5 tools and session guide

Menu map

The terminal menu, host activity monitor, and navigation help share one catalogue.
Each category has at most eight entries, A-H. Workshop is section 6 and System
is now section 7. Existing command names remain available. Shortcuts show eight entries per page;
use < and > to change pages.

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

Browsing and finding files

File Manager, File Transfers, Archive Browser, Document Viewer, and Text Library
use one browser. Audio uses the same directory/filter/favorites model with audio
filtering and playback controls. The current directory and filename filter are
shared within a session; folder favorites persist across sessions. Full host
filesystem access remains available.

- A number opens a directory or a file's action menu.
- D lists drives/root, B opens the parent, H opens the shared folder, G accepts a path.
- F changes the filename filter; * clears it. The current filter is displayed.
- V manages folder favorites, M manages marked items, O opens other operations.
- A selected file offers relevant view/play/image/ZIP actions, plus copy, move,
  rename, transfer, and marking.
- Copy/move accepts = to reuse the remembered destination. Mark multiple items
  to copy/move a batch; conflicting destinations are rejected before starting.
- Other operations include folder creation, upload, protocol selection, search,
  opening a web URL, and reading notifications.

Find Files accepts a filename wildcard and a host folder. Plain text searches are
also supported (manual matches names containing that text). Searches stop after
200 results or 5 seconds and report that limit, so narrow the folder if needed.
Inaccessible directories are skipped and counted. Results use the same file actions.

Tool screens separate action lists, navigation controls, usage syntax, information,
and input prompts with blank rows. Page budgets reserve those rows so the added
spacing does not push results off the configured screen.

All generic tool menus show at most eight actions per page. N/B changes action
pages when necessary. Q goes back, Enter refreshes ordinary menus, and empty
prompted arguments cancel. ATM unwinds the standard nested tool menus to the
main menu. Reader/game-specific controls are shown on their own screens.

Reading and notes

The reader supports Enter=next, B=back, F=find, N=next match, M=bookmark,
R=recall bookmark, G=page, and Q=back. Position and bookmark are saved by file
and terminal width. The Text Library and note selections open this reader.
Files selected for viewing use the host's existing extraction support.

In Notepad, O opens edit, rename, export, and search operations. E<number> edits
an existing note. The line editor accepts replace <line> <text>, append <text>,
delete <line>, save, N/B for preview pages, and Q to cancel changes. Quotes in
replacement text are retained. R<number> renames a note, X<number> exports to a new
host path, F text searches names and content, and ALL resets the search.
Large content searches inspect note text up to 1 MiB, while filenames are always searched.
Clipboard creation/copy and the original read/create/delete operations remain.

Audio

The player stays compact. Queue/playlists opens queue editing (remove/reorder),
repeat, shuffle, and Radio / Music Folder. Save radio stations by name and save a
preferred music folder. Browse Files opens the saved music folder when one exists.
Stop playback before removing or reordering the current track;
shuffle preserves that track and randomizes the upcoming queue.

CLI examples:

text
audio station add "Retro Radio" "https://example.org/stream"
audio station play "Retro Radio"
audio musicfolder "F:/Music"
audio remove 3
audio reorder 4 2
audio repeat on
audio shuffle


Capture, diagnostics, notifications

Session Capture records readable outgoing terminal text, including locally echoed
conversation, to hub_tools/captures/. Control sequences are translated/removed;
raw binary transfers and secret input/output are excluded. Captures can be stopped,
listed, viewed, and exported. It does not replay captured keystrokes or commands.

Serial Diagnostics lists connected sessions, byte counters, last-input age,
settings and modem signals where supported, recent ASCII/hex traffic, and active
transfer progress. The host can request cancellation using
diagnostics cancel <terminal-name-or-port>. It never opens a second connection
to a busy port or toggles modem control lines automatically.

Messages, reminders, scheduled broadcasts, and text-file deliveries are queued.
They are not injected into another terminal's prompts or binary transfer stream.
The main menu shows a pending count; Connected Terminals N or notifications
reads them. At a CLI command boundary, pending messages are shown unless quiet
mode is enabled. notifications quiet on/off changes quiet mode for that session.
machine quiet on/off also saves the default. Connected Terminals shows input age
and queued counts. The host status panel shows transfer byte/retry progress.

Transfers

XMODEM supports checksum and CRC send negotiation, fragmented reads, duplicate
block acknowledgment, bounded waits/retries, and host-requested cancellation.
YMODEM sends CRC headers/data and completes the end-of-batch handshake. Progress
is host-side and is excluded from the protocol byte stream.

XMODEM does not carry the original length. Received final-block padding is
preserved by default; trailing 0x1A bytes are never blindly removed. For an exact
binary length, use:

text
xrecv "F:/Incoming/program.bin" 12345


A completed receive is published to its destination only after successful receipt.
Failed receives keep a uniquely named .part file; inspect or remove it yourself.
Existing destination files are not replaced. Hardware testing with your vintage
terminal software is still necessary alongside the automated protocol tests.

Machine preferences and launch presets

Terminal Settings includes transfer protocol, starting screen, reconnect behavior,
and idle timeout. Host Settings > Machine Preferences exposes all saved settings.
Width, uppercase mode, character pacing, and ANSI preferences remain available.

text
machine list
machine pace_ms 5
machine caps on
machine columns 40
machine protocol YMODEM
machine start menu
machine reconnect menu
machine idle_seconds 300
machine clear_sequence 1b76


Clear sequences are hex bytes. reconnect resume retains the active screen;
reconnect menu returns to a fresh menu on input after the serial idle timeout.
An idle timeout is inferred inactivity, not proof that a cable was disconnected.
Starting-screen changes apply on the next session. Preferences live in
settings/local/machine_preferences.json and are separate from the existing width/ANSI
preference files; setting width through the menus/CLI keeps them in agreement.

Host Applications > Launch Presets saves a name, application, working directory,
and background/terminal/keyboard launch mode. The CLI also accepts arguments:

text
presets add "Build BASIC" terminal "F:/Retro/Project" python build.py
presets run "Build BASIC"


New preparation/session tools use Python's standard library. Existing optional
viewer, audio, keyboard, and speech dependencies remain unchanged.


Terminal height, stable menu footers, and console borders

System (7) > Terminal Settings (C) > Screen Size (1) has width and height controls.
Height defaults to 24 rows and is saved per profile. Set it to the actual
terminal height (16-100); the hub does not guess a vintage terminal's dimensions.
The CLI equivalents are machine rows 25 or height 25. rows: 24 can also be
supplied in a serial profile in config.py before a saved preference exists.

At both 40 and 80 columns, the main menu retains a blank row between the version
and Shortcuts. Its footer ends at the configured last row, with padding above the
status line so selecting a short category does not move the prompt. At both widths
there is a blank row between the ATM note and the input prompt. On a 24-row
screen, the status/ATM/prompt rows are 21/22/24 at both widths (row 23 is blank). Shorter screens page active entries
using < and > when needed. Submenu entry/redraw uses the configured clearing
sequence before displaying new work.

The modern host dashboard uses Unicode box borders when stdout's encoding can
represent them. This is independent of the vintage terminal's character set;
serial/Telnet menus retain their existing ASCII output. Windows, macOS, and Linux
Unicode-capable terminals need a font with box-drawing glyphs. An incompatible
output encoding automatically uses ASCII borders. Set RSH_ASCII_BORDERS=1
before starting the hub to force the old borders if your font or terminal needs it.

JSON settings and personal data

JSON files now live in settings/local/ (ignored by Git). Public starter
templates live in settings/defaults/ and retain supplied bookmarks. Missing
files are seeded from templates or generated as needed. Existing root, mail/,
hub_tools/, and retro_os/ JSON migrates automatically; conflicting old copies
are retained in settings/local/legacy/. Back up local/ privately and publish
only deliberately sanitized templates. config.py remains startup configuration.

Configuration

All configuration is centralized in config.py. This is the first file you
should edit after installation.

Serial Port Configuration

Edit the SERIAL_CONFIGS dictionary in config.py to match your hardware
setup. Each entry represents one vintage computer or device:

SERIAL_CONFIGS = {
    "APPLE2": {
        "port": "COM2",           # Change to your COM port
        "baud": 115200,           # Adjust to match your hardware
        "bytesize": EIGHTBITS,
        "parity": PARITY_NONE,
        "stopbits": STOPBITS_ONE,
        "xonxoff": False,
        "rtscts": True,
        "ansi": False,            # Set to True when the local terminal supports ANSI
        "translate_ansi": False,  # Optional: translate incoming ANSI/VT100 for a non-ANSI terminal
        "ansi_clear_sequence": b"\x0c",  # Replacement bytes for supported clear requests
        "ansi_home_clears_screen": False, # Optional: treat cursor-home as a screen clear
        "columns": 80,                   # 40- or 80-column terminal layout
        "rows": 24                       # Terminal height
    },
    # Add more computers as needed...
}

Set columns independently for each machine profile to 40 or 80. This is
the profile's default width; the main-menu System -> Columns option can
switch and save that profile's preference. The saved selection is stored in
terminal_columns.json and takes precedence over config.py. At 40 columns,
menus use a compact layout, browser pages wrap to the configured width, long
labels are shortened to fit, and ANSI translation uses the configured
terminal
width. The included defaults use 80 columns for APPLE2, IBM, and TRS80
profiles,
and 40 columns for C64; profiles without this setting default to 80.

Common baud rates for vintage systems:
* Apple II with Super Serial Card: 300, 1200, 2400, 9600, 19200, or 115200
* Commodore 64: 300, 1200, 2400
* IBM PC/XT/AT: 300, 1200, 2400, 9600
* TRS-80: 300, 1200, 2400, 9600

Optional translation for non-ANSI terminals

ANSI translation is useful with any terminal or display that cannot
interpret
the control sequences sent by a remote system. It is configured
independently
in each SERIAL_CONFIGS entry and affects incoming BBS/Telnet data on that
serial profile. It does not affect the serial-to-serial COM Port Bridge or
other configured ports. Hub menu screens use ansi for native ANSI
clear/home controls; when ANSI translation is enabled, they use
ansi_clear_sequence to clear the terminal.

"RETRO_TERMINAL": {
    # Existing serial settings go here...
    "ansi": False,
    "translate_ansi": True,
    "ansi_clear_sequence": b"\x0c",
    "ansi_home_clears_screen": False,
}

* translate_ansi enables the lossy ANSI/VT100-to-text translator. It strips
  color and unsupported control sequences, approximates common CP437
  line-drawing characters, and linearizes supported cursor positioning. It
  is
  not a complete terminal emulator; applications using complex screen
  addressing or terminal queries may not display correctly.
* ansi_clear_sequence is the byte sequence sent to the terminal for a
  supported erase-in-display/reset request, incoming form-feed (0x0C), or a
  Hub menu screen clear when translate_ansi is enabled.
  Set this to the clear-screen control sequence expected by the receiving
  terminal or its software. The default when omitted is form feed
  (b"\x0c").
* ansi_home_clears_screen defaults to False. Set it to True when an
  application redraws a screen by returning the cursor home and the
  configured
  clear sequence is suitable. This can be useful for refreshed or animated
  interfaces; cursor-home is then treated as a clear rather than merely
  repositioning the cursor.

The clear sequence can be any byte sequence understood by the terminal or
its
software. Some terminal emulators can map a custom sequence to a screen
action.
Leave translation disabled for terminals that already interpret the remote
system's control sequences.

BBS Directory

The initial BBS directory is seeded from three synchronized lists in
config.py:

* BBSS: Display names for each BBS
* IPS: Hostnames or IP addresses
* PORTS: TCP port numbers

The first time the hub starts, it uses those lists as its directory. Changes
made with Bulletin Boards -> M=Manage directory are saved to
bbs_directory.json and include the original entries. The saved directory
then
takes precedence over config.py, so entries can be added, edited, and
deleted
without keeping three lists synchronized. Delete bbs_directory.json while
the hub is stopped to restore the defaults from config.py.

In the Telnet option, enter a hostname/IP and port for a direct TCP terminal
connection. Choose whether to save that destination in Telnet bookmarks, add
it
to the Bulletin Boards directory, or connect without saving. Telnet
bookmarks
are stored separately in telnet_bookmarks.json; select a saved destination
by
number or use D to delete it. Both connection types support ATH to hang up
and ATM to return to the main menu. Incoming data uses the same configured
ANSI translation and screen-clear behavior.

Inbound Telnet-Compatible Server (Optional)

Retro Serial Hub can also accept incoming TCP terminal connections. Add a
TELNET_SERVER_CONFIGS entry in config.py for each machine profile you want
to expose, using a distinct port for each profile:

TELNET_SERVER_CONFIGS = {
    "APPLE2": {"host": "0.0.0.0", "port": 6400},
    "IBM": {"host": "0.0.0.0", "port": 6401},
}

The keys must match entries in SERIAL_CONFIGS. Set host to 0.0.0.0 to
accept connections from other devices on the LAN, or 127.0.0.1 for local
connections only. Start the hub, then connect a TCP terminal or Wi-Fi modem
to
the hub computer's IP address and the configured port (for example,
192.168.1.20:6400). The selected profile controls the menu's ANSI behavior;
the server works even if that profile's serial port is not connected.
When a listener starts, the hub prints detected LAN IPv4 address(es) and
ports
to use for connecting.

Telnet connections require a source IP entry in telnet_allowlist.json. The hub
creates an empty allowlist on its first network-enabled start. Serial connections
are exempt. No IP, including loopback, is automatically trusted.

Unknown clients wait up to 120 seconds for approval. At the HOST COMPUTER'S
console, type allow <request number> or deny <request number>, then Enter.
The dashboard shows the source IP and requested profile. The pending command
lists requests. Approval saves the IP before opening a session; future connections
from that address enter any profile normally. Remote input cannot approve itself.

Alternatively, edit the JSON manually:
{"allowed_ips": ["192.168.1.13", "192.168.1.14"]}

Manual additions apply without restarting, including to waiting clients. Removing
an IP blocks its next connection; existing approved sessions continue. Missing
files mean an empty allowlist. Invalid files or failed saves never grant access.
Without an interactive host console, unknown clients are refused; manually add
their IPs and reconnect. The queue holds at most 16 requests, one per source IP.

IP approval trusts an address, not a hardware identity. Use DHCP reservations
where possible; clients behind the same NAT/proxy may share an approved address.
Telnet remains unencrypted. Restrict access with your firewall and do not forward
these ports from the Internet. An empty TELNET_SERVER_CONFIGS disables listeners.

AI Assistant Configuration (Optional)

To enable the AI Assistant feature:

1. Edit settings/local/ai_config.json:
   {
       "api_key": "your-openai-api-key-here",
       "model": "gpt-5.6-terra"
   }

2. Or set the OPENAI_API_KEY environment variable

The default model is gpt-5.6-terra, replacing retired gpt-3.5-turbo. Set model
in ai_config.json or OPENAI_MODEL to select another Chat Completions model;
the environment variable takes precedence. Reopen AI after changing the model.
The selected model is shown in the assistant header and fixed per conversation.
The default uses reasoning_effort none and a 500-token completion budget.
For other models, reasoning is omitted unless configured through reasoning_effort
or OPENAI_REASONING_EFFORT. The value default omits the field for any model.

Usage

Starting the Hub

Run the hub from the command line:

python RETRO_SERIAL_HUB.py

The startup console shows each profile's serial-port and inbound
TCP-listener
status, connection addresses, and active remote-client counts. In an
interactive
terminal, the status dashboard updates live and uses color when supported.
Serial ports that are not present are marked unavailable; enabled TCP
listeners
continue to run independently. When output is redirected, status changes and
errors are printed as ordinary text without ANSI color codes.

Connecting Your Vintage Computer

1. Connect your vintage computer to the USB-to-Serial adapter
2. Start your terminal software on the vintage computer
3. Configure the terminal to match the settings in config.py (baud rate, data bits, parity, stop bits)
4. Press Enter to see the main menu. Type ATM at any time to return to it.

Main Menu

The accordion main menu groups features into:

* [1] Communications: Bulletin Boards, Telnet Terminal, Web Browser, FTP Client,
  Electronic Mail, Connected Terminals, Session Capture, and WOPR
* [2] Host Connectivity: Host Applications, Launch Host App, Keyboard Bridge,
  COM Port Bridge, Host Terminal, System Monitor & Media, Host Printing, and Serial Diagnostics
* [3] Files & Media: File Manager, File Transfers, Archive Browser, Text Library,
  Document Viewer, ASCII Image Viewer, Audio Player, Find Files
* [4] Games: Minesweeper, Solitaire, Lunar Lander, Hunt the Wumpus, Blackjack,
  Mastermind, Word Guess, and Star Trek. WOPR is in Communications H or available through WARGAMES.
* [5] Accessories: Notepad, Calendar, Calculator, Address Book, Unit Converter,
  Weather & News, AI Assistant, LOGO
* [6] Workshop: Disk Image Inspector, Hex Viewer, Checksums, Text Converter,
  BASIC Listing Tools, Split / Join Files, Binary / Text Encoding, Compare Files.
* [7] System: Command Shell, Task Scheduler, Terminal Settings, Keyboard Profiles,
  Help & User Guide, Welcome Banner, Host Settings, and remote-client Disconnect

Enter a section number (0-7) to expand it and an item letter to launch it. At 80
columns, the menu is arranged in three columns; at 40 columns, it uses a compact
layout. The Keyboard option types into the focused host
application. Enter, Tab, Backspace, and Escape are supported. The configured
Ctrl+letter exit binding defaults to Ctrl+X and can be changed under
System > Host Settings. This uses Windows' native input API on Windows and
pynput on macOS/Linux. Keep the intended application focused while using
this
mode.

From the CLI, use terminals to list destinations and msg to <terminal> <text>
to send a direct message; msg <text> broadcasts. The Connected Terminals menu
also offers a selected-terminal message or text-file delivery action.

LOGO Programming

Select Accessories > H > LOGO or type LOGO at the main menu. Use commands at the
Logo> prompt. For example, REPEAT 4 (FD 80 RT 90) draws a square; square brackets
work as well. FD and BK move, RT and LT turn, PU and PD lift or lower the pen,
and STATUS reports the turtle position and heading. MAKE defines variables, TO
and END define procedures, and HELP lists the supported commands. Type BYE to
return to the hub. Drawing state is reported in the terminal; a host turtle
window opens when Python Tkinter and a graphical display are available.

Host Console Commands

Type hub commands directly at Host>, just as in the terminal CLI:
  terminals
  msg to APPLE2 Hello from the host
  broadcast Meeting in five minutes
  calc 6 * 7

Other machines can reply using msg to Host <text>. ATM opens the regular menus;
CLI returns to commands. PgUp/PgDn scroll host output, Up/Down recall commands,
and clear clears output and normally expands the activity monitor.
Use monitor collapse to keep it compact across clear; monitor auto (or
monitor expand) restores automatic behavior. This lasts until changed or restart. Blank Enter responds to prompts; Ctrl+X is
forwarded to the active session. Host commands work with Telnet listeners off.
The allow/deny/pending approval commands remain local host-console controls.

New Accessories and Media Tools

Calendar saves appointments using the host's local clock. Timed
reminders are queued for connected terminals; today's and overdue appointments
also appear when connecting. Use calendar month, calendar agenda, or
calendar add YYYY-MM-DD HH:MM "Title". Use calendar done <id> to complete one.

Unit Converter handles length, mass, US volume, temperature, and number bases:
convert 72 F C; convert 1 mi km; convert FF hex bin.

Address Book stores names, email, phone, BBS addresses, and notes. Use contacts
add "Name", contacts set <id> email user@example.org, contacts mail <id> to
compose a host draft, or contacts connect <id> to open a saved BBS destination.
Appointments and contacts are shared across terminals in settings/local/.

File Manager browses files, creates folders, renames, copies, moves, views, and
transfers files. Archive Browser lists ZIP members and extracts selected files
or all contents. Both can browse accessible host folders outside files/; existing output files
are not replaced.
Try fileman ls or archive open software.zip; each command accepts help.

Audio Player plays through host speakers with a shared queue, playback controls,
volume, and saved M3U playlists. Try audio list, audio play 1, audio queue 2,
audio save "Retro Mix", audio load "Retro Mix", or audio radio <stream URL>.
Windows supports native local playback; FFmpeg (ffplay on PATH) enables internet
radio, additional formats, and playback on other platforms.

Terminal Games

The Games menu contains Minesweeper, Solitaire, Lunar Lander, Hunt the Wumpus,
Blackjack, Mastermind, Word Guess, and Star Trek. WOPR is available in Communications H or through WARGAMES. Blackjack uses H to hit, S to stand, N to start a new hand, and Q to
quit. Other games display their available single-key actions at their prompt.

The ANSI Translation option toggles translating incoming ANSI/VT100 BBS
output
for the connected machine. Its setting is saved per machine profile and
applies
to later connections as well.

Welcome Banner sets a persistent main-menu banner. The WELCOME_BANNER value
in config.py is the default; a banner set here is saved separately and takes
precedence until an empty entry resets it to the configured default.

The main menu status line shows the current local time, the number of open
serial ports, and the number of connected remote Telnet clients.

Type ATM at any time to return to the main menu and disconnect an active
network or serial bridge session.

Use N and P to scroll, G to jump to a page number, F to return to
the first page, and enter a displayed link number (such as 3 or [3]) to
follow it. B goes back, U enters another address, and Q returns to the
main menu. A saves the current page as a bookmark; M opens saved
bookmarks, where you can enter a number to open it or D followed by a
number to delete it. HTML search inputs appear as I<number>; choose one,
enter the value, then use S<number> to submit its form. Press Backspace to
edit the current input line. Bookmarks are stored in browser_bookmarks.json
beside the hub. The browser includes starter bookmarks for retro-computing
resources. It displays text and numbered links; JavaScript and images are
not
supported. HTML GET/POST forms are supported when their fields
are standard text controls. HTML and plain-text responses are limited to 1
MiB.

FTP Downloads

Select FTP, enter the server hostname and port (default 21), choose regular
FTP or explicit FTPS, and provide credentials. Press Enter at the username
prompt for anonymous login. The client uses passive mode and displays files
and
directories; use C<number> to open a directory, U to go up, and R to
refresh. Enter A to bookmark the current site; M opens saved FTP sites,
where a number opens a site and D<number> deletes a bookmark. Bookmarks
retain
the hostname, port, FTP/FTPS selection, and username, but never the
password;
the password is prompted for when opening a saved site. They are stored in
ftp_bookmarks.json.
The file includes starter FTP sites.

Selecting a file prompts for Host or Direct:

* Host saves the file in files/, where it appears in File Transfers
  the next time that menu is opened.
* Direct downloads to a temporary host file and immediately sends it using
  XMODEM, YMODEM, or ASCII. The temporary copy is removed after transfer.

Press Q to disconnect and return to the main menu. ATM also returns to the
main menu. Explicit FTPS encrypts the connection; ordinary FTP does not
encrypt
credentials or data.

Special Commands

* ATM: Return to main menu from anywhere (like the old modem "AT" commands)
* ATH: Hang up / disconnect from a BBS or Telnet host
* Q: Quit from most sub-menus

File Transfers

The hub supports multiple file transfer protocols:

* XMODEM: Classic 128-byte block protocol with checksum
* YMODEM: 1024-byte block protocol for faster transfers
* ASCII: Plain text streaming (no error correction)

To send a file from the hub to your vintage computer:
1. Select "File Transfers" from the main menu
2. Browse into a directory by selecting its number, or type a directory path
   to jump directly to it. D opens the available drives (or filesystem
   root),
   B goes to the parent directory, and H returns to the hub's files/
   home directory.
3. Choose the transfer protocol (X/Y/A)
4. Select the file number
5. Start the receive function on your vintage computer

To upload a file from your vintage computer:
1. Select "File Transfers" from the main menu
2. Press "U" for upload
3. Enter the filename to save as
4. Start the send function on your vintage computer
Uploads are saved in the directory currently open in File Transfers.

The File Transfers menu opens in the hub's files/ directory by default, but
you can browse or type a path to transfer files from anywhere the hub
process
can access. Uploads are saved in the currently open directory.

Directory Structure

Retro-Serial-Hub/
 RETRO_SERIAL_HUB.py    # Main hub program
 config.py               # Configuration file (edit this!)
 ai_config.json          # OpenAI API key (optional)
 bbs_directory.json     # Managed BBS directory (created when first changed)
 terminal_columns.json  # Saved per-profile 40/80-column choices
 telnet_bookmarks.json  # Telnet bookmarks (created when first saved)
 ftp_bookmarks.json     # FTP/FTPS bookmarks (created when first saved)
 requirements.txt       # Python dependencies
 rsh_ai.py              # AI Assistant module
 rsh_bbs.py             # BBS directory and management module
 rsh_directory.py       # Persistent BBS directory storage
 rsh_telnet.py          # Direct TCP terminal connections and bookmarks
 rsh_ftp.py             # FTP/FTPS browser and downloads
 rsh_browser.py         # Text-first web browser and bookmarks
 rsh_bridge.py          # COM port bridge module
 rsh_files.py           # File transfer module
 rsh_keyboard.py        # Host keyboard bridge
 rsh_notes.py           # Notes module
 rsh_terminal.py        # ANSI translation and screen clearing
 rsh_text.py            # Text library module
 rsh_wargames.py        # WarGames module
 rsh_welcome.py         # Persistent welcome banner
 files/                 # File transfer storage
 text/                  # Text library files, README, and starter articles
 notes/                 # Notes storage
 tests/                 # Unit tests

Module Development

The hub uses a modular architecture. Each feature is implemented in a
separate rsh_*.py module that can be edited without restarting the hub.
Modules are automatically reloaded when accessed.

Each module implements a standard interface:

def create_session(ser, use_ansi=True, **kwargs):
    """Initialize and return a session object"""
    pass

def handle_input(session, line_str, ser, use_ansi=True):
    """Handle user input. Returns (consumed, action) tuple"""
    pass

This design allows you to customize or extend features without modifying the
core hub.

Troubleshooting

Port Won't Open

* Check that the COM port name in config.py matches your system
* On Windows, use Device Manager to verify COM port numbers
* On Linux/Mac, ports are typically /dev/ttyUSB0, /dev/ttyACM0, etc.
* Ensure no other program is using the port
* Check cable connections

Connection Issues with Vintage Computer

* Verify baud rate matches between hub and terminal software
* Check data bits, parity, and stop bits settings
* Try disabling hardware flow control (rtscts) if connections are unreliable
* Some vintage systems require null-modem adapters

BBS Won't Connect

* Verify the hostname/IP and port in the BBS directory or Telnet bookmark
* Check your internet connection
* Some BBSs may be offline; try a different one
* Firewall may be blocking outbound Telnet connections

Garbled Text

* Check baud rate settings
* Verify data bits setting (usually 8)
* Disable ANSI support for terminals that don't support it
* Try a different cable

Release Notes

v2.5

* Star Trek shows command examples, course directions, and resupply guidance
  on launch, with terminal output paged to the configured screen size.
* Consolidated JSON under settings/: public defaults/ templates and ignored
  local/ personal data, with automatic migration from legacy locations.
- Added Workshop as category 6 with disk-image inspection, hex viewing, checksums, text conversion, BASIC listing preparation, split/join, hex/Base64 encoding, and file comparison. System moves to category 7; categories retain at most eight A–H entries.
- Unified host-file browsing across file tools, with drives/root, parent folders, direct paths, favorites, filters, marking, and batch copy/move. Audio can select files anywhere the host can access. Added Find Files under Files & Media H.
- Added searchable, resumable reading and bookmarks, plus note editing, renaming, exporting, and content search.
- Simplified the audio player menu; added queue editing, repeat/shuffle, named radio stations, and a remembered music folder.
- Added Session Capture under Communications G and Serial Diagnostics under Host Connectivity H, including transfer progress and host cancellation.
- Improved XMODEM/YMODEM negotiation, retries, fragmented reads, and completion handling. Receives preserve binary padding, avoid overwriting files, and publish completed files only after success.
- Added serial inactivity timeouts and cleared stale menu selections when a port becomes active again. Queued notifications keep messages out of prompts and transfer streams, with optional quiet mode.
- Added saved machine preferences and host application launch presets. Terminal height defaults to 24 rows per profile; menus keep the footer stable, clear submenus, and reserve readable spacing in 40- and 80-column layouts.
- Updated the host dashboard with Unicode borders and ASCII fallback, a single color-coded Connections list, and an activity monitor that collapses during host interaction to give output more room. clear normally restores the expanded layout; monitor collapse pins it compact and monitor auto restores automatic behavior.
- Enhanced the WOPR/Joshua interaction while retaining the IMSAI/CP/M dialer, with movie-style displays, gentler pacing, and optional synchronized host speech. Open it from Communications H or wargames.

v2.4

* AI Model Compatibility: Replaced retired GPT-3.5 Turbo with GPT-5.6 Terra,
  updated completion parameters, and added configurable model/reasoning settings
  with clearer guidance when a model is unavailable.
* Interactive Host Console: Run hub CLI commands and interactive menus from the
  host keyboard. Added messages to other terminals and replies to Host, command
  history, scrollable output, and masked FTP password input.
* Telnet Source Approval: New IPs require allow <request #> or deny <request #>
  at the host console, or a manual telnet_allowlist.json entry. Approval is saved
  before opening a session. Invalid policies/saves never grant access. Requests
  expire and the pending queue is bounded. Serial connections are exempt.
* Added Calendar with reminders, Unit Converter, Address Book, File Manager,
  ZIP Archive Browser, and Audio Player with playlists and optional FFmpeg radio.
* Added Word Guess and a Star Trek adaptation inspired by Apple II BASIC, with
  quadrant scans, navigation, phasers, torpedoes, shields, and starbase resupply.
* Added Host Settings with a saved keyboard bridge exit key, default Ctrl+X.
  Escape is forwarded to applications instead of exiting the bridge.
* Reordered Files & Media and Accessories; shortened Calendar and Weather & News
  labels. Disconnect is last in System. Active connection rows now match waiting
  rows in field order and indentation, under matching gray section dividers.
* Fixed redraw drift after console input using fixed screen positions and
  viewport limits, while retaining the host prompt on smaller windows.
* Isolated game, Logo, and mail sessions, serialized module initialization, and
  shared one scheduler per task file to prevent duplicate background jobs.
* Updated application version to v2.4, both user guides, in-hub help, and tests.
  Source allowlists, appointments, and contacts remain local installation data.

v2.3

* Added a terminal Logo accessory and CLI launcher with repeat loops, bracket or
  parenthesis command groups, variables, arithmetic, procedures, and turtle
  position feedback. Optional host graphics use Python turtle.
* Added the Communications > Connected Terminals feature to list terminals,
  send direct messages, and deliver text files over ASCII. Added terminals and
  targeted msg commands to the CLI.
* Added Lunar Lander, Hunt the Wumpus, Blackjack, and Mastermind to the Games
  menu while keeping WarGames available through the CLI. Standardized single-key
  game actions in interactive prompts.
* Moved Host Printing to Host Connectivity, renamed Notes to Notepad, and added
  host clipboard capture and note-to-clipboard actions.
* Fixed dashboard section activity numbering and normalized menu spacing.
* Updated application version to v2.3.

v2.2

* Task Scheduler Command Chaining: Scheduled tasks can now chain multiple
  commands in a single scheduled event using ' : ' (or ';'), executing them
  sequentially and compiling the outputs cleanly (for example:
  news : weather Austin : broadcast Morning briefing complete).
* Resilient Chained Task Execution: If an individual command in a chain
  encounters an error or is unrecognized, subsequent chained commands continue
  to run and report output without halting the sequence.
* Dynamic Scheduler CLI Command Discovery: schedule modules now dynamically
  enumerates all shell commands available in the active runtime rather than a
  static list, and schedule info <cmd> provides detailed syntax and chaining
  guidance for any registered command.
* Scheduler Alert & Broadcast Integration: Added explicit scheduler
  documentation and module usage info for real-time messaging commands
  (broadcast, notify, msg, alert), enabling scheduled tasks to push
  instant notifications to all connected terminals.
* Enhanced Scheduler Menu & URL Handling: Updated the interactive menu
  ([2] Add New Scheduled Task) with command chaining support, helpful chaining
  prompts, and automatic URL detection and wrapping for web endpoints.
* Incremented application version to v2.2.

v2.1

* Document Viewer Windows Path Resolution: Fixed an issue where Windows
  backslashes were stripped during shell argument parsing (causing duplicated or
  corrupted paths such as OneDriveSoftware...), allowing documents, images,
  and local files to load seamlessly from local drives.
* Interactive News Article Reader: Added interactive headline article selection
  to Weather & News, allowing vintage terminals to type an article number directly
  to read the complete summary and download full web article contents (F /
  news <num> full).
* Dedicated News Task Scheduler Option: Added news and weather command
  scheduling to the background task scheduler (schedule add <interval> news ...),
  listing them under schedule modules.
* Console Pseudo Interface & Connected User Highlighting: Enhanced the live
  host console dashboard with an interactive pseudo interface layout displaying
  connected client activity and highlighting active menu items in real time.
* Updated Copyright Notices: Updated all system banners, headers, and
  documentation to 2025-2026.
* Incremented application version to v2.1.

v2.0

* Retro Serial OS Runtime: Full host-side operating system extension with
  an interactive command prompt (cli> / OS), hot-reloadable module system,
  event bus publish/subscribe architecture, multi-client session tracking,
  and programmable keyboard bridge shortcut profiles.
* Accordion Main Menu & Custom Shortcuts: Fast categorized accordion flyout
  menu layout optimized for 40- and 80-column terminals, complete with a
  user-defined command shortcut macro system with automatic flyout.
* Host Terminal & Quick Shell: Bidirectional streaming console session to
  the host OS (cmd.exe, powershell, or unix shells) with configurable local
  echo, newline translation, and interactive parameters.
* Real-Time Host System Monitor: Live CPU load measurement, memory, disk,
  and uptime monitor with continuous screen clearing, pause/resume, and
  adjustable refresh rates (top / sysinfo live).
* Modern Document Viewer Pipeline: Automatic text extraction and pagination
  for modern file formats including PDF, Word (.docx), Excel (.xlsx / .csv),
  plain text, Markdown, HTML, and web URLs.
* Integrated Hub Mail & Internet Email: Central inter-terminal hub mailbox
  identifying senders by hardware/connection, along with full IMAP/SMTP
  internet email support and host desktop configuration GUI.
* Dedicated Retro Games: Native text-mode Minesweeper, Solitaire (Klondike),
  and WarGames (W.O.P.R.) simulation.
* Ambient Desk Companion: Live ASCII weather forecasts (wttr.in), RSS news
  feeds (NPR, Hacker News, BBC), and automated morning briefings (briefing).
* Background Task Scheduler: Automated periodic task execution with
  terminal broadcast notifications and cron-like intervals.
* Terminal Hardware Settings & In-Hub Help: Caps-Only mode for vintage
  uppercase-only ROMs (Apple II Plus, Commodore PET, TRS-80 Model I), serial
  character pacing delays (1-3ms), and 9 comprehensive in-hub help guide topics.
* Incremented application version to v2.0.

v1.5

* Added a persistent, per-machine ANSI translation toggle in the System menu
  (option 12), and moved the terminal-width toggle to option 13.
* Added File Transfers directory browsing, drive/root selection, direct path
  entry, and shortcuts to move to the parent or return to the files/ home.
* Expanded Text Library reader pages to use the available 24 terminal rows at
  40 and 80 columns.
* Incremented the application version to v1.5.

v1.4

* Fixed text-library pagination to account for wrapped lines, terminal width,
  the continuation prompt, and the echoed Enter key so the first displayed
  lines remain visible on 40- and 80-column terminals.
* Added plain-text versions of this README and short vintage-computer articles
  on the Apple II, Commodore 64, TRS-80, IBM PC, and Altair 8800 to the Text
  Library.
* Added starter browser bookmarks for retro-computing resources and anonymous
  FTP bookmarks for three public file archives.
* Set saved terminal-column defaults to match the bundled machine profiles
  and reordered the System menu so option 12 switches column width and
  option
  13 opens Welcome Banner.
* Included the recent menu-routing and Notes workflow fixes, incoming
  Telnet-compatible Wi-Fi modem documentation, Keyboard Bridge feature
  listing,
  and Aaron Smith copyright notice.
* Updated the application version to v1.4.

v1.3

* Fixed main-menu routing after the Accessories/Files reorder and restored
  Notes creation, cancellation, and deletion workflows.
* Fixed returning to the Notes menu after reading a note.
* Documented incoming Telnet-compatible Wi-Fi modem access and the Keyboard
  Bridge; set the default C64 terminal width to 40 columns.
* Added the project copyright notice and incremented the application version.

v1.2

* Added optional per-machine inbound TCP terminal servers for Wi-Fi modems and
  other remote terminals, plus startup connection addresses and a live,
  colorized console dashboard with serial, listener, and client status.
* Added a remote-session-only Disconnect menu option and a main-menu status
  line showing local time and active connections.
* Added per-machine 40/80-column layouts with a persistent width toggle,
  reorganized and renumbered the menu sections, and adapted browser pages
  and
  other feature menus to the configured terminal width.
* Added bracketed, consistent menu section headings and improved startup and
  menu spacing for both display widths.
* Centralized the displayed application version and updated it to v1.2.

v1.1

* Replaced the former URL Reader with a text-first Web Browser supporting
  paginated pages, numbered links, standard HTML forms, history, and
  bookmarks.
* Added direct Telnet connections with persistent Telnet bookmarks and the
  option to add destinations to the Bulletin Boards directory.
* Added persistent BBS directory management for adding, editing, and deleting
  configured and user-added entries.
* Added FTP/explicit-FTPS directory browsing, saved site bookmarks, and
  downloads to the hub's file library or directly to the terminal using
  XMODEM, YMODEM, or ASCII.
* Added a cross-platform Keyboard Bridge (Windows native input; macOS/Linux
  through pynput), plus Ctrl+X as an exit shortcut.
* Added persistent welcome-banner customization, main-menu and submenu screen
  clearing, and improved ANSI translation for non-ANSI terminals.
* Migrated the AI Assistant to the current OpenAI Python client interface.
* Reordered the main menu, added the FTP option, shortened the banner option
  label to Welcome Banner, and documented ATM as the menu return command.

Hardware Recommendations

* USB-to-Serial Adapters: Look for adapters with FTDI chipsets for best compatibility
* Cables: DB9 or DB25 cables depending on your vintage computer
* Null-Modem Adapters: Required for some vintage systems
* RS-232 Level Shifters: May be needed for some single-board computers

Contributing

Contributions are welcome! Please feel free to submit pull requests or open
issues for bugs and feature requests.

License

This project is provided as-is for use by the retro computing community.
Feel free to modify and distribute.

Acknowledgments

* Inspired by classic BBS systems and the retro computing community
* Special thanks to the maintainers of the various BBSs listed in the default configuration
* Built with the assistance of GitHub Copilot and AI coding agents

Support

For questions or issues, please open a GitHub issue or contact the retro
computing community forums.


Happy retro computing!
