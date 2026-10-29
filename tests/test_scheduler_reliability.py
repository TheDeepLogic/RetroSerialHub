"""Scheduler persistence and malformed-task isolation regressions."""
import datetime
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from retro_os.scheduler import TaskScheduler, calculate_next_run, split_commands


class SchedulerReliabilityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'tasks.json'

    def test_recurrences_and_calendar_rollovers(self):
        base = datetime.datetime(2024, 1, 31, 12, 30)
        cases = [
            ('interval', {'every': 15}, datetime.datetime(2024, 1, 31, 12, 45)),
            ('hourly', {'minute': 30}, datetime.datetime(2024, 1, 31, 13, 30)),
            ('daily', {'time': '12:30'}, datetime.datetime(2024, 2, 1, 12, 30)),
            ('weekly', {'weekday': 'wed', 'time': '12:30'}, datetime.datetime(2024, 2, 7, 12, 30)),
            ('monthly', {'day': 31, 'time': '12:30'}, datetime.datetime(2024, 2, 29, 12, 30)),
        ]
        for kind, params, expected in cases:
            with self.subTest(kind=kind):
                self.assertEqual(calculate_next_run(kind, params, base), expected)
        self.assertEqual(calculate_next_run('monthly', {'day': 31}, datetime.datetime(2024, 12, 31)),
                         datetime.datetime(2025, 1, 31))

    def test_invalid_schedules_are_rejected_before_persisting(self):
        scheduler = TaskScheduler(self.path)
        for kind, params in [('unknown', {}), ('interval', {'every': 0}),
                             ('hourly', {'minute': 60}), ('daily', {'time': '25:00'}),
                             ('weekly', {'weekday': 'oops'}), ('monthly', {'day': 32})]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                scheduler.add_task('Bad', 'news', kind, params)
        self.assertEqual(scheduler.list_tasks(), [])
        self.assertFalse(self.path.exists())

    def test_chain_preserves_quotes_paths_and_urls(self):
        command = r'''view "C:\My Files\a;b.txt" : broadcast "hello : world; ready"; https://example.com/a;b'''
        self.assertEqual(split_commands(command), [r'''view "C:\My Files\a;b.txt"''',
                         'broadcast "hello : world; ready"', 'https://example.com/a;b'])
        with self.assertRaises(ValueError):
            split_commands('broadcast "unfinished')

    def test_enable_disable_are_idempotent_and_survive_reload(self):
        scheduler = TaskScheduler(self.path)
        task = scheduler.add_task('News', 'news')
        original = task['next_run']
        self.assertTrue(scheduler.toggle_task('1', True))
        self.assertEqual(task['next_run'], original)
        self.assertFalse(scheduler.toggle_task('1', False))
        self.assertFalse(scheduler.toggle_task('1', False))
        self.assertFalse(TaskScheduler(self.path).get_task('1')['enabled'])
        self.assertTrue(scheduler.toggle_task('1', True))

    def test_concurrent_manual_execution_is_not_duplicated(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def execute(command):
            calls.append(command)
            entered.set()
            release.wait(3)
            return 'done'
        scheduler = TaskScheduler(self.path, executor=execute)
        scheduler.add_task('News', 'news')
        worker = threading.Thread(target=scheduler.run_task_now, args=('1',))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertIn('already running', scheduler.run_task_now('1'))
        finally:
            release.set()
            worker.join(3)
        self.assertEqual(calls, ['news'])
        self.assertFalse(worker.is_alive())

    def test_worker_stops_and_restarts_without_duplicate_threads(self):
        scheduler = TaskScheduler(self.path)
        self.addCleanup(scheduler.stop)
        scheduler.start()
        first = scheduler._thread
        scheduler.start()
        self.assertIs(scheduler._thread, first)
        scheduler.stop()
        self.assertFalse(first.is_alive())
        scheduler.start()
        self.assertIsNot(scheduler._thread, first)
        self.assertTrue(scheduler._thread.is_alive())

    def test_disabled_and_deleted_queued_tasks_are_skipped(self):
        for operation in ('disable', 'delete'):
            with self.subTest(operation=operation):
                calls = []
                scheduler = TaskScheduler(self.path)
                for task in scheduler.list_tasks():
                    scheduler.remove_task(task['id'])
                first = scheduler.add_task('First', 'first')
                second = scheduler.add_task('Second', 'second')
                for task in (first, second):
                    task['next_run'] = '2020-01-01T00:00:00'
                def execute(command):
                    calls.append(command)
                    if operation == 'disable':
                        scheduler.toggle_task(second['id'], False)
                    else:
                        scheduler.remove_task(second['id'])
                    return 'OK'
                scheduler.executor = execute
                scheduler._running = True
                with patch.object(scheduler._stop_event, 'wait', side_effect=lambda _: scheduler.stop()):
                    scheduler._worker_loop()
                self.assertEqual(calls, ['first'])

    def test_executor_and_broadcaster_failures_do_not_stop_later_runs(self):
        def fail(_command):
            raise RuntimeError('command failed')
        def broadcast(_task, _output):
            raise RuntimeError('broadcast failed')
        scheduler = TaskScheduler(self.path, executor=fail, broadcaster=broadcast)
        task = scheduler.add_task('News', 'news')
        with self.assertLogs('retro_os.scheduler', level='WARNING'):
            self.assertIn('Execution error', scheduler.run_task_now('1'))
        self.assertIn('command failed', task['last_status'])
        scheduler.executor = lambda _: 'recovered'
        with self.assertLogs('retro_os.scheduler', level='WARNING'):
            self.assertEqual(scheduler.run_task_now('1'), 'recovered')
        self.assertEqual(TaskScheduler(self.path).get_task('1')['last_status'], 'OK')

    def test_runtime_cli_preserves_command_and_exposes_details(self):
        from retro_os.runtime import create_runtime
        root = self.path.parent
        _, _, host, shell, _ = create_runtime({'tasks': self.path, 'files': root / 'files'},
                                               profiles_path=root / 'keyboard.json')
        self.addCleanup(host.scheduler.stop)
        shell.register_command('echo', lambda args: repr(args))
        result = shell.execute('schedule add "Quoted task" 5 echo "hello; world : ready" : calc 2 + 2')
        self.assertIn('Scheduled task', result)
        self.assertEqual(shell.execute('schedule run 1'), "['hello; world : ready']\n\n4")
        self.assertIn('Last status: OK', shell.execute('schedule details 1'))
        self.assertIn('disabled', shell.execute('schedule disable 1'))
        self.assertIn('disabled', shell.execute('schedule disable 1'))
        self.assertIn('enabled', shell.execute('schedule enable 1'))
        self.assertIn('enabled', shell.execute('schedule enable 1'))
        self.assertIn('must be positive', shell.execute('schedule add Bad 0 news'))

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
        with patch.object(scheduler._stop_event, 'wait', side_effect=stop_after_tick):
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
        with patch.object(scheduler._stop_event, 'wait', side_effect=lambda _: scheduler.stop()):
            scheduler._worker_loop()
        self.assertIsNone(datetime.datetime.fromisoformat(task['next_run']).tzinfo)
        self.assertTrue(task['enabled'])
