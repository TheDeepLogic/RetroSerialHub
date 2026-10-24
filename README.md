![Retro Serial Hub](images/retroserialhub_banner.jpg)

# Retro Serial Hub

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
- **Console Pseudo Interface & Live User Activity**: Host console dashboard displays an interactive pseudo-interface view highlighting the menu items connected retro users are currently browsing in real time
- **Real-Time Host System Monitor**: Live CPU load measurement, RAM, disk, and uptime metrics with automatic screen clearing and interactive controls (`top` / `sysinfo live`)
- **Multi-Format Document Viewer**: Text extraction and pagination pipeline for PDF, Word (.docx), Excel (.xlsx / .csv), Markdown, HTML, and web URLs with native Windows path handling
- **Direct File Transfers**: XMODEM, YMODEM, and ASCII transfers callable directly from the shell or menu (`xsend`, `ysend`, `asend`, `xrecv`)
- **Electronic Mail (Hub & Internet)**: Central inter-terminal hub mailbox with auto-detected sender identity, plus IMAP/SMTP internet email and desktop configuration GUI
- **Connected Terminal Messaging**: List active serial/Telnet terminals, send a direct message, or deliver a text file from the Communications menu
- **Terminal Messages**: List connected terminals and send a message to one machine or broadcast to all connected screens
- **Dedicated Retro Games**: Native text-mode Minesweeper, Solitaire (Klondike), Hunt the Wumpus, Lunar Lander, Blackjack, Mastermind, and the WarGames (W.O.P.R.) CLI simulation
- **Ambient Desk Companion**: Live ASCII weather forecasts (`wttr.in`), RSS news feeds (NPR, Hacker News, BBC), automated morning briefings (`briefing`), and interactive article reader (`news <num>`)
- **Background Task Scheduler**: Automated periodic task execution with broadcast notifications, cron-like intervals, and multi-command chaining (e.g. `news : weather Austin : broadcast Morning briefing complete`)
- **LOGO Programming**: A line-oriented terminal Logo interpreter with repeat loops, variables, procedures, detailed turtle status, and optional host-side turtle graphics
- **Terminal Hardware Settings**: Screen width (40/80 cols), Caps-Only mode for vintage uppercase-only ROMs (Apple II Plus, PET, TRS-80 Model I), and serial character pacing delays
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
- **AI Assistant**: Optional ChatGPT-powered assistant accessible from vintage terminals
- **Hot-Reload Modules**: Edit feature modules without restarting the hub
- **ANSI Support**: Automatic detection and handling of ANSI escape codes for compatible terminals

## Requirements

- Python 3.8 or higher
- Dependencies listed in `requirements.txt`
- USB-to-Serial adapters or RS-232 ports for connecting vintage computers
- Optional: OpenAI API key for AI Assistant feature

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

Retro Serial Hub features an accordion flyout main menu organized into 6 purposeful pillars optimized for 40- and 80-column retro terminals:
- **Sections (0–6)**: Only the selected category is expanded, showing its available actions (`[A]–[G]`, `[+]`, `[-]`), while other categories remain collapsed as headers:
  - `[0] Shortcuts`: User-defined quick shortcuts to commands and tools with custom arguments (e.g., weather feeds, favorite BBS connections, games, calculations). If any shortcuts are populated, this section automatically flies out upon opening the main menu.
  - `[1] Communications`: Bulletin Boards, Telnet Terminal, Web Browser, FTP Client, Electronic Mail, Connected Terminals (messages and file delivery)
  - `[2] Host Connectivity`: Host Applications, Launch Host App, Keyboard Bridge, COM Port Bridge, Host Terminal / Prompt (cmd/powershell/bash), System Monitor & Media, Host Printing
  - `[3] Files & Media`: File Transfers (XMODEM/YMODEM/ASCII), Document Viewer, Text Library, ASCII Image Viewer
  - `[4] Games`: Dedicated Retro Games (Minesweeper, Solitaire, Hunt the Wumpus, Lunar Lander, Blackjack, Mastermind)
  - `[5] Accessories`: Notepad, Calculator, Live Weather & News, AI Assistant, LOGO
  - `[6] System`: Command Shell (CLI), Task Scheduler, Terminal Hardware Settings, Keyboard Profiles, Help & User Guide, Welcome Banner, Disconnect
- **Navigation**: Enter `0`–`6` (or section names such as `GAMES`, `CONNECTIVITY`, `SYS`) to expand that section. Enter `A`–`G`, `+`, or `-` to run the item within the currently active section.
- **Shortcuts Management**: In the Shortcuts section, press `+` to add a shortcut with custom arguments (saved to `user_shortcuts.json`), or `-` to remove an existing shortcut. You can also manage shortcuts from the CLI via `shortcut add <name> <cmd>`, `shortcut list`, `shortcut run <id>`, or `shortcut del <id>`.
- **Help & User Guide**: Comprehensive multi-topic documentation is accessible directly inside the hub by pressing `HELP`, `H`, or `?` at the main menu, selecting `[E]` under System, or typing `help <topic>` in the CLI.
- **Direct Commands**: You can enter commands directly from the main menu prompt, such as `CLI` (or `OS`), `HELP` (or `?`), `SYSINFO`, `CLIP`, `VOL`, `MEDIA`, `WEATHER`, `NEWS`, `BRIEFING`, `SHORTCUT`, `APPS`, `VIEW`, `FETCH`, `LAUNCH`, `TERMINAL`, `CALC`, `LOGO`, `MAIL`, `MAILTO`, `MINES`, `SOLITAIRE`, `WUMPUS`, `WARGAMES`, `PRINT`, `KB`, `SCHEDULE`, `CAPS`, `PACE`, or `ATM` to return/refresh.

### Command Shell (CLI)

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
- `kb profile <name>` and `kb map <key> <action>`: Selects or configures shortcut mappings in `keyboard_profiles.json` (e.g., mapping `CTRL+W` to `WIN` or `CTRL+M` to `WIN+R`).
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
- **Lunar Lander** (`games lander`): Turn-based descent challenge controlled with numeric engine burns.
- **Hunt the Wumpus** (`games wumpus` in the CLI, or Games section `[D]`): Cave exploration with numbered rooms, danger clues, bats, pits, and three-room arrow shots, designed for line-oriented terminals.
- **Blackjack** (`games blackjack`): Play hit or stand against a dealer with standard ace scoring.
- **Mastermind** (`games mastermind`): Crack a four digit code using exact and misplaced clues in up to ten guesses.

### Built-in Help & User Guide

An interactive multi-topic guide is accessible anywhere by typing `HELP`, `H`, or `?` at the main menu or selecting `[E]` under System. Topics cover hub capabilities, navigation, shell commands, hardware settings, games, and emergency hotkeys with built-in `--More--` paging.

## Configuration

All configuration is centralized in `config.py`. This is the first file you should edit after installation.

### Serial Port Configuration

Edit the `SERIAL_CONFIGS` dictionary in `config.py` to match your hardware setup. Each entry represents one vintage computer or device:

```python
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
        "columns": 80                    # 40- or 80-column terminal layout
    },
    # Add more computers as needed...
}
```

Set `columns` independently for each machine profile to `40` or `80`. This is
the profile's default width; the main-menu **System → Columns** option can
switch and save that profile's preference. The saved selection is stored in
`terminal_columns.json` and takes precedence over `config.py`. At 40 columns,
menus use a compact layout, browser pages wrap to the configured width, long
labels are shortened to fit, and ANSI translation uses the configured terminal
width. The included defaults use 80 columns for APPLE2, IBM, and TRS80 profiles,
and 40 columns for C64; profiles without this setting default to 80.

Common baud rates for vintage systems:
- Apple II with Super Serial Card: 300, 1200, 2400, 9600, 19200, or 115200
- Commodore 64: 300, 1200, 2400
- IBM PC/XT/AT: 300, 1200, 2400, 9600
- TRS-80: 300, 1200, 2400, 9600

#### Optional translation for non-ANSI terminals

ANSI translation is useful with any terminal or display that cannot interpret
the control sequences sent by a remote system. It is configured independently
in each `SERIAL_CONFIGS` entry and affects **incoming BBS/Telnet data** on that
serial profile. It does not affect the serial-to-serial COM Port Bridge or
other configured ports. Hub menu screens use `ansi` for native ANSI
clear/home controls; when ANSI translation is enabled, they use
`ansi_clear_sequence` to clear the terminal.

```python
"RETRO_TERMINAL": {
    # Existing serial settings go here...
    "ansi": False,
    "translate_ansi": True,
    "ansi_clear_sequence": b"\x0c",
    "ansi_home_clears_screen": False,
}
```

- `translate_ansi` enables the lossy ANSI/VT100-to-text translator. It strips
  color and unsupported control sequences, approximates common CP437
  line-drawing characters, and linearizes supported cursor positioning. It is
  not a complete terminal emulator; applications using complex screen
  addressing or terminal queries may not display correctly.
- `ansi_clear_sequence` is the byte sequence sent to the terminal for a
  supported erase-in-display/reset request, incoming form-feed (`0x0C`), or a
  Hub menu screen clear when `translate_ansi` is enabled.
  Set this to the clear-screen control sequence expected by the receiving
  terminal or its software. The default when omitted is form feed
  (`b"\x0c"`).
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

The initial BBS directory is seeded from three synchronized lists in `config.py`:

- `BBSS`: Display names for each BBS
- `IPS`: Hostnames or IP addresses
- `PORTS`: TCP port numbers

The first time the hub starts, it uses those lists as its directory. Changes
made with **Bulletin Boards → M=Manage directory** are saved to
`bbs_directory.json` and include the original entries. The saved directory then
takes precedence over `config.py`, so entries can be added, edited, and deleted
without keeping three lists synchronized. Delete `bbs_directory.json` while
the hub is stopped to restore the defaults from `config.py`.

In the **Telnet** option, enter a hostname/IP and port for a direct TCP terminal
connection. Choose whether to save that destination in Telnet bookmarks, add it
to the Bulletin Boards directory, or connect without saving. Telnet bookmarks
are stored separately in `telnet_bookmarks.json`; select a saved destination by
number or use `D` to delete it. Both connection types support `ATH` to hang up
and `ATM` to return to the main menu. Incoming data uses the same configured
ANSI translation and screen-clear behavior.

### Inbound Telnet-Compatible Server (Optional)

Retro Serial Hub can also accept incoming TCP terminal connections. Add a
`TELNET_SERVER_CONFIGS` entry in `config.py` for each machine profile you want
to expose, using a distinct port for each profile:

```python
TELNET_SERVER_CONFIGS = {
    "APPLE2": {"host": "0.0.0.0", "port": 6400},
    "IBM": {"host": "0.0.0.0", "port": 6401},
}
```

The keys must match entries in `SERIAL_CONFIGS`. Set `host` to `0.0.0.0` to
accept connections from other devices on the LAN, or `127.0.0.1` for local
connections only. Start the hub, then connect a TCP terminal or Wi-Fi modem to
the hub computer's IP address and the configured port (for example,
`192.168.1.20:6400`). The selected profile controls the menu's ANSI behavior;
the server works even if that profile's serial port is not connected.
When a listener starts, the hub prints detected LAN IPv4 address(es) and ports
to use for connecting.

These sessions are unauthenticated and unencrypted. Keep the server disabled
unless needed, restrict access with your firewall, and do not forward these
ports from the Internet. The listener is disabled by default when
`TELNET_SERVER_CONFIGS` is empty.

### AI Assistant Configuration (Optional)

To enable the AI Assistant feature:

1. Create `ai_config.json` in the project directory:
   ```json
   {
       "api_key": "your-openai-api-key-here"
   }
   ```

2. Or set the `OPENAI_API_KEY` environment variable

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
3. Configure the terminal to match the settings in `config.py` (baud rate, data bits, parity, stop bits)
4. Press Enter to see the main menu. Type `ATM` at any time to return to it.

### Main Menu

The main menu features an interactive accordion flyout layout designed for vintage 40- and 80-column terminals:

- **[0] Shortcuts**: User-defined command macros with custom arguments. Automatically flies out when populated. Press `+` to add a shortcut or `-` to remove one.
- **[1] Communications**: `A` Bulletin Boards, `B` Telnet, `C` Web Browser, `D` FTP, `E` Electronic Mail (Hub & Internet), and `F` Connected Terminals (list, message, or send a text file).
- **[2] Host Connectivity**: `A` Host Applications, `B` Launch with Keyboard Bridge, `C` Keyboard Bridge Profiles, `D` Serial COM Port Bridge, `E` Host Terminal / Prompt (`cmd.exe`/`powershell`/unix shell), `F` System Monitor & Media Controls, and `G` Host Printing.
- **[3] Files & Media**: `A` File Transfers (XMODEM, YMODEM, ASCII), `B` Document Viewer (PDF, DOCX, XLSX, CSV, Markdown, Web), `C` Text Library, and `D` ASCII Image Viewer.
- **[4] Games**: Dedicated retro text games: `A` Minesweeper, `B` Solitaire (Klondike), `C` Lunar Lander, `D` Hunt the Wumpus, `E` Blackjack, and `F` Mastermind. WarGames remains available through the `WARGAMES` CLI command.
- **[5] Accessories**: `A` Notepad, `B` Calculator, `C` Live Weather & News Briefings, `D` AI Assistant, and `E` LOGO. Logo accepts commands in the terminal and reports turtle position and heading after drawing; when Tkinter is available, it also opens a host-side turtle window.
- **[6] System**: `A` Command Shell (`cli>` / `OS`), `B` Background Task Scheduler, `C` Terminal Hardware Settings (40/80 cols, Caps-Only, Serial Pacing, ANSI), `D` Welcome Banner, and `E` Help & User Guide (`HELP` or `?`). Remote TCP clients also see `F` Disconnect.

Enter a section number (`0`-`6`) or name (`GAMES`, `SYS`, `HOST`, etc.) to expand it, then enter the letter (`A`-`G`) to activate an option. You can also switch between the accordion flyout and the legacy numbered menu layout.

### LOGO

Select **Accessories > E > LOGO**, or type `LOGO` at the main menu. At the `Logo>` prompt, try `REPEAT 4 (FD 80 RT 90)` to draw a square; square brackets work too. Use `STATUS` to inspect turtle state and `HELP` to see the supported commands. Variables (`MAKE "side 60`), arithmetic words, and user procedures (`TO SQUARE :side`, then commands, then `END`) are supported. Type `BYE` to return to the hub. Drawing output is always described in the terminal; the graphical turtle window is optional and requires a working Tkinter display.

The Keyboard option types into the focused host application. Enter, Tab, and Backspace are supported;
press **Ctrl+X** to exit. Escape and Ctrl+] are also recognized when the
terminal can send them. This uses Windows' native input API on Windows and
`pynput` on macOS/Linux. Keep the intended application focused while using this
mode.

The ANSI Translation option toggles translating incoming ANSI/VT100 BBS output
for the connected machine. Its setting is saved per machine profile and applies
to later connections as well.

Welcome Banner sets a persistent main-menu banner. The `WELCOME_BANNER` value
in `config.py` is the default; a banner set here is saved separately and takes
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
edit the current input line. Bookmarks are stored in `browser_bookmarks.json`
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
`ftp_bookmarks.json`.
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

- **XMODEM**: Classic 128-byte block protocol with checksum
- **YMODEM**: 1024-byte block protocol for faster transfers
- **ASCII**: Plain text streaming (no error correction)

To send a file from the hub to your vintage computer:
1. Select "File Transfers" from the main menu
2. Browse into a directory by selecting its number, or type a directory path
   to jump directly to it. `D` opens the available drives (or filesystem root),
   `B` goes to the parent directory, and `H` returns to the hub's `files/`
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

The File Transfers menu opens in the hub's `files/` directory by default, but
you can browse or type a path to transfer files from anywhere the hub process
can access. Uploads are saved in the currently open directory.

### Directory Structure

```
Retro-Serial-Hub/
├── RETRO_SERIAL_HUB.py    # Main hub program
├── config.py               # Configuration file (edit this!)
├── ai_config.json          # OpenAI API key (optional)
├── bbs_directory.json     # Managed BBS directory (created when first changed)
├── user_shortcuts.json    # User-configured shortcuts (created when first added)
├── terminal_columns.json  # Saved per-profile 40/80-column choices
├── telnet_bookmarks.json  # Telnet bookmarks (created when first saved)
├── ftp_bookmarks.json     # FTP/FTPS bookmarks (created when first saved)
├── keyboard_profiles.json # Retro keyboard mapping profiles (Apple II, C64, etc.)
├── requirements.txt       # Python dependencies
├── rsh_ai.py              # AI Assistant module
├── rsh_bbs.py             # BBS directory and management module
├── rsh_directory.py       # Persistent BBS directory storage
├── rsh_telnet.py          # Direct TCP terminal connections and bookmarks
├── rsh_ftp.py             # FTP/FTPS browser and downloads
├── rsh_browser.py         # Text-first web browser and bookmarks
├── rsh_bridge.py          # COM port bridge module
├── rsh_files.py           # File transfer module
├── rsh_keyboard.py        # Host keyboard bridge
├── rsh_notes.py           # Notes module
├── rsh_terminal.py        # ANSI translation and screen clearing
├── rsh_text.py            # Text library module
├── rsh_wargames.py        # WarGames module
├── rsh_welcome.py         # Persistent welcome banner
├── retro_os/              # Retro Serial OS core, runtime, shell, and services
│   ├── core.py            # Shell, EventBus, Session model, ModuleLoader
│   ├── runtime.py         # Runtime initialization and built-in command handlers
│   ├── host_env.py        # Host OS integration, app scanner, clipboard, sysinfo
│   ├── menu.py            # Accordion flyout menu engine
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

- Check that the COM port name in `config.py` matches your system
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

## Release Notes

### v2.3

- **Terminal Logo Programming**: Added the LOGO accessory and CLI launcher, with
  movement, pen controls, repeat groups using brackets or parentheses, variables,
  arithmetic, user procedures, terminal turtle status, and optional host graphics.
- **Connected Terminal Tools**: Added a Communications menu for listing active
  terminals, messaging a selected terminal, and delivering a text file over ASCII;
  the CLI also supports `terminals` and `msg to <terminal> <text>`.
- **Expanded Terminal Games**: Added Lunar Lander, Hunt the Wumpus, Blackjack,
  and Mastermind to Games. WarGames remains available through the CLI. Game prompts
  now show the single-letter keys that activate each action.
- **Menu and Notes Updates**: Moved Host Printing to Host Connectivity, renamed
  the Notes menu item to Notepad, added host clipboard capture/copy workflows,
  corrected dashboard section activity numbering, and normalized menu spacing.
- Updated both user guides and incremented the application version to v2.3.

### v2.2

- **Task Scheduler Command Chaining**: Scheduled tasks can now chain multiple
  commands in a single scheduled event using ` : ` (or `;`), executing them
  sequentially and compiling the outputs cleanly (for example:
  `news : weather Austin : broadcast Morning briefing complete`).
- **Resilient Chained Task Execution**: If an individual command in a chain
  encounters an error or is unrecognized, subsequent chained commands continue
  to run and report output without halting the sequence.
- **Dynamic Scheduler CLI Command Discovery**: `schedule modules` now dynamically
  enumerates all shell commands available in the active runtime rather than a
  static list, and `schedule info <cmd>` provides detailed syntax and chaining
  guidance for any registered command.
- **Scheduler Alert & Broadcast Integration**: Added explicit scheduler
  documentation and module usage info for real-time messaging commands
  (`broadcast`, `notify`, `msg`, `alert`), enabling scheduled tasks to push
  instant notifications to all connected terminals.
- **Enhanced Scheduler Menu & URL Handling**: Updated the interactive menu
  (`[2] Add New Scheduled Task`) with command chaining support, helpful chaining
  prompts, and automatic URL detection and wrapping for web endpoints.
- Incremented application version to v2.2.

### v2.1

- **Document Viewer Windows Path Resolution**: Fixed an issue where Windows
  backslashes were stripped during shell argument parsing (causing duplicated or
  corrupted paths such as `OneDriveSoftware...`), allowing documents, images,
  and local files to load seamlessly from local drives.
- **Interactive News Article Reader**: Added interactive headline article selection
  to Weather & News, allowing vintage terminals to type an article number directly
  to read the complete summary and download full web article contents (`F` /
  `news <num> full`).
- **Dedicated News Task Scheduler Option**: Added news and weather command
  scheduling to the background task scheduler (`schedule add <interval> news ...`),
  listing them under `schedule modules`.
- **Console Pseudo Interface & Connected User Highlighting**: Enhanced the live
  host console dashboard with an interactive pseudo interface layout displaying
  connected client activity and highlighting active menu items in real time.
- **Updated Copyright Notices**: Updated all system banners, headers, and
  documentation to 2025-2026.
- Incremented application version to v2.1.

### v2.0

- **Retro Serial OS Runtime**: Full host-side operating system extension with
  an interactive command prompt (`cli>` / `OS`), hot-reloadable module system,
  event bus publish/subscribe architecture, multi-client session tracking, and
  programmable keyboard bridge shortcut profiles.
- **Accordion Main Menu & Custom Shortcuts**: Fast categorized accordion flyout
  menu layout optimized for 40- and 80-column terminals, complete with a
  user-defined command shortcut macro system with automatic flyout.
- **Host Terminal & Quick Shell**: Bidirectional streaming console session to
  the host OS (`cmd.exe`, `powershell`, or unix shells) with configurable local
  echo, newline translation, and interactive parameters.
- **Real-Time Host System Monitor**: Live CPU load measurement, memory, disk,
  and uptime monitor with continuous screen clearing, pause/resume, and
  adjustable refresh rates (`top` / `sysinfo live`).
- **Modern Document Viewer Pipeline**: Automatic text extraction and pagination
  for modern file formats including PDF, Word (.docx), Excel (.xlsx / .csv),
  plain text, Markdown, HTML, and web URLs.
- **Integrated Hub Mail & Internet Email**: Central inter-terminal hub mailbox
  identifying senders by hardware/connection, along with full IMAP/SMTP internet
  email support and host desktop configuration GUI.
- **Dedicated Retro Games**: Native text-mode Minesweeper, Solitaire (Klondike),
  and WarGames (W.O.P.R.) simulation.
- **Ambient Desk Companion**: Live ASCII weather forecasts (`wttr.in`), RSS news
  feeds (NPR, Hacker News, BBC), and automated morning briefings (`briefing`).
- **Background Task Scheduler**: Automated periodic task execution with
  terminal broadcast notifications and cron-like intervals. Weather and news
  commands can be scheduled directly (for example, `weather Austin` or
  `news npr 6`) and are listed by `schedule modules`.
- **Terminal Hardware Settings & In-Hub Help**: Caps-Only mode for vintage
  uppercase-only ROMs (Apple II Plus, Commodore PET, TRS-80 Model I), serial
  character pacing delays (1-3ms), and 9 comprehensive in-hub help guide topics.
- Incremented application version to v2.0.

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
