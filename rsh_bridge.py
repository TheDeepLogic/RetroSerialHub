"""
rsh_bridge.py

Pluggable COM Port Bridge module.

Interface:
- create_session(ser, use_ansi=True, active_ports=None, surrendered_ports=None) -> session_object
- handle_input(session, line_str, ser, use_ansi=True) -> (consumed:bool, action_or_None)

Actions returned to core:
- ('OPEN_BRIDGE', serial_obj, port_name) -> core will set bridge_serial to serial_obj and switch to COMBRIDGE mode

The module performs staged prompts for COM port parameters and attempts to open the requested serial port.
It accepts optional references to the hub's ACTIVE_PORTS and SURRENDERED_PORTS dictionaries so it can perform the same "take over" behavior as the original inline logic.
"""

import serial
# Compatibility fallbacks if the environment's 'serial' module doesn't expose
# pyserial constants. This keeps the bridge module import-safe in such cases.
EIGHTBITS = getattr(serial, 'EIGHTBITS', 8)
SEVENBITS = getattr(serial, 'SEVENBITS', 7)
PARITY_NONE = getattr(serial, 'PARITY_NONE', 'N')
PARITY_ODD = getattr(serial, 'PARITY_ODD', 'O')
PARITY_EVEN = getattr(serial, 'PARITY_EVEN', 'E')
STOPBITS_ONE = getattr(serial, 'STOPBITS_ONE', 1)
STOPBITS_TWO = getattr(serial, 'STOPBITS_TWO', 2)
import time
import os


def _write(ser, s):
    ser.write(s.encode('ascii', errors='ignore'))


def create_session(ser, use_ansi=True, active_ports=None, surrendered_ports=None):
    sess = {
        'stage': 0,
        'values': {},
        'active_ports': active_ports,
        'surrendered_ports': surrendered_ports,
    }
    _render_intro(ser)
    return sess


def _render_intro(ser):
    _write(ser, "\r\nCOM Port Bridge setup. Press Enter to accept the default for any prompt.\r\n\r\n")
    _write(ser, "COM Port Number (Default: 1): ")


def handle_input(sess, line_str, ser, use_ansi=True):
    stage = sess.get('stage', 0)
    v = sess.get('values', {})

    # Stage 0: COM Port Number
    if stage == 0:
        txt = line_str.strip()
        if txt == "":
            port_num = 1
        else:
            try:
                port_num = int(txt)
                if port_num <= 0:
                    raise ValueError()
            except Exception:
                _write(ser, "\r\nInvalid port number. COM Port Number (Default: 1): ")
                return True, None
        v['port_num'] = port_num
        sess['stage'] = 1
        _write(ser, "\r\nBaud (Default: 115200): ")
        return True, None

    # Stage 1: Baud
    if stage == 1:
        txt = line_str.strip()
        if txt == "":
            baud = 115200
        else:
            try:
                baud = int(txt)
            except Exception:
                _write(ser, "\r\nInvalid baud. Baud (Default: 115200): ")
                return True, None
        v['baud'] = baud
        sess['stage'] = 2
        _write(ser, "\r\nData Bits (Options: 8,7 Default: 8): ")
        return True, None

    # Stage 2: Data Bits
    if stage == 2:
        txt = line_str.strip()
        if txt == "":
            db = 8
        else:
            try:
                db = int(txt)
                if db not in (7, 8):
                    raise ValueError()
            except Exception:
                _write(ser, "\r\nInvalid. Data Bits (Options: 8,7 Default: 8): ")
                return True, None
        v['data_bits'] = db
        sess['stage'] = 3
        _write(ser, "\r\nStop Bits (Default: 1): ")
        return True, None

    # Stage 3: Stop Bits
    if stage == 3:
        txt = line_str.strip()
        if txt == "":
            sb = 1
        else:
            try:
                sb = int(txt)
                if sb not in (1, 2):
                    raise ValueError()
            except Exception:
                _write(ser, "\r\nInvalid. Stop Bits (Default: 1): ")
                return True, None
        v['stop_bits'] = sb
        sess['stage'] = 4
        _write(ser, "\r\nParity (Options: O, E, N, Default: N): ")
        return True, None

    # Stage 4: Parity
    if stage == 4:
        txt = line_str.strip().upper()
        if txt == "":
            parity = "N"
        else:
            if txt[0] in ("O", "E", "N"):
                parity = txt[0]
            else:
                _write(ser, "\r\nInvalid. Parity (Options: O, E, N, Default: N): ")
                return True, None
        v['parity'] = parity
        sess['stage'] = 5
        _write(ser, "\r\nXON/XOFF (Options: Y, N, Default: N): ")
        return True, None

    # Stage 5: XON/XOFF
    if stage == 5:
        txt = line_str.strip().upper()
        if txt == "":
            xon = False
        else:
            if txt[0] == "Y":
                xon = True
            elif txt[0] == "N":
                xon = False
            else:
                _write(ser, "\r\nInvalid. XON/XOFF (Options: Y, N, Default: N): ")
                return True, None
        v['xonxoff'] = xon
        sess['stage'] = 6
        _write(ser, "\r\nRTS/CTS (Options: Y, N, Default: N): ")
        return True, None

    # Stage 6: RTS/CTS
    if stage == 6:
        txt = line_str.strip().upper()
        if txt == "":
            rts = False
        else:
            if txt[0] == "Y":
                rts = True
            elif txt[0] == "N":
                rts = False
            else:
                _write(ser, "\r\nInvalid. RTS/CTS (Options: Y, N, Default: N): ")
                return True, None
        v['rtscts'] = rts

        # All prompts collected — attempt to open the requested COM port
        port_num = v['port_num']
        port_name = f"COM{port_num}"
        try:
            # map data bits
            bytesize = EIGHTBITS if v['data_bits'] == 8 else SEVENBITS
            # parity
            p = v['parity']
            if p == 'O':
                parity_val = PARITY_ODD
            elif p == 'E':
                parity_val = PARITY_EVEN
            else:
                parity_val = PARITY_NONE
            # stop bits
            sb = v['stop_bits']
            stopbits_val = STOPBITS_ONE if sb == 1 else STOPBITS_TWO

            # If that port is currently active in this process, attempt to take it over
            active = sess.get('active_ports')
            surrendered = sess.get('surrendered_ports')
            if active and isinstance(active, dict):
                owner = active.get(port_name.upper())
                if owner and owner.get('serial'):
                    _write(ser, f"\r\nNote: {port_name} is currently owned by this hub. Taking over...\r\n")
                    try:
                        owner_ser = owner['serial']
                        if surrendered is not None and isinstance(surrendered, set):
                            surrendered.add(port_name.upper())
                        try:
                            owner_ser.close()
                        except Exception:
                            pass
                        active.pop(port_name.upper(), None)
                    except Exception:
                        pass

            # On Windows, COM names >= COM10 must be opened via the "\\.\\COMn" namespace.
            # Also, after closing an owner Serial object there can be a short delay before
            # the OS releases the device; retry a few times with a small sleep to handle that.
            port_to_open = port_name
            try:
                # detect numeric part
                pn = int(port_name.replace('COM', ''))
                if os.name == 'nt' and pn >= 10:
                    port_to_open = r"\\.\\" + port_name
            except Exception:
                pass

            last_exc = None
            bridge_serial = None
            for attempt in range(6):
                try:
                    bridge_serial = serial.Serial(
                        port=port_to_open,
                        baudrate=v['baud'],
                        bytesize=bytesize,
                        parity=parity_val,
                        stopbits=stopbits_val,
                        xonxoff=v['xonxoff'],
                        rtscts=v['rtscts'],
                        timeout=0
                    )
                    last_exc = None
                    break
                except Exception as e:
                    last_exc = e
                    # small backoff to allow OS to release device if we just closed it
                    time.sleep(0.25)

            if last_exc is not None:
                _write(ser, f"\r\n*** Unable to open {port_name}: {last_exc} ***\r\n")
                _write(ser, "Press any key to continue.\r\n")
                sess['stage'] = 0
                _render_intro(ser)
                return True, None
        except Exception as e:
            _write(ser, f"\r\n*** Unable to open {port_name}: {e} ***\r\n")
            _write(ser, "Press any key to continue.\r\n")
            sess['stage'] = 0
            _render_intro(ser)
            return True, None

        # Return the opened serial object to the core
        return True, ('OPEN_BRIDGE', bridge_serial, port_name)

    # default: re-render intro
    _render_intro(ser)
    return True, None


# ----- Runtime bridge helpers -----
def create_runtime_session(bridge_serial, port_name, active_ports=None, surrendered_ports=None, ser=None, use_ansi=True):
    """Create a runtime session used while a bridge is active.

    The hub should call this after receiving ('OPEN_BRIDGE', serial_obj, port_name)
    from handle_input during the prompt stage. The returned session is then
    used for runtime operations: polling incoming bytes from the bridged port,
    forwarding raw input from the local session to the bridged port, and
    handling bridge-mode commands (like ATH to hang up).
    """
    return {
        'stage': 'runtime',
        'bridge_serial': bridge_serial,
        'port_name': port_name,
        'active_ports': active_ports,
        'surrendered_ports': surrendered_ports,
    }


def handle_raw_input(sess, data):
    """Forward raw bytes from the local serial into the bridged port.

    This is intended to be called from the hub immediately after reading
    raw bytes from the local session's serial port.
    """
    bs = sess.get('bridge_serial')
    if not bs:
        return False
    try:
        out = data.replace(b"\r\n", b"\r\n").replace(b"\n", b"\r\n").replace(b"\r", b"\r\n")
        bs.write(out)
        return True
    except Exception:
        try:
            bs.close()
        except Exception:
            pass
        sess['bridge_serial'] = None
        return False


def poll_bridge(sess, ser):
    """Poll the bridged serial for incoming bytes and write them to the local serial.

    Called by the hub regularly (each loop) when a bridge runtime session exists.
    """
    bs = sess.get('bridge_serial')
    if not bs:
        return
    try:
        if getattr(bs, 'in_waiting', 0):
            d = bs.read(bs.in_waiting)
            if d:
                ser.write(d)
    except Exception:
        try:
            bs.close()
        except Exception:
            pass
        sess['bridge_serial'] = None


def handle_input_runtime(sess, line_str, ser, use_ansi=True, raw_line=None):
    """Handle line-oriented input while a bridge runtime session is active.

    Returns same (consumed, action) tuple as create_session.handle_input.
    Supported actions:
      - 'MENU' : close bridge and return to hub menu
      - None   : input forwarded/handled
    """
    bs = sess.get('bridge_serial')
    if not bs:
        return True, 'MENU'

    upper = line_str.strip().upper()
    # Local hangup
    if upper == 'ATH':
        try:
            pname = getattr(bs, 'port', None)
            if pname and sess.get('surrendered_ports') and pname.upper() in sess.get('surrendered_ports'):
                try:
                    bs.close()
                except Exception:
                    pass
                sess['surrendered_ports'].discard(pname.upper())
            try:
                bs.close()
            except Exception:
                pass
        except Exception:
            pass
        sess['bridge_serial'] = None
        return True, 'MENU'

    # Empty line => send CRLF
    if not line_str:
        try:
            bs.write(b"\r\n")
            return True, None
        except Exception:
            try:
                bs.close()
            except Exception:
                pass
            sess['bridge_serial'] = None
            return True, 'MENU'

    # Otherwise send the provided raw_line if available (preserves original bytes),
    # otherwise encode the textual line.
    try:
        if raw_line is not None:
            out_line = raw_line.replace(b"\r\n", b"\r\n").replace(b"\n", b"\r\n").replace(b"\r", b"\r\n")
            bs.write(out_line + b"\r\n")
        else:
            bs.write(line_str.encode('utf-8', errors='ignore') + b"\r\n")
        return True, None
    except Exception:
        try:
            bs.close()
        except Exception:
            pass
        sess['bridge_serial'] = None
        return True, 'MENU'


# Backwards-compatible wrapper: if a runtime session is passed to handle_input,
# dispatch to handle_input_runtime.
def handle_input_dispatch(sess, line_str, ser, use_ansi=True, raw_line=None):
    if sess.get('stage') == 'runtime' or sess.get('bridge_serial'):
        return handle_input_runtime(sess, line_str, ser, use_ansi, raw_line=raw_line)
    return handle_input(sess, line_str, ser, use_ansi)
