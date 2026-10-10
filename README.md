![Retro Serial Hub](images/retroserialhub_banner.jpg)

# Retro Serial Hub

A multi-port serial hub that bridges vintage computers to modern TCP/IP networks, providing access to bulletin board systems (BBS), file transfers, and other retro computing services through a unified menu interface.

> **AI-Assisted Development Notice**
> 
> Hello, fellow human! My name is Aaron Smith. I've been in the IT field for nearly three decades and have extensive experience as both an engineer and architect. While I've had various projects in the past that have made their way into the public domain, I've always wanted to release more than I could. I write useful utilities all the time that aid me with my vintage computing and hobbyist electronic projects, but rarely publish them. I've had experience in both the public and private sectors and can unfortunately slip into treating each one of these as a fully polished cannonball ready for market. It leads to scope creep and never-ending updates to documentation.
> 
> With that in-mind, I've leveraged GitHub Copilot to create or enhance the code within this repository and, outside of this notice, all related documentation. While I'd love to tell you that I pore over it all and make revisions, that just isn't the case. To prevent my behavior from keeping these tools from seeing the light of day, I've decided to do as little of that as possible! My workflow involves simply stating the need to GitHub Copilot, providing reference material where helpful, running the resulting code, and, if there is an actionable output, validating that it's correct. If I find a change I'd like to make, I describe it to Copilot. I've been leveraging the Agent CLI and it takes care of the core debugging.
>
> With all that being said, please keep in-mind that what you read and execute was created by Claude Sonnet 4.5. There may be mistakes. If you find an error, please feel free to submit a pull request with a correction!

## Features

- **Multi-Port Serial Support**: Connect multiple vintage computers simultaneously, each with independent configurations
- **BBS Directory**: Browse, connect to, and manage saved BBS destinations
- **Telnet**: Connect to a host and port directly; manage Telnet bookmarks or add destinations to the BBS directory
- **FTP/FTPS**: Browse FTP servers and save downloads to the hub or transfer them directly to the connected terminal
- **File Transfers**: Send and receive files using XMODEM, YMODEM, or ASCII protocols
- **Text Library**: View text files with pagination support for vintage terminals
- **Web Browser**: Browse paginated text pages, follow numbered links, and manage bookmarks
- **Notes System**: Create, read, and manage text notes
- **COM Port Bridge**: Bridge between different serial ports for direct computer-to-computer communication
- **WarGames Mode**: Nostalgic WarGames movie-inspired interface (proof-of-concept)
- **AI Assistant**: Optional ChatGPT-powered assistant accessible from vintage terminals
- **Hot-Reload Modules**: Edit feature modules without restarting the hub
- **ANSI Support**: Automatic detection and handling of ANSI escape codes for compatible terminals

## Requirements

- Python 3.6 or higher
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
        "ansi_home_clears_screen": False  # Optional: treat cursor-home as a screen clear
    },
    # Add more computers as needed...
}
```

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

The hub will attempt to open each configured serial port. Ports that are not present will be automatically skipped.

### Connecting Your Vintage Computer

1. Connect your vintage computer to the USB-to-Serial adapter
2. Start your terminal software on the vintage computer
3. Configure the terminal to match the settings in `config.py` (baud rate, data bits, parity, stop bits)
4. Press Enter to see the main menu. Type `ATM` at any time to return to it.

### Main Menu

When connected, you'll see the LogicNet BBS main menu with these options:

1. **Bulletin Boards**: Browse and connect to BBSs; enter `M` to add, edit, or delete directory entries
2. **Web Browser**: Browse web pages as paginated text
3. **Telnet**: Connect directly to a host and port, or open/delete saved Telnet bookmarks
4. **FTP**: Connect to traditional FTP or explicit FTPS, browse directories, and choose whether a download is saved on the hub or sent directly to the terminal
5. **File Transfers**: Send or receive files
6. **Text Library**: View text files
7. **AI Assistant**: Chat with ChatGPT (if configured)
8. **Wargames**: WarGames-inspired interface
9. **Notes**: Create and manage notes
10. **COM Port Bridge**: Bridge to another serial port
11. **Keyboard Bridge**: Type into the focused host application from the
   serial terminal. Enter, Tab, and Backspace are supported; press **Ctrl+X**
   to exit. Escape and Ctrl+] are also recognized when the terminal can send
   them. This uses Windows' native input API on Windows and `pynput` on
   macOS/Linux. Keep the intended application focused while using this mode.
12. **Welcome Banner**: Set a persistent main-menu banner. The `WELCOME_BANNER`
    value in `config.py` is the default; a banner set here is saved separately
    and takes precedence until an empty entry resets it to the configured default.

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
beside the hub. The browser displays text and numbered links; JavaScript and
images are not supported. HTML GET/POST forms are supported when their fields
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
2. Choose the transfer protocol (X/Y/A)
3. Select the file number
4. Start the receive function on your vintage computer

To upload a file from your vintage computer:
1. Select "File Transfers" from the main menu
2. Press "U" for upload
3. Enter the filename to save as
4. Start the send function on your vintage computer

Files are stored in the `files/` directory.

### Directory Structure

```
Retro-Serial-Hub/
├── RETRO_SERIAL_HUB.py    # Main hub program
├── config.py               # Configuration file (edit this!)
├── ai_config.json          # OpenAI API key (optional)
├── bbs_directory.json     # Managed BBS directory (created when first changed)
├── telnet_bookmarks.json  # Telnet bookmarks (created when first saved)
├── ftp_bookmarks.json     # FTP/FTPS bookmarks (created when first saved)
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
├── files/                 # File transfer storage
├── text/                  # Text library files
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
- Built with the assistance of GitHub Copilot and Claude Sonnet 4.5

## Support

For questions or issues, please open a GitHub issue or contact the retro computing community forums.

---

**Happy retro computing!** 🖥️📞
