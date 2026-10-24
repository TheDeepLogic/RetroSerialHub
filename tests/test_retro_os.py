import tempfile
import unittest
from pathlib import Path

from retro_os.core import EventBus, Session, Shell
from retro_os.keyboard_profiles import KeyboardProfiles
from retro_os.runtime import create_runtime
from retro_os.viewer import extract_text, paginate_text


class RetroOsCoreTests(unittest.TestCase):
    def test_shell_register_execute_and_help(self):
        shell = Shell()
        shell.register_command("greet", lambda args: "Hello " + " ".join(args))

        self.assertEqual(shell.execute('GREET "retro user"'), "Hello retro user")
        self.assertIn("greet", shell.help())
        self.assertIn("Unknown command", shell.execute("missing"))
        self.assertIn("Syntax error", shell.execute('"unfinished'))

    def test_shell_preserves_windows_paths_and_backslashes(self):
        shell = Shell()
        received = []
        shell.register_command("view", lambda args: received.append(args) or "OK")

        # Quoted Windows path with backslashes
        shell.execute(r'view "D:\OneDrive\Software\text\TRS-80.txt"')
        self.assertEqual(received[-1], [r"D:\OneDrive\Software\text\TRS-80.txt"])

        # Quoted Windows path with spaces and backslashes
        shell.execute(r'view "C:\Program Files\Vintage App\doc.txt"')
        self.assertEqual(received[-1], [r"C:\Program Files\Vintage App\doc.txt"])

        # Unquoted path with backslashes
        shell.execute(r"view D:\Retro\README.txt")
        self.assertEqual(received[-1], [r"D:\Retro\README.txt"])

    def test_event_bus_subscribe_publish_and_unsubscribe(self):
        bus = EventBus()
        events = []
        unsubscribe = bus.subscribe("notify", events.append)
        bus.publish("notify", {"message": "ready"})
        unsubscribe()
        bus.publish("notify", {"message": "ignored"})

        self.assertEqual(events, [{"message": "ready"}])

    def test_keyboard_profiles_persist_per_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            profiles = KeyboardProfiles(path)
            profiles.set_mapping("default", "CTRL+M", "WIN+R")
            loaded = KeyboardProfiles(path)

        self.assertEqual(loaded.get("default")["CTRL+M"], "WIN+R")
        self.assertNotIn("CTRL+M", loaded.get("apple2"))

    def test_runtime_has_required_shell_commands_and_session_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = Session(client_type="telnet", cols=40, user="guest")
            _, bus, _, shell, loader = create_runtime(
                {
                    "notes": root / "notes",
                    "text": root / "text",
                    "files": root / "files",
                    "bookmarks": root / "bookmarks.json",
                    "mail": root / "mail",
                },
                session=session,
                profiles_path=root / "keyboard.json",
            )
            session = loader.context.session

            for name in ("apps", "launch", "view", "kb", "notes", "textlib", "bbs", "browser", "telnet", "ftp", "calc", "mail", "print", "games", "ascii", "ascii_viewer", "help"):
                self.assertIn(name, shell._commands)
            self.assertEqual(session.client_type, "telnet")
            self.assertEqual(session.cols, 40)
            self.assertIn("notes", loader.context.fs)
            received = []
            bus.subscribe("notify", received.append)
            bus.publish("notify", "hello")
            self.assertEqual(received, ["hello"])

    def test_scheduler_lists_and_runs_every_cli_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, bus, host_env, shell, _ = create_runtime(
                {
                    "notes": root / "notes",
                    "text": root / "text",
                    "files": root / "files",
                    "tasks": root / "scheduled_tasks.json",
                },
                session=Session(),
                profiles_path=root / "keyboard.json",
            )
            received = []
            bus.subscribe("notify", received.append)

            command_listing = shell.execute("schedule modules")
            for command_name in shell.command_names():
                self.assertIn(command_name, command_listing)
            self.assertIn("Command: broadcast", shell.execute("schedule info broadcast"))

            task = host_env.scheduler.add_task(
                name="Scheduled Broadcast",
                command="broadcast hello from scheduler",
                schedule_type="interval",
                params={"every": 15},
            )
            self.assertEqual(
                shell.execute(f"schedule run {task['id']}"),
                "hello from scheduler",
            )
            self.assertEqual(received[-1]["message"], "hello from scheduler")

            chained_task = host_env.scheduler.add_task(
                name="Scheduled Update",
                command="calc 1 + 1 : calc 2 + 2 : broadcast update complete",
                schedule_type="interval",
                params={"every": 15},
            )
            self.assertEqual(
                shell.execute(f"schedule run {chained_task['id']}"),
                "2\n\n4\n\nupdate complete",
            )
            self.assertEqual(received[-1]["message"], "update complete")

    def test_scheduler_chained_news_weather_and_broadcast(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, bus, host_env, shell, _ = create_runtime(
                {
                    "notes": root / "notes",
                    "text": root / "text",
                    "files": root / "files",
                    "tasks": root / "scheduled_tasks.json",
                },
                session=Session(),
                profiles_path=root / "keyboard.json",
            )
            broadcast_events = []
            bus.subscribe("scheduler.broadcast", broadcast_events.append)
            notify_events = []
            bus.subscribe("notify", notify_events.append)

            # Override news and weather with predictable outputs for this shell
            shell.register_command("news", lambda _args: "Top Headlines:\n1. Retro Revival")
            shell.register_command("weather", lambda args: f"{' '.join(args)}: +72F, Sunny" if args else "Austin: +72F, Sunny")

            add_res = shell.execute(
                "schedule add MorningBriefing 30 news : weather Austin : broadcast Morning briefing complete"
            )
            self.assertIn("Scheduled task 'MorningBriefing'", add_res)

            run_res = shell.execute("schedule run 1")
            self.assertIn("Top Headlines:\n1. Retro Revival", run_res)
            self.assertIn("Austin: +72F, Sunny", run_res)
            self.assertIn("Morning briefing complete", run_res)

            self.assertEqual(notify_events[-1]["message"], "Morning briefing complete")
            self.assertEqual(len(broadcast_events), 1)
            self.assertIn("Top Headlines", broadcast_events[0]["output"])
            self.assertIn("Austin: +72F, Sunny", broadcast_events[0]["output"])
            self.assertIn("Morning briefing complete", broadcast_events[0]["output"])

            semi_task = host_env.scheduler.add_task(
                name="Semi Task",
                command="calc 5 * 5 ; calc 10 * 10",
                schedule_type="interval",
                params={"every": 15},
            )
            self.assertEqual(
                shell.execute(f"schedule run {semi_task['id']}"),
                "25\n\n100",
            )

            resilient_task = host_env.scheduler.add_task(
                name="Resilient Task",
                command="badcommand1234 : calc 3 * 3",
                schedule_type="interval",
                params={"every": 15},
            )
            self.assertEqual(
                shell.execute(f"schedule run {resilient_task['id']}"),
                "Unknown command: badcommand1234. Type 'help' for commands.\n\n9",
            )

    def test_runtime_commands_keep_their_own_client_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_profiles = root / "first.json"
            second_profiles = root / "second.json"
            _, _, _, first_shell, _ = create_runtime(
                {"notes": root / "first-notes", "text": root / "text", "files": root / "files"},
                session=Session(user="first"),
                profiles_path=first_profiles,
            )
            _, _, _, second_shell, _ = create_runtime(
                {"notes": root / "second-notes", "text": root / "text", "files": root / "files"},
                session=Session(user="second"),
                profiles_path=second_profiles,
            )

            first_shell.execute("kb map CTRL+M WIN+R")

            self.assertTrue(first_profiles.is_file())
            self.assertFalse(second_profiles.exists())

    def test_calculator_and_file_viewer_shell_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text_dir = root / "text"
            text_dir.mkdir()
            (text_dir / "sample.txt").write_text("A line that wraps cleanly.", encoding="utf-8")
            _, _, _, shell, _ = create_runtime(
                {"notes": root / "notes", "text": text_dir, "files": root / "files"},
                session=Session(cols=40),
                profiles_path=root / "keyboard.json",
            )

            self.assertEqual(shell.execute("calc 2 + 3 * 4"), "14")
            output = shell.execute("view sample.txt")
            self.assertIn("A line that wraps cleanly.", output)

    def test_ascii_viewer_shell_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files_dir = root / "files"
            files_dir.mkdir()
            _, _, _, shell, _ = create_runtime(
                {"notes": root / "notes", "text": root / "text", "files": files_dir},
                session=Session(cols=40),
                profiles_path=root / "keyboard.json",
            )

            # Both `ascii` and `ascii_viewer` commands exist
            self.assertIn("Usage: ascii <image_path>", shell.execute("ascii"))
            self.assertIn("Usage: ascii <image_path>", shell.execute("ascii_viewer"))

            # Missing file check
            self.assertIn("Image file not found: missing.png", shell.execute("ascii missing.png"))

    def test_text_games_start_in_session_scoped_states(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = Session(cols=40)
            _, _, _, shell, _ = create_runtime(
                {"notes": root / "notes", "text": root / "text", "files": root / "files"},
                session=session,
                profiles_path=root / "keyboard.json",
            )

            minesweeper = shell.execute("games minesweeper new 4 4 1")
            solitaire = shell.execute("games solitaire new")

            self.assertIn("Mines: 1", minesweeper)
            self.assertIn("1 2 3 4", minesweeper)
            self.assertIn("##", solitaire)
            self.assertIn("Stock:", solitaire)

    def test_document_pagination_wraps_to_supported_terminal_widths(self):
        text = "X" * 41
        self.assertEqual(paginate_text(text, 40), [["X" * 40, "X"]])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.txt"
            path.write_text("text", encoding="utf-8")
            self.assertEqual(extract_text(path), "text")

    def test_runtime_view_command_with_absolute_windows_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doc = root / "TRS-80.txt"
            doc.write_text("TRS-80 Model I documentation line 1\nLine 2", encoding="utf-8")

            _, _, _, shell, _ = create_runtime(
                {"notes": root / "notes", "text": root / "text", "files": root / "files"},
                session=Session(cols=40),
                profiles_path=root / "keyboard.json",
            )

            # Test viewing with exact string representation of Path (includes backslashes on Windows)
            res = shell.execute(f'view "{doc}"')
            self.assertIn("TRS-80 Model I documentation", res)

            # Test viewing with unquoted path
            res_unquoted = shell.execute(f'view {doc}')
            self.assertIn("TRS-80 Model I documentation", res_unquoted)


class ShortcutBridgeTests(unittest.TestCase):
    def test_mapped_control_shortcut_dispatches_to_host(self):
        from rsh_keyboard import KeyboardBridge

        shortcuts = []
        events = []
        bridge = KeyboardBridge(
            send_character=lambda _character: self.fail("unexpected character"),
            send_key=lambda _key: self.fail("unexpected key"),
            send_shortcut=shortcuts.append,
            shortcut_mappings={"CTRL+W": "WIN"},
            on_shortcut=lambda source, action: events.append((source, action)),
        )

        self.assertFalse(bridge.feed(b"\x17"))
        self.assertEqual(shortcuts, ["WIN"])
        self.assertEqual(events, [("CTRL+W", "WIN")])


class RetroOsMenuAndLauncherTests(unittest.TestCase):
    def test_flyout_menu_accordion_expansion(self):
        from retro_os.menu import OSFlyoutMenu

        menu = OSFlyoutMenu(0)
        self.assertEqual(menu.active_section_name, "Communications")
        # Communications has Bulletin Boards as A
        self.assertEqual(menu.get_action_for_key("A"), "bbs")
        self.assertEqual(menu.get_action_for_key("C"), "browser")

        # Select section 2: Host Connectivity (also via alias BRIDGING)
        self.assertTrue(menu.select_section("2"))
        self.assertEqual(menu.active_section_name, "Host Connectivity")
        self.assertEqual(menu.get_action_for_key("A"), "apps")
        self.assertEqual(menu.get_action_for_key("B"), "launch")
        self.assertEqual(menu.get_action_for_key("F"), "host_media")
        self.assertTrue(menu.select_section("BRIDGING"))
        self.assertEqual(menu.active_section_name, "Host Connectivity")

        # Select section by name
        self.assertTrue(menu.select_section("FILES"))
        self.assertEqual(menu.active_section_name, "Files & Media")
        self.assertEqual(menu.get_action_for_key("A"), "files")
        self.assertEqual(menu.get_action_for_key("B"), "view")

        # Select section 4: Games
        self.assertTrue(menu.select_section("4"))
        self.assertEqual(menu.active_section_name, "Games")
        self.assertEqual(menu.get_action_for_key("A"), "mines")
        self.assertEqual(menu.get_action_for_key("B"), "solitaire")
        self.assertEqual(menu.get_action_for_key("C"), "lander")

        # Select section 5: Accessories
        self.assertTrue(menu.select_section("5"))
        self.assertEqual(menu.active_section_name, "Accessories")
        self.assertEqual(menu.get_action_for_key("A"), "notes")
        self.assertEqual(menu.get_action_for_key("B"), "calc")
        self.assertEqual(menu.get_action_for_key("C"), "weather_news")

        # Select section 6: System (by abbreviation)
        self.assertTrue(menu.select_section("sys"))
        self.assertEqual(menu.active_section_name, "System")
        self.assertEqual(menu.get_action_for_key("A"), "cli")
        self.assertEqual(menu.get_action_for_key("E"), "help_menu")

    def test_flyout_menu_rendering_40_and_80_columns(self):
        from retro_os.menu import OSFlyoutMenu

        menu = OSFlyoutMenu(0)
        rendered_80 = menu.render(columns=80)
        self.assertIn("[1] > COMMUNICATIONS <", rendered_80)
        self.assertIn("[2]   HOST CONNECTIVITY", rendered_80)
        self.assertIn("[3]   FILES & MEDIA", rendered_80)
        self.assertIn("[4]   GAMES", rendered_80)
        self.assertIn("[5]   ACCESSORIES", rendered_80)
        self.assertIn("[6]   SYSTEM", rendered_80)
        self.assertIn("A] Bulletin Boards", rendered_80)

        rendered_40 = menu.render(columns=40)
        self.assertIn("[1] > COMMUNICATIONS <", rendered_40)
        for line in rendered_40.split("\r\n"):
            self.assertLessEqual(len(line), 40)

    def test_launch_app_translates_forward_slashes_on_windows(self):
        from retro_os.host_env import HostEnvironment
        from unittest.mock import patch

        host = HostEnvironment()
        executed_commands = []

        def fake_popen(cmd, **kwargs):
            executed_commands.append(cmd)
            class FakeProc:
                pid = 9999
            return FakeProc()

        with patch("subprocess.Popen", side_effect=fake_popen), \
             patch("pathlib.Path.is_file", return_value=True):
            # Pass forward slashes like from an Apple II
            proc = host.launch_app("C:/Windows/notepad.exe", args=["C:/test/file.txt"])
            self.assertEqual(proc.pid, 9999)
            self.assertEqual(len(executed_commands), 1)
            # The command arguments must have backslashes on Windows
            self.assertIn("\\", executed_commands[0][0])
            self.assertNotIn("/", executed_commands[0][0])
            self.assertIn("\\", executed_commands[0][1])
            self.assertNotIn("/", executed_commands[0][1])

    def test_apps_letter_and_query_filtering(self):
        from retro_os.modules import apps as apps_module
        from retro_os.core import Session, Shell

        class DummyContext:
            def __init__(self):
                self.session = Session()
                self.fs = {}
                self.bus = None
                self.host_env = type("DummyHost", (), {
                    "list_apps": lambda self, refresh=False: {
                        "Calculator": "calc.exe",
                        "Command Prompt": "cmd.exe",
                        "Notepad": "notepad.exe",
                        "Paint": "mspaint.exe",
                    }
                })()

        apps_module.init(DummyContext())
        shell = Shell()
        apps_module.register_commands(shell)

        # Filter by letter 'c'
        result_c = shell.execute("apps c")
        self.assertIn("Calculator", result_c)
        self.assertIn("Command Prompt", result_c)
        self.assertNotIn("Notepad", result_c)

        # Filter by query 'note'
        result_note = shell.execute("apps note")
        self.assertIn("Notepad", result_note)
        self.assertNotIn("Calculator", result_note)


class UserShortcutsTests(unittest.TestCase):
    def test_shortcuts_manager_crud_and_persistence(self):
        from retro_os.shortcuts import ShortcutsManager

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "user_shortcuts.json"
            mgr = ShortcutsManager(path)
            self.assertFalse(mgr.has_shortcuts())
            self.assertEqual(mgr.list_shortcuts(), [])

            # Add shortcut with arguments
            sc1 = mgr.add_shortcut("Daily Weather", "view https://wttr.in/Austin?0")
            self.assertEqual(sc1["name"], "Daily Weather")
            self.assertEqual(sc1["command"], "view https://wttr.in/Austin?0")
            self.assertEqual(sc1["id"], 1)
            self.assertTrue(mgr.has_shortcuts())

            sc2 = mgr.add_shortcut("Quick Calc", "calc 50 * 12")
            self.assertEqual(sc2["id"], 2)
            self.assertEqual(len(mgr.list_shortcuts()), 2)

            # Lookup by id (int or str), by letter, by name
            self.assertEqual(mgr.get_shortcut(1)["name"], "Daily Weather")
            self.assertEqual(mgr.get_shortcut("1")["name"], "Daily Weather")
            self.assertEqual(mgr.get_shortcut("A")["name"], "Daily Weather")
            self.assertEqual(mgr.get_shortcut("B")["name"], "Quick Calc")
            self.assertEqual(mgr.get_shortcut("Daily Weather")["command"], "view https://wttr.in/Austin?0")

            # Reload from disk
            loaded = ShortcutsManager(path)
            self.assertEqual(len(loaded.list_shortcuts()), 2)
            self.assertEqual(loaded.list_shortcuts()[0]["name"], "Daily Weather")

            # Delete by letter
            self.assertTrue(loaded.delete_shortcut("A"))
            self.assertEqual(len(loaded.list_shortcuts()), 1)
            self.assertEqual(loaded.list_shortcuts()[0]["name"], "Quick Calc")
            self.assertEqual(loaded.list_shortcuts()[0]["id"], 1)

            # Delete remaining
            self.assertTrue(loaded.delete_shortcut(1))
            self.assertFalse(loaded.has_shortcuts())

    def test_flyout_menu_shortcuts_empty_and_populated_auto_flyout(self):
        from retro_os.menu import OSFlyoutMenu
        from retro_os.shortcuts import ShortcutsManager

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shortcuts.json"
            mgr = ShortcutsManager(path)

            # 1. When empty: defaults to Communications, Shortcuts is section 0
            menu = OSFlyoutMenu(shortcuts_manager=mgr)
            self.assertEqual(menu.active_section_name, "Communications")
            rendered = menu.render(columns=80)
            self.assertIn("[0]   SHORTCUTS", rendered)
            self.assertIn("[1] > COMMUNICATIONS <", rendered)

            # Select section 0 explicitly
            self.assertTrue(menu.select_section("0"))
            self.assertEqual(menu.active_section_name, "Shortcuts")
            self.assertEqual(menu.get_action_for_key("+"), "shortcut_add")
            rendered_sc = menu.render(columns=80)
            self.assertIn("[0] > SHORTCUTS <", rendered_sc)
            self.assertIn("No shortcuts configured yet", rendered_sc)
            self.assertIn("+] Add Shortcut", rendered_sc)

            # 2. Add shortcuts: now menu auto-flies out to Shortcuts!
            mgr.add_shortcut("BBS Direct", "bbs connect 1")
            mgr.add_shortcut("Minesweeper", "games mines 9 9 10")

            menu_populated = OSFlyoutMenu(shortcuts_manager=mgr)
            self.assertEqual(menu_populated.active_section_name, "Shortcuts")
            self.assertEqual(menu_populated.get_action_for_key("A"), "shortcut_run:bbs connect 1")
            self.assertEqual(menu_populated.get_action_for_key("B"), "shortcut_run:games mines 9 9 10")
            self.assertEqual(menu_populated.get_action_for_key("+"), "shortcut_add")
            self.assertEqual(menu_populated.get_action_for_key("-"), "shortcut_del")

            rendered_pop = menu_populated.render(columns=80)
            self.assertIn("[0] > SHORTCUTS <", rendered_pop)
            self.assertIn("A] BBS Direct (bbs connect 1)", rendered_pop)
            self.assertIn("B] Minesweeper (games mines 9 9 10)", rendered_pop)
            self.assertIn("+] Add Shortcut", rendered_pop)
            self.assertIn("-] Remove Shortcut", rendered_pop)

            # 40-column rendering check
            rendered_pop_40 = menu_populated.render(columns=40)
            self.assertIn("[0] > SHORTCUTS <", rendered_pop_40)
            for line in rendered_pop_40.split("\r\n"):
                self.assertLessEqual(len(line), 40)

    def test_shortcut_shell_commands(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            session = Session()
            _, _, _, shell, _ = create_runtime(
                {"notes": root / "notes", "text": root / "text", "files": root / "files"},
                session=session,
                shortcuts_path=root / "shortcuts.json",
            )

            # Initially empty
            self.assertIn("No shortcuts configured", shell.execute("shortcut list"))

            # Add shortcut
            add_res = shell.execute('shortcut add "Quick Math" calc 25 * 4')
            self.assertIn("added", add_res)

            # List
            list_res = shell.execute("shortcut list")
            self.assertIn("Quick Math", list_res)
            self.assertIn("calc 25 * 4", list_res)

            # Run shortcut
            run_res = shell.execute("shortcut run A")
            self.assertEqual(run_res, "100")

            # Delete shortcut
            del_res = shell.execute("shortcut del A")
            self.assertIn("deleted", del_res)
            self.assertIn("No shortcuts configured", shell.execute("shortcut list"))

    def test_launch_command_modes_and_flags(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            session = Session()
            activate_mock = MagicMock()
            _, _, _, shell, _ = create_runtime(
                {"notes": root / "notes", "text": root / "text", "files": root / "files"},
                session=session,
                activate_module=activate_mock,
            )

            # Usage on empty args
            usage = shell.execute("launch")
            self.assertIn("Usage: launch", usage)
            self.assertIn("-i", usage)
            self.assertIn("-k", usage)

            # Interactive flag (-i)
            res_i = shell.execute("launch -i notepad readme.txt")
            self.assertIn("interactive terminal", res_i.lower())
            activate_mock.assert_called_with(("app_interactive", "notepad", ["readme.txt"]))

            # Terminal alias flag (--terminal)
            res_t = shell.execute("launch --terminal cmd.exe")
            self.assertIn("interactive terminal", res_t.lower())
            activate_mock.assert_called_with(("app_interactive", "cmd.exe", []))

            # Keyboard bridge flag (-k)
            res_k = shell.execute("launch -k notepad.exe")
            self.assertIn("keyboard bridge", res_k.lower())
            activate_mock.assert_called_with(("app_keyboard", "notepad.exe", []))

    def test_host_env_find_app_and_interactive_launch(self):
        from retro_os.host_env import HostEnvironment
        from unittest.mock import patch, MagicMock

        host = HostEnvironment()

        # Mock list_apps on scanner
        with patch.object(host.apps, "list_apps", return_value={"CustomApp": "C:\\Tools\\custom.exe"}):
            self.assertEqual(host.find_app("customapp"), "C:\\Tools\\custom.exe")
            self.assertEqual(host.find_app("CustomApp"), "C:\\Tools\\custom.exe")

        # Test interactive launch creates pipes
        popen_mock = MagicMock()
        with patch("subprocess.Popen", popen_mock), \
             patch("pathlib.Path.is_file", return_value=True):
            host.launch_app("C:\\Windows\\notepad.exe", args=["test.txt"], interactive=True)
            self.assertTrue(popen_mock.called)
            _, kwargs = popen_mock.call_args
            import subprocess
            self.assertEqual(kwargs.get("stdin"), subprocess.PIPE)
            self.assertEqual(kwargs.get("stdout"), subprocess.PIPE)
            self.assertEqual(kwargs.get("stderr"), subprocess.STDOUT)

    def test_write_crlf_normalization(self):
        from unittest.mock import MagicMock
        import importlib
        rsh = importlib.import_module("RETRO_SERIAL_HUB")

        ser = MagicMock()
        # Bare \n converted to \r\n
        rsh.write(ser, "Line 1\nLine 2\n")
        ser.write.assert_called_with(b"Line 1\r\nLine 2\r\n")

        # Existing \r\n not doubled
        ser.reset_mock()
        rsh.write(ser, "Line 1\r\nLine 2\r\n")
        ser.write.assert_called_with(b"Line 1\r\nLine 2\r\n")

        # Mixed \r\n and bare \n
        ser.reset_mock()
        rsh.write(ser, "Line 1\r\nLine 2\nLine 3")
        ser.write.assert_called_with(b"Line 1\r\nLine 2\r\nLine 3")

    def test_solitaire_column_widths_and_moves(self):
        from retro_os.modules import games as games_module
        from retro_os.core import Session, Shell

        class DummyContext:
            def __init__(self, cols=40):
                self.session = Session(cols=cols)
                self.fs = {}
                self.bus = None
                self.host_env = None

        ctx40 = DummyContext(cols=40)
        games_module.init(ctx40)
        reg = Shell()
        games_module.register_commands(reg)

        # Start new game on 40 cols
        status40 = reg.execute("solitaire new")
        for line in status40.split("\n"):
            self.assertLessEqual(len(line), 40, f"Line too long for 40 cols: {line!r}")

        # Start new game on 80 cols
        ctx80 = DummyContext(cols=80)
        games_module.init(ctx80)
        status80 = reg.execute("solitaire new")
        self.assertIn("Stock:", status80)
        self.assertIn("Waste:", status80)
        self.assertIn("Foundations:", status80)

        # Test move to foundation with auto-match 'f'
        game = games_module._cards[ctx80.session.id]
        # Set top card of column 1 to Ace of Spades
        game["tableau"][0] = [("A", "S", "B")]
        game["face_up"][0] = 1
        res = reg.execute("solitaire move 1 f")
        self.assertIn("1: --", res)
        self.assertIn("AS", res)

        # Test move stack to another tableau column
        game["tableau"][0] = [("7", "D", "R"), ("6", "C", "B")]
        game["face_up"][0] = 2
        game["tableau"][1] = [("8", "S", "B")]
        game["face_up"][1] = 1
        res_m = reg.execute("solitaire move 1 2")
        self.assertIn("1: --", res_m)
        self.assertIn("2: 8S 7D 6C", res_m)
        self.assertEqual(game["face_up"][1], 3)

    def test_host_env_get_host_shell(self):
        from retro_os.host_env import HostEnvironment
        import platform
        he = HostEnvironment()
        shell_info = he.get_host_shell()
        self.assertIn("system", shell_info)
        self.assertIn("default_shell", shell_info)
        self.assertIn("default_args", shell_info)
        self.assertIn("default_name", shell_info)
        if platform.system() == "Windows":
            self.assertEqual(shell_info["system"], "Windows")
            self.assertTrue(shell_info["default_shell"].lower().endswith("cmd.exe"))
            self.assertEqual(shell_info["alt_shell"], "powershell.exe")

    def test_menu_bridging_host_terminal(self):
        import RETRO_SERIAL_HUB
        self.assertTrue(hasattr(RETRO_SERIAL_HUB, "platform"))
        self.assertTrue(callable(RETRO_SERIAL_HUB.platform.system))
        self.assertTrue(callable(RETRO_SERIAL_HUB.platform.machine))

        from retro_os.menu import OSFlyoutMenu
        menu = OSFlyoutMenu()
        menu.select_section("2")
        self.assertEqual(menu.active_section_name, "Host Connectivity")
        action = menu.get_action_for_key("E")
        self.assertEqual(action, "host_terminal")
        rendered = menu.render(columns=80)
        self.assertIn("E] Host Terminal / Prompt", rendered)
        rendered_40 = menu.render(columns=40)
        self.assertIn("E] Host Terminal / Prompt", rendered_40)

    def test_runtime_terminal_and_cmd_commands(self):
        from retro_os.runtime import create_runtime
        from retro_os.core import Session
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            fs = {"notes": tmpdir, "text": tmpdir, "bookmarks": tmpdir, "files": tmpdir}
            session = Session()
            activated = []
            session, bus, host_env, shell, loader = create_runtime(
                fs,
                session=session,
                activate_module=lambda req: activated.append(req),
            )
            # Default terminal quick launch
            out = shell.execute("terminal")
            self.assertIn("Opening host terminal", out)
            self.assertEqual(len(activated), 1)
            self.assertEqual(activated[0][0], "host_terminal")

            # Command prompt alias
            activated.clear()
            out_cmd = shell.execute("cmd")
            self.assertIn("Opening host terminal", out_cmd)
            self.assertEqual(activated[0][0], "host_terminal")
            self.assertIn("cmd.exe", activated[0][1].lower())

            # Powershell argument
            activated.clear()
            out_ps = shell.execute("terminal powershell")
            self.assertIn("Opening host terminal", out_ps)
            self.assertEqual(activated[0][0], "host_terminal")
            self.assertIn("powershell", activated[0][1].lower())


class RetroWorkstationCompanionTests(unittest.TestCase):
    def test_sysinfo_and_format_sysinfo(self):
        from retro_os.host_env import HostEnvironment
        he = HostEnvironment()
        info = he.get_sysinfo()
        self.assertIn("system", info)
        self.assertIn("cpus", info)
        self.assertIn("ram_total_mb", info)
        self.assertIn("disk_total_gb", info)

        fmt80 = he.format_sysinfo(cols=80)
        self.assertIn("HOST SYSTEM MONITOR", fmt80)
        self.assertIn("Logical Cores", fmt80)
        self.assertIn("Physical Memory", fmt80)

        fmt40 = he.format_sysinfo(cols=40)
        for line in fmt40.split("\n"):
            self.assertLessEqual(len(line), 40)

    def test_clipboard_bridge_and_shell_commands(self):
        from retro_os.runtime import create_runtime
        from retro_os.core import Session
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            fs = {"notes": tmpdir, "text": tmpdir, "bookmarks": tmpdir, "files": tmpdir}
            session = Session()
            session, bus, host_env, shell, loader = create_runtime(fs, session=session)

            # Test set clipboard
            res = shell.execute("clip Hello Retro World")
            self.assertIn("Copied 17 characters", res)

            # Test get clipboard
            res_get = shell.execute("clip")
            self.assertIn("Hello Retro World", res_get)

            # Test copy alias
            res_copy = shell.execute("copy Another string")
            self.assertIn("Copied 14 characters", res_copy)

    def test_media_control_and_shell_commands(self):
        from retro_os.runtime import create_runtime
        from retro_os.core import Session
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            fs = {"notes": tmpdir, "text": tmpdir, "bookmarks": tmpdir, "files": tmpdir}
            session = Session()
            session, bus, host_env, shell, loader = create_runtime(fs, session=session)

            self.assertIn("Host media command sent: play", shell.execute("media play"))
            self.assertIn("Host media command sent: next", shell.execute("media next"))
            self.assertIn("Host media command sent: vol_up", shell.execute("vol up"))
            self.assertIn("Host media command sent: vol_down", shell.execute("vol down"))
            self.assertIn("Host media command sent: mute", shell.execute("vol mute"))

    def test_weather_news_and_briefing_clean_ascii(self):
        from retro_os.news import _clean_ascii, get_news
        from retro_os.weather_news import get_news as legacy_get_news
        from retro_os.weather_news import get_weather, get_briefing
        from retro_os.scheduler import MODULE_USAGE_INFO
        from unittest.mock import patch

        self.assertIn("weather", MODULE_USAGE_INFO)
        self.assertIn("news", MODULE_USAGE_INFO)
        self.assertIs(legacy_get_news, get_news)

        # Clean ASCII translates special unicode quotes, degrees, and dashes
        dirty = "\u201cHello\u201d 72\u00b0F \u2014 world\u2026"
        clean = _clean_ascii(dirty)
        self.assertEqual(clean, '"Hello" 72 degF -- world...')

        # Mock urllib.request.urlopen for weather
        fake_weather = b"Austin: +72F, Sunny, Wind 5mph"
        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.return_value = fake_weather
            out = get_weather("Austin")
            self.assertIn("Austin", out)
            self.assertIn("72F", out)

        # Mock RSS feed for news
        fake_rss = b"""<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Retro Computing Revival</title>
                    <description>Serial terminals make a comeback.</description>
                </item>
            </channel>
        </rss>"""
        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.return_value = fake_rss
            out_news = get_news("npr", count=1)
            self.assertIn("Retro Computing Revival", out_news)

        # Desk Briefing on 40 and 80 cols
        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.side_effect = [fake_weather, fake_rss]
            brief_40 = get_briefing(columns=40)
            for line in brief_40.split("\n"):
                self.assertLessEqual(len(line), 40)

    def test_news_article_reading_and_shell_integration(self):
        from retro_os.news import (
            fetch_news_items,
            get_news,
            get_article_by_index,
            get_full_article_by_index,
            format_article,
        )
        from retro_os.runtime import create_runtime
        from retro_os.core import Session
        import tempfile
        from unittest.mock import patch

        fake_rss = b"""<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Apple II Breakthrough</title>
                    <link>https://example.com/apple2</link>
                    <description>&lt;p&gt;New expansion card released.&lt;/p&gt;</description>
                    <pubDate>Mon, 12 Oct 2026 12:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>Commodore 64 Mod</title>
                    <link>https://example.com/c64</link>
                    <description>WiFi modem tested at 9600 baud.</description>
                    <pubDate>Mon, 12 Oct 2026 13:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""

        with patch("urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.return_value = fake_rss
            items = fetch_news_items("npr", count=2)
            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["title"], "Apple II Breakthrough")
            self.assertEqual(items[0]["summary"], "New expansion card released.")
            self.assertEqual(items[0]["link"], "https://example.com/apple2")
            self.assertEqual(items[1]["title"], "Commodore 64 Mod")

            # Article formatting
            art1 = format_article(items[0])
            self.assertIn("Article [1]: Apple II Breakthrough", art1)
            self.assertIn("New expansion card released.", art1)
            self.assertIn("https://example.com/apple2", art1)

            # Get article by index (1-based)
            read_1 = get_article_by_index(1)
            self.assertIn("Article [1]: Apple II Breakthrough", read_1)

            read_2 = get_article_by_index(2)
            self.assertIn("Commodore 64 Mod", read_2)
            self.assertIn("WiFi modem tested at 9600 baud.", read_2)

            read_invalid = get_article_by_index(99)
            self.assertIn("Article [99] not found", read_invalid)

            # Full article extraction using viewer mock
            with patch("retro_os.viewer.extract_text_from_url", return_value="Detailed article web contents."):
                full_art = get_full_article_by_index(1)
                self.assertIn("Full Web Article [1]", full_art)
                self.assertIn("Detailed article web contents.", full_art)

        # Runtime shell command integration
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = {"notes": tmpdir, "text": tmpdir, "bookmarks": tmpdir, "files": tmpdir}
            session = Session()
            session, bus, host_env, shell, loader = create_runtime(fs, session=session)

            with patch("urllib.request.urlopen") as mock_url:
                mock_url.return_value.__enter__.return_value.read.return_value = fake_rss
                headlines_res = shell.execute("news")
                self.assertIn("Apple II Breakthrough", headlines_res)
                self.assertIn("Commodore 64 Mod", headlines_res)

                # Type article number directly in shell: 'news 1'
                art1_res = shell.execute("news 1")
                self.assertIn("Article [1]: Apple II Breakthrough", art1_res)

                # 'news read 2'
                art2_res = shell.execute("news read 2")
                self.assertIn("Article [2]: Commodore 64 Mod", art2_res)

                # 'news 1 full'
                with patch("retro_os.viewer.extract_text_from_url", return_value="Webpage body text."):
                    full_res = shell.execute("news 1 full")
                    self.assertIn("Webpage body text.", full_res)

    def test_hardware_settings_commands_and_serial_tuning(self):
        from retro_os.runtime import create_runtime
        from retro_os.core import Session
        import tempfile
        from unittest.mock import MagicMock
        import importlib

        rsh = importlib.import_module("RETRO_SERIAL_HUB")

        with tempfile.TemporaryDirectory() as tmpdir:
            fs = {"notes": tmpdir, "text": tmpdir, "bookmarks": tmpdir, "files": tmpdir}
            session = Session()
            activated = []
            session, bus, host_env, shell, loader = create_runtime(
                fs,
                session=session,
                activate_module=lambda req: activated.append(req),
            )

            # Caps command
            self.assertIn("OFF", shell.execute("caps"))
            res_on = shell.execute("caps on")
            self.assertIn("ON", res_on)
            self.assertTrue(session.caps_only)
            self.assertEqual(activated[-1], ("set_caps", True))

            # Pacing command
            self.assertIn("0 ms", shell.execute("pace"))
            res_p = shell.execute("pace 2")
            self.assertIn("2 ms", res_p)
            self.assertEqual(session.pace_delay, 0.002)
            self.assertEqual(activated[-1], ("set_pace", 0.002))

            # Columns command
            self.assertIn("80 columns", shell.execute("cols"))
            res_c = shell.execute("cols 40")
            self.assertIn("40", res_c)
            self.assertEqual(session.cols, 40)
            self.assertEqual(activated[-1], ("set_columns", 40))

            # ANSI command
            res_a = shell.execute("ansi off")
            self.assertIn("OFF", res_a)
            self.assertEqual(activated[-1], ("set_ansi", False))

        # Test rsh.write() with caps_only
        ser = MagicMock()
        ser._rsh_caps_only = True
        ser._rsh_pace_delay = 0.0
        rsh.write(ser, "hello world")
        ser.write.assert_called_with(b"HELLO WORLD")

    def test_direct_file_transfers_from_shell(self):
        from retro_os.runtime import create_runtime
        from retro_os.core import Session
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            fs = {"notes": tmpdir, "text": tmpdir, "bookmarks": tmpdir, "files": tmpdir}
            session = Session()
            activated = []
            session, bus, host_env, shell, loader = create_runtime(
                fs,
                session=session,
                activate_module=lambda req: activated.append(req),
            )

            # xsend
            out = shell.execute("xsend test.bin")
            self.assertIn("Starting XMODEM send", out)
            self.assertEqual(activated[-1], ("file_transfer", "XMODEM_SEND", "test.bin"))

            # ysend
            out = shell.execute("ysend test.bin")
            self.assertIn("Starting YMODEM send", out)
            self.assertEqual(activated[-1], ("file_transfer", "YMODEM_SEND", "test.bin"))

            # asend
            out = shell.execute("asend test.txt")
            self.assertIn("Starting ASCII send", out)
            self.assertEqual(activated[-1], ("file_transfer", "ASCII_SEND", "test.txt"))

            # xrecv
            out = shell.execute("xrecv received.bin")
            self.assertIn("Starting XMODEM receive", out)
            self.assertEqual(activated[-1], ("file_transfer", "XMODEM_RECV", "received.bin"))

    def test_menu_bridging_system_media_and_terminal_settings(self):
        from retro_os.menu import OSFlyoutMenu
        menu = OSFlyoutMenu()

        # Host Connectivity section: Host Terminal (E), System Monitor & Media (F)
        menu.select_section("2")
        self.assertEqual(menu.active_section_name, "Host Connectivity")
        self.assertEqual(menu.get_action_for_key("F"), "host_media")

        # Games section: Minesweeper (A), Solitaire (B), Lunar Lander (C)
        menu.select_section("4")
        self.assertEqual(menu.active_section_name, "Games")
        self.assertEqual(menu.get_action_for_key("A"), "mines")
        self.assertEqual(menu.get_action_for_key("B"), "solitaire")
        self.assertEqual(menu.get_action_for_key("C"), "lander")

        # Accessories section: Weather & News (C)
        menu.select_section("5")
        self.assertEqual(menu.active_section_name, "Accessories")
        self.assertEqual(menu.get_action_for_key("C"), "weather_news")

        # System section: Terminal Settings (C), Help & User Guide (E)
        menu.select_section("6")
        self.assertEqual(menu.active_section_name, "System")
        self.assertEqual(menu.get_action_for_key("C"), "terminal_settings")
        self.assertEqual(menu.get_action_for_key("E"), "help_menu")

    def test_help_data_topics(self):
        from retro_os.help_data import get_help_topics, get_topic_content, HELP_TOPICS
        topics = get_help_topics()
        self.assertEqual(len(topics), 9)
        self.assertEqual(topics[0][0], "1")
        self.assertIn("Retro Serial Hub", topics[0][1])

        # Test topic retrieval
        content1 = get_topic_content("1")
        self.assertIn("WHAT IS RETRO SERIAL HUB?", content1)
        content_games = get_topic_content("games")
        self.assertIn("RETRO GAMES GUIDE", content_games)
        content_hotkeys = get_topic_content("9")
        self.assertIn("QUICK REFERENCE & HOTKEYS", content_hotkeys)

    def test_integrated_hub_mail_and_commands(self):
        from retro_os.mail_service import MailManager
        from retro_os.runtime import create_runtime
        from retro_os.core import Session
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mail_dir = Path(tmpdir) / "mail"
            session = Session()
            session.user = "APPLE2"
            session.client_type = "Serial"
            session.cols = 80

            mgr = MailManager(mail_dir=mail_dir, session=session)
            self.assertEqual(mgr.get_mode(), "hub")
            self.assertIn("APPLE2 [Serial]", mgr.get_sender_identity())

            # Send a hub message
            msg = mgr.send_hub_message(
                to="All",
                subject="Hello Retro World",
                body="Testing hub mail transmission.",
            )
            self.assertEqual(msg["id"], 2)
            self.assertEqual(msg["subject"], "Hello Retro World")
            self.assertFalse(msg["read"])

            # Check inbox formatting
            inbox_text = mgr.format_hub_inbox(columns=80)
            self.assertIn("INTEGRATED HUB MAILBOX", inbox_text)
            self.assertIn("Hello Retro World", inbox_text)
            self.assertIn("APPLE2 [Serial]", inbox_text)

            # Read message
            read_text = mgr.format_hub_message(2, columns=80)
            self.assertIn("Testing hub mail transmission.", read_text)
            # Should now be marked read
            msg_after = mgr.get_hub_message(2)
            self.assertTrue(msg_after["read"])

            # Toggle mode
            new_mode = mgr.toggle_mode()
            self.assertEqual(new_mode, "internet")
            self.assertEqual(mgr.get_mode(), "internet")

            # Test through shell runtime
            fs = {
                "notes": tmpdir,
                "text": tmpdir,
                "bookmarks": tmpdir,
                "files": tmpdir,
                "mail": str(mail_dir),
            }
            activated = []
            _, _, _, shell, _ = create_runtime(
                fs,
                session=session,
                activate_module=lambda name, *a: activated.append((name, *a)),
            )
            out_inbox = shell.execute("mail hub")
            self.assertIn("INTEGRATED HUB MAILBOX", out_inbox)
            out_mode = shell.execute("mail mode hub")
            self.assertIn("Default mail mode set to: Integrated Hub Mailbox", out_mode)

    def test_realtime_sysinfo_and_top_commands(self):
        from retro_os.runtime import create_runtime
        from retro_os.core import Session
        import RETRO_SERIAL_HUB as rsh
        from unittest.mock import MagicMock
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            fs = {"notes": tmpdir, "text": tmpdir, "bookmarks": tmpdir, "files": tmpdir}
            session = Session()
            session.cols = 80
            activated = []
            session, bus, host_env, shell, loader = create_runtime(
                fs,
                session=session,
                activate_module=lambda req: activated.append(req),
            )

            # sysinfo static
            static_out = shell.execute("sysinfo")
            self.assertIn("HOST SYSTEM MONITOR", static_out)
            self.assertEqual(len(activated), 0)

            # sysinfo live activates sysinfo_live
            live_out = shell.execute("sysinfo live")
            self.assertIn("real-time", live_out.lower())
            self.assertEqual(len(activated), 1)
            self.assertEqual(activated[0], ("sysinfo_live",))
            self.assertEqual(session.active_module, "sysinfo")

            # top command defaults to live
            activated.clear()
            top_out = shell.execute("top")
            self.assertIn("real-time", top_out.lower())
            self.assertEqual(activated[0], ("sysinfo_live",))

            # top snapshot returns static
            activated.clear()
            top_snap = shell.execute("top -s")
            self.assertIn("HOST SYSTEM MONITOR", top_snap)
            self.assertEqual(len(activated), 0)

            # Test delta CPU calculation in get_sysinfo
            info1 = host_env.get_sysinfo()
            self.assertIn("timestamp", info1)
            self.assertIn("cpus", info1)

            # Test host_env.format_sysinfo includes timestamp
            fmt = host_env.format_sysinfo(cols=80)
            self.assertIn("HOST SYSTEM MONITOR", fmt)
            self.assertIn("Time", fmt)

            # Test format_sysinfo with cpu_load present
            info_mock = host_env.get_sysinfo()
            host_env._last_cpu_times = (100, 100, 100) if host_env.get_sysinfo()["system"] == "Windows" else (100, 200)
            fmt_load = host_env.format_sysinfo(cols=80)
            self.assertIn("HOST SYSTEM MONITOR", fmt_load)

            # Test 40-column format
            fmt40 = host_env.format_sysinfo(cols=40)
            self.assertIn("CPU", fmt40)
            for line in fmt40.split("\n"):
                self.assertLessEqual(len(line), 40)


if __name__ == "__main__":
    unittest.main()
