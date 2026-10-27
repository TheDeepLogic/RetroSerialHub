"""Local dashboard palettes inspired by DOS Shell and QBasic."""

import json
from pathlib import Path
import tempfile
import os

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (170, 170, 170)
BLUE = (0, 0, 170)
TEAL = (0, 170, 170)


def palette(title, bar, selection, paper=WHITE, ink=BLACK, border=None):
    return {
        "info": (ink, paper), "bold": (ink, paper),
        "green": ((0, 100, 40), paper),
        "yellow": ((128, 72, 0), paper), "red": ((170, 0, 0), paper),
        "dim": border or (BLACK, GRAY), "cyan": bar,
        "highlight": selection, "active_header": title, "title": title,
    }


THEMES = {
    "Ocean": palette((WHITE, BLUE), (BLACK, TEAL), (WHITE, BLACK)),
    "Turquoise": palette((WHITE, (85, 85, 255)), (BLACK, (85, 255, 255)),
                         (WHITE, (85, 85, 255))),
    "Emerald City": palette((BLACK, (85, 255, 85)), (WHITE, (0, 170, 0)),
                            (BLACK, (85, 255, 85)), border=(WHITE, (0, 170, 0))),
    "Hot Pink": palette((WHITE, (255, 85, 255)), (WHITE, (170, 0, 170)),
                        (BLACK, (255, 85, 255)), border=(WHITE, (170, 0, 170))),
    "Light": palette((WHITE, (85, 85, 85)), (BLACK, GRAY),
                                   (WHITE, (85, 85, 85))),
    "Dark": palette((BLACK, WHITE), (WHITE, (48, 48, 48)),
                    (BLACK, WHITE), paper=BLACK, ink=WHITE,
                    border=(GRAY, BLACK)),
    "QBasic": palette((BLUE, GRAY), (BLACK, TEAL), (BLACK, GRAY),
                      paper=BLUE, ink=WHITE, border=(WHITE, BLUE)),
}
THEMES["Light"].update(
    green=(BLACK, WHITE), yellow=(BLACK, WHITE), red=(BLACK, WHITE))
THEMES["QBasic"].update(green=((85, 255, 85), BLUE),
                         yellow=((255, 255, 85), BLUE), red=((255, 85, 85), BLUE))


def phosphor(ink, paper=BLACK):
    scheme = palette((paper, ink), (paper, ink), (paper, ink),
                     paper=paper, ink=ink, border=(ink, paper))
    scheme.update(green=(ink, paper), yellow=(ink, paper), red=(ink, paper))
    return scheme


THEMES["Commodore"] = phosphor((136, 122, 222), (64, 49, 151))
THEMES["Apple IIGS"] = phosphor(WHITE, BLUE)
# Colors sampled visually from the TI title screen, including its color bars.
TI_CYAN = (48, 230, 240)
THEMES["TI-99/4A"] = palette(
    (WHITE, (85, 75, 235)), (BLACK, (232, 210, 128)),
    (BLACK, (80, 216, 112)), paper=TI_CYAN, ink=BLACK,
    border=(BLACK, TI_CYAN))
THEMES["Windows 95"] = palette(
    (WHITE, (0, 0, 128)), (BLACK, (192, 192, 192)),
    (WHITE, (0, 0, 128)), paper=(192, 192, 192), ink=BLACK,
    border=(BLACK, (192, 192, 192)))
THEMES["Windows 95"]["desktop"] = (BLACK, (0, 128, 128))
THEMES["Windows 3.1"] = palette(
    (WHITE, BLUE), (BLACK, GRAY), (WHITE, BLUE))
THEMES["Amber Monochrome"] = phosphor((255, 176, 0))
THEMES["Green Monochrome"] = phosphor((85, 255, 85))
THEMES["Dark"].update(green=(WHITE, BLACK), yellow=(WHITE, BLACK), red=(WHITE, BLACK))

THEME_ALIASES = {"basic blue": "Windows 3.1",
                 "basic blue / windows 3.1": "Windows 3.1",
                 "windows 3.1": "Windows 3.1"}


class ConsoleTheme:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else None
        self.name = "Ocean"
        self.background = True
        self.colors = True
        if self.path is not None:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    saved_name = data.get("name")
                    if isinstance(saved_name, str):
                        saved_name = THEME_ALIASES.get(saved_name.casefold(), saved_name)
                        if saved_name in THEMES:
                            self.name = saved_name
                    for key in ("background", "colors"):
                        if type(data.get(key)) is bool:
                            setattr(self, key, data[key])
            except (OSError, ValueError, TypeError):
                pass

    def ansi(self, role="info"):
        if not self.colors:
            return "\x1b[0m"
        if not self.background and role not in ("title", "highlight", "active_header", "cyan"):
            # Default terminal colors preserve both transparency and the user's
            # readable foreground; accents use bright terminal palette colors.
            if self.name in ("Commodore", "Apple IIGS", "Amber Monochrome", "Green Monochrome"):
                foreground = ";".join(map(str, THEMES[self.name]["info"][0]))
                return f"\x1b[0;38;2;{foreground};49m"
            foreground = {"green": 92, "yellow": 93, "red": 91,
                          "cyan": 96, "title": 96, "highlight": 93,
                          "active_header": 96}.get(role, 39)
            if self.name in ("Light", "Dark"):
                foreground = 39
            return f"\x1b[0;{foreground};49m"
        foreground, background = THEMES[self.name].get(role, THEMES[self.name]["info"])
        fg = ";".join(map(str, foreground))
        bg = ";".join(map(str, background))
        return f"\x1b[0;38;2;{fg};48;2;{bg}m"

    def save(self):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.path.parent, delete=False) as output:
                temporary = output.name
                json.dump({"name": self.name, "background": self.background,
                           "colors": self.colors}, output, indent=2)
                output.write("\n")
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
