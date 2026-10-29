"""Download, event delivery, and batch file-operation failure regressions."""

import asyncio
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from retro_os.core import EventBus, ModuleLoader
from retro_os.toolkit import FileTools
from retro_os.viewer import DOWNLOAD_CHUNK_SIZE, fetch_url


def fail_listener(_event):
    raise RuntimeError('broken listener')


async def fail_async_listener(_event):
    await asyncio.sleep(0)
    raise RuntimeError('broken async listener')


class EventDeliveryTests(unittest.TestCase):
    def test_sync_listener_failure_does_not_block_other_listeners(self):
        bus, received = EventBus(), []
        bus.subscribe('notify', fail_listener)
        bus.subscribe('notify', lambda event: received.append(event) or 'delivered')
        with self.assertLogs('retro_os.core', level='ERROR') as logs:
            self.assertEqual(bus.publish('notify', 'hello'), [None, 'delivered'])
        self.assertEqual(received, ['hello'])
        self.assertIn('notify', '\n'.join(logs.output))

    def test_async_listener_failure_without_running_loop_is_isolated(self):
        bus = EventBus()
        bus.subscribe('notify', fail_async_listener)
        bus.subscribe('notify', lambda _: 'healthy')
        with self.assertLogs('retro_os.core', level='ERROR'):
            self.assertEqual(bus.publish('notify'), [None, 'healthy'])

    def test_sync_publish_returns_async_listener_result_without_running_loop(self):
        async def listener(event):
            return event.upper()
        bus = EventBus()
        bus.subscribe('notify', listener)
        self.assertEqual(bus.publish('notify', 'hello'), ['HELLO'])

    def test_one_module_failure_does_not_block_other_module_hooks(self):
        loader, received = ModuleLoader(None, None), []
        loader.modules = {
            'broken': SimpleNamespace(handle_event=fail_listener),
            'healthy': SimpleNamespace(handle_event=received.append),
        }
        with self.assertLogs('retro_os.core', level='ERROR'):
            loader.dispatch_event('hello')
        self.assertEqual(received, ['hello'])


class AsyncEventDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_publish_continues_after_sync_and_async_failures(self):
        bus = EventBus()
        bus.subscribe('notify', fail_listener)
        bus.subscribe('notify', fail_async_listener)
        bus.subscribe('notify', lambda _: 'healthy')
        with self.assertLogs('retro_os.core', level='ERROR'):
            self.assertEqual(await bus.publish_async('notify'), [None, None, 'healthy'])

    async def test_sync_publish_inside_loop_observes_async_errors(self):
        bus = EventBus()
        bus.subscribe('notify', fail_async_listener)
        bus.subscribe('notify', lambda _: 'healthy')
        with self.assertLogs('retro_os.core', level='ERROR'):
            task, value = bus.publish('notify')
            self.assertEqual(value, 'healthy')
            self.assertIsNone(await task)

    async def test_existing_future_is_supported_by_sync_publish_inside_loop(self):
        bus = EventBus()
        future = asyncio.get_running_loop().create_future()
        bus.subscribe('notify', lambda _: future)
        task, = bus.publish('notify')
        future.set_result('delivered')
        self.assertEqual(await task, 'delivered')

    async def test_cancellation_is_not_swallowed(self):
        bus = EventBus()
        async def cancelled(_event):
            raise asyncio.CancelledError()
        bus.subscribe('notify', cancelled)
        with self.assertRaises(asyncio.CancelledError):
            await bus.publish_async('notify')


class Response(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(data)
        self.headers = headers or {}
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.target = self.root / 'download.bin'

    def download(self, response, name='download.bin'):
        with patch('retro_os.viewer.urllib.request.urlopen', return_value=response):
            return fetch_url('https://example.org/download', self.root, name)

    def test_download_streams_in_bounded_chunks_and_replaces_on_success(self):
        data = b'payload' * 30_000
        self.target.write_bytes(b'original')
        response = Response(data, {'Content-Length': str(len(data))})
        path, size = self.download(response)
        self.assertEqual((path, size), (self.target, len(data)))
        self.assertEqual(path.read_bytes(), data)
        self.assertTrue(response.closed)
        self.assertGreater(len(response.read_sizes), 2)
        self.assertTrue(all(size == DOWNLOAD_CHUNK_SIZE for size in response.read_sizes))
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_truncated_body_preserves_existing_file_and_allows_retry(self):
        self.target.write_bytes(b'original')
        with self.assertRaisesRegex(OSError, 'expected 100 bytes, received 3'):
            self.download(Response(b'abc', {'Content-Length': '100'}))
        self.assertEqual(self.target.read_bytes(), b'original')
        self.assertEqual(list(self.root.glob('*.tmp')), [])
        self.download(Response(b'complete'))
        self.assertEqual(self.target.read_bytes(), b'complete')

    def test_network_failure_does_not_publish_partial_new_file(self):
        response = Response(b'partial')
        with patch.object(response, 'read', side_effect=[b'partial', TimeoutError('connection lost')]):
            with self.assertRaises(TimeoutError):
                self.download(response)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.root.glob('*.tmp')), [])
        self.assertTrue(response.closed)

    def test_disk_sync_and_replace_failures_preserve_previous_file(self):
        self.target.write_bytes(b'original')
        for method in ('sync', 'replace'):
            with self.subTest(method=method):
                failure = (patch('retro_os.viewer.os.fsync', side_effect=OSError('disk error'))
                           if method == 'sync' else patch.object(Path, 'replace', side_effect=OSError('locked')))
                with failure, self.assertRaises(OSError):
                    self.download(Response(b'new'))
                self.assertEqual(self.target.read_bytes(), b'original')
                self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_automatic_filename_and_unknown_length_are_supported(self):
        path, size = self.download(Response(b'news', {'Content-Type': 'text/plain',
                                                   'Content-Length': 'not-a-number'}), name=None)
        self.assertEqual(path.name, 'download.txt')
        self.assertEqual(size, 4)
        self.assertEqual(path.read_bytes(), b'news')

    def test_partial_disk_write_preserves_previous_file(self):
        self.target.write_bytes(b'original')
        original_temporary_file = tempfile.NamedTemporaryFile
        def failing_output(**kwargs):
            output = original_temporary_file(**kwargs)
            original_write = output.write
            def partial_write(data):
                original_write(data[:2])
                output.flush()
                raise OSError('disk full')
            output.write = partial_write
            return output
        with patch('retro_os.viewer.tempfile.NamedTemporaryFile', side_effect=failing_output):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.download(Response(b'new content'))
        self.assertEqual(self.target.read_bytes(), b'original')
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_response_close_failure_does_not_replace_previous_file(self):
        class CloseFailure(Response):
            def __exit__(self, *args):
                super().__exit__(*args)
                raise OSError('response close failed')
        self.target.write_bytes(b'original')
        with self.assertRaisesRegex(OSError, 'response close failed'):
            self.download(CloseFailure(b'new content'))
        self.assertEqual(self.target.read_bytes(), b'original')
        self.assertEqual(list(self.root.glob('*.tmp')), [])


class BatchDestinationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.destination = self.root / 'destination'
        self.destination.mkdir()
        self.tools = FileTools(self.root, SimpleNamespace(fs={'tool_data': self.root}))

    def test_duplicate_names_rejected_before_any_copy_or_move(self):
        sources = []
        for name, contents in [('first', 'first data'), ('second', 'second data')]:
            folder = self.root / name
            folder.mkdir()
            path = folder / 'game.dsk'
            path.write_text(contents)
            sources.append(path)
        for action in ('copy', 'move'):
            with self.subTest(action=action):
                self.tools.marked = set(sources)
                with self.assertRaisesRegex(ValueError, 'same destination name'):
                    self.tools.command([action, 'marked', str(self.destination)])
                self.assertEqual(list(self.destination.iterdir()), [])
                self.assertEqual([p.read_text() for p in sources], ['first data', 'second data'])
                self.assertEqual(self.tools.marked, set(sources))

    def test_distinct_names_can_still_be_copied_and_moved_in_batches(self):
        for action in ('copy', 'move'):
            with self.subTest(action=action):
                folder = self.root / action
                folder.mkdir()
                paths = [folder / f'{index}.txt' for index in range(2)]
                for path in paths:
                    path.write_text(path.name)
                destination = self.destination / action
                destination.mkdir()
                self.tools.marked = set(paths)
                self.tools.command([action, 'marked', str(destination)])
                self.assertEqual(sorted(p.name for p in destination.iterdir()), ['0.txt', '1.txt'])
                self.assertEqual([p.exists() for p in paths], [action == 'copy'] * 2)
                self.assertEqual(self.tools.marked, set())


if __name__ == '__main__':
    unittest.main()
