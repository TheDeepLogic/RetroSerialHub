"""COM bridge byte preservation and line-ending regressions."""
import unittest
from unittest.mock import Mock

from rsh_bridge import create_runtime_session, handle_input_runtime, handle_raw_input


class BridgeReliabilityTests(unittest.TestCase):
    def test_raw_forwarding_preserves_all_byte_values(self):
        bridge = Mock()
        session = create_runtime_session(bridge, 'COM9')
        payload = bytes(range(256))
        self.assertTrue(handle_raw_input(session, payload))
        bridge.write.assert_called_once_with(payload)

    def test_raw_forwarding_preserves_split_crlf(self):
        bridge = Mock()
        session = create_runtime_session(bridge, 'COM9')
        for chunk in (b'hello\r', b'\nworld\r', b'\n'):
            self.assertTrue(handle_raw_input(session, chunk))
        self.assertEqual(b''.join(call.args[0] for call in bridge.write.call_args_list),
                         b'hello\r\nworld\r\n')

    def test_line_mode_normalizes_each_newline_once(self):
        bridge = Mock()
        session = create_runtime_session(bridge, 'COM9')
        self.assertEqual(handle_input_runtime(
            session, 'hello', Mock(), raw_line=b'one\r\ntwo\nthree\rfour\xff'),
            (True, None))
        bridge.write.assert_called_once_with(b'one\r\ntwo\r\nthree\r\nfour\xff\r\n')

    def test_raw_write_failure_closes_bridge(self):
        bridge = Mock()
        bridge.write.side_effect = OSError('Disconnected')
        session = create_runtime_session(bridge, 'COM9')
        self.assertFalse(handle_raw_input(session, b'data'))
        bridge.close.assert_called_once_with()
        self.assertIsNone(session['bridge_serial'])
