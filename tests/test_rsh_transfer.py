"""Transfer deadlines and failure reporting with simulated transports."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from rsh_transfer import ACK, CAN, EOT, packet, protected, read_exact, xreceive


class TransferReliabilityTests(unittest.TestCase):
    def receive_terminal(self):
        terminal = Mock()
        terminal._rsh_services = None
        terminal.read.side_effect = [bytes([1]), packet(1, b'A' * 128)[1:], bytes([EOT])]
        return terminal

    def test_failed_destination_copy_preserves_partial_and_allows_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'received.bin'
            terminal = self.receive_terminal()
            failure = OSError('Disk full')

            def fail_copy(source, output):
                output.write(source.read(7))
                raise failure

            with patch('rsh_transfer.shutil.copyfileobj', side_effect=fail_copy):
                with self.assertRaises(OSError) as caught:
                    xreceive(terminal, destination)
            self.assertIs(caught.exception, failure)
            self.assertFalse(destination.exists())
            partials = list(Path(folder).glob('*.part'))
            self.assertEqual(len(partials), 1)
            self.assertEqual(partials[0].read_bytes(), b'A' * 128)
            self.assertEqual(terminal.write.call_args_list[-1].args[0], bytes([CAN, CAN]))
            self.assertEqual(xreceive(self.receive_terminal(), destination), 128)
            self.assertEqual(destination.read_bytes(), b'A' * 128)

    def test_destination_created_during_receive_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'received.bin'
            terminal = self.receive_terminal()

            def peer_write(data):
                if data == bytes([ACK]):
                    destination.write_bytes(b'Other writer')

            terminal.write.side_effect = peer_write
            with self.assertRaises(FileExistsError):
                xreceive(terminal, destination)
            self.assertEqual(destination.read_bytes(), b'Other writer')
            self.assertEqual(len(list(Path(folder).glob('*.part'))), 1)

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
