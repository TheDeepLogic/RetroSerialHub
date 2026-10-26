"""Behavioral coverage for persistent tools, filesystem boundaries, and playback."""

import datetime as dt
import pathlib
import tempfile
import socket
import threading
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from retro_os.audio_player import AudioPlayer, AudioTool
from retro_os.core import EventBus, ModuleContext, ModuleLoader, Session, Shell
from retro_os.modules import toolkit as toolkit_module
from retro_os.menu import OSFlyoutMenu
from retro_os.toolkit import CalendarTool, ContactsTool, Converter, FileTools


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.files = self.root / "files"
        self.files.mkdir()
        self.actions = []
        self.shell = Shell()
        host = SimpleNamespace(shell=self.shell)
        self.context = ModuleContext(Session(), {"files": self.files}, EventBus(), host, self.actions.append)
        self.loader = ModuleLoader(self.context, self.shell)
        self.loader.load("toolkit")

    def test_calendar_persists_and_emits_due_reminder_once_across_sessions(self):
        when = dt.datetime.now() - dt.timedelta(minutes=1)
        result = self.shell.execute(f'calendar add {when:%Y-%m-%d %H:%M} "Retro club meeting"')
        self.assertIn("saved", result)
        other = CalendarTool(self.root / "settings" / "local" / "appointments.json")
        self.assertIn("Retro club meeting", other.connection_reminders())
        self.assertIn("Retro club meeting", other.due())
        self.assertEqual(self.context.host_env.calendar_tool.due(), "")
        identifier = result.split()[1]
        self.shell.execute(f"calendar done {identifier}")
        self.assertEqual(other.connection_reminders(), "")
        self.assertNotIn("Retro club meeting", other.agenda())

    def test_calendar_month_and_invalid_date(self):
        self.assertIn("February 2028", self.shell.execute("calendar month 2028-02"))
        self.assertIn("Could not complete", self.shell.execute("calendar add 2026-02-30 09:00 nope"))

    def test_converter_dimensions_temperatures_and_bases(self):
        for args, expected in [(["1", "mi", "km"], "1.609344"),
                               (["32", "F", "C"], "= 0 c"),
                               (["FF", "hex", "bin"], "11111111"),
                               (["1", "gal", "l"], "3.785411784")]:
            self.assertIn(expected, Converter.command(args))
        self.assertIn("same kind", self.shell.execute("convert 1 kg km"))
        self.assertIn("absolute zero", self.shell.execute("convert -1 K C"))
        self.assertIn("finite", self.shell.execute("convert nan m ft"))

    def test_contacts_reload_search_draft_and_bbs_action(self):
        response = self.shell.execute('contacts add "Retro Friend"')
        identifier = response.split()[1]
        self.shell.execute(f"contacts set {identifier} email retro@example.org")
        self.shell.execute(f"contacts set {identifier} bbs bbs.example.org:6400")
        other = ContactsTool(self.root / "settings" / "local" / "contacts.json", self.context)
        self.assertIn("Retro Friend", other.command(["list", "friend"]))
        self.assertIn("6400", other.command(["show", identifier]))
        received = []
        self.shell.register_command("mail", lambda args: received.append(args) or "draft opened")
        self.assertEqual(other.command(["mail", identifier, "A subject"]), "draft opened")
        self.assertEqual(received, [["mailto", "retro@example.org", "A subject"]])
        other.command(["connect", identifier])
        self.assertEqual(self.actions, [("bbs_connect", "bbs.example.org", 6400)])
        self.shell.execute(f"contacts delete {identifier}")
        self.assertIn("No matching", other.command(["list"]))

    def test_simultaneous_record_updates_do_not_lose_contacts(self):
        tools = [ContactsTool(self.root / "settings" / "local" / "contacts.json", self.context) for _ in range(12)]
        threads = [threading.Thread(target=tool.command, args=(["add", f"Friend {i}"],)) for i, tool in enumerate(tools)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(tools[0].store.load()), 12)

    def test_file_operations_preserve_data_and_delegate_view_and_transfer(self):
        source = self.files / "Original file.txt"
        source.write_text("hello")
        tools = FileTools(self.files, self.context)
        tools.command(["mkdir", "copies"])
        tools.command(["copy", source.name, "copies"])
        tools.command(["rename", "copies/Original file.txt", "copies/Renamed.txt"])
        self.assertEqual((self.files / "copies/Renamed.txt").read_text(), "hello")
        tools.command(["move", "copies/Renamed.txt", "Moved.txt"])
        with self.assertRaisesRegex(ValueError, "exists"):
            tools.command(["copy", source.name, "Moved.txt"])
        calls = []
        for name in ("view", "ysend"):
            self.shell.register_command(name, lambda args, name=name: calls.append((name, args)) or "OK")
        tools.command(["view", source.name])
        tools.command(["send", source.name, "y"])
        self.assertEqual(calls, [("view", [str(source)]), ("ysend", [str(source)])])
        self.assertIn("Modified:", tools.command(["info", source.name]))

    def test_host_browsing_copy_and_session_scoped_directory(self):
        outside = self.root / "Host Music"
        outside.mkdir()
        track = outside / "Large Track.mp3"
        track.write_bytes(b"host audio" * 1024)
        first, second = FileTools(self.files, self.context), FileTools(self.files, self.context)
        first.command(["cd", str(outside)])
        self.assertEqual(second.cwd, self.files.resolve())
        self.assertIn("Large Track.mp3", first.command(["ls"]))
        first.command(["copy", "1", str(self.files)])
        self.assertEqual((self.files / track.name).read_bytes(), track.read_bytes())
        self.assertIn(str(track), first.command(["info", "1"]))
        first.command(["b"])
        self.assertEqual(first.cwd, self.root.resolve())
        first.command(["h"])
        self.assertEqual(first.cwd, self.files.resolve())
        with patch("rsh_files._root_directories", return_value=[outside]):
            self.assertIn(str(outside), first.command(["d"]))
            first.command(["cd", "1"])
        self.assertEqual(first.cwd, outside.resolve())
        restricted = FileTools(self.files, self.context, allow_host=False)
        with self.assertRaisesRegex(ValueError, "inside"):
            restricted.path(str(track))

    def test_zip_selected_extraction_and_no_replacement(self):
        path = self.files / "Software.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("docs/readme.txt", "instructions")
            archive.writestr("program.bin", b"123")
        tools = FileTools(self.files, self.context)
        self.assertIn("program.bin", tools.archive_command(["open", path.name]))
        tools.archive_command(["extract", "1", "unpacked"])
        self.assertEqual((self.files / "unpacked/docs/readme.txt").read_text(), "instructions")
        self.assertFalse((self.files / "unpacked/program.bin").exists())
        with self.assertRaisesRegex(ValueError, "exists"):
            tools.archive_command(["extract", "1", "unpacked"])

    def test_zip_traversal_and_conflicting_members_are_rejected_before_writes(self):
        tools = FileTools(self.files, self.context)
        for filename in ("../escape.txt", "..\\escape.txt", "/absolute.txt", "C:/escape.txt"):
            path = self.files / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("good.txt", "good")
                archive.writestr(filename, "bad")
            tools.archive_command(["open", path.name])
            with self.assertRaises(ValueError):
                tools.archive_command(["extract", "all", "unsafe"])
            self.assertFalse((self.files / "unsafe").exists())
        with zipfile.ZipFile(self.files / "conflict.zip", "w") as archive:
            archive.writestr("file", "data")
            archive.writestr("file/child", "data")
        tools.archive_command(["open", "conflict.zip"])
        with self.assertRaisesRegex(ValueError, "conflict"):
            tools.archive_command(["extract", "all", "unsafe"])
        self.assertFalse((self.files / "unsafe").exists())

    def test_bad_zip_and_bad_input_are_readable_errors(self):
        (self.files / "broken.zip").write_bytes(b"not a zip")
        self.assertIn("Could not complete", self.shell.execute("archive open broken.zip"))
        self.assertIn("Could not complete", self.shell.execute("fileman cd missing"))

    def test_tool_commands_and_aliases_are_registered(self):
        for name in ("calendar", "cal", "convert", "units", "contacts", "addressbook", "fileman", "fm", "archive", "zip", "audio", "player"):
            self.assertIn(name, self.shell.command_names())
        self.assertIn("hex", self.shell.execute("units help"))
        self.assertTrue({"calendar", "convert", "contacts", "fileman", "archive", "audio", "capture", "diagnostics", "findfiles", "diskinfo"}.issubset(toolkit_module.TOOL_MENUS))

    def test_all_six_tools_are_reachable_in_40_and_80_column_menus(self):
        from rsh_console import MENU_SECTIONS
        labels = {
            2: ["File Manager", "File Transfers", "Archive Browser", "Text Library", "Document Viewer", "ASCII Image Viewer", "Audio Player", "Find Files"],
            4: ["Notepad", "Calendar", "Calculator", "Address Book", "Unit Converter", "Weather & News", "AI Assistant", "LOGO"],
        }
        for section, entries in [(2, {"A": "fileman", "B": "files", "C": "archive", "D": "textlib", "E": "view", "F": "ascii_viewer", "G": "audio"}),
                                 (4, {"A": "notes", "B": "calendar", "C": "calc", "D": "contacts", "E": "convert", "F": "weather_news", "G": "ai", "H": "logo"})]:
            menu = OSFlyoutMenu(initial_section=section)
            self.assertEqual([label for _, label, _ in menu.get_active_items()], labels[section])
            self.assertEqual([item[1] for item in MENU_SECTIONS[section][2]], labels[section])
            for key, action in entries.items():
                self.assertEqual(menu.get_action_for_key(key), action)
            for cols in (40, 80):
                output = menu.render(columns=cols)
                for key in entries:
                    self.assertIn(key + "] ", output)

    def test_numbered_tool_submenus_and_converter_work_through_serial_bridge(self):
        import RETRO_SERIAL_HUB as hub
        from rsh_server import SocketTerminal
        from retro_os.scheduler import TaskScheduler
        client, peer = socket.socketpair()
        self.addCleanup(peer.close)
        terminal = SocketTerminal(client)
        self.addCleanup(terminal.close)
        self.addCleanup(hub.unregister_active_terminal, terminal)
        terminal._rsh_menu_style = "legacy"
        (self.root / "notes").mkdir()
        (self.root / "text").mkdir()
        # Send replies after prompts, just as an interactive terminal does.
        script = [
            (b"Command: ", b"convert\r"),
            (b"Choice (or command): ", b"1\r"),
            (b"Value (Enter cancels): ", b"72\r"),
            (b"From unit/base (Enter cancels): ", b"F\r"),
            (b"To unit/base (Enter cancels): ", b"C\r"),
            (b"Choice (or command): ", b"Q\r"),
        ]
        for tool in ("fileman", "archive", "audio", "calendar", "contacts"):
            script.extend([(b"Command: ", tool.encode() + b"\r"), (b"Choice (or command): ", b"Q\r")])
        script.append((b"Command: ", b"15\r"))
        output = bytearray()
        errors = []
        done = threading.Event()
        peer.settimeout(.2)
        def receive():
            cursor = 0
            while not done.is_set():
                try:
                    block = peer.recv(65536)
                    if not block:
                        return
                    output.extend(block)
                    if script:
                        marker, reply = script[0]
                        position = output.find(marker, cursor)
                        if position >= 0:
                            cursor = position + len(marker)
                            script.pop(0)
                            peer.sendall(reply)
                except socket.timeout:
                    continue
                except OSError:
                    return
        def bridge():
            try:
                hub.bridge_loop("TEST", terminal, use_ansi=False)
            except BaseException as exc:
                errors.append(exc)
        reader = threading.Thread(target=receive, daemon=True)
        reader.start()
        with patch.object(hub, "BASE_DIR", self.root), patch.object(hub, "FILES_DIR", self.files), patch.object(hub, "NOTES_DIR", self.root / "notes"), patch.object(hub, "TEXT_DIR", self.root / "text"), patch.object(TaskScheduler, "start"), patch("retro_os.toolkit.start_calendar_reminders"):
            worker = threading.Thread(target=bridge, daemon=True)
            worker.start()
            worker.join(5)
            if worker.is_alive():
                terminal.close()
                worker.join(1)
                self.fail("Tool submenu did not return: " + output.decode(errors="replace")[-2000:])
        reader.join(.3)
        done.set()
        reader.join(.5)
        self.assertEqual(errors, [])
        for tool in ("calendar","convert","contacts","fileman","archive","audio"):
            self.assertIn(toolkit_module.TOOL_MENUS[tool][0].encode(), output)
        self.assertIn(b"22.2222222222", output)

    def test_reminder_checks_do_not_rewrite_unchanged_data(self):
        tool = self.context.host_env.calendar_tool
        tool.command(["add", "2099-01-01", "09:00", "Future appointment"])
        with patch.object(tool.store, "save") as save:
            self.assertEqual(tool.due(), "")
            save.assert_not_called()

    def test_audio_library_playlists_and_path_boundaries_without_playing(self):
        path = self.files / "Test Track.mp3"
        path.write_bytes(b"audio fixture")
        player = SimpleNamespace(lock=threading.RLock(), tracks=[], play=MagicMock(return_value="playing"), control=MagicMock(return_value="paused"))
        tools = AudioTool(FileTools(self.files, self.context), player)
        self.assertIn("Test Track.mp3", tools.command(["list"]))
        tools.command(["queue", "1"])
        tools.command(["queue", "https://example.org/radio"])
        tools.command(["save", "Retro Mix"])
        self.assertIn("Retro Mix", tools.command(["playlists"]))
        self.assertEqual(tools.command(["load", "Retro Mix"]), "playing")
        player.play.assert_called_with([str(path), "https://example.org/radio"])
        tools.command(["pause"])
        player.control.assert_called_with("pause")
        with self.assertRaises(ValueError):
            tools.command(["save", "../escape"])
        outside = self.root / "Host Music"
        outside.mkdir()
        external = outside / "Private Track.mp3"
        external.write_bytes(b"audio fixture")
        tools.command(["play", str(external)])
        player.play.assert_called_with([str(external)])
        self.assertIn(external.name, tools.command(["cd", str(outside)]))
        tools.command(["play", "1"])
        player.play.assert_called_with([str(external)])
        tools.command(["queue", "1"])
        tools.command(["save", "Host Mix"])
        tools.command(["load", "Host Mix"])
        self.assertIn(str(external), player.play.call_args.args[0])
        tools.command(["h"])
        self.assertEqual(tools.files.cwd, self.files.resolve())
        with patch("rsh_files._root_directories", return_value=[self.root]):
            tools.command(["d"])
            self.assertIn("[DIR] Host Music", tools.command(["cd", "1"]))
        folder_number = tools.entries.index(outside) + 1
        tools.command(["cd", str(folder_number)])
        tools.command(["play", "1"])
        player.play.assert_called_with([str(external)])

    def test_audio_backend_pause_resume_volume_and_navigation(self):
        player = AudioPlayer()
        self.addCleanup(player.stop)
        process = MagicMock()
        process.poll.return_value = None
        with patch("retro_os.audio_player.shutil.which", return_value="ffplay"), patch("retro_os.audio_player.subprocess.Popen", return_value=process) as launch, patch.object(player, "_suspend") as suspend, patch("retro_os.audio_player.threading.Thread"):
            player.play([str(self.files / "one.mp3"), str(self.files / "two.mp3")])
            self.assertIn("-volume", launch.call_args.args[0])
            player.control("pause")
            self.assertTrue(player.paused)
            player.control("resume")
            self.assertFalse(player.paused)
            self.assertEqual(suspend.call_count, 2)
            player.control("volume", "42")
            self.assertEqual(player.volume, 42)
            player.control("next")
            self.assertEqual(player.index, 1)
            player.control("prev")
            self.assertEqual(player.index, 0)
            player.stop()
            self.assertIn("stopped", player.status())


if __name__ == "__main__":
    unittest.main()


class AudioMenuTests(unittest.TestCase):
    setUp = ToolTests.setUp
    def test_browser_opens_drives_and_plays_file_without_main_navigation_clutter(self):
        from retro_os.audio_menu import run_audio_menu
        folder = self.root / 'Music'
        folder.mkdir()
        track = folder / 'Track.mp3'
        track.write_bytes(b'fixture')
        choices = iter(['1', 'D', '1', '1', 'Q'])
        frames = []
        current = []
        def clear():
            if current:
                frames.append(''.join(current))
            current.clear()
        def render(result, page_lines=None):
            current.append(str(result) + '\r\n')
        with patch('rsh_files._root_directories', return_value=[folder]), patch('retro_os.audio_player._PLAYER.play', return_value='Audio: playing\nTrack: Track.mp3') as play:
            run_audio_menu(self.shell.execute, lambda: next(choices), current.append, render, clear)
        frames.append(''.join(current))
        play.assert_called_once_with([str(track)])
        self.assertIn('Audio: playing', frames[-1])
        self.assertLess(frames[-1].index('[1] Browse'), frames[-1].index('Audio: playing'))
        self.assertLess(frames[-1].index('Track: Track.mp3'), frames[-1].index('Choice (or command):'))
        self.assertNotIn('D=Drives', frames[0])
        self.assertIn('D=Drives', frames[1])
        self.assertIn('Drives / filesystem roots', frames[2])
        self.assertIn('Track.mp3', frames[3])
        self.assertLessEqual(len(frames[-1].splitlines()), 24)

    def test_queue_and_playlists_are_in_a_separate_submenu(self):
        from retro_os.audio_menu import run_audio_menu
        choices = iter(['8', '3', 'Q', 'Q'])
        frames, current = [], []
        def clear():
            frames.append(''.join(current))
            current.clear()
        run_audio_menu(self.shell.execute, lambda: next(choices), current.append,
                       lambda result, **kwargs: current.append(str(result)), clear)
        self.assertNotIn('Save playlist', frames[1])
        self.assertIn('Save playlist', frames[2])
        self.assertIn('No saved playlists.', frames[3])
