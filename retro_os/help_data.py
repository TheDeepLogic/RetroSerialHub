"""Help topics and user guide for Retro Serial Hub."""

from __future__ import annotations

from typing import Dict, List, Tuple


HELP_TOPICS: List[Tuple[str, str, str]] = [
    (
        "1",
        "What is Retro Serial Hub?",
        """WHAT IS RETRO SERIAL HUB?
=========================
Retro Serial Hub is a modern host-side operating system and gateway that
transforms vintage computers into capable modern workstation companions.

Whether you connect an Apple II, Commodore 64, TRS-80, IBM PC, Atari,
or any ASCII/ANSI terminal over an RS-232 serial cable or Telnet, the hub
bridges the gap between retro hardware and modern computing:

* Terminal Shell & OS: Interactive command prompt (cli>) with hot-reloadable
  modules, background task scheduling, and scripting.
* Host Connectivity: Launch modern PC apps from your retro keyboard, stream
  interactive console programs, bridge serial COM ports, and map keystrokes.
* Ambient Desk Companion: Live system monitor (CPU/RAM/disk/uptime),
  live weather forecasts, RSS news headlines, and daily morning briefings.
* Host Clipboard & Media Control: Read/write the host PC clipboard and control
  music playback and volume straight from vintage keyboards.
* File Transfers & Modern Document Viewing: Fast XMODEM/YMODEM/ASCII file
  transfers, plus automatic text extraction and pagination for PDF, DOCX,
  XLSX, CSV, Markdown, and HTML files.
* Communications & Mail: Bulletin board directory, telnet terminal, web
  browser, FTP client, and integrated inter-terminal electronic mail.
* Retro Games: Native text-mode Minesweeper, Solitaire, Hunt the Wumpus, Lunar Lander, Blackjack, and Mastermind, plus the WarGames W.O.P.R. CLI simulation.
""",
    ),
    (
        "2",
        "Navigation & Menu Guide",
        """MAIN MENU & ACCORDION NAVIGATION
=================================
The main menu uses an accordion flyout layout designed for vintage 40- and
80-column screens:

* Sections (0 to 6):
  [0] Shortcuts: Quick user-defined command macros with custom arguments.
  [1] Communications: BBS, Telnet, Web Browser, FTP, Electronic Mail, Connected Terminals.
  [2] Host Connectivity: Host Applications, Keyboard Bridge, Terminal Prompt, Host Printing.
  [3] Files & Media: File Transfers, Document Viewer, Text Library, ASCII Art.
  [4] Games: Dedicated retro games (Minesweeper, Solitaire, Wumpus, Lunar Lander, Blackjack, Mastermind).
  [5] Accessories: Notepad, Calculator, Live Weather & News, AI, LOGO.
  [6] System: Command Shell (CLI), Task Scheduler, Hardware Settings, Help.

* Navigation Keys:
  - Enter a section number (0-6) or name (e.g. 'GAMES' or 'SYS') to expand it.
  - Enter an item letter (A-G) to launch the option in the active section.
  - Communications > Connected Terminals lists active links; select one to message it or send a text file.
  - In Notepad, P saves the host clipboard as a note and C<number> copies a note to the clipboard.
  - In Accessories > LOGO, enter commands such as REPEAT 4 (FD 80 RT 90). Parentheses or square brackets group commands.
  - In Shortcuts: press '+' to add a shortcut, or '-' to remove one.
  - At any prompt: type 'ATM' to return to the Main Menu immediately.
  - While connected to a BBS or Telnet host: type 'ATH' to hang up.
  - Paged text (--More--): press Space or Enter to advance, or 'Q' to quit.
""",
    ),
    (
        "3",
        "Command Shell (CLI) Guide",
        """COMMAND SHELL (CLI) GUIDE
=========================
Type 'CLI' or 'OS' at the main menu to enter the interactive command prompt:

  cli> help                      List all registered shell commands
  cli> apps                      List installed host PC applications
  cli> launch <app> [-k|-b]      Launch application (with keyboard bridge or bg)
  cli> terminal [cmd|ps|bash]    Open bidirectional host command prompt
  cli> top (or sysinfo live)     Real-time host system monitor with clear screen
  cli> sysinfo [-s]              Display host CPU, RAM, disk, and uptime snapshot
  cli> clip [text]               View or copy text to host clipboard
  cli> terminals                 List connected serial/Telnet terminals
  cli> msg to <terminal> <text>  Send a message to one terminal
  cli> media play|pause|next     Control host media playback
  cli> vol up|down|mute          Control host system volume
  cli> weather [location]        Fetch live ASCII weather from wttr.in
  cli> news [src] | news <num>   Read news headlines or view article story
  cli> briefing [location]       Generate complete morning desk briefing
  cli> logo                      Start the terminal Logo programming prompt
  cli> view <file|url>           Extract and paginate modern docs (PDF/DOCX/XLS)
  cli> fetch <url> [dest]        Download internet file to hub storage
  cli> xsend/ysend/asend <file>  Direct file transfer to retro computer
  cli> xrecv <dest_file>         Receive file via XMODEM from retro computer
  cli> mail [inbox|read|send]    Read and send integrated hub or internet email
  cli> games wumpus new          Start Hunt the Wumpus
  cli> calc <expression>         Evaluate mathematical expressions
  cli> schedule list|add|run     Manage automated periodic background tasks
  cli> caps on|off               Toggle uppercase-only mode for vintage ROMs
  cli> pace <milliseconds>       Adjust inter-character pacing delay
  cli> exit                      Return to main menu
""",
    ),
    (
        "4",
        "Host Connectivity & Applications",
        """HOST CONNECTIVITY & BRIDGING
=============================
Retro Serial Hub lets your vintage terminal interact directly with the modern
host computer:

* Host Applications:
  Scans Start Menu, Program Files, and system paths. You can list apps with
  pagination and filter by letter or keyword.

* Application Launch Modes:
  - Console Terminal: Streams input/output between the retro terminal and
    command-line tools, compilers, or interpreters running on the host.
  - Keyboard Bridge: Launches GUI applications on the host while your vintage
    computer acts as the keyboard! Keystrokes are translated through
    customizable key profiles (e.g. mapping Apple II keys to Windows/Ctrl keys).
  - Background Mode: Starts programs silently on the host without interaction.

* Host Terminal / Prompt:
  Quick-launch an interactive Windows Command Prompt (cmd.exe), PowerShell,
  or Unix Bash shell streamed live to your serial terminal.

* System Monitor & Media Controls:
  Live updating host hardware vitals (CPU load %, memory usage, disk, uptime)
  with screen clearing on each update cycle and adjustable refresh rates:
  - [Q]: Exit monitor and return to menu
  - [C]: Toggle clear screen before each refresh
  - [+/-]: Adjust refresh rate (1 to 10 seconds)
  - [S]: Pause/freeze live updating snapshot
  - [Space]: Refresh immediately
  Also provides quick clipboard sharing and Spotify/media player controls.
""",
    ),
    (
        "5",
        "File Transfers & Document Viewer",
        """FILE TRANSFERS & DOCUMENT VIEWER
=================================
Modern file formats cannot be parsed natively by 8-bit computers. Retro Serial
Hub bridges this with a real-time extraction pipeline:

* Supported Viewer Formats:
  - PDF: Extracts plain text and wraps cleanly for 40- or 80-column screens.
  - Word (.docx): Extracts text, paragraphs, and headings.
  - Excel (.xlsx / .csv): Formats tabular data into clean ASCII tables.
  - Web Pages (HTML / URLs): Strips markup and downloads clean reading text.
  - Plain Text & Markdown (.txt / .md): Formats and paginates.

* Direct File Transfers:
  - XMODEM (128-byte blocks with checksum)
  - YMODEM (1024-byte blocks with batch headers)
  - ASCII Raw Stream
  Use menu option [Files & Media] -> [A] File Transfers or direct CLI commands
  (xsend, ysend, asend, xrecv).
""",
    ),
    (
        "6",
        "Electronic Mail (Hub & Internet)",
        """ELECTRONIC MAIL GUIDE
=====================
Retro Serial Hub provides two complementary electronic mail systems:

1. Integrated Hub Mailbox:
   - Designed specifically for multi-computer setups and local networks!
   - Messages are stored centrally on the hub.
   - Senders are automatically identified by machine name and connection type
     (e.g. 'APPLE2 [Serial COM2]' or 'Remote Telnet [192.168.1.50]').
   - Any connected terminal or host user can read, compose, and delete mail.
   - Ideal for leaving notes, file transfer notices, or intra-office messages.

2. Internet Email (IMAP & SMTP):
   - Connects directly to modern mail providers (Gmail, Outlook, Yahoo, etc.).
   - IMAP Inbox: Reads real email headers and extracts plain-text bodies.
   - SMTP Sending: Sends standard internet email messages.
   - Host GUI Setup: Pop up an authentication window on your host desktop
     to configure credentials, or configure them directly in the terminal.
   - Mailto: Quick shortcut to trigger the host PC's default desktop mail app.

Toggle between Hub Mail and Internet Mail at any time inside the Mail menu!
""",
    ),
    (
        "7",
        "Terminal Hardware Settings",
        """TERMINAL HARDWARE SETTINGS
==========================
Vintage UARTs and early video hardware often require special tuning:

* Screen Width (40 vs 80 Columns):
  Toggle between 40-column (Apple II, C64, TRS-80) and 80-column layouts.
  Preferences are saved per serial port profile in terminal_columns.json.

* Caps-Only Mode (Uppercase Only):
  Early machines (Apple II Plus, Commodore PET 2001, TRS-80 Model I) lack
  lowercase character generator ROMs. Lowercase letters display as flashing
  inverse symbols or corrupted characters. Caps-Only mode automatically
  maps all outgoing text to ASCII uppercase.

* Serial Pacing Delay:
  Vintage computers with software bit-banging serial routines or 6551 ACIAs
  lack FIFO buffers and drop bytes at high baud rates. Pacing adds a tiny
  programmable delay (e.g. 1-3 ms per character) to ensure rock-solid
  reception without dropped characters.

* ANSI Translation:
  Strips color codes and translates VT100 cursor controls for monochrome
  or non-ANSI terminals.
""",
    ),
    (
        "8",
        "Retro Games",
        """RETRO GAMES GUIDE
=================
All games are fully playable on 40- and 80-column vintage displays:

* Minesweeper:
  - Command: 'r row col' to reveal a cell, 'f row col' to toggle a flag.
  - 'new' to start a fresh board, 'q' to quit.
  - 1-based indexing for rows and columns.

* Solitaire (Klondike):
  - Standard 7-column Klondike with stock and waste piles.
  - Commands: 'd' to draw from stock, 'move <src> <dst>' to move cards,
    'f' for automatic foundation moves.

* Hunt the Wumpus:
  - Start with 'games wumpus new'. The cave has 20 numbered rooms.
  - 'games wumpus' shows your room, connected tunnels, and nearby danger clues.
  - Move with 'M <room>'; shoot with 'S <room>[,<room>,<room>]'. Arrows travel at most 3 rooms.
  - Use N for a new hunt and Q to quit.
  - Avoid bottomless pits, bats, and the Wumpus. 'games wumpus quit' ends a hunt.

* Lunar Lander:
  - Start with 'games lander new'. Each turn, enter 'B <0-4>' to burn.
  - A higher burn slows the descent but consumes the same number of fuel units.
  - Land at 2 m/s or less. Use I for instruments, N for a new flight, or Q to quit.

* Blackjack:
  - Start a hand with 'games blackjack new'. Use H to hit, S to stand, N for a new hand, or Q to quit.
  - Aces count as 1 or 11; face cards count as 10.

* Mastermind:
  - Start with 'games mastermind new'. Enter 'G <four digits>' to guess four different digits from 1-6.
  - Each clue reports exact positions and matching digits in the wrong position.
  - You have 10 guesses to crack the code. Use N for a new puzzle or Q to quit.

* WarGames (W.O.P.R.):
  - Launch from the CLI with 'WARGAMES'. The game is no longer on the Games menu.
""",
    ),
    (
        "9",
        "Quick Reference & Hotkeys",
        """QUICK REFERENCE & HOTKEYS
=========================
* Global Commands:
  - ATM: Return immediately to the Main Menu from any module or BBS.
  - ATH: Hang up / disconnect an active BBS or Telnet session.
  - CLI: Open the interactive command shell.
  - HELP or ?: Open this Help & User Guide.

* Main Menu Hotkeys:
  - 0-6: Switch accordion section.
  - A-G: Activate item in current section.
  - +: Add a user shortcut (in Shortcuts section).
  - -: Delete a user shortcut (in Shortcuts section).

* Pager Navigation:
  - Space / Enter: Advance one screen or line.
  - Q: Quit pager and return to prompt.
""",
    ),
]


def get_help_topics() -> List[Tuple[str, str]]:
    """Return list of (key, title) tuples."""
    return [(key, title) for key, title, _ in HELP_TOPICS]


def get_topic_content(selector: str) -> str:
    """Return the content for a topic by number (1-9) or keyword."""
    s = selector.strip().lower()
    for key, title, content in HELP_TOPICS:
        if s == key or s in title.lower():
            return content
    return "Help topic not found. Enter a topic number (1-9)."
