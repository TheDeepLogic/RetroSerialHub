"""Exact terminal-height budgets, anchored footers, and host-only Unicode borders."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from retro_os.menu import OSFlyoutMenu
from rsh_console import ConsoleDashboard
from rsh_preferences import MachinePreferences
from rsh_terminal import configure_screen_clearing, terminal_rows
from test_rsh_console import VirtualScreen


class Shortcuts:
    def __init__(self,count):
        self.items=[{'name':f'Tool {i}','command':f'calc {i}'} for i in range(count)]
    def has_shortcuts(self):
        return bool(self.items)
    def list_shortcuts(self):
        return self.items


class EncodedOutput(io.StringIO):
    def __init__(self,encoding):
        super().__init__(); self._encoding=encoding
    @property
    def encoding(self):
        return self._encoding


class MenuHeightTests(unittest.TestCase):
    def test_all_sections_and_shortcut_sizes_anchor_footer_without_scrolling(self):
        for columns in (40,80):
            for height in (16,20,24,25,30,43):
                for count in (0,2,8,17):
                    for section in ['shortcuts',*range(7)]:
                        with self.subTest(columns=columns,rows=height,shortcuts=count,section=section):
                            menu=OSFlyoutMenu(section,shortcuts_manager=Shortcuts(count))
                            status='12:34 | Serial 4 Telnet 3'
                            rendered=menu.render(columns=columns,rows=height,status=status,is_remote=True)
                            lines=rendered.split('\r\n')
                            self.assertEqual(len(lines),height)
                            self.assertTrue(all(len(line)<columns for line in lines),lines)
                            self.assertEqual(lines[2],'')
                            self.assertTrue(lines[3].startswith('[0]'))
                            footer=4
                            self.assertEqual(lines[-footer],status)
                            self.assertEqual(lines[-footer+1],'Type ATM to return to this menu.')
                            self.assertEqual(lines[-2],'')
                            screen=VirtualScreen(columns,height)
                            screen.feed(rendered)
                            self.assertEqual(screen.scrolls,0)
                            self.assertEqual(screen.row,height-1)
                            self.assertTrue(rendered.isascii())

    def test_short_screens_can_page_to_hidden_menu_items(self):
        menu=OSFlyoutMenu('6',shortcuts_manager=Shortcuts(0))
        menu.render(rows=16,columns=80)
        self.assertEqual(menu.get_action_for_key('A'),'diskinfo')
        menu.get_action_for_key('>')
        self.assertEqual(menu.get_action_for_key('B'),'hexview')
        self.assertIsNone(menu.get_action_for_key('A'))
        menu.render(rows=24,columns=80)
        self.assertEqual(menu.get_action_for_key('A'),'diskinfo')

    def test_local_system_menu_pages_when_disconnect_is_hidden(self):
        for columns in (40,80):
            for height in (16,20,24):
                menu=OSFlyoutMenu('7',shortcuts_manager=Shortcuts(0))
                for _ in range(8):
                    rendered=menu.render(rows=height,columns=columns,is_remote=False,status='Ready')
                    self.assertEqual(len(rendered.split('\r\n')),height)
                    self.assertNotIn('Disconnect',rendered)
                    menu.get_action_for_key('>',is_remote=False)

    def test_height_defaults_validation_and_profile_persistence(self):
        from retro_os.session_tools import apply_preferences
        from retro_os.core import Session
        class Terminal: pass
        terminal=Terminal()
        self.assertEqual(terminal_rows(terminal),24)
        configure_screen_clearing(terminal,rows=30)
        self.assertEqual(terminal_rows(terminal),30)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'prefs.json'
            store=MachinePreferences(path)
            store.set('APPLE2','rows',25)
            store.set('IBM','rows',43)
            session=Session()
            apply_preferences(terminal,MachinePreferences(path).get('APPLE2'),session)
            self.assertEqual(terminal_rows(terminal),25)
            self.assertEqual(session.rows,25)
            for invalid in (0,15,101):
                with self.assertRaises(ValueError):
                    store.set('APPLE2','rows',invalid)


class UnicodeBorderTests(unittest.TestCase):
    def test_unicode_borders_preserve_width_and_host_output_text(self):
        from rsh_host import HostTerminal
        dashboard=ConsoleDashboard({})
        dashboard.set_host_terminal(HostTerminal(dashboard.append_host_output))
        dashboard.append_host_output('Literal command: echo + - |\n')
        with patch('rsh_console.sys.stdout',EncodedOutput('utf-8')),patch.dict(os.environ,{'RSH_ASCII_BORDERS':'0'}):
            for width in (40,80,118):
                rendered=dashboard.render_interface(inner_width=width,use_color=True)
                plain=[dashboard._strip_ansi(row) for row in rendered]
                self.assertTrue(plain[0].startswith('\u250c'))
                self.assertTrue(plain[-1].endswith('\u2518'))
                self.assertTrue(all(len(row)==width for row in plain))
            frame='\n'.join(dashboard._frame(height=50,terminal_size=os.terminal_size((120,50))))
            self.assertIn('Literal command: echo + - |',frame)

    def test_one_connections_heading_preserves_status_colors_and_unicode_divider(self):
        profiles={
            'APPLE2':{'serial_port':'COM2','serial_status':'OPEN','terminal_status':'ACTIVE'},
            'C64':{'serial_port':'COM4','serial_status':'OPEN','terminal_status':'WAITING'},
            'IBM':{'serial_port':'COM6','serial_status':'MISSING','terminal_status':'OFFLINE'},
        }
        dashboard=ConsoleDashboard(profiles)
        with patch('rsh_console.sys.stdout',EncodedOutput('utf-8')),patch.dict(os.environ,{'RSH_ASCII_BORDERS':'0'}):
            rows=dashboard._status_panel_rows(118,force_color=True)
        plain=[dashboard._strip_ansi(row) for row,_ in rows]
        text='\n'.join(plain)
        self.assertEqual(text.count('Connections'),1)
        self.assertNotIn('Active Connections',text)
        self.assertNotIn('Waiting / Inactive',text)
        divider=next(row for row in plain if 'Connections' in row)
        self.assertTrue(divider.startswith('\u251c\u2500\u2500 Connections '))
        self.assertTrue(divider.endswith('\u2524'))
        self.assertNotIn('-',divider)
        for name,color in [('APPLE2','green'),('C64','yellow'),('IBM','red')]:
            row=next(row for row,_ in rows if name in row)
            palette=dashboard._paint('',color,force_color=True).removesuffix('\x1b[0m')
            self.assertIn(palette,row)
        self.assertTrue(all(len(row)==118 for row in plain))

    def test_ascii_fallback_and_explicit_override(self):
        dashboard=ConsoleDashboard({})
        for encoding,override in [('ascii','0'),('utf-8','1')]:
            with patch('rsh_console.sys.stdout',EncodedOutput(encoding)),patch.dict(os.environ,{'RSH_ASCII_BORDERS':override}):
                rows=dashboard.render_interface(inner_width=80,use_color=False)
                self.assertTrue(rows[0].startswith('+'))
                self.assertTrue(all(row.isascii() for row in rows))

    def test_live_unicode_redraw_never_wraps_or_scrolls(self):
        from rsh_host import HostTerminal
        dashboard=ConsoleDashboard({}); dashboard._tty=True; dashboard._running=True
        dashboard._color=True
        dashboard.set_host_terminal(HostTerminal(dashboard.append_host_output))
        dashboard.append_host_output('cli> ')
        for columns,height in ((40,24),(80,24),(120,50)):
            output=EncodedOutput('utf-8'); screen=VirtualScreen(columns,height)
            with patch('rsh_console.sys.stdout',output),patch('shutil.get_terminal_size',return_value=os.terminal_size((columns,height))),patch.object(dashboard,'host_input_available',return_value=True),patch.dict(os.environ,{'RSH_ASCII_BORDERS':'0'}):
                dashboard._draw_frame()
            screen.feed(output.getvalue())
            self.assertEqual(screen.scrolls,0)
            self.assertIn('cli>',screen.text())
