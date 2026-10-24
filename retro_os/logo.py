"""A small, line-oriented Logo interpreter with optional host turtle graphics."""

from __future__ import annotations

import math
import queue
import re
import shlex
import threading


class _TurtleWindow:
    """Keep all Tk/turtle calls on one dedicated GUI thread."""

    def __init__(self):
        self.commands = queue.Queue()
        self.ready = threading.Event()
        self.error = None
        self.closed = False
        self.thread = threading.Thread(target=self._run, name="RetroLogoTurtle", daemon=True)
        self.thread.start()
        self.ready.wait(0.35)

    def _run(self):
        try:
            import turtle

            screen = turtle.Screen()
            screen.setup(width=800, height=600)
            screen.title("Retro Serial Hub - Logo")
            screen.mode("logo")
            screen.tracer(0, 0)
            pen = turtle.Turtle()
            pen.speed(0)
            self.ready.set()

            def pump():
                try:
                    while True:
                        operation, value = self.commands.get_nowait()
                        if operation == "close":
                            screen.bye()
                            self.closed = True
                            return
                        if operation == "forward":
                            pen.forward(value)
                        elif operation == "backward":
                            pen.backward(value)
                        elif operation == "left":
                            pen.left(value)
                        elif operation == "right":
                            pen.right(value)
                        elif operation == "heading":
                            pen.setheading(value)
                        elif operation == "home":
                            pen.home()
                        elif operation == "clear":
                            pen.clear()
                        elif operation == "penup":
                            pen.penup()
                        elif operation == "pendown":
                            pen.pendown()
                        elif operation == "pencolor":
                            pen.pencolor(value)
                        elif operation == "background":
                            screen.bgcolor(value)
                        elif operation == "width":
                            pen.pensize(value)
                        elif operation == "dot":
                            pen.dot(value)
                        elif operation == "circle":
                            pen.circle(value)
                        elif operation == "hide":
                            pen.hideturtle()
                        elif operation == "show":
                            pen.showturtle()
                except queue.Empty:
                    pass
                except Exception as exc:
                    self.error = str(exc)
                try:
                    screen.update()
                    screen.getcanvas().winfo_toplevel().after(25, pump)
                except Exception as exc:
                    self.error = str(exc)
                    self.closed = True

            screen.getcanvas().winfo_toplevel().after(25, pump)
            screen.mainloop()
        except Exception as exc:
            self.error = str(exc)
            self.ready.set()
            self.closed = True

    def send(self, operation, value=None):
        if self.closed or self.error:
            return False
        self.commands.put((operation, value))
        return True


class LogoInterpreter:
    """Stateful Logo subset for interactive terminal use."""

    VALUE_OPS = {
        "SUM": lambda a, b: a + b,
        "DIFFERENCE": lambda a, b: a - b,
        "PRODUCT": lambda a, b: a * b,
        "QUOTIENT": lambda a, b: a / b,
        "REMAINDER": lambda a, b: a % b,
    }

    ALIASES = {
        "FORWARD": "FD", "BACK": "BK", "BACKWARD": "BK",
        "RIGHT": "RT", "LEFT": "LT", "PENUP": "PU", "PENDOWN": "PD",
        "HOME": "HOME", "CLEARSCREEN": "CS",
        "SETHEADING": "SETH", "SETPENCOLOR": "SETPC", "PENCOLOR": "SETPC",
        "SETBACKGROUND": "SETBG", "BACKGROUND": "SETBG", "SETWIDTH": "SETWIDTH",
        "PENSIZE": "SETWIDTH", "HIDETURTLE": "HT", "SHOWTURTLE": "ST",
        "DONE": "BYE", "EXIT": "BYE", "QUIT": "BYE",
    }

    def __init__(self, graphics=True):
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0  # Logo mode: zero points north.
        self.pen_down = True
        self.pen_color = "black"
        self.background = "white"
        self.pen_width = 1
        self.moves = 0
        self.variables = {}
        self.procedures = {}
        self.definition = None
        self.done = False
        self.graphics_enabled = graphics
        self.window = None
        self.window_message = "Graphics window opens on the first drawing command."
        self.call_depth = 0

    @property
    def prompt(self):
        return "...> " if self.definition else "Logo> "

    @staticmethod
    def _tokens(line):
        line = re.sub(r'(?<!\S)"([A-Za-z_]\w*)', r'LOGO_WORD_\1', line)
        lexer = shlex.shlex(line, posix=True, punctuation_chars="[]()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        lexer.escape = ""
        return list(lexer)

    def _graphics(self, operation, value=None):
        if not self.graphics_enabled:
            return
        if self.window is None:
            self.window = _TurtleWindow()
            if self.window.error:
                self.window_message = f"Graphics unavailable: {self.window.error}"
                self.graphics_enabled = False
                self.window = None
                return
            self.window_message = "Host turtle window is open."
        if not self.window.send(operation, value):
            self.window_message = f"Graphics unavailable: {self.window.error or 'window closed'}"
            self.graphics_enabled = False

    def _value(self, tokens, index):
        if index >= len(tokens):
            raise ValueError("A value is missing.")
        token = tokens[index]
        if token.startswith("LOGO_WORD_"):
            return token[len("LOGO_WORD_"):], index + 1
        upper = token.upper()
        if upper in self.VALUE_OPS:
            left, index = self._value(tokens, index + 1)
            right, index = self._value(tokens, index)
            return self.VALUE_OPS[upper](left, right), index
        if token.startswith(":"):
            key = token[1:].lower()
            if key not in self.variables:
                raise ValueError(f"Variable '{key}' has no value.")
            return self.variables[key], index + 1
        try:
            return float(token), index + 1
        except ValueError:
            return token, index + 1

    @staticmethod
    def _group(tokens, index):
        pairs = {"[": "]", "(": ")"}
        if index >= len(tokens) or tokens[index] not in pairs:
            raise ValueError("Expected '[' or '(' before the command list.")
        closing = [pairs[tokens[index]]]
        start = index + 1
        index += 1
        while index < len(tokens):
            token = tokens[index]
            if token in pairs:
                closing.append(pairs[token])
            elif token in ("]", ")"):
                if token != closing[-1]:
                    raise ValueError("Command list brackets must match.")
                closing.pop()
                if not closing:
                    return tokens[start:index], index + 1
            index += 1
        raise ValueError("Command list is missing a closing bracket or parenthesis.")

    def _run(self, tokens):
        if self.call_depth >= 40:
            raise ValueError("Procedure nesting limit reached.")
        self.call_depth += 1
        output = []
        try:
            index = 0
            while index < len(tokens):
                raw = tokens[index]
                index += 1
                command = self.ALIASES.get(raw.upper(), raw.upper())
                if command in ("REPEAT",):
                    count, index = self._value(tokens, index)
                    count = int(count)
                    body, index = self._group(tokens, index)
                    if not 0 <= count <= 1000:
                        raise ValueError("REPEAT count must be from 0 to 1000.")
                    for _ in range(count):
                        output.extend(self._run(body))
                elif command in ("FD", "BK", "RT", "LT", "SETH", "SETPC", "SETBG", "SETWIDTH", "CIRCLE", "DOT", "PRINT"):
                    value, index = self._value(tokens, index)
                    if command == "FD":
                        distance = float(value)
                        self.x += distance * math.sin(math.radians(self.heading))
                        self.y += distance * math.cos(math.radians(self.heading))
                        self.moves += 1
                        self._graphics("forward", distance)
                        output.append(self.status(f"FORWARD {distance:g}"))
                    elif command == "BK":
                        distance = float(value)
                        self.x -= distance * math.sin(math.radians(self.heading))
                        self.y -= distance * math.cos(math.radians(self.heading))
                        self.moves += 1
                        self._graphics("backward", distance)
                        output.append(self.status(f"BACK {distance:g}"))
                    elif command in ("RT", "LT"):
                        angle = float(value) * (1 if command == "RT" else -1)
                        self.heading = (self.heading + angle) % 360
                        self._graphics("right" if command == "RT" else "left", abs(angle))
                        output.append(self.status(f"TURN {angle:g} degrees"))
                    elif command == "SETH":
                        self.heading = float(value) % 360
                        self._graphics("heading", self.heading)
                        output.append(self.status(f"HEADING {self.heading:g}"))
                    elif command == "SETPC":
                        self.pen_color = str(value)
                        self._graphics("pencolor", self.pen_color)
                        output.append(f"Pen color: {self.pen_color}")
                    elif command == "SETBG":
                        self.background = str(value)
                        self._graphics("background", self.background)
                        output.append(f"Background color: {self.background}")
                    elif command == "SETWIDTH":
                        width = int(value)
                        if width < 1 or width > 50:
                            raise ValueError("Pen width must be from 1 to 50.")
                        self.pen_width = width
                        self._graphics("width", width)
                        output.append(f"Pen width: {width}")
                    elif command == "CIRCLE":
                        radius = float(value)
                        self._graphics("circle", radius)
                        output.append(f"Drew circle with radius {radius:g}; {self.status()}")
                    elif command == "DOT":
                        size = int(value)
                        if size < 1 or size > 200:
                            raise ValueError("DOT size must be from 1 to 200.")
                        self._graphics("dot", size)
                        output.append(f"Drew dot, size {size}")
                    else:
                        output.append(str(value))
                elif command == "MAKE":
                    if index >= len(tokens):
                        raise ValueError('MAKE needs a variable, e.g. MAKE "side 50.')
                    key = tokens[index].removeprefix("LOGO_WORD_").lstrip(":").lower()
                    value, index = self._value(tokens, index + 1)
                    self.variables[key] = value
                    output.append(f"{key} = {value}")
                elif command in ("PU", "PD"):
                    self.pen_down = command == "PD"
                    self._graphics("pendown" if self.pen_down else "penup")
                    output.append("Pen down." if self.pen_down else "Pen up.")
                elif command in ("HOME", "CS"):
                    if command == "CS":
                        self._graphics("clear")
                    self.x, self.y, self.heading = 0.0, 0.0, 0.0
                    self._graphics("home")
                    output.append(self.status("Screen cleared and turtle home." if command == "CS" else "Turtle home."))
                elif command in ("HT", "ST"):
                    self._graphics("hide" if command == "HT" else "show")
                    output.append("Turtle hidden." if command == "HT" else "Turtle visible.")
                elif command == "STATUS":
                    output.append(self.status())
                elif command == "HELP":
                    output.append(self.help_text())
                elif command == "BYE":
                    self.done = True
                    if self.window:
                        self.window.send("close")
                    output.append("Leaving Logo.")
                    break
                elif command in self.procedures:
                    params, body = self.procedures[command]
                    arguments = []
                    for _ in params:
                        value, index = self._value(tokens, index)
                        arguments.append(value)
                    previous = {param: self.variables.get(param) for param in params}
                    had_value = {param: param in self.variables for param in params}
                    self.variables.update(dict(zip(params, arguments)))
                    try:
                        for source in body:
                            output.extend(self._run(self._tokens(source)))
                    finally:
                        for param in params:
                            if had_value[param]:
                                self.variables[param] = previous[param]
                            else:
                                self.variables.pop(param, None)
                else:
                    raise ValueError(f"I don't know how to {raw}. Type HELP for commands.")
        finally:
            self.call_depth -= 1
        return output

    def execute(self, line):
        source = line.strip()
        if not source:
            return ""
        try:
            tokens = self._tokens(source)
            if self.definition:
                if tokens and tokens[0].upper() == "END":
                    name, params, body = self.definition
                    self.procedures[name] = (params, body)
                    self.definition = None
                    return f"Defined {name} with {len(params)} parameter(s)."
                self.definition[2].append(source)
                return ""
            if tokens and tokens[0].upper() == "TO":
                if len(tokens) < 2:
                    return "Usage: TO name [:parameter ...]"
                name = tokens[1].upper()
                params = [token.lstrip(":").lower() for token in tokens[2:]]
                self.definition = [name, params, []]
                return f"Defining {name}. Enter commands, then END."
            results = self._run(tokens)
            status = self.window.error if self.window else None
            if status:
                self.window_message = f"Graphics unavailable: {status}"
                self.graphics_enabled = False
                self.window = None
            if results:
                results.append(self.window_message)
            return "\n".join(results)
        except (ValueError, ArithmeticError, IndexError) as exc:
            return f"Logo: {exc}"

    def status(self, prefix=""):
        direction = "N" if self.heading == 0 else "E" if self.heading == 90 else "S" if self.heading == 180 else "W" if self.heading == 270 else ""
        lead = f"{prefix} | " if prefix else ""
        return f"{lead}position ({self.x:.1f}, {self.y:.1f}), heading {self.heading:.1f}{direction}, pen {'down' if self.pen_down else 'up'}, moves {self.moves}"

    @staticmethod
    def help_text():
        return (
            "Logo commands: FD/BK distance, RT/LT degrees, SETH angle, PU/PD, HOME, CS, "
            "SETPC color, SETBG color, SETWIDTH size, CIRCLE radius, DOT size, HT/ST, STATUS.\n"
            "Programming: REPEAT count [commands] or (commands), TO name :parameters ... END, MAKE \"name value, PRINT value.\n"
            "Values: :variable, SUM a b, DIFFERENCE a b, PRODUCT a b, QUOTIENT a b.\n"
            "Examples: REPEAT 4 (FD 80 RT 90) | MAKE \"side 60 | TO SQUARE :side (then FD :side RT 90; END) | BYE"
        )
