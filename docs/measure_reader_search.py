"""Compare temporary search memory against the previous reader algorithm.

Run from the repository root: python docs/measure_reader_search.py
This measures only searching, excluding document loading, wrapping, and storage.
"""

from pathlib import Path
import statistics
import sys
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retro_os.reader import find_next_match


def previous_search(lines, query, start=0):
    return next((i for i in list(range(start, len(lines))) + list(range(0, start))
                 if query.casefold() in lines[i].casefold()), None)


def measure(search, lines, query):
    peaks, durations = [], []
    for _ in range(5):
        tracemalloc.start()
        started = time.perf_counter()
        result = search(lines, query)
        durations.append(time.perf_counter() - started)
        peaks.append(tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
        assert result == len(lines) - 1
    return statistics.median(peaks), statistics.median(durations)


if __name__ == '__main__':
    lines = ['A line of ordinary document text.'] * 100_000 + ['Straße']
    print(sys.version.split()[0], '- 100,001 lines, match at end, median of five searches')
    for label, search in [('Previous', previous_search), ('Current', find_next_match)]:
        peak, seconds = measure(search, lines, 'STRASSE')
        print(f'{label}: {peak:,} bytes peak temporary allocation; {seconds * 1000:.1f} ms')
