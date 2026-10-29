import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from retro_os.scheduler import TaskScheduler


class SchedulerReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'tasks.json'

    def task(self, task_id='1', **changes):
        task = dict(id=task_id, name='Test', command='calc 6 * 7',
                    schedule_type='interval', params={'every': 15},
                    next_run='2000-01-01T00:00:00', enabled=True)
        task.update(changes)
        return task

    def test_invalid_entries_do_not_hide_valid_dictionary_tasks(self):
        self.path.write_text(json.dumps({
            'bad-shape': None,
            'bad-schedule': self.task('2', params={'every': 'broken'}),
            'missing-schedule': {'command': 'news'},
            'bad-command': self.task('3', command=None),
            '1': self.task(),
        }), encoding='utf-8')
        original = self.path.read_bytes()
        with self.assertLogs('retro_os.scheduler', level='WARNING') as logs:
            scheduler = TaskScheduler(self.path)
        self.assertEqual(len(logs.output), 4)
        self.assertEqual([t['id'] for t in scheduler.list_tasks()], ['1'])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(scheduler.run_task_now('1').split('Command: ')[1], 'calc 6 * 7')

    def test_legacy_list_skips_invalid_entries_and_normalizes_ids(self):
        self.path.write_text(json.dumps([None, self.task(7), self.task(7), self.task('8')]),
                             encoding='utf-8')
        with self.assertLogs('retro_os.scheduler', level='WARNING'):
            scheduler = TaskScheduler(self.path)
        self.assertEqual([t['id'] for t in scheduler.list_tasks()], ['7', '8'])
        self.assertEqual(scheduler.get_task('7')['id'], '7')

    def test_replacement_failure_preserves_saved_tasks_and_allows_retry(self):
        scheduler = TaskScheduler(self.path)
        scheduler.add_task('First', 'news')
        original = self.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=PermissionError('locked')):
            with self.assertLogs('retro_os.scheduler', level='ERROR'):
                scheduler.add_task('Second', 'weather')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        scheduler.save()
        self.assertEqual(len(TaskScheduler(self.path).list_tasks()), 2)

    def test_partial_write_failure_preserves_original_and_cleans_temp_file(self):
        scheduler = TaskScheduler(self.path)
        scheduler.add_task('First', 'news')
        original = self.path.read_bytes()

        def fail_after_write(tasks, output, **kwargs):
            output.write('{"partial":')
            raise OSError('disk full')

        with patch('retro_os.scheduler.json.dump', side_effect=fail_after_write):
            with self.assertLogs('retro_os.scheduler', level='ERROR'):
                scheduler.save()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        scheduler.save()
        self.assertEqual(len(TaskScheduler(self.path).list_tasks()), 1)

    def test_worker_handles_edited_timestamps_and_runs_other_due_tasks(self):
        for timestamp in ('broken', 123, '2000-01-01T00:00:00+00:00'):
            with self.subTest(timestamp=timestamp):
                self.path.write_text(json.dumps({
                    '1': self.task(next_run=timestamp), '2': self.task('2'),
                }), encoding='utf-8')
                executed = []
                scheduler = TaskScheduler(self.path, executor=lambda cmd: executed.append(cmd) or 'OK')
                scheduler._running = True
                # One deterministic worker iteration without sleeping or threads.
                with patch('retro_os.scheduler.time.sleep', side_effect=lambda _: scheduler.stop()):
                    scheduler._worker_loop()
                self.assertIn('calc 6 * 7', executed)
                self.assertEqual(scheduler.get_task('2')['last_status'], 'OK')
                repaired = datetime.datetime.fromisoformat(scheduler.get_task('1')['next_run'])
                self.assertGreater(repaired, datetime.datetime.now())


if __name__ == '__main__':
    unittest.main()
