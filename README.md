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
- **BBS Directory**: Browse and connect to a curated list of retro bulletin board systems
- **File Transfers**: Send and receive files using XMODEM, YMODEM, or ASCII protocols
- **Text Library**: View text files with pagination support for vintage terminals
- **URL Reader**: Fetch web content and strip HTML for display on text-only terminals
- **Notes System**: Create, read, and manage text notes
- **COM Port Bridge**: Bridge between different serial ports for direct computer-to-computer communication
- **WarGames Mode**: Nostalgic WarGames movie-inspired interface (proof-of-concept)
- **AI Assistant**: Optional ChatGPT-powered assistant accessible from vintage terminals
- **Hot-Reload Modules**: Edit feature modules without restarting the hub
- **ANSI Support**: Automatic detection and handling of ANSI escape codes for compatible terminals

## Requirements

- Python 3.6 or higher
- PySerial library (`pip install pyserial`)
- USB-to-Serial adapters or RS-232 ports for connecting vintage computers
- Optional: OpenAI API key for AI Assistant feature

## Installation

1. Clone or download this repository to your computer

2. Install Python dependencies:
   ```bash
   pip install pyserial
   ```

3. Optional - For AI Assistant functionality:
   ```bash
   pip install openai
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
        "ansi": False             # Set to True if terminal supports ANSI
    },
    # Add more computers as needed...
}
```

Common baud rates for vintage systems:
- Apple II with Super Serial Card: 300, 1200, 2400, 9600, 19200, or 115200
- Commodore 64: 300, 1200, 2400
- IBM PC/XT/AT: 300, 1200, 2400, 9600
- TRS-80: 300, 1200, 2400, 9600

### BBS Directory Configuration

The BBS directory is configured using three synchronized lists in `config.py`:

- `BBSS`: Display names for each BBS
- `IPS`: Hostnames or IP addresses
- `PORTS`: TCP port numbers

To add a new BBS, append entries to all three lists in the same order:

```python
BBSS.append("My BBS")
IPS.append("mybbs.example.com")
PORTS.append(23)
```

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
4. Press Enter to see the main menu

### Main Menu

When connected, you'll see the LogicNet BBS main menu with these options:

1. **Bulletin Boards**: Browse and connect to BBSs
2. **File Transfers**: Send or receive files
3. **Text Library**: View text files
4. **URL Reader**: Fetch and read web content
5. **Notes**: Create and manage notes
6. **COM Port Bridge**: Bridge to another serial port
7. **Wargames**: WarGames-inspired interface
8. **AI Assistant**: Chat with ChatGPT (if configured)

### Special Commands

- **ATM**: Return to main menu from anywhere (like the old modem "AT" commands)
- **ATH**: Hang up / disconnect from a BBS
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
├── rsh_ai.py              # AI Assistant module
├── rsh_bbs.py             # BBS directory module
├── rsh_bridge.py          # COM port bridge module
├── rsh_files.py           # File transfer module
├── rsh_notes.py           # Notes module
├── rsh_text.py            # Text library module
├── rsh_url.py             # URL reader module
├── rsh_wargames.py        # WarGames module
├── files/                 # File transfer storage
├── text/                  # Text library files
└── notes/                 # Notes storage
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

- Verify the hostname/IP and port in `config.py`
- Check your internet connection
- Some BBSs may be offline; try a different one
- Firewall may be blocking outbound Telnet connections

### Garbled Text

- Check baud rate settings
- Verify data bits setting (usually 8)
- Disable ANSI support for terminals that don't support it
- Try a different cable

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
