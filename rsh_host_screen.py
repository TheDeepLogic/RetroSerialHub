"""Bounded text screen for host output; terminal controls never reach the dashboard."""

import re


class HostScreen:
    def __init__(self, columns=80, height=24, capacity=500):
        self.columns, self.height, self.capacity = columns, height, capacity
        self.line_events = 0
        self.clear()

    def clear(self):
        self.lines = [""]
        self.row = self.column = 0
        self.saved = (0, 0)
        self.escape = ""
        self.string_kind = None
        self.generation = getattr(self, "generation", 0) + 1

    def _ensure(self):
        self.row = max(0, self.row)
        self.column = max(0, min(self.columns, self.column))
        while len(self.lines) <= self.row:
            self.lines.append("")
        if len(self.lines) > self.capacity:
            removed = len(self.lines) - self.capacity
            del self.lines[:removed]
            self.row -= removed
            self.saved = (max(0, self.saved[0] - removed), self.saved[1])

    def _put(self, char):
        if self.column >= self.columns:
            self.line_events += 1
            self.row += 1
            self.column = 0
        self._ensure()
        line = self.lines[self.row].ljust(self.column)
        self.lines[self.row] = line[:self.column] + char + line[self.column + 1:]
        self.column += 1

    def _control(self, sequence):
        if sequence in ("\x1bc",):
            self.clear()
            return
        if sequence in ("\x1b7", "\x1b8"):
            if sequence.endswith("7"):
                self.saved = self.row, self.column
            else:
                self.row, self.column = self.saved
                self._ensure()
            return
        if sequence in ("\x1bD", "\x1bE", "\x1bM"):
            self.row = max(0, self.row + (-1 if sequence.endswith("M") else 1))
            if sequence.endswith("E"):
                self.column = 0
            self._ensure()
            return
        match = re.fullmatch(r"\x1b\[([0-9;]*)([A-Za-z@`])", sequence)
        if not match:
            return
        values = [int(part or 0) for part in match[1].split(";")]
        action = match[2]
        value = values[0]
        count = min(value or 1, max(self.height, self.columns))
        top = max(0, len(self.lines) - self.height)
        if action in ("H", "f"):
            self.row = top + min(self.height - 1, (value or 1) - 1)
            self.column = min(self.columns - 1, ((values[1] if len(values) > 1 else 1) or 1) - 1)
        elif action in ("A", "F"):
            self.row = max(top, self.row - count)
            if action == "F":
                self.column = 0
        elif action in ("B", "E"):
            self.row = min(top + self.height - 1, self.row + count)
            if action == "E":
                self.column = 0
        elif action == "C":
            self.column = min(self.columns - 1, self.column + count)
        elif action == "D":
            self.column = max(0, self.column - count)
        elif action in ("G", "`"):
            self.column = min(self.columns - 1, (value or 1) - 1)
        elif action == "d":
            self.row = top + min(self.height - 1, (value or 1) - 1)
        elif action == "s":
            self.saved = self.row, self.column
        elif action == "u":
            self.row, self.column = self.saved
        self._ensure()
        line = self.lines[self.row]
        if action == "K":
            if value == 0:
                self.lines[self.row] = line[:self.column]
            elif value == 1:
                self.lines[self.row] = (" " * (self.column + 1) + line[self.column + 1:])[:self.columns]
            elif value == 2:
                self.lines[self.row] = ""
        elif action == "J":
            if value == 2:
                row, column = self.row - top, self.column
                self.clear()
                self.row, self.column = row, column
                self._ensure()
            elif value == 3:
                del self.lines[:top]
                self.row -= top
                self.saved = (max(0, self.saved[0] - top), self.saved[1])
            elif value == 0:
                self.lines[self.row] = line[:self.column]
                del self.lines[self.row + 1:]
            elif value == 1:
                for row in range(top, self.row):
                    self.lines[row] = ""
                self.lines[self.row] = (" " * (self.column + 1) + line[self.column + 1:])[:self.columns]
        elif action == "P":
            self.lines[self.row] = line[:self.column] + line[self.column + count:]
        elif action == "@":
            self.lines[self.row] = (line[:self.column].ljust(self.column) + " " * count + line[self.column:])[:self.columns]
        elif action == "X":
            self.lines[self.row] = (line[:self.column].ljust(self.column) + " " * count + line[self.column + count:])[:self.columns]

    def feed(self, text):
        for char in text:
            if self.string_kind:
                if char == "\x07" or (self.escape == "\x1b" and char == "\\"):
                    self.string_kind = None
                    self.escape = ""
                else:
                    self.escape = "\x1b" if char == "\x1b" else ""
                continue
            if self.escape:
                self.escape += char
                if self.escape in ("\x1b]", "\x1bP", "\x1b^", "\x1b_"):
                    self.string_kind = self.escape
                    self.escape = ""
                elif self.escape == "\x1b[":
                    continue
                elif len(self.escape) == 2 or "@" <= char <= "~" or len(self.escape) > 128:
                    sequence, self.escape = self.escape, ""
                    self._control(sequence)
                continue
            if char == "\x1b":
                self.escape = char
            elif char == "\x0c":
                self.clear()
            elif char == "\r":
                self.column = 0
            elif char == "\n":
                self.line_events += 1
                self.row += 1
                self.column = 0
                self._ensure()
            elif char == "\b":
                self.column = max(0, self.column - 1)
            elif char == "\t":
                for _ in range(8 - self.column % 8):
                    self._put(" ")
            elif char.isprintable():
                self._put(char)
