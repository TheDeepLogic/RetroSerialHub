"""Transfer deadlines and failure reporting with simulated transports."""
import unittest
from unittest.mock import Mock, patch

from rsh_transfer import protected, read_exact


class TransferReliabilityTests(unittest.TestCase):
    def test_continuous_fragments_cannot_extend_deadline(self):
        terminal = Mock()
        terminal._rsh_services = None
        terminal.read.return_value = b'A'
        with patch('rsh_transfer.time.monotonic', side_effect=[0, 0, 1, 2, 3]):
            with self.assertRaises(TimeoutError):
                read_exact(terminal, 100, timeout=3)
        self.assertEqual(terminal.read.call_count, 3)

    def test_fragmented_read_within_deadline_succeeds(self):
        terminal = Mock()
        terminal._rsh_services = None
        terminal.read.side_effect = [b'A', b'BC']
        with patch('rsh_transfer.time.monotonic', side_effect=[0, 0, 1]):
            self.assertEqual(read_exact(terminal, 3, timeout=3), b'ABC')

    def test_failed_cancel_write_preserves_original_error_and_clears_progress(self):
        terminal = Mock()
        terminal._rsh_services = None
        terminal.write.side_effect = OSError('Disconnected')
        original = ValueError('Invalid received size')

        @protected
        def transfer(ser):
            raise original

        with self.assertRaises(ValueError) as caught:
            transfer(terminal)
        self.assertIs(caught.exception, original)
        terminal.write.assert_called_once_with(b'\x18\x18')
        self.assertIsNone(terminal._rsh_transfer_progress)
