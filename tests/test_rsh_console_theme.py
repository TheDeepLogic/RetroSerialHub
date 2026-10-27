import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from rsh_console import ConsoleDashboard
from rsh_console_theme import ConsoleTheme, THEMES


class ConsoleThemeTests(unittest.TestCase):
    def test_exact_requested_schemes_and_ocean_default(self):
        self.assertEqual(list(THEMES), ["Ocean", "Turquoise",
                                      "Emerald City", "Hot Pink", "Light", "Dark", "QBasic",
                                      "Commodore", "Apple IIGS", "TI-99/4A", "Windows 95", "Windows 3.1",
                                      "Amber Monochrome", "Green Monochrome"])
        theme = ConsoleTheme()
        self.assertEqual(theme.name, "Ocean")
        self.assertIn("48;2;255;255;255", theme.ansi())
        theme.name = "QBasic"
        self.assertIn("48;2;0;0;170", theme.ansi())
        self.assertEqual(THEMES["Light"]["info"], ((0, 0, 0), (255, 255, 255)))
        self.assertEqual(THEMES["Dark"]["info"], ((255, 255, 255), (0, 0, 0)))
        self.assertEqual(THEMES["TI-99/4A"]["info"], ((0, 0, 0), (48, 230, 240)))

    def test_local_selection_persists_and_never_reaches_host_session(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "console_theme.json"
            dashboard = ConsoleDashboard({}, theme_path=path)
            terminal = MagicMock()
            dashboard.set_host_terminal(terminal)
            dashboard.host_input_available = lambda: True
            for name in THEMES:
                dashboard.handle_host_command("theme " + name)
                self.assertEqual(ConsoleTheme(path).name, name)
            dashboard.handle_host_command("theme background off")
            dashboard.handle_host_command("theme colors off")
            restored = ConsoleTheme(path)
            self.assertFalse(restored.background)
            self.assertFalse(restored.colors)
            terminal.submit.assert_not_called()
            before = path.read_bytes()
            dashboard.handle_host_command("theme nonexistent")
            dashboard.handle_host_command("theme background maybe")
            self.assertEqual(path.read_bytes(), before)
            dashboard.host_input_available = lambda: False
            dashboard.handle_host_command("theme Ocean")
            self.assertEqual(path.read_bytes(), before)

    def test_password_input_is_not_intercepted_as_theme_command(self):
        dashboard = ConsoleDashboard({})
        terminal = MagicMock(secret_input=True)
        dashboard.set_host_terminal(terminal)
        dashboard.host_input_available = lambda: True
        dashboard.handle_host_command("theme Hot Pink")
        terminal.submit.assert_called_once_with("theme Hot Pink")
        self.assertEqual(dashboard._theme.name, "Ocean")

    def test_basic_blue_saved_name_and_both_windows31_aliases(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "console_theme.json"
            path.write_text('{"name": "Basic Blue", "background": false}', encoding="utf-8")
            dashboard = ConsoleDashboard({}, theme_path=path)
            self.assertEqual(dashboard._theme.name, "Windows 3.1")
            self.assertFalse(dashboard._theme.background)
            dashboard.set_host_terminal(MagicMock())
            dashboard.host_input_available = lambda: True
            for name in ("Windows 95", "Basic Blue", "Windows 3.1"):
                dashboard.handle_host_command("theme " + name)
                expected = name if name == "Windows 95" else "Windows 3.1"
                self.assertEqual(ConsoleTheme(path).name, expected)

    def test_corrupt_settings_and_failed_save_preserve_working_theme(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "console_theme.json"
            for data in ("{broken", "[]", '{"name": [], "background": false}',
                         '{"name": "Unknown", "background": "off"}'):
                path.write_text(data, encoding="utf-8")
                self.assertEqual(ConsoleTheme(path).name, "Ocean")
            dashboard = ConsoleDashboard({}, theme_path=path)
            dashboard.set_host_terminal(MagicMock())
            dashboard.host_input_available = lambda: True
            with patch.object(dashboard._theme, "save", side_effect=OSError("Disk full")):
                dashboard.handle_host_command("theme QBasic")
            self.assertEqual(dashboard._theme.name, "Ocean")

    def test_background_off_preserves_bars_and_highlights_in_all_layouts(self):
        dashboard = ConsoleDashboard({})
        dashboard._color = True
        dashboard.set_host_terminal(MagicMock())
        dashboard.host_input_available = lambda: True
        dashboard.set_user_activity("client", "calc", user_label="APPLE2")
        dashboard.append_host_output("Visible menu\n")
        for name in THEMES:
            dashboard._theme.name = name
            for enabled in (True, False):
                dashboard._theme.background = enabled
                for size in ((150, 40), (100, 40)):
                    output = io.StringIO()
                    with patch("rsh_console.sys.stdout", output), patch("shutil.get_terminal_size",
                               return_value=os.terminal_size(size)):
                        dashboard._draw_frame()
                    rendered = output.getvalue()
                    self.assertIn("Visible menu", rendered)
                    self.assertIn("APPLE2", rendered)
                    self.assertIn("48;2;", rendered)
                    if not enabled:
                        self.assertIn(";49m", rendered)
                    self.assertTrue(rendered.endswith("\x1b[?25h"))
        dashboard._theme.colors = False
        self.assertEqual(dashboard._paint("plain", "title"), "plain")

    def test_no_color_environment_retains_plain_output(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}), patch("rsh_console.sys.stdout.isatty", return_value=True):
            dashboard = ConsoleDashboard({})
        self.assertEqual(dashboard._paint("text", "title"), "text")

    def test_phosphor_schemes_preserve_their_ink_without_backgrounds(self):
        theme = ConsoleTheme()
        for name in ("Commodore", "Apple IIGS", "Amber Monochrome", "Green Monochrome"):
            theme.name = name
            for role in ("green", "yellow", "red"):
                self.assertEqual(THEMES[name][role], THEMES[name]["info"])
            theme.background = False
            expected = ";".join(map(str, THEMES[name]["info"][0]))
            for role in THEMES[name]:
                if role not in ("title", "highlight", "active_header", "cyan"):
                    self.assertIn("38;2;" + expected + ";49m", theme.ansi(role))

    def test_background_switch_only_removes_panel_backgrounds(self):
        theme = ConsoleTheme()
        highlights = {"title", "highlight", "active_header", "cyan"}
        for name in THEMES:
            theme.name = name
            theme.background = True
            original = {role: theme.ansi(role) for role in THEMES[name]}
            theme.background = False
            for role in original:
                if role in highlights:
                    self.assertEqual(theme.ansi(role), original[role])
                else:
                    self.assertNotIn("48;2;", theme.ansi(role))
                    self.assertIn(";49m", theme.ansi(role))
        theme.colors = False
        self.assertEqual(theme.ansi("title"), "\x1b[0m")


if __name__ == "__main__":
    unittest.main()
