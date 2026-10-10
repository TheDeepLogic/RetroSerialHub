"""Lossy ANSI/VT100-to-ASCII translation for terminals without ANSI support."""


_CP437_ASCII = {
    176: b".",
    177: b":",
    178: b"#",
    179: b"|",
    186: b"|",
    196: b"-",
    205: b"=",
    218: b"+",
    191: b"+",
    192: b"+",
    217: b"+",
    195: b"+",
    180: b"+",
    197: b"+",
    200: b"+",
    188: b"+",
    201: b"+",
    187: b"+",
    204: b"+",
    185: b"+",
    206: b"+",
    219: b"#",
    220: b"#",
    223: b"#",
}


def configure_screen_clearing(ser, translate_ansi=False, clear_sequence=b"\x0c"):
    """Attach the configured non-ANSI clear sequence to a serial connection."""
    if isinstance(clear_sequence, str):
        clear_sequence = clear_sequence.encode("ascii")
    ser._rsh_translate_ansi = bool(translate_ansi)
    ser._rsh_clear_sequence = clear_sequence


def clear_terminal_screen(ser, use_ansi=True):
    """Clear a terminal using its native or configured emulation sequence."""
    if use_ansi:
        ser.write(b"\x1b[2J\x1b[H")
    elif getattr(ser, "_rsh_translate_ansi", False):
        ser.write(getattr(ser, "_rsh_clear_sequence", b"\x0c"))
    else:
        ser.write(b"\r\n")


class AnsiToTextTranslator:
    """Convert common ANSI screen controls into readable, plain serial text.

    Cursor-addressed rows are linearized instead of emulating a full terminal
    screen. This preserves text and ASCII approximations of CP437 line art.
    """

    def __init__(self, clear_sequence=b"\x0c", rows=24, columns=80, clear_on_home=False):
        if isinstance(clear_sequence, str):
            clear_sequence = clear_sequence.encode("ascii")
        self.clear_sequence = clear_sequence
        self.rows = rows
        self.columns = columns
        self.clear_on_home = clear_on_home
        self.reset()

    def reset(self):
        self.state = "normal"
        self.sequence = bytearray()
        self.row = 0
        self.column = 0
        self.saved_position = (0, 0)
        self.telnet_state = "normal"

    def feed(self, data):
        output = bytearray()
        for byte in data:
            if self._consume_telnet(byte):
                continue
            if self.state == "normal":
                self._consume_normal(byte, output)
            elif self.state == "escape":
                self._consume_escape(byte, output)
            elif self.state == "csi":
                self._consume_csi(byte, output)
            elif self.state == "osc":
                if byte == 7:
                    self.state = "normal"
                elif byte == 27:
                    self.state = "osc_escape"
            elif self.state in ("osc_escape", "string_escape"):
                if byte == ord("\\"):
                    self.state = "normal"
                elif self.state == "osc_escape":
                    self.state = "osc"
                else:
                    self.state = "string"
            elif self.state == "string":
                if byte == 27:
                    self.state = "string_escape"
        return bytes(output)

    def _consume_telnet(self, byte):
        state = self.telnet_state
        if state == "normal":
            if byte == 255:
                self.telnet_state = "iac"
                return True
            return False
        if state == "iac":
            if byte == 255:
                self.telnet_state = "normal"
                return False
            if byte in (251, 252, 253, 254):
                self.telnet_state = "option"
            elif byte == 250:
                self.telnet_state = "subnegotiation"
            else:
                self.telnet_state = "normal"
            return True
        if state == "option":
            self.telnet_state = "normal"
            return True
        if state == "subnegotiation":
            if byte == 255:
                self.telnet_state = "subnegotiation_iac"
            return True
        if byte == 240:
            self.telnet_state = "normal"
        else:
            self.telnet_state = "subnegotiation"
        return True

    def _consume_normal(self, byte, output):
        if byte == 27:
            self.state = "escape"
        elif byte == 12:
            self._clear(output)
        elif byte == 13:
            output.append(13)
            self.column = 0
        elif byte == 10:
            self._newline(output)
        elif byte == 8:
            output.append(8)
            self.column = max(0, self.column - 1)
        elif byte == 9:
            spaces = 8 - (self.column % 8)
            output.extend(b" " * spaces)
            self.column += spaces
        elif byte >= 32 and byte != 127:
            self._write_character(byte, output)

    def _consume_escape(self, byte, output):
        self.state = "normal"
        if byte == ord("["):
            self.state = "csi"
            self.sequence.clear()
        elif byte == ord("]"):
            self.state = "osc"
        elif byte in (ord("P"), ord("^"), ord("_")):
            self.state = "string"
        elif byte == ord("c"):
            self._clear(output)
        elif byte in (ord("D"), ord("E")):
            self._newline(output)

    def _consume_csi(self, byte, output):
        if 0x40 <= byte <= 0x7e:
            self._apply_csi(chr(byte), output)
            self.state = "normal"
            self.sequence.clear()
            return
        if len(self.sequence) >= 128:
            self.state = "normal"
            self.sequence.clear()
            return
        self.sequence.append(byte)

    def _apply_csi(self, command, output):
        raw_params = self.sequence.decode("ascii", errors="ignore")
        params = raw_params.lstrip("?=>!")
        values = []
        for value in params.split(";"):
            try:
                values.append(int(value) if value else 0)
            except ValueError:
                values.append(0)

        def parameter(index, default=1):
            value = values[index] if index < len(values) else 0
            return value or default

        if command == "J":
            # CSI J defaults to mode 0 (erase from cursor to end of display).
            # A text-only target cannot erase a display region, so map each
            # erase-in-display mode to the configured full-screen clear.
            if not values or values[0] in (0, 1, 2, 3):
                self._clear(output)
        elif command in ("H", "f"):
            row, column = parameter(0), parameter(1)
            if self.clear_on_home and row == 1 and column == 1:
                # Some animated ANSI programs redraw each frame from home
                # without issuing another erase-in-display sequence.
                self._clear(output)
            else:
                self._position(row, column, output)
        elif command == "d":
            self._position(parameter(0), self.column + 1, output)
        elif command in ("G", "`"):
            self._horizontal_position(parameter(0), output)
        elif command in ("B", "E"):
            for _ in range(min(parameter(0), self.rows)):
                self._newline(output)
            if command == "E":
                self._carriage_return(output)
        elif command == "A":
            self._newline(output)
        elif command in ("C", "a"):
            spaces = min(parameter(0), self.columns)
            output.extend(b" " * spaces)
            self.column += spaces
        elif command == "D":
            count = min(parameter(0), self.column)
            output.extend(b"\x08" * count)
            self.column -= count
        elif command == "s":
            self.saved_position = (self.row, self.column)
        elif command == "u":
            self._position(self.saved_position[0] + 1, self.saved_position[1] + 1, output)

    def _position(self, row, column, output):
        target_row = min(max(row, 1), self.rows)
        target_column = min(max(column, 1), self.columns) - 1
        if target_row <= self.row:
            self._newline(output)
        else:
            while self.row < target_row - 1:
                self._newline(output)
        if target_column < self.column:
            self._carriage_return(output)
        if target_column > self.column:
            output.extend(b" " * (target_column - self.column))
        self.column = target_column

    def _horizontal_position(self, column, output):
        target = min(max(column, 1), self.columns) - 1
        if target < self.column:
            self._carriage_return(output)
        if target > self.column:
            output.extend(b" " * (target - self.column))
        self.column = target

    def _newline(self, output):
        output.extend(b"\r\n")
        self.row = min(self.row + 1, self.rows)
        self.column = 0

    def _carriage_return(self, output):
        output.append(13)
        self.column = 0

    def _clear(self, output):
        output.extend(self.clear_sequence)
        self.row = 0
        self.column = 0

    def _write_character(self, byte, output):
        output.extend(_CP437_ASCII.get(byte, bytes((byte,)) if byte < 128 else b"?"))
        self.column += 1
        if self.column >= self.columns:
            self.row = min(self.row + 1, self.rows)
            self.column = 0
