"""Speech subprocess isolation, replacement, and failure behavior."""
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from rsh_speech import HostSpeech, find_espeak


class SpeechTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.engine = stack.enter_context(patch("rsh_speech.find_espeak", return_value="espeak-ng"))
        self.speech = HostSpeech()
        self.addCleanup(self.speech.stop)

    def test_text_is_passed_via_stdin_without_a_shell(self):
        process = MagicMock(returncode=0)
        process.communicate.return_value = ('', '')
        process.poll.return_value = 0
        owner = object()
        text = 'Joshua says "hello"; $(Get-Process)'
        with patch('rsh_speech.threading.Thread'), patch('rsh_speech.subprocess.Popen', return_value=process) as launch:
            self.speech.say(owner, text)
            self.assertTrue(self.speech.busy(owner))
            self.speech._speak(self.speech.generation, ['espeak-ng', '--stdin'], text)
        self.assertNotIn(text, str(launch.call_args.args[0]))
        self.assertEqual(process.communicate.call_args.args[0], text)
        self.assertFalse(self.speech.busy(owner))

    def test_stop_only_cancels_the_owning_session(self):
        owner, other = object(), object()
        process = MagicMock()
        process.poll.return_value = None
        self.speech.owner = owner
        self.speech.process = process
        self.speech.speaking = True
        self.speech.stop(other)
        process.terminate.assert_not_called()
        self.speech.stop(owner)
        process.terminate.assert_called_once()
        self.assertFalse(self.speech.busy(owner))

    def test_new_speech_invalidates_old_worker(self):
        with patch('rsh_speech.threading.Thread'), patch('rsh_speech.subprocess.Popen') as launch:
            self.speech.say(object(), 'first')
            old_token = self.speech.generation
            self.speech.say(object(), 'second')
            self.speech._speak(old_token, ['espeak-ng', '--stdin'], 'stale')
            launch.assert_not_called()

    def test_backend_failure_releases_display_and_reports_error(self):
        owner = object()
        with patch('rsh_speech.threading.Thread'), patch('rsh_speech.subprocess.Popen', side_effect=OSError('missing voice backend')):
            self.speech.say(owner, 'hello')
            self.speech._speak(self.speech.generation, ['espeak-ng', '--stdin'], 'hello')
        self.assertFalse(self.speech.busy(owner))
        self.assertIn('missing voice backend', self.speech.error)

    def test_missing_engine_does_not_block_or_speak_with_windows(self):
        owner = object()
        self.engine.side_effect = FileNotFoundError('Install eSpeak NG')
        with patch('rsh_speech.subprocess.Popen') as launch:
            self.speech.say(owner, 'hello')
        launch.assert_not_called()
        self.assertFalse(self.speech.busy(owner))
        self.assertIn('Install eSpeak NG', self.speech.error)

    def test_settings_reach_the_portable_engine(self):
        with patch('rsh_speech.threading.Thread') as thread:
            self.speech.say(object(), 'hello', rate=145, pitch=25, voice='en-us+m3', gap=3)
        command = thread.call_args.kwargs['args'][1]
        self.assertEqual(command, ['espeak-ng', '--stdin', '-b', '1', '-v', 'en-us+m3',
                                   '-s', '145', '-a', '85', '-p', '25', '-g', '3'])


class EngineDiscoveryTests(unittest.TestCase):
    def test_path_discovery(self):
        with patch('rsh_speech.shutil.which', side_effect=lambda name: '/usr/bin/espeak-ng' if name == 'espeak-ng' else None):
            self.assertEqual(find_espeak(), '/usr/bin/espeak-ng')

    def test_explicit_override_does_not_fall_back(self):
        with patch('rsh_speech.shutil.which', return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, 'Configured'):
                find_espeak('/missing/espeak-ng')
