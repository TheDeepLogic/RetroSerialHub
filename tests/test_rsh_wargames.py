"""WarGames terminal flows and deterministic, nonblocking screen playback."""
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import rsh_joshua as joshua
import rsh_wargames as wargames


class Terminal:
    def __init__(self, columns=80):
        self._rsh_columns = columns
        self._rsh_translate_ansi = True
        self._rsh_clear_sequence = b'\x1bv'
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    def text(self):
        return b''.join(self.writes).decode('ascii')


class WarGamesTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.speech = stack.enter_context(patch("rsh_joshua.SPEECH"))
        self.speech.busy.return_value = False
        self.speech.error = ""
        self.ser = Terminal()
        self.sess = wargames.create_session(self.ser, False)

    def command(self, text):
        return wargames.handle_input(self.sess, text, self.ser, False)

    def drain(self):
        state = self.sess['joshua']
        now = 1000000000.0
        for _ in range(200):
            if state['phase'] != 'DISPLAY':
                return
            joshua.poll(self.sess, self.ser, False, now)
            now += 100
        self.fail('Display did not complete')

    def login(self):
        self.command('term')
        self.command('4')
        self.command('joshua')
        self.drain()

    def start_war(self):
        self.login()
        self.command('How about Global Thermonuclear War?')
        self.assertIn('CHESS?', self.ser.text())
        self.command("Later. Let's play Global Thermonuclear War.")
        self.command('2')
        self.command('Seattle')
        self.command('Las Vegas')
        self.command('')
        self.drain()

    def test_cpm_dialer_and_known_phone_number(self):
        self.command('DIR')
        self.assertIn('DIALER', self.ser.text())
        self.command('dialer')
        self.command('bad')
        self.assertEqual(self.sess['submode'], 'DIALER')
        self.command('311767')
        self.assertEqual(self.sess['submode'], 'CPM')
        self.assertIn('UNKNOWN', self.ser.text())
        self.command('TERM.COM')
        self.command('(311) 767-7305')
        self.assertIn('LOGON:', self.ser.text())
        self.assertEqual(self.sess['submode'], 'TERM_PROTO')

    def test_logon_help_and_failures_do_not_authenticate(self):
        self.command('term')
        self.command('4')
        for text in ('HELP LOGON', 'LIST GAMES', 'HELP GAMES', 'wrong', 'wrong'):
            self.command(text)
        self.assertEqual(self.sess['joshua']['phase'], 'LOGON')
        self.assertIn('GLOBAL THERMONUCLEAR WAR', self.ser.text())
        self.assertIn('HINT:', self.ser.text())

    def test_status_flashes_wait_for_deadlines_and_use_native_clear(self):
        self.command('term')
        self.command('4')
        self.command('joshua')
        self.ser.writes.clear()
        joshua.poll(self.sess, self.ser, False, 10)
        self.assertEqual(self.ser.writes[0], b'\x1bv')
        count = len(self.ser.writes)
        joshua.poll(self.sess, self.ser, False, 10.1)
        self.assertEqual(len(self.ser.writes), count)
        self.drain()
        self.assertIn('GREETINGS PROFESSOR FALKEN', self.ser.text())
        self.assertEqual(self.sess['joshua']['phase'], 'TALK')

    def test_conversation_understands_movie_style_phrases(self):
        self.login()
        for question, expected in [('Hello, Joshua?', 'FEELING TODAY'),
                                   ("I'm fine. How are you?", 'USER ACCOUNT'),
                                   ('People sometimes make mistakes', 'SHALL WE PLAY'),
                                   ('What is the primary goal?', 'PROGRAMMED ME'),
                                   ('What is the primary goal???', 'TO WIN THE GAME'),
                                   ('Is this a game or is it real?', "WHAT'S THE DIFFERENCE")]:
            self.command(question)
            self.assertIn(expected, self.ser.text())

    def test_strategic_game_and_zero_player_ending(self):
        self.start_war()
        self.assertEqual(self.sess['joshua']['war']['targets'], ['SEATTLE', 'LAS VEGAS'])
        for _ in range(2):
            self.command('next')
            self.drain()
        self.assertEqual(self.sess['joshua']['phase'], 'CRISIS')
        self.command('tic-tac-toe')
        self.command('0')
        self.drain()
        self.assertIn('WINNER: NONE', self.ser.text())
        self.assertIn('THE ONLY WINNING MOVE IS NOT TO PLAY.', self.ser.text())
        self.assertTrue(self.sess['joshua']['war']['finished'])
        self.assertEqual(self.sess['joshua']['phase'], 'TALK')

    def test_invalid_side_and_target_do_not_start_strike(self):
        self.login()
        self.command('gtw')
        self.command('gtw')
        self.command('invalid')
        self.assertEqual(self.sess['joshua']['phase'], 'SIDE')
        self.command('USA')
        self.command('')
        self.command('Seattle')
        self.assertEqual(self.sess['joshua']['war']['targets'], [])
        self.command('Moscow')
        self.command('Moscow')
        self.assertEqual(self.sess['joshua']['war']['targets'], ['MOSCOW'])

    def test_hangup_cancels_pages_and_reconnect_preserves_game(self):
        self.start_war()
        war = self.sess['joshua']['war']
        self.command('NORAD')
        self.command('LOGOFF')
        self.ser.writes.clear()
        wargames.poll(self.sess, self.ser, False)
        self.assertEqual(self.ser.writes, [])
        self.command('term')
        self.command('4')
        self.command('joshua')
        self.drain()
        self.assertIs(self.sess['joshua']['war'], war)
        self.assertIn("YESTERDAY'S GAME WAS INTERRUPTED", self.ser.text())
        self.assertEqual(self.sess['joshua']['phase'], 'WAR')

    def test_skip_is_nonblocking_and_speed_is_session_local(self):
        self.command('term')
        self.command('4')
        self.command('SPEED FAST')
        self.command('joshua')
        self.command('SKIP')
        self.assertEqual(self.sess['joshua']['phase'], 'TALK')
        other = wargames.create_session(Terminal(), False)
        self.assertEqual(other['joshua']['speed'], 1)
        self.assertEqual(self.sess['joshua']['speed'], .3)

    def test_report_returns_to_strategic_phase(self):
        self.start_war()
        self.command('KILL RATIOS')
        self.drain()
        self.assertEqual(self.sess['joshua']['phase'], 'WAR')
        self.assertIn('PROJECTED KILL RATIOS', self.ser.text())
        self.command('ADDRESS')
        self.assertIn('GOOSE ISLAND', self.ser.text())

    def test_two_player_tic_tac_toe_validates_moves(self):
        self.login()
        self.command('TTT')
        self.command('2')
        self.command('42')
        self.assertEqual(self.sess['joshua']['board'], [' '] * 9)
        for move in ('1', '4', '2', '5', '3'):
            self.command(move)
        self.assertEqual(self.sess['joshua']['phase'], 'TALK')
        self.assertIn('RESULT: X', self.ser.text())

    def test_computer_cannot_lose_tic_tac_toe(self):
        board = [' '] * 9
        def explore():
            for move in range(9):
                if board[move] != ' ':
                    continue
                board[move] = 'X'
                result = joshua.winner(board)
                self.assertNotEqual(result, 'X')
                if not result:
                    response = joshua.best_move(board, 'O')
                    board[response] = 'O'
                    if not joshua.winner(board):
                        explore()
                    board[response] = ' '
                board[move] = ' '
        explore()

    def test_all_screens_fit_40_columns(self):
        self.ser._rsh_columns = 40
        self.ser.writes.clear()
        self.start_war()
        self.command('next')
        self.drain()
        self.command('next')
        self.drain()
        self.command('NORAD')
        self.drain()
        self.command('ZERO PLAYERS')
        self.drain()
        for line in self.ser.text().replace('\x1bv', '').split('\r\n'):
            self.assertLessEqual(len(line), 39, line)

    def test_existing_school_and_other_systems_remain_accessible(self):
        self.command('term')
        self.command('1')
        self.command('David Lightman')
        self.assertIn('BIOLOGY', self.ser.text())
        self.assertEqual(self.sess['submode'], 'CPM')
        self.assertEqual(self.command('exit'), (True, 'MENU'))


    def test_speech_follows_display_and_holds_narrated_page(self):
        self.command('term')
        self.command('4')
        self.command('joshua')
        state = self.sess['joshua']
        for now in (10, 20, 30):
            joshua.poll(self.sess, self.ser, False, now)
        self.assertIn('GREETINGS PROFESSOR FALKEN.', self.ser.text())
        self.speech.say.assert_called_once()
        self.assertIn('GREETINGS PROFESSOR', self.speech.say.call_args.args[1])
        self.speech.busy.return_value = True
        joshua.poll(self.sess, self.ser, False, 40)
        self.assertEqual(state['phase'], 'DISPLAY')
        self.speech.busy.return_value = False
        joshua.poll(self.sess, self.ser, False, 50)
        self.assertEqual(state['phase'], 'TALK')
        self.command('Hello')
        self.assertIn('HOW ARE YOU FEELING TODAY?', self.speech.say.call_args.args[1])

    def test_speech_off_and_logoff_cancel_narration(self):
        self.login()
        self.command('SPEECH OFF')
        self.speech.say.reset_mock()
        self.command('Hello')
        self.speech.say.assert_not_called()
        self.speech.stop.assert_called_with(self.sess['joshua']['speech_owner'])
        self.command('SPEECH ON')
        self.command('Hello')
        self.speech.say.assert_called_once()
        self.command('LOGOFF')
        self.speech.stop.assert_called_with(self.sess['joshua']['speech_owner'])

    def test_skip_stops_speech_and_finishes_display(self):
        self.command('term')
        self.command('4')
        self.command('joshua')
        self.command('skip')
        self.speech.stop.assert_called_with(self.sess['joshua']['speech_owner'])
        self.assertEqual(self.sess['joshua']['phase'], 'TALK')
