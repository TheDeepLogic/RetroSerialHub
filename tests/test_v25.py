"""Behavioral coverage for v2.5 Workshop and session integration."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from retro_os.core import Session
from retro_os.runtime import create_runtime
from retro_os.workshop import Workshop
from rsh_preferences import MachinePreferences
from rsh_session import SessionServices
from rsh_transfer import packet, xsend, xreceive, ysend, read_exact


class Terminal:
    _profile_name = 'APPLE2'
    _terminal_name = 'APPLE2'
    port = 'COM2'
    secret_input = False
    def __init__(self, incoming=b'', fragment=1):
        self.incoming = bytearray(incoming)
        self.output = []
        self.fragment = fragment
    def read(self, count=1):
        count = min(count,self.fragment)
        value = bytes(self.incoming[:count]); del self.incoming[:count]
        return value
    def write(self,data):
        self.output.append(bytes(data)); return len(data)


class WorkshopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.tool = Workshop()
    def source(self, name, data):
        path = self.root/name; path.write_bytes(data); return str(path)
    def test_binary_encoding_round_trip_and_no_overwrite(self):
        source = self.source('binary', bytes(range(256)))
        for kind in ('hex','base64'):
            text, binary = self.root/(kind+'.txt'), self.root/(kind+'.bin')
            self.tool.command(['encode',kind,source,str(text)])
            self.tool.command(['decode',kind,str(text),str(binary)])
            self.assertEqual(binary.read_bytes(),bytes(range(256)))
            with self.assertRaises(FileExistsError):
                self.tool.command(['decode',kind,str(text),str(binary)])
    def test_text_conversion_is_strict_and_preserves_source(self):
        source = self.source('source.txt',b'Hello\r\nWorld\rEnd\n')
        target = self.root/'converted.txt'
        self.tool.command(['text',source,str(target),'cr','upper','ascii','ascii'])
        self.assertEqual(target.read_bytes(),b'HELLO\rWORLD\rEND\r')
        self.assertEqual(Path(source).read_bytes(),b'Hello\r\nWorld\rEnd\n')
        unicode_source = self.source('unicode.txt','caf\u00e9'.encode())
        with self.assertRaises(UnicodeEncodeError):
            self.tool.command(['text',unicode_source,str(self.root/'bad.txt')])
        self.assertFalse((self.root/'bad.txt').exists())
    def test_basic_renumber_changes_references_but_not_strings_data_or_comments(self):
        source = self.source('basic.txt',b'10 PRINT "GOTO 20"\n20 ON X GOTO 10,30\n30 REM GOTO 10\n40 DATA 10,20: GOSUB 20\n50 IF A THEN 10\n')
        output = self.root/'renumbered.bas'
        self.tool.command(['basic',source,str(output),'100','100'])
        text = output.read_text()
        self.assertIn('100 PRINT "GOTO 20"',text)
        self.assertIn('200 ON X GOTO 100,300',text)
        self.assertIn('300 REM GOTO 10',text)
        self.assertIn('400 DATA 10,20: GOSUB 200',text)
        self.assertIn('500 IF A THEN 100',text)
    def test_basic_data_colons_and_quotes_are_not_line_references(self):
        source = self.source('quoted.bas',b'10 DATA "GOTO 20: GOTO 10",10: GOTO20\n20 END\n')
        output = self.root/'quoted-output.bas'
        self.tool.command(['basic',source,str(output),'100','100'])
        self.assertIn('DATA "GOTO 20: GOTO 10",10: GOTO 200',output.read_text())

    def test_basic_invalid_reference_creates_no_output(self):
        source = self.source('invalid.bas',b'10 GOTO 99\n')
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            self.tool.command(['basic',source,str(self.root/'bad.bas')])
        self.assertFalse((self.root/'bad.bas').exists())
    def test_split_join_checks_integrity_before_creating_output(self):
        original = bytes(range(256))*7+b'end\x1a'
        source = self.source('source.bin',original)
        folder = self.root/'parts'
        self.tool.command(['split',source,str(folder),'128'])
        output = self.root/'joined.bin'
        self.tool.command(['join',str(folder/'manifest.json'),str(output)])
        self.assertEqual(output.read_bytes(),original)
        part = folder/'part-000001.bin'; part.write_bytes(b'x'*128)
        with self.assertRaisesRegex(ValueError,'checksum'):
            self.tool.command(['join',str(folder/'manifest.json'),str(self.root/'bad.bin')])
        self.assertFalse((self.root/'bad.bin').exists())
    def test_inspection_hash_and_streaming_comparison(self):
        source = self.source('image.dsk', b'A'*143360)
        self.assertIn('140 KiB',self.tool.command(['disk',source]))
        self.assertIn('00000010',self.tool.command(['hex',source,'0x10','16']))
        self.assertIn(hashlib.sha256(b'A'*143360).hexdigest(),self.tool.command(['hash',source]))
        other = self.source('other.dsk',b'A'*70000+b'B')
        self.assertIn('byte 70000',self.tool.command(['compare',source,other]))
        self.assertIn('identical',self.tool.command(['compare',source,source]))


class SessionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.terminal = Terminal(b'hello')
        self.service = SessionServices(self.terminal,self.root/'captures')
        self.addCleanup(self.service.close)
    def test_capture_and_notifications_do_not_touch_binary_transfers(self):
        self.service.start_capture('session')
        self.terminal.write(b'Visible\n')
        with self.service.transfer():
            self.terminal.write(b'\x01binary\x1a')
            self.service.notify('Message from IBM')
            self.assertIn('deferred',self.service.deliver(force=True))
        self.assertNotIn(b'Message from IBM',b''.join(self.terminal.output))
        self.assertEqual(self.service.deliver(force=True),'Message from IBM')
        self.service.stop_capture()
        self.assertEqual((self.root/'captures/session.txt').read_text(),'Visible\n')
    def test_quiet_mode_and_secret_input_diagnostics(self):
        self.service.quiet=True; self.service.notify('Pending')
        self.assertIn('1 notifications',self.service.deliver())
        self.terminal.secret_input=True
        self.terminal.read(5)
        self.assertEqual(self.service.last_rx,b'')
        self.assertEqual(self.service.received,1)
        self.assertEqual(self.service.deliver(force=True),'Pending')
    def test_reconnect_policy_sets_menu_reset_only_after_inactivity(self):
        tracker = SimpleNamespace(active=True)
        self.terminal._rsh_activity_tracker=tracker
        self.terminal._rsh_machine_settings={'reconnect':'menu'}
        self.terminal.read()
        tracker.active=False
        self.terminal.read()
        self.assertTrue(self.terminal._rsh_reconnect_pending)
    def test_preferences_validate_and_survive_reload(self):
        path = self.root/'prefs.json'; store = MachinePreferences(path)
        store.set('APPLE2','pace_ms','5'); store.set('APPLE2','protocol','ymodem')
        self.assertEqual(MachinePreferences(path).get('APPLE2'),{'pace_ms':5,'protocol':'YMODEM'})
        for key,value in [('columns',41),('reconnect','unknown'),('pace_ms',-1)]:
            with self.assertRaises(ValueError):
                store.set('APPLE2',key,value)


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def test_crc_sender_retries_identical_packet_and_preserves_binary(self):
        path=self.root/'data'; path.write_bytes(b'A'*127+b'\x1a')
        terminal=Terminal(bytes([ord('C'),21,6,6]))
        self.assertEqual(xsend(terminal,path),128)
        self.assertEqual(terminal.output[0],packet(1,path.read_bytes()))
        self.assertEqual(terminal.output[0],terminal.output[1])
        self.assertEqual(terminal.output[-1],b'\x04')
    def test_fragmented_receive_acknowledges_duplicate_without_duplicating_data(self):
        data=b'A'*127+b'\x1a'
        terminal=Terminal(packet(1,data)+packet(1,data)+b'\x04',fragment=3)
        path=self.root/'received'
        self.assertEqual(xreceive(terminal,path),128)
        self.assertEqual(path.read_bytes(),data)
        self.assertEqual(terminal.output.count(b'\x06'),3)
    def test_receive_expected_size_trims_only_explicit_padding(self):
        body=b'A\x1a'+b'\x1a'*126
        terminal=Terminal(packet(1,body)+b'\x04')
        target=self.root/'exact'
        xreceive(terminal,target,exact_size=2)
        self.assertEqual(target.read_bytes(),b'A\x1a')
    def test_receiver_negotiates_checksum_after_crc_startup_timeouts(self):
        import rsh_transfer
        data = b'B'*128
        terminal = Terminal(packet(1,data,crc=False)+b'\x04')
        actual = rsh_transfer.read_exact
        attempts = 0
        def read(ser,count,timeout=10):
            nonlocal attempts
            if count == 1 and attempts < 3:
                attempts += 1
                raise TimeoutError('legacy sender waits for NAK')
            return actual(ser,count,timeout)
        with patch('rsh_transfer.read_exact',side_effect=read):
            xreceive(terminal,self.root/'legacy')
        self.assertEqual((self.root/'legacy').read_bytes(),data)
        self.assertEqual(terminal.output[:4],[b'C',b'C',b'C',b'\x15'])

    def test_checksum_sender_and_bounded_timeout(self):
        path=self.root/'source'; path.write_bytes(b'hello')
        terminal=Terminal(bytes([21,6,6]))
        xsend(terminal,path)
        self.assertEqual(len(terminal.output[0]),132)
        with patch('rsh_transfer.time.monotonic',side_effect=[0,2]),patch('rsh_transfer.time.sleep'):
            with self.assertRaises(TimeoutError):
                read_exact(Terminal(),1,1)
    def test_ymodem_crc_header_data_eof_and_empty_batch_terminator(self):
        path=self.root/'test.bin'; path.write_bytes(b'hello')
        terminal=Terminal(bytes([ord('C'),6,ord('C'),6,21,6,ord('C'),6]))
        self.assertEqual(ysend(terminal,path),5)
        packets=terminal.output
        self.assertEqual(packets[0][0],1)
        self.assertEqual(packets[0][1],0)
        self.assertEqual(packets[1][0],2)
        self.assertEqual(packets[2:4],[b'\x04',b'\x04'])
        self.assertEqual(packets[-1],packet(0,bytes(128)))
    def test_cancellation_keeps_partial_file_and_releases_protection(self):
        terminal=Terminal(b'\x18')
        service=SessionServices(terminal,self.root/'captures'); self.addCleanup(service.close)
        with self.assertRaises(InterruptedError):
            xreceive(terminal,self.root/'cancelled')
        self.assertEqual(service.protected,0)
        self.assertFalse((self.root/'cancelled').exists())
        self.assertTrue(list(self.root.glob('cancelled-*.part')))
        self.assertEqual(terminal.output[-1],b'\x18\x18')


class IntegratedToolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); (self.root/'files').mkdir()
        self.actions=[]
        with patch('retro_os.toolkit.start_calendar_reminders'):
            _,_,self.host,self.shell,_=create_runtime({'files':self.root/'files'},session=Session(user='APPLE2',client_type='host'),activate_module=self.actions.append)
        self.terminal=Terminal(); self.host.terminal=self.terminal
        self.service=SessionServices(self.terminal,self.root/'captures'); self.addCleanup(self.service.close)
    def test_search_favorites_marked_copy_and_archive_use_host_paths(self):
        outside=self.root/'outside'; outside.mkdir()
        (outside/'Game.DSK').write_bytes(b'image'); (outside/'other.txt').write_text('other')
        result=self.shell.execute('findfiles *.dsk "'+str(outside)+'"')
        self.assertIn('Game.DSK',result)
        self.assertIn('Modified:',self.shell.execute('fileman info 1'))
        self.host.file_tools.command(['cd',str(outside)])
        self.host.file_tools.command(['favorite','add','Games'])
        self.host.file_tools.command(['mark','Game.DSK'])
        destination=self.root/'destination'; destination.mkdir()
        self.host.file_tools.command(['copy','marked',str(destination)])
        self.assertEqual((destination/'Game.DSK').read_bytes(),b'image')
        self.host.file_tools.command(['h'])
        self.host.file_tools.command(['favorite','go','Games'])
        self.assertEqual(self.host.file_tools.cwd,outside.resolve())
    def test_audio_stations_folder_and_queue_controls(self):
        from retro_os.audio_player import AudioTool
        player = SimpleNamespace(lock=threading.RLock(),tracks=['first','second','third'],index=0,
                                 repeat=False,play=MagicMock(return_value='playing'))
        tool=AudioTool(self.host.file_tools,player)
        folder=self.root/'music'; folder.mkdir(); (folder/'song.mp3').write_bytes(b'audio')
        tool.command(['musicfolder',str(folder)])
        self.assertIn('song.mp3',tool.command(['musicfolder']))
        tool.command(['station','add','Retro','https://example.org/stream'])
        tool.command(['station','play','Retro'])
        player.play.assert_called_once_with(['https://example.org/stream'])
        tool.command(['reorder','3','2'])
        self.assertEqual(player.tracks,['first','third','second'])
        tool.command(['remove','3'])
        self.assertEqual(player.tracks,['first','third'])
        tool.command(['repeat','on']); self.assertTrue(player.repeat)
        tool.command(['shuffle']); self.assertEqual(player.tracks[0],'first')

    def test_raw_sector_extraction_has_exact_bounds_and_preserves_original(self):
        path=self.root/'disk.img'; path.write_bytes(b'A'*128+b'B'*128)
        output=self.root/'sector.bin'
        Workshop().command(['diskextract',str(path),str(output),'128','1','1'])
        self.assertEqual(output.read_bytes(),b'B'*128)
        with self.assertRaises(ValueError):
            Workshop().command(['diskextract',str(path),str(self.root/'bad'),'128','1','2'])
        self.assertEqual(path.read_bytes(),b'A'*128+b'B'*128)

    def test_session_commands_capture_and_machine_settings(self):
        self.assertIn('started',self.shell.execute('capture start test'))
        self.terminal.write(b'Test text\n')
        self.shell.execute('capture stop')
        self.assertEqual((self.root/'captures/test.txt').read_text(),'Test text\n')
        self.assertIn('Saved',self.shell.execute('machine pace_ms 5'))
        self.assertEqual(self.terminal._rsh_pace_delay,.005)
        self.assertIn('RX',self.shell.execute('diagnostics info APPLE2'))
    def test_launch_preset_retains_directory_arguments_and_mode(self):
        with patch.object(self.host,'launch_app') as launch:
            self.host.session_tools.preset(['add','Editor','background',str(self.root),'editor','a file.txt'])
            self.shell.execute('presets run Editor')
            launch.assert_called_once_with('editor',['a file.txt'],cwd=str(self.root))
    def test_reader_persists_bookmark_and_finds_next_match(self):
        from retro_os.reader import run_reader
        path=self.root/'document.txt'; path.write_text('\n'.join(f'Line {i}' for i in range(60)))
        choices=iter(['F','Line 40','M','Q']); output=[]
        store=self.root/'positions.json'
        run_reader(str(path),store,lambda:next(choices),output.append,lambda:None,rows=12)
        self.assertIn('Match on line', ''.join(output))
        saved=json.loads(store.read_text())[0]
        self.assertGreater(saved['page'],0)
        output.clear(); choices=iter(['Q'])
        run_reader(str(path),store,lambda:next(choices),output.append,lambda:None,rows=12)
        self.assertIn('Line 40',''.join(output))
    def test_notes_editor_search_rename_and_export(self):
        import rsh_notes
        path=self.root/'note.txt'; path.write_text('Original\n')
        terminal=Terminal()
        sess=rsh_notes.create_session(terminal,False,['note.txt'],self.root)
        for line in ('E1','replace 1 Revised text','save','F Revised','R1','Renamed','X1',str(self.root/'export.txt')):
            rsh_notes.handle_input(sess,line,terminal,False)
        self.assertEqual((self.root/'Renamed.txt').read_text(),'Revised text\n')
        self.assertEqual((self.root/'export.txt').read_text(),'Revised text\n')
    def test_note_edit_retains_quotes_and_refuses_concurrent_overwrite(self):
        import rsh_notes
        path=self.root/'program.txt'; path.write_text('Original\n')
        terminal=Terminal()
        sess=rsh_notes.create_session(terminal,False,['program.txt'],self.root)
        rsh_notes.handle_input(sess,'E1',terminal,False)
        rsh_notes.handle_input(sess,'replace 1 PRINT "HELLO"',terminal,False)
        self.assertEqual(sess['edit_lines'],['PRINT "HELLO"'])
        path.write_text('Edited by another terminal\n')
        rsh_notes.handle_input(sess,'save',terminal,False)
        self.assertIn('editing',sess)
        self.assertEqual(path.read_text(),'Edited by another terminal\n')

    def test_launch_preset_menu_parses_quoted_arguments_without_altering_cli_arguments(self):
        tools=self.host.session_tools
        tools.preset(['add-menu','Quoted','background',str(self.root),'editor','--file "a file.txt"'])
        with patch.object(self.host,'launch_app') as launch:
            tools.preset(['run','Quoted'])
            launch.assert_called_once_with('editor',['--file','a file.txt'],cwd=str(self.root))

    def test_shortcut_pages_keep_a_to_h_and_all_entries_reachable(self):
        from retro_os.shortcuts import ShortcutsManager
        from retro_os.menu import OSFlyoutMenu
        manager=ShortcutsManager(self.root/'shortcuts.json')
        for index in range(12):
            manager.add_shortcut('Tool '+str(index),'calc '+str(index))
        menu=OSFlyoutMenu(shortcuts_manager=manager)
        self.assertEqual(menu.get_action_for_key('H'),'shortcut_run:calc 7')
        self.assertEqual(menu.get_action_for_key('>'),'shortcut_page')
        self.assertEqual(menu.get_action_for_key('A'),'shortcut_run:calc 8')
        for columns in (40,80):
            self.assertLessEqual(len(menu.render(columns=columns,status='Ready').splitlines()),24)

    def test_menu_catalogue_matches_console_and_every_category_fits_a_to_h(self):
        from retro_os.menu import OSFlyoutMenu
        from rsh_console import MENU_SECTIONS
        self.assertEqual(OSFlyoutMenu.SECTIONS[5][0],'Workshop')
        self.assertEqual(OSFlyoutMenu.SECTIONS[6][1],'7')
        from retro_os.help_data import get_topic_content
        self.assertIn('Session Capture',get_topic_content('2'))
        self.assertIn('[7] System',get_topic_content('2'))
        for (title,num,items),(cnum,ctitle,citems) in zip(OSFlyoutMenu.SECTIONS,MENU_SECTIONS):
            self.assertEqual(num,cnum)
            self.assertEqual([(k,label,action) for k,label,_,action in citems],items)
            self.assertLessEqual(len(items),8)
            for columns in (40,80):
                rendered=OSFlyoutMenu(num).render(columns=columns,status='Ready')
                self.assertLessEqual(len(rendered.splitlines()),24)
