"""Scheduler persistence and malformed-task isolation regressions."""
import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from retro_os.scheduler import TaskScheduler


class SchedulerReliabilityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'tasks.json'

    def test_failed_replace_preserves_saved_tasks_and_cleans_temporary_file(self):
        scheduler = TaskScheduler(self.path)
        scheduler.add_task('Original', 'news')
        original = self.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('disk unavailable')):
            with self.assertLogs('retro_os.scheduler', level='ERROR'):
                scheduler.add_task('New', 'weather')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        self.assertTrue(scheduler.save())
        self.assertEqual(len(TaskScheduler(self.path).list_tasks()), 2)

    def test_serialization_failure_preserves_saved_file(self):
        scheduler = TaskScheduler(self.path)
        scheduler.add_task('Original', 'news')
        original = self.path.read_bytes()
        scheduler.get_task('1')['params'] = {'invalid': object()}
        with self.assertLogs('retro_os.scheduler', level='ERROR'):
            self.assertFalse(scheduler.save())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_invalid_task_does_not_stop_other_due_tasks(self):
        executed = []
        scheduler = TaskScheduler(self.path, executor=lambda command: executed.append(command) or 'OK')
        bad = scheduler.add_task('Broken', 'bad')
        good = scheduler.add_task('Healthy', 'news')
        bad['params'] = {'every': 'invalid'}
        good['next_run'] = (datetime.datetime.now() - datetime.timedelta(minutes=1)).isoformat()
        scheduler._running = True
        def stop_after_tick(_):
            scheduler.stop()
        with patch('retro_os.scheduler.time.sleep', side_effect=stop_after_tick):
            with self.assertLogs('retro_os.scheduler', level='WARNING'):
                scheduler._worker_loop()
        self.assertEqual(executed, ['news'])
        self.assertFalse(bad['enabled'])
        self.assertIn('Invalid schedule', bad['last_status'])
        self.assertEqual(good['last_status'], 'OK')
        self.assertFalse(TaskScheduler(self.path).get_task('1')['enabled'])

    def test_load_skips_non_object_entries_and_normalizes_ids(self):
        self.path.write_text(json.dumps({'1': None, '2': {'name': 'Keep'}}))
        with self.assertLogs('retro_os.scheduler', level='WARNING'):
            scheduler = TaskScheduler(self.path)
        self.assertEqual(scheduler.list_tasks(), [{'id': '2', 'name': 'Keep'}])
        self.path.write_text(json.dumps([None, {'id': 7, 'name': 'Legacy'}]))
        scheduler.load()
        self.assertEqual(scheduler.get_task('7')['id'], '7')

    def test_timezone_timestamp_is_repaired_without_crashing_worker(self):
        scheduler = TaskScheduler(self.path)
        task = scheduler.add_task('News', 'news')
        task['next_run'] = '2020-01-01T00:00:00+00:00'
        scheduler._running = True
        with patch('retro_os.scheduler.time.sleep', side_effect=lambda _: scheduler.stop()):
            scheduler._worker_loop()
        self.assertIsNone(datetime.datetime.fromisoformat(task['next_run']).tzinfo)
        self.assertTrue(task['enabled'])
