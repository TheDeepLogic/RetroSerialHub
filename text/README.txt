Image: Retro Serial Hub

Retro Serial Hub v2.7a

* Anchored host scrollback, a new-line counter, and End to return to live output.
* Immediate message notices, safe deferral during transfers, and M=Messages at
  the main menu. A session inbox keeps received text files and read history
  separate from email.
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
* WOPR: IMSAI/CP-M and Joshua simulation in Communications H or via WARGAMES
* Notepad clipboard actions: Save host clipboard text as a note, or copy a note to the host clipboard
* AI Assistant: Optional OpenAI, Gemini, or local Ollama chat accessible from vintage terminals
* Hot-Reload Modules: Edit feature modules without restarting the hub
* ANSI Support: Automatic detection and handling of ANSI escape codes for compatible terminals

Requirements

* Python 3.9 or higher
* Dependencies listed in requirements.txt
* USB-to-Serial adapters or RS-232 ports for connecting vintage computers
* Optional: AI Assistant uses local Ollama without a key, or an OpenAI/Gemini API key

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

Tools and session guide

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
If a note was deleted, cannot be read, or is not valid UTF-8, Edit displays an
error and returns to the Notes menu so you can choose another note or quit.
If saving fails while writing or replacing the temporary file, the original note
and your in-memory edits remain intact so you can retry save. Failed saves also
clean up their temporary file when filesystem permissions allow it.
Large content searches inspect note text up to 1 MiB, while filenames are always searched.
Content search skips notes that cannot be read or disappear during the search,
reports the skipped count, and continues returning the other matches.
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


Capture, diagnostics, messages

Session Capture records readable outgoing terminal text, including locally echoed
conversation, to hub_tools/captures/. Control sequences are translated/removed;
raw binary transfers and secret input/output are excluded. Captures can be stopped,
listed, viewed, and exported. It does not replay captured keystrokes or commands.

Serial Diagnostics lists connected sessions, byte counters, last-input age,
settings and modem signals where supported, recent ASCII/hex traffic, and active
transfer progress. The host can request cancellation using
diagnostics cancel <terminal-name-or-port>. It never opens a second connection
to a busy port or toggles modem control lines automatically.

Terminal messages and received text files announce themselves immediately, even
at an idle prompt. Only active file transfers automatically defer notices;
waiting notices appear after the transfer. Explicit quiet mode is still available.
Press M at the main menu (M=Messages), or type MESSAGES / MSGS at the menu or CLI.
Messages is separate from Electronic Mail. The session inbox keeps up to 100 items,
with unread markers, paging, read-all-unread, and history until disconnect.
Long files stay in the inbox rather than flooding the screen. Connected Terminals
also accepts M=Messages (N still works). messages quiet on/off toggles notices for
this session; machine quiet on/off saves the default.
Connected Terminals shows input age
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
supplied in serial_profiles in settings/local/hub_config.json before a saved preference exists.

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

Configuration

Core settings are in settings/local/hub_config.json. There is no config.py.
Use the host console's config menu to add a computer, or edit the JSON while
the hub is stopped. New installations start with APPLE2 on COM1 and C64 on COM2;
inbound Telnet is disabled until configured. These are starter assignments, so
select the ports actually present on your computer.

On the first interactive launch, the console opens the configuration menu
automatically. Serial workers and inbound listeners wait until you leave setup,
so starter assignments do not produce connection failures while you configure
them. Use 5 Edit existing profile to adjust the starter computers, or add
another. Q Return to hub finishes setup, reloads saved settings, and starts
the configured profiles. This also acknowledges unchanged starter defaults.
Completion is saved locally as configuration_completed: true; later launches
open normally. Your existing local setup is already marked complete. Without an
interactive console, the hub uses the JSON settings directly.

Host configuration wizard

At the physical host console, type config (or host config). Its separate menu
offers Add Profile, Edit Profile, List Profiles, Hub Defaults, and WOPR Speech.

Add Profile walks through a unique name, a scanned serial-port selection, baud,
data bits, parity, stop bits, software/hardware flow control, ANSI menus and
translation, screen-clear hex bytes, cursor-home clearing, width (40/80), height
(16-100), inactivity timeout, and optional inbound Telnet bind address and port.
The port step shows eight detected devices per page: use Next/Prev, R to rescan,
or type a device name manually for an offline device or a Unix serial path.

Enter accepts a displayed default; Back revisits a field. Cancel discards the
draft and returns to the configuration menu, and Q exits that menu. A review
screen requires yes before writing anything. Duplicate serial assignments,
conflicting listener ports, invalid values, and settings changed by another
writer are rejected without overwriting the saved configuration.

Newly saved profiles start their serial worker and optional Telnet listener
immediately, without restarting existing connections. Missing hardware is shown
by the normal connection status; saving does not guarantee a port can be opened.
If activation fails, the saved profile remains available for the next launch.
Outside first setup, hub-default, speech, and existing-profile changes require a
restart, as do manual JSON edits. Use 5 Edit existing profile for an existing
computer; remove profiles in JSON while stopped. Remote HOST commands cannot
open or operate this menu, even after host-control approval.

JSON settings and personal data

Configuration and application data live under settings/:

- settings/defaults/ contains version-controlled, public starter templates,
  including the supplied web/FTP bookmarks and keyboard profiles. The AI template
  contains a placeholder key and the Telnet allowlist starts empty. hub_config.json
  supplies two example computers; bbs_directory.json supplies structured BBS entries.
- settings/local/ contains live JSON: credentials, mail, bookmarks, contacts,
  appointments, shortcuts, scheduler tasks, terminal preferences, reading
  positions, and other saved settings. Missing starter files are copied here;
  other files are generated when their features need them. Editing live settings
  never changes the public templates.
- On first use, existing JSON files from the project root, mail/, hub_tools/,
  and the former retro_os/ storage location move into settings/local/.
  Existing local files take priority; differing old copies are preserved under
  settings/local/legacy/. Identical duplicate copies are removed. No existing
  settings are replaced by templates. JSON migration leaves non-JSON content,
  such as session captures in hub_tools/captures/, in place.

Back up settings/local/ privately. It may contain passwords, API keys, mail,
addresses, and personal paths. Git ignores that directory and JSON outside the
explicit public-defaults location, including legacy JSON locations. Only put
reviewed, sanitized starter content in settings/defaults/; do not copy live
files there wholesale or force-add ignored personal files. To publish a new
bookmark default, add the intended public entry to its template separately.
Template changes affect missing local files, never existing personal copies.
Moving a previously tracked file does not erase it from older Git history.

The hub JSON contains schema_version: 1, serial_profiles, telnet_listeners,
welcome_banner, serial_idle_timeout_seconds, and wopr_speech. WOPR speech
uses enabled, rate, volume, voice, pitch, gap, and executable (empty
means auto-detect). The general timeout uses seconds, with 0 disabling it;
profiles can override it using idle_timeout_seconds. JSON uses numeric serial
settings (8 data bits, parity "N", 1 stop bit), not Python constants.

Specialized stores remain separate: AI credentials, BBS directory, approvals,
console appearance, terminal/machine preferences, and the welcome-banner override.
Saved terminal width/translation/machine preferences and the saved welcome banner
continue to override profile/global defaults. Changing those defaults does not
erase an existing terminal preference or banner override.

Serial Port Configuration

Each entry in serial_profiles represents one vintage computer or device.
For example, this is a fragment of hub_config.json:

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

Set columns independently for each machine profile to 40 or 80. This is
the profile's default width; the main-menu System → Terminal Settings → Screen Size option can
switch and save that profile's preference. The saved selection is stored in
settings/local/terminal_columns.json and takes precedence over the profile default. At 40 columns,
menus use a compact layout, browser pages wrap to the configured width, long
labels are shortened to fit, and ANSI translation uses the configured terminal
width. The included defaults use 80 columns for APPLE2 and 40 for C64;
profiles without this setting default to 80.

Common baud rates for vintage systems:
- Apple II with Super Serial Card: 300, 1200, 2400, 9600, 19200, or 115200
- Commodore 64: 300, 1200, 2400
- IBM PC/XT/AT: 300, 1200, 2400, 9600
- TRS-80: 300, 1200, 2400, 9600

Optional translation for non-ANSI terminals

ANSI translation is useful with any terminal or display that cannot interpret
the control sequences sent by a remote system. It is configured independently
in each serial_profiles entry and affects incoming BBS/Telnet data on that
serial profile. It does not affect the serial-to-serial COM Port Bridge or
other configured ports. Hub menu screens use ansi for native ANSI
clear/home controls; when ANSI translation is enabled, they use
clear_sequence_hex to clear the terminal.

{
    "ansi": false,
    "translate_ansi": true,
    "clear_sequence_hex": "0c",
    "ansi_home_clears_screen": false
}

- translate_ansi enables the lossy ANSI/VT100-to-text translator. It strips
  color and unsupported control sequences, approximates common CP437
  line-drawing characters, and linearizes supported cursor positioning. It is
  not a complete terminal emulator; applications using complex screen
  addressing or terminal queries may not display correctly.
- clear_sequence_hex represents the bytes sent to the terminal for a
  supported erase-in-display/reset request, incoming form-feed (0x0C), or a
  Hub menu screen clear when translate_ansi is enabled.
  Set this to the clear-screen control sequence expected by the receiving
  terminal or its software. The default when omitted is form feed
  (hex "0c"). For ESC-v, use "1b76"; no Python byte literal is needed.
- ansi_home_clears_screen defaults to False. Set it to True when an
  application redraws a screen by returning the cursor home and the configured
  clear sequence is suitable. This can be useful for refreshed or animated
  interfaces; cursor-home is then treated as a clear rather than merely
  repositioning the cursor.

The clear sequence can be any byte sequence understood by the terminal or its
software. Some terminal emulators can map a custom sequence to a screen action.
Leave translation disabled for terminals that already interpret the remote
system's control sequences.

BBS Directory

Both the numbered menu and CLI load settings/local/bbs_directory.json, a list
of objects containing name, host, and numeric port. There are no parallel
name/host/port lists to edit. On first use the supplied 64-entry directory is
copied from settings/defaults/bbs_directory.json; existing local entries win.
Changes made with Bulletin Boards → M=Manage directory update the local file.
Delete it while stopped to restore the public template on the next launch.

[
    {"name": "Example BBS", "host": "bbs.example.org", "port": 23}
]

In the Telnet option, enter a hostname/IP and port for a direct TCP terminal
connection. Choose whether to save that destination in Telnet bookmarks, add it
to the Bulletin Boards directory, or connect without saving. Telnet bookmarks
are stored separately in settings/local/telnet_bookmarks.json; select a saved destination by
number or use D to delete it. Both connection types support ATH to hang up
and ATM to return to the main menu. Incoming data uses the same configured
ANSI translation and screen-clear behavior.

Inbound Telnet-Compatible Server (Optional)

Retro Serial Hub can also accept incoming TCP terminal connections. Add a
telnet_listeners entry in settings/local/hub_config.json for each profile you want
to expose, using a distinct port for each profile:

{
    "telnet_listeners": {
        "APPLE2": {"host": "0.0.0.0", "port": 6400},
        "C64": {"host": "0.0.0.0", "port": 6401}
    }
}

The keys must match entries in serial_profiles. Set host to 0.0.0.0 to
accept connections from other devices on the LAN, or 127.0.0.1 for local
connections only. Start the hub, then connect a TCP terminal or Wi-Fi modem to
the hub computer's IP address and the configured port (for example,
192.168.1.20:6400). The selected profile controls the menu's ANSI behavior;
the server works even if that profile's serial port is not connected.
When a listener starts, the hub prints detected LAN IPv4 address(es) and ports
to use for connecting.

Incoming Telnet clients must be listed in settings/local/telnet_allowlist.json. The hub
creates this file with an empty allowed_ips array on its first network-enabled
start; no address, including loopback, is automatically trusted. Serial
connections do not use this approval process.

An unknown address waits for up to 120 seconds while the host dashboard shows
its request number, source IP, and requested machine profile. At the host
computer's console, type allow 1 or deny 1 (using the displayed request
number), then press Enter. pending lists pending requests. Approval is saved
before the waiting client receives a hub session. Future connections from that
IP can enter any machine profile without another prompt. Input sent by an
unapproved client is discarded and cannot approve its own connection.

You can also edit the JSON manually, using individual IP addresses:

{
  "allowed_ips": ["192.168.1.13", "192.168.1.14"]
}

See settings/defaults/telnet_allowlist.example.json for an empty template. Manual additions apply
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
telnet_listeners is empty, as in the public starter configuration.

AI Assistant Configuration (Optional)

The assistant supports OpenAI, Google Gemini, and local Ollama from
Accessories G. All three use the same terminal chat interface and the optional
client library: python -m pip install openai. Using that library with another
provider does not send requests to OpenAI.

Choose one provider in settings/local/ai_config.json. Configuration is managed
on the host; the terminal displays the selected provider and model.

Local Ollama: no API key or token charges

Install Ollama (https://ollama.com/download) on the hub computer, start it, and
run ollama pull llama3.2:3b once to download the example model. Use:

{
    "provider": "ollama",
    "model": "llama3.2:3b"
}

The hub connects to http://localhost:11434/v1/. No API key, paid account, or
cloud service is needed for a downloaded local model. Model speed and capacity
depend on the host's hardware. Use ollama list to see installed model names.
For an Ollama server on another host, set base_url to its full HTTP(S) address
ending in /v1/, or set OLLAMA_BASE_URL. See
Ollama compatibility (https://docs.ollama.com/api/openai-compatibility).

Google Gemini: hosted free-tier option

Get a key from Google AI Studio (https://aistudio.google.com/apikey), then use:

{
    "provider": "gemini",
    "model": "gemini-3.8-flash",
    "api_key": "your-gemini-api-key"
}

You can omit api_key and set GEMINI_API_KEY instead. Gemini offers a free tier
for eligible models, accounts, and regions, with quotas and rate limits. A key
alone does not guarantee free usage: keep the project on the free tier if that
is your intent. Free-tier content may be used to improve Google's products.
Check current pricing and terms (https://ai.google.dev/gemini-api/docs/pricing).
Gemini uses the model's default thinking settings unless reasoning_effort is
explicitly configured. Available levels depend on the model; the hub accepts
minimal, low, medium, or high as explicit overrides. Use default or
remove the setting if Gemini rejects a thinking level. See
Gemini compatibility (https://ai.google.dev/gemini-api/docs/openai).

OpenAI: existing configuration remains supported

{
    "provider": "openai",
    "model": "gpt-5.6-terra",
    "api_key": "your-openai-api-key"
}

Omitting provider keeps the existing OpenAI behavior. OPENAI_API_KEY can
supply the key instead. OpenAI API usage is billed separately from a ChatGPT
subscription; this option does not provide free ChatGPT access.
The existing default model and OpenAI reasoning settings are preserved.

Overrides, conversation settings, and troubleshooting

- AI_PROVIDER overrides provider: openai, gemini, or ollama.
- AI_MODEL overrides the model for the selected provider. Next in precedence
  are OPENAI_MODEL, GEMINI_MODEL, or OLLAMA_MODEL, respectively, then JSON
  model, then that provider's default.
- Provider-specific key environment variables override JSON api_key. Switching
  providers through AI_PROVIDER does not reuse another provider's JSON key,
  model, token budget, or reasoning settings.
- max_tokens in JSON sets the response budget (1-8192; default 500). Reasoning
  models can consume part of that budget before producing visible text; increase
  it or choose another model if replies are empty or cut short.
- For OpenAI, reasoning_effort in JSON or OPENAI_REASONING_EFFORT controls
  reasoning. The default OpenAI model uses none; custom models omit the field
  unless configured. default omits it for any OpenAI model. Ollama omits the
  reasoning field; choose a suitable local model.
- Reopen the assistant after changing configuration. An active conversation keeps
  its provider, model, credentials, and options. N clears its history while keeping
  those settings; Q exits. Configuration is never written by terminal chat.
- Requests have a 60-second timeout and no automatic retries. A quota, connection,
  or model error stays with the selected provider; there is no automatic fallback
  to a potentially paid service. Failed requests leave conversation history ready
  to retry. For Ollama connection/model errors, check the service and ollama list.

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
3. Configure the terminal to match the settings in its JSON profile (baud rate, data bits, parity, stop bits)
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

The host console opens the numbered menu on startup. Type directly into the
active hub prompt, with console control hints immediately above it. CLI opens
the command shell; ATM returns to the main menu. For example:
  terminals
  msg to APPLE2 Hello from the host
  broadcast Meeting in five minutes
  calc 6 * 7

PgUp/PgDn browse output; Up/Down recall input. PgUp holds the view while new
output arrives, with a Scrollback - N new lines indicator. End returns live;
PgDn also returns live at the bottom. Incoming screen clears and resizes preserve
what you are reading. Submitting input or clearing the console resumes live
output. Clear clears output while keeping the active prompt. Host help lists console controls; HELP reaches the hub.
On the main menu, status and the ATM/messages hint sit near the bottom, followed
by a blank line, the host controls, another blank line, and the active prompt.
The activity monitor always shows active selections. Approvals and errors take
priority over ordinary status/activity when the window is crowded.

Theme lists console schemes. Theme Windows 3.1 selects a scheme. Theme background
off preserves terminal transparency while retaining title and highlight colors;
theme colors off uses terminal-default colors. Appearance choices are saved in
settings/local/console_theme.json. Theme background on and theme colors on restore
the selected scheme. Schemes, in menu order:
  Ocean, Turquoise, Emerald City, Hot Pink, Light, Dark, QBasic, Commodore,
  Apple IIGS, TI-99/4A, Windows 95, Windows 3.1, Amber Monochrome, Green Monochrome.

A connected terminal can type HOST <text> to submit a line to the host session,
for example HOST theme Commodore or HOST ATM. Its first attempt requires local
approval by source IP or physical serial port, separate from Telnet admission.
At the physical host keyboard, type allow host <request #> or deny host <request #>.
Then retry the HOST command; the first attempt is not executed or queued.
Forwarded commands cannot approve host-control requests. Pending lists both
kinds of request. Approval lasts across reconnects and restarts, stored in
settings/local/host_command_allowlist.json. Remove a saved entry to revoke it.
Incoming Telnet sessions still use allow <#> / deny <#> and telnet_allowlist.json.
HOST works at hub and nested tool prompts, leaving the source session in place.
Raw bridges, binary transfers, and BBS streams keep normal byte handling.

WOPR CP/M Environment

WOPR opens at an IMSAI-style CP/M prompt. DIR lists the session-local disk;
TYPE README.TXT and TYPE MODEM.DOC explain the installed software. A: and B:
switch disks. DIR filters, TYPE, REN, ERA, SAVE, STAT, PIP, DUMP, and CLS provide
a small working environment. Changes last for the WOPR session; no host files
are modified. EXIT or ATM returns to the hub.

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

Welcome Banner sets a persistent main-menu banner. The welcome_banner value
in hub_config.json is the default; a banner set here is saved separately and takes
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
+-- RETRO_SERIAL_HUB.py    # Main hub program
+-- rsh_config.py           # Validated core JSON configuration store
+-- rsh_config_wizard.py    # Host-only configuration menu and profile wizard
+-- requirements.txt       # Python dependencies
+-- docs/                  # Engineering notes and reproducible measurements
+-- rsh_ai.py              # AI Assistant module
+-- rsh_bbs.py             # BBS directory and management module
+-- rsh_directory.py       # Persistent BBS directory storage
+-- rsh_telnet.py          # Direct TCP terminal connections and bookmarks
+-- rsh_ftp.py             # FTP/FTPS browser and downloads
+-- rsh_browser.py         # Text-first web browser and bookmarks
+-- rsh_bridge.py          # COM port bridge module
+-- rsh_files.py           # File transfer interface
+-- rsh_transfer.py        # XMODEM/YMODEM protocol engines
+-- rsh_storage.py         # Central JSON paths, defaults, and upgrade migration
+-- rsh_session.py         # Session capture, notifications, and diagnostics
+-- rsh_preferences.py     # Saved machine preferences
+-- rsh_keyboard.py        # Host keyboard bridge
+-- rsh_access.py          # Telnet admission and host approval queue
+-- rsh_host.py            # Local host-console terminal session
+-- rsh_console.py         # Adaptive dashboard, host input, and scrollback
+-- rsh_console_theme.py   # Console schemes and saved appearance settings
+-- rsh_host_screen.py     # Isolated host text screen and cursor controls
+-- rsh_host_access.py     # First-use HOST command approval by IP/serial port
+-- rsh_cpm.py             # WOPR session-local CP/M disks and commands
+-- rsh_notes.py           # Notes module
+-- rsh_terminal.py        # ANSI translation and screen clearing
+-- rsh_text.py            # Text library module
+-- rsh_wargames.py        # WarGames module
+-- rsh_welcome.py         # Persistent welcome banner
+-- retro_os/              # Retro Serial OS core, runtime, shell, and services
|   +-- core.py            # Shell, EventBus, Session model, ModuleLoader
|   +-- runtime.py         # Runtime initialization and built-in command handlers
|   +-- host_env.py        # Host OS integration, app scanner, clipboard, sysinfo
|   +-- toolkit.py         # Calendar, conversion, contacts, files, and ZIP tools
|   +-- audio_player.py    # Shared audio playback and playlists
|   +-- menu.py            # Accordion flyout menu engine
|   +-- menu_data.py       # Shared terminal/dashboard menu catalogue
|   +-- menu_layout.py     # Screen-height-aware menu layout
|   +-- file_browser.py    # Shared host file navigation and actions
|   +-- reader.py          # Searchable reader with saved positions
|   +-- workshop.py        # File preparation and inspection tools
|   +-- session_tools.py   # Capture, diagnostics, presets, and preferences
|   +-- shortcuts.py       # User-defined command shortcuts manager
|   +-- scheduler.py       # Background periodic task scheduler
|   +-- mail_service.py    # Hub mailbox and internet email backend
|   +-- viewer.py          # Multi-format document text extraction pipeline
|   +-- news.py            # RSS news headlines
|   +-- weather_news.py    # Live weather and combined desk briefings
|   +-- help_data.py       # In-hub help system and user guide
|   +-- modules/           # Built-in OS modules (calc, games, mail, print, etc.)
+-- files/                 # File transfer storage
+-- text/                  # Text library files, README, and starter articles
+-- notes/                 # Notes storage
+-- settings/              # Central JSON storage
|   +-- defaults/          # Publishable starter templates
|   +-- local/             # Ignored personal settings and data
+-- hub_tools/             # Session captures (not committed)
+-- tests/                 # Unit tests

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

* Check that the COM port name in settings/local/hub_config.json matches your system
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

Technical Notes

See docs/README.md in the distribution or source repository for engineering
field notes on console redraws, terminal layout and cursor budgets, screen
controls and frozen scrollback, transfer-safe messages, host-control approvals,
XMODEM wire costs, and Notepad recovery. Each note links to code and tests;
the index includes reproduction commands and recorded measurements.

Release Notes

v2.7a (alpha)

* Scheduler Review: Fixed enable/disable state, quoted command chains, URL
  semicolons, schedule validation, and overlapping runs. Added schedule details
  <id> for next/last run and status. See docs/scheduler-reliability.md.
* Reader Recovery: A failed reading-position save displays a notice and keeps
  the document readable. Later pages retry saving automatically.

* JSON Hub Configuration: Removed config.py and moved serial/Telnet profiles,
  welcome text, serial inactivity defaults, and WOPR speech to validated
  settings/local/hub_config.json. Preserved the current local hardware settings;
  public defaults now contain only APPLE2 on COM1 and C64 on COM2, with no inbound
  listeners. BBS defaults are 64 structured JSON entries shared by menu and CLI.
* Host Configuration Wizard: Type config at the physical console for a
  separate menu and guided profile setup with scanned serial ports, serial framing,
  flow control, ANSI/clear behavior, width/height, timeouts, and optional Telnet.
  Review/confirm before atomic save, cancel/back navigation, conflict validation,
  and remote-input blocking protect the draft. New profiles start immediately;
  global and speech changes are saved for restart.
* First-Launch Setup: Fresh installations open configuration automatically and
  defer serial/Telnet workers until setup finishes. Edit the two starter profiles
  or add a computer, then Q starts the saved configuration. Completion is remembered
  locally; existing setups keep their normal startup. Existing-profile edits use
  the same wizard and take effect at first-setup completion or after a restart.
* Gemini Thinking Compatibility: Removed the automatic minimal reasoning
  setting that caused HTTP 400 errors on models rejecting that thinking level.
  Gemini now chooses its own thinking defaults unless explicitly configured.
  Added a simulated provider rejection to the SDK request test and coverage for
  omitted, explicit, and default reasoning settings.
* AI Provider Choice: Added Google Gemini and local Ollama alongside OpenAI.
  Local models need no API key or token billing; Gemini supports a hosted
  free-tier setup subject to provider limits. Existing OpenAI settings work.
  Added provider/model headers, host configuration and environment overrides,
  isolated per-conversation clients, configurable response budgets, and
  provider-specific request options. Includes setup instructions, error guidance,
  and SDK-level tests. Errors never switch to a paid service automatically.
* Resilient Note Search: An unreadable or disappearing note no longer aborts
  content search. Continue searching other notes and report the skipped count.
  Filename matches require no content read, and the 1 MiB content-search limit
  remains in place. Regression coverage exercises metadata and read failures,
  successful retries, filename-only matches, and oversized files.
* Notepad Save Recovery: Clean up temporary files after failed writes or file
  replacements, including partially written saves. Keep the original note and
  unsaved editor contents intact so save can be retried without reopening the
  note. Regression coverage injects both a disk-write failure and a replacement
  permission error, verifies cleanup and unchanged source bytes, then retries
  successfully.
* Notepad Edit Recovery: Fixed editing notes that were deleted, cannot be read,
  or contain invalid UTF-8. Failed reads leave the menu usable without entering
  a partially initialized editor or changing the source file. Merged from the
  experiment branch in PR #1:
  https://github.com/TheDeepLogic/RetroSerialHub/pull/1
* Engineering Field Notes: Added six technical writeups covering terminal layout
  budgets, screen controls and frozen scrollback, transfer-safe message delivery,
  host-control approval boundaries, XMODEM wire costs, and Notepad recovery.
  Includes a repeatable assertion-based measurement harness and recorded results.
  See docs/README.md for the technical documentation index.
* Development Version: Updated the displayed application version, bundled guide,
  and web-viewer user agent to 2.7a (alpha). The v2.6 notes remain the release record.

v2.6

* Adaptive Console Layout: Reworked the dashboard around a bordered 80-column
  host pane, serial/network status, and an active-only activity monitor.
  Narrow windows stack the panels; taller windows move status and connections
  across the top. Approvals remain visible, errors sit below activity, and
  overflow counts identify hidden items.
* Direct Host Input: The host opens the standard numbered menu on startup and
  edits directly at the active hub prompt. Main-menu status and ATM/messages
  hints sit above separated console controls near the bottom. Screen clears,
  cursor movement, and erase commands update the host pane correctly.
* Console Themes: Added fourteen saved DOS Shell and vintage-system schemes,
  including Ocean, Apple IIGS, Commodore, TI-99/4A, Windows 95, and Windows
  3.1. Background-off supports terminal transparency while retaining title and
  highlight colors; colors-off uses terminal defaults. Colored bands extend
  across the pane, including the input separator.
* Stable Scrollback: PgUp holds the text being read while output continues,
  with a new-line counter and End to resume live output. Resizing, incoming
  screen clears, and live-history eviction preserve the held view.
* Efficient Redrawing: Only changed rows are repainted; unchanged refreshes
  emit nothing. Resizes and appearance changes still trigger a full repaint.
  See redraw measurements (docs/console-redraw-measurements.md) for measured
  terminal-traffic reductions.
* Terminal Messages: Messages and received text files announce themselves
  immediately, including at idle prompts, with notices deferred during file
  transfers. M=Messages opens a session inbox with unread counts, paging, and
  read history, separate from email. MESSAGES and MSGS also work at the menu
  or CLI.
* Approved Host Control: Serial and Telnet terminals can submit HOST <text> to
  the host session. First use requires approval typed at the physical console,
  remembered per source IP or physical serial port in a separate allowlist.
  Forwarded commands cannot approve host-control requests.
* CP/M Exploration: Expanded WOPR's IMSAI shell with session-local A/B disks,
  discoverable documentation, directory filters, text viewing,
  copy/rename/erase commands, disk statistics, simulated memory images, and
  native screen clearing. Communications programs are discovered by exploring
  the disk.
* Console Help: Added host help for dashboard controls while HELP continues to
  reach the hub. Retired monitor-collapse behavior and refreshed the README,
  in-menu guide, hotkeys, and regression coverage.

v2.5

* Star Trek Guide: Star Trek now shows a quick-start command guide on launch,
  with examples, course directions, combat, and resupply instructions;
  terminal output pages to the configured screen size.
* Settings Storage: Consolidated JSON settings and application data under
  settings/: publishable starter defaults are separate from ignored personal
  files, with automatic migration from earlier locations and preservation of
  existing bookmarks.
* Workshop Tools: Added Workshop as category 6 with disk-image inspection, hex
  viewing, checksums, text conversion, BASIC listing preparation, split/join,
  hex/Base64 encoding, and file comparison. System moves to category 7;
  categories retain at most eight A-H entries.
* Host File Browsing: Unified host-file browsing across file tools, with
  drives/root, parent folders, direct paths, favorites, filters, marking, and
  batch copy/move. Audio can select files anywhere the host can access. Added
  Find Files under Files & Media H.
* Reading and Notes: Added searchable, resumable reading and bookmarks, plus
  note editing, renaming, exporting, and content search.
* Audio Player: Simplified the audio player menu; added queue editing,
  repeat/shuffle, named radio stations, and a remembered music folder.
* Capture and Diagnostics: Added Session Capture under Communications G and
  Serial Diagnostics under Host Connectivity H, including transfer progress
  and host cancellation.
* Transfer Reliability: Improved XMODEM/YMODEM negotiation, retries,
  fragmented reads, and completion handling. Receives preserve binary padding,
  avoid overwriting files, and publish completed files only after success.
* Session Activity: Added serial inactivity timeouts and cleared stale menu
  selections when a port becomes active again. Queued notifications keep
  messages out of prompts and transfer streams, with optional quiet mode.
* Machine Preferences: Added saved machine preferences and host application
  launch presets. Terminal height defaults to 24 rows per profile; menus keep
  the footer stable, clear submenus, and reserve readable spacing in 40- and
  80-column layouts.
* Host Dashboard: Updated the host dashboard with Unicode borders and ASCII
  fallback, a single color-coded Connections list, and an activity monitor
  that collapses during host interaction to give output more room. clear
  restores the expanded layout unless monitor collapse pins it compact;
  monitor auto restores automatic behavior.
* WOPR Interaction: Enhanced the WOPR/Joshua interaction while retaining the
  IMSAI/CP/M dialer, with movie-style displays, gentler pacing, and optional
  synchronized host speech. Open it from Communications H or wargames.

v2.4

* AI Model Compatibility: Replaced the retired GPT-3.5 Turbo default with
  GPT-5.6 Terra, updated completion parameters, and added configurable model
  and reasoning settings with actionable errors when a model is unavailable.
* Interactive Host Console: The host keyboard now runs the hub's CLI and
  interactive menus. Added host-to-terminal messaging and replies to Host,
  scrollable command output, command history, and masked FTP password input.
* Telnet Source Approval: Unknown source IPs wait for allow <request #> or
  deny <request #> at the host keyboard. Approvals persist in a manually
  editable JSON allowlist. Missing/invalid policies and failed saves never
  grant access; pending requests expire and the queue is bounded. Serial
  connections are exempt.
* Six New Tools: Added Calendar with persistent reminders, Unit Converter,
  Address Book with mail/BBS shortcuts, File Manager, ZIP Archive Browser, and
  Audio Player with host playback controls, M3U playlists, and optional
  internet radio through FFmpeg.
* More Terminal Games: Added Word Guess and a Star Trek adaptation inspired by
  the supplied Apple II BASIC listing, with quadrant exploration, scans,
  phasers, photon torpedoes, shields, starbase resupply, and a mission
  deadline.
* Host Settings: Added a host preferences menu with a saved keyboard bridge
  exit binding, defaulting to Ctrl+X. Escape is forwarded to the host
  application.
* Menus and Status Formatting: Reordered Files & Media and Accessories,
  shortened Calendar and Weather & News labels, and placed Disconnect last in
  System. Active and waiting profile rows share field order and indentation;
  active rows stay green under a gray divider without redundant terminal text.
* Stable Console Redrawing: Fixed cursor drift after host input and approval
  changes. Redraws use fixed screen positions, fit the viewport, and retain
  the host prompt when the full dashboard will not fit.
* Session Reliability: Kept game, Logo, and mail context tied to the correct
  terminal, serialized module initialization, and shared one scheduler per
  task file so adding a host session does not duplicate scheduled jobs.
* Documentation and Tests: Updated the README, in-hub help, text-library
  guide, and regression coverage. Private allowlists and saved tool data
  remain local to the installation.

v2.3

* Terminal Logo Programming: Added the LOGO accessory and CLI launcher, with
  movement, pen controls, repeat groups using brackets or parentheses,
  variables, arithmetic, user procedures, terminal turtle status, and optional
  host graphics.
* Connected Terminal Tools: Added a Communications menu for listing active
  terminals, messaging a selected terminal, and delivering a text file over
  ASCII; the CLI also supports terminals and msg to <terminal> <text>.
* Expanded Terminal Games: Added Lunar Lander, Hunt the Wumpus, Blackjack, and
  Mastermind to Games. WarGames remains available through the CLI. Game
  prompts now show the single-letter keys that activate each action.
* Menu and Notes Updates: Moved Host Printing to Host Connectivity, renamed
  the Notes menu item to Notepad, added host clipboard capture/copy workflows,
  corrected dashboard section activity numbering, and normalized menu spacing.
* Documentation: Updated both user guides and incremented the application
  version to v2.3.

v2.2

* Scheduler Commands: Added resilient command chaining, dynamic command
  discovery, broadcast guidance, and URL tasks. Current syntax and examples
  are maintained in docs/scheduler-reliability.md.
* Release Version: Incremented application version to v2.2.

v2.1

* Document Viewer Windows Path Resolution: Fixed an issue where Windows
  backslashes were stripped during shell argument parsing (causing duplicated
  or corrupted paths such as OneDriveSoftware...), allowing documents, images,
  and local files to load seamlessly from local drives.
* Interactive News Article Reader: Added interactive headline article
  selection to Weather & News, allowing vintage terminals to type an article
  number directly to read the complete summary and download full web article
  contents (F / news <num> full).
* Dedicated News Task Scheduler Option: Added news and weather command
  scheduling to the background task scheduler (schedule add <name> <minutes> news
  ...), listing them under schedule modules.
* Console Pseudo Interface & Connected User Highlighting: Enhanced the live
  host console dashboard with an interactive pseudo interface layout
  displaying connected client activity and highlighting active menu items in
  real time.
* Updated Copyright Notices: Updated all system banners, headers, and
  documentation to 2025-2026.
* Release Version: Incremented application version to v2.1.

v2.0

* Retro Serial OS Runtime: Full host-side operating system extension with an
  interactive command prompt (cli> / OS), hot-reloadable module system, event
  bus publish/subscribe architecture, multi-client session tracking, and
  programmable keyboard bridge shortcut profiles.
* Accordion Main Menu & Custom Shortcuts: Fast categorized accordion flyout
  menu layout optimized for 40- and 80-column terminals, complete with a
  user-defined command shortcut macro system with automatic flyout.
* Host Terminal & Quick Shell: Bidirectional streaming console session to the
  host OS (cmd.exe, powershell, or unix shells) with configurable local echo,
  newline translation, and interactive parameters.
* Real-Time Host System Monitor: Live CPU load measurement, memory, disk, and
  uptime monitor with continuous screen clearing, pause/resume, and adjustable
  refresh rates (top / sysinfo live).
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
* Background Task Scheduler: Automated periodic task execution with terminal
  broadcast notifications and cron-like intervals. Weather and news commands
  can be scheduled directly (for example, weather Austin or news npr 6) and
  are listed by schedule modules.
* Terminal Hardware Settings & In-Hub Help: Caps-Only mode for vintage
  uppercase-only ROMs (Apple II Plus, Commodore PET, TRS-80 Model I), serial
  character pacing delays (1-3ms), and 9 comprehensive in-hub help guide
  topics.
* Release Version: Incremented application version to v2.0.

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
* Set saved terminal-column defaults to match the bundled machine profiles and
  reordered the System menu so option 12 switches column width and option 13
  opens Welcome Banner.
* Included the recent menu-routing and Notes workflow fixes, incoming
  Telnet-compatible Wi-Fi modem documentation, Keyboard Bridge feature
  listing, and Aaron Smith copyright notice.
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
  reorganized and renumbered the menu sections, and adapted browser pages and
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
