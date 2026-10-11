"""
Configuration file for Retro Serial Hub

This file contains all user-configurable settings for the hub.
Edit these values to match your hardware and preferences.
"""

import serial

# Compatibility: some environments may have a non-pyserial "serial" module installed
# which doesn't expose the usual pyserial constants (EIGHTBITS, PARITY_NONE, etc.).
# Provide safe fallbacks so the module can import and the hub can still run.
EIGHTBITS = getattr(serial, 'EIGHTBITS', 8)
SEVENBITS = getattr(serial, 'SEVENBITS', 7)
PARITY_NONE = getattr(serial, 'PARITY_NONE', 'N')
STOPBITS_ONE = getattr(serial, 'STOPBITS_ONE', 1)
STOPBITS_TWO = getattr(serial, 'STOPBITS_TWO', 2)

# Main menu welcome banner. A value changed through the Welcome Banner option is saved
# separately and takes precedence until the saved override is reset.
WELCOME_BANNER = "Welcome to the Retro Serial Hub"

# ============================================================================
# SERIAL PORT CONFIGURATION
# ============================================================================
# Configure each vintage computer or device that will connect to the hub.
# Each entry defines the COM port and serial parameters for one machine.
#
# Configuration parameters:
#   port:     COM port name (e.g., "COM1", "COM2", etc.)
#   baud:     Baud rate (e.g., 300, 1200, 2400, 9600, 19200, 38400, 115200)
#   bytesize: Data bits (EIGHTBITS or SEVENBITS)
#   parity:   Parity (PARITY_NONE, PARITY_ODD, or PARITY_EVEN)
#   stopbits: Stop bits (STOPBITS_ONE or STOPBITS_TWO)
#   xonxoff:  Software flow control (True or False)
#   rtscts:   Hardware flow control (True or False)
#   ansi:     Hub menus should use ANSI sequences (True) or plain text (False)
#   translate_ansi: Translate incoming BBS ANSI/VT100 data for a non-ANSI terminal
#   ansi_clear_sequence: Bytes sent to clear the screen on translated terminals
#   ansi_home_clears_screen: Treat cursor-home as a clear for screen redraws
#   columns: 40 or 80 column terminal layout
#
# Example configurations are provided below for common vintage systems.
# Modify the port assignments and parameters to match your setup.
# ============================================================================

SERIAL_CONFIGS = {
    "APPLE2": {
        "port": "COM2",           # Change to your Apple II COM port
        "baud": 19200,           # Adjust to match your serial card
        "bytesize": EIGHTBITS,
        "parity": PARITY_NONE,
        "stopbits": STOPBITS_ONE,
        "xonxoff": False,
        "rtscts": False,
        "ansi": False,            # Hub menus use the non-ANSI rendering path
        "translate_ansi": True,   # Convert ANSI/VT100 output for a non-ANSI terminal
        "ansi_clear_sequence": b"\x1bv",  # Terminal-specific screen-clear sequence
        "ansi_home_clears_screen": True,  # Clear when applications redraw from cursor home
        "columns": 80,
    },
    "IBM": {
        "port": "COM6",           # Change to your IBM PC COM port
        "baud": 9600,
        "bytesize": EIGHTBITS,
        "parity": PARITY_NONE,
        "stopbits": STOPBITS_ONE,
        "xonxoff": False,
        "rtscts": False,
        "ansi": True,             # IBM PC supports ANSI
        "columns": 80,
    },
    "C64": {
        "port": "COM4",           # Change to your Commodore 64 COM port
        "baud": 2400,
        "bytesize": EIGHTBITS,
        "parity": PARITY_NONE,
        "stopbits": STOPBITS_ONE,
        "xonxoff": False,
        "rtscts": False,
        "ansi": True,             # C64 terminal software may support ANSI
        "columns": 40,
    },
    "TRS80": {
        "port": "COM80",          # Change to your TRS-80 COM port
        "baud": 9600,
        "bytesize": EIGHTBITS,
        "parity": PARITY_NONE,
        "stopbits": STOPBITS_ONE,
        "xonxoff": True,
        "rtscts": True,
        "ansi": False,            # TRS-80: assume no ANSI
        "columns": 80,
    }
}

# Optional inbound TCP terminal servers, keyed by a SERIAL_CONFIGS profile.
# Leave empty to keep network access disabled. Use a distinct port per profile.
# Binding to 0.0.0.0 allows other devices on the LAN to connect; do not expose
# these unauthenticated, unencrypted terminal sessions directly to the Internet.
TELNET_SERVER_CONFIGS = {
    "APPLE2": {"host": "0.0.0.0", "port": 6400},
    "IBM": {"host": "0.0.0.0", "port": 6401},
    "C64": {"host": "0.0.0.0", "port": 6402},
    "TRS80": {"host": "0.0.0.0", "port": 6403}
}

# ============================================================================
# BBS DIRECTORY CONFIGURATION
# ============================================================================
# Default bulletin board systems (BBSs) used to seed the saved directory.
# The hub's Bulletin Boards manager can edit or remove these entries; saved
# changes are stored in bbs_directory.json and override these defaults.
# Each default BBS needs corresponding entries in BBSS, IPS, and PORTS.
# The entries must be in the same order across all three lists.
#
# BBSS:  Display names shown in the BBS menu
# IPS:   Hostnames or IP addresses
# PORTS: TCP port numbers
#
# The example configuration below includes a variety of BBSs organized by
# platform. You can add, remove, or modify entries as needed. Just ensure
# the three lists stay synchronized (same number of entries, same order).
# ============================================================================

BBSS = [
    # General (no platform tag)
    "Arrakis","Beebs","Citadel","Dead Zone","Deep Skies","DJ's Place",
    "Enterprise","High Desert","Hoyvision","Lost Caverns","Lower Planes",
    "LV-426","Mad World","Night Owl","Particles","RapidFire","Retro Campus",
    "Satellite 4","Surf Shop","Telehack","The Keep II","Willow Creek","Zelch",
    "Amberstar","Blue Nebula","Chaos Realm","Dragon's Den","Elysium Fields",
    "Frostbyte","Galaxy Express","Hack Shack","Infinity Point","Jupiter Station",
    "Karma BBS","Lunar Outpost","Matrix Node","Neon Nights","Oblivion",
    "Phantom Zone","Quantum Link","Rogue's Gallery","Starforge","Twilight Zone",
    "Underground","Vector Base","Warp Gate","Xanadu","Yellow Subnet","Zenith",

    # Apple II
    "AII: An 80s Apple II BBS","AII: Captain's Quarters","AII: CQ II BBS",
    "AII: GBBS Pro! BBS","AII: Pro-Kegs","AII: The Lost Dungeon",
    "AII: Willamette Apple Connection",

    # C64
    "C64: Cottonwood","C64: League of Commodore","C64: Particles! BBS",

    # IBM
    "IBM: Black Flag BBS","IBM: Dura-Europos BBS","IBM: The Cave BBS",

    # TRS
    "TRS: Level 29 BBS","TRS: The Keep BBS"
]

IPS = [
    # General
    "atl.ddns.net",             # Arrakis
    "beebs.ddns.net",           # Beebs
    "citadel64.thejlab.com",    # Citadel
    "dzbbs.hopto.org",          # Dead Zone
    "bbs.deepskies.com",        # Deep Skies
    "bbs.impakt.net",           # DJ's Place
    "enterprisebbs.ddns.net",   # Enterprise
    "highdesertbbs.ddns.net",   # High Desert
    "13th.hoyvision.com",       # Hoyvision
    "lostcavernsbbs.example.net", # Lost Caverns (placeholder)
    "lowerplanesbbs.example.net", # Lower Planes (placeholder)
    "lv426bbs.hopto.org",       # LV-426
    "madworldbbs.com",          # Mad World
    "nightowlbbs.ddns.net",     # Night Owl
    "particlesbbs.dyndns.org",  # Particles
    "rapidfire.hopto.org",      # RapidFire
    "bbs.retrocampus.com",      # Retro Campus
    "satellite4.dynu.net",      # Satellite 4
    "surfshopbbs.example.net",  # Surf Shop (placeholder)
    "telehack.com",             # Telehack
    "thekeep2.ddns.net",        # The Keep II
    "willowcreekbbs.dynu.net",  # Willow Creek
    "zelchbbs.example.net",     # Zelch (placeholder)

    # New General (alphabetical extras)
    "amberstarbbs.example.net", # Amberstar
    "bluenebula.example.net",   # Blue Nebula
    "chaosrealm.example.net",   # Chaos Realm
    "dragonsden.example.net",   # Dragon's Den
    "elysiumfields.example.net",# Elysium Fields
    "frostbytebbs.example.net", # Frostbyte
    "galaxyexpress.example.net",# Galaxy Express
    "hackshack.example.net",    # Hack Shack
    "infinitypoint.example.net",# Infinity Point
    "jupiterstation.example.net",# Jupiter Station
    "karmabbs.example.net",     # Karma BBS
    "lunaroutpost.example.net", # Lunar Outpost
    "matrixnode.example.net",   # Matrix Node
    "neonnights.example.net",   # Neon Nights
    "oblivionbbs.example.net",  # Oblivion
    "phantomzone.example.net",  # Phantom Zone
    "quantumlink.example.net",  # Quantum Link
    "roguesgallery.example.net",# Rogue's Gallery
    "starforge.example.net",    # Starforge
    "twilightzone.example.net", # Twilight Zone
    "undergroundbbs.example.net",# Underground
    "vectorbase.example.net",   # Vector Base
    "warpgate.example.net",     # Warp Gate
    "xanadu.example.net",       # Xanadu
    "yellowsubnet.example.net", # Yellow Subnet
    "zenithbbs.example.net",    # Zenith

    # Apple II
    "a80sappleiibbs.ddns.net",  # AII: An 80s Apple II BBS
    "cqbbs.ddns.net",           # AII: Captain's Quarters
    "gbbspro.ddns.net",         # AII: CQ II BBS
    "prolin.ksherlock.com",     # AII: GBBS Pro! BBS
    "prokegs.example.net",      # AII: Pro-Kegs (placeholder)
    "lostdungeonbbs.com",       # AII: The Lost Dungeon
    "wacbbs.ddns.net",          # AII: Willamette Apple Connection

    # C64
    "cottonwoodbbs.dyndns.org", # C64: Cottonwood
    "tlocbbs.dyndns.net",       # C64: League of Commodore
    "particlesbbs.dyndns.org",  # C64: Particles! BBS

    # IBM
    "blackflag.acid.org",       # IBM: Black Flag BBS
    "dura-bbs.net",             # IBM: Dura-Europos BBS
    "cavebbs.homeip.net",       # IBM: The Cave BBS

    # TRS
    "level29bbs.ddns.net",      # TRS: Level 29 BBS
    "thekeep.net"               # TRS: The Keep BBS
]

PORTS = [
    # General
    6403,   # Arrakis
    6502,   # Beebs
    6400,   # Citadel
    64128,  # Dead Zone
    6400,   # Deep Skies
    6502,   # DJ's Place
    6400,   # Enterprise
    6400,   # High Desert
    6400,   # Hoyvision
    6400,   # Lost Caverns
    6400,   # Lower Planes
    6464,   # LV-426
    6400,   # Mad World
    6400,   # Night Owl
    6400,   # Particles
    64128,  # RapidFire
    6400,   # Retro Campus
    6400,   # Satellite 4
    6400,   # Surf Shop
    23,     # Telehack
    6400,   # The Keep II
    23,     # Willow Creek
    6502,   # Zelch

    # New General (defaults to 23 unless you know otherwise)
    23,     # Amberstar
    23,     # Blue Nebula
    23,     # Chaos Realm
    23,     # Dragon's Den
    23,     # Elysium Fields
    23,     # Frostbyte
    23,     # Galaxy Express
    23,     # Hack Shack
    23,     # Infinity Point
    23,     # Jupiter Station
    23,     # Karma BBS
    23,     # Lunar Outpost
    23,     # Matrix Node
    23,     # Neon Nights
    23,     # Oblivion
    23,     # Phantom Zone
    23,     # Quantum Link
    23,     # Rogue's Gallery
    23,     # Starforge
    23,     # Twilight Zone
    23,     # Underground
    23,     # Vector Base
    23,     # Warp Gate
    23,     # Xanadu
    23,     # Yellow Subnet
    23,     # Zenith

    # Apple II
    6502,   # AII: An 80s Apple II BBS
    6800,   # AII: Captain's Quarters
    6502,   # AII: CQ II BBS
    6523,   # AII: GBBS Pro! BBS
    23,     # AII: Pro-Kegs
    6502,   # AII: The Lost Dungeon
    6502,   # AII: Willamette Apple Connection

    # C64
    6502,   # C64: Cottonwood
    6400,   # C64: League of Commodore
    6400,   # C64: Particles! BBS

    # IBM
    23,     # IBM: Black Flag BBS
    6359,   # IBM: Dura-Europos BBS
    23,     # IBM: The Cave BBS

    # TRS
    23,     # TRS: Level 29 BBS
    23      # TRS: The Keep BBS
]
