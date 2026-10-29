"""Searchable, resumable document reader for text extracted on the host."""
from pathlib import Path
from itertools import chain
import logging
import textwrap
from .toolkit import JsonRecords
from .viewer import extract_text, extract_text_from_url

logger = logging.getLogger(__name__)


def find_next_match(lines, query, start=0):
    """Return the next matching line, wrapping once without copying indices."""
    start = max(0, min(start, len(lines)))
    folded_query = query.casefold()
    return next((i for i in chain(range(start, len(lines)), range(0, start))
                 if folded_query in lines[i].casefold()), None)


def _position_line(record, key, legacy_key, page_size):
    """Accept nonnegative saved offsets, including legacy page-based records."""
    value = record.get(key)
    if value is None:
        value = record.get(legacy_key, 0)
        scale = page_size
    else:
        scale = 1
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value) * scale


def run_reader(target, store_path, read, write, clear, columns=80, rows=24):
    remote = str(target).lower().startswith(('http://','https://'))
    key = str(target) if remote else str(Path(target).expanduser().resolve())
    text = extract_text_from_url(key) if remote else extract_text(Path(key))
    lines = []
    for line in text.splitlines():
        lines.extend(textwrap.wrap(line, max(1, columns-1), replace_whitespace=False) or [''])
    page_size = max(1, rows-8)
    store = JsonRecords(store_path)
    try:
        records = store.load()
    except (OSError, ValueError) as exc:
        logger.warning('Could not load reading positions from %s: %s', store.path, exc)
        records = []
    saved = next((r for r in records if r.get('path') == key and r.get('columns') == columns), {})
    last_page = max(0, (len(lines)-1)//page_size)
    page = min(_position_line(saved, 'line', 'page', page_size)//page_size, last_page)
    bookmark = min(_position_line(saved, 'bookmark_line', 'bookmark', page_size)//page_size, last_page)
    match_line = -1
    query, notice = '', ''
    def save_position():
        def save(records):
            records[:] = [r for r in records if not (r.get('path') == key and r.get('columns') == columns)]
            records.append({'path':key,'columns':columns,'page':page,'bookmark':bookmark,
                            'line':page*page_size,'bookmark_line':bookmark*page_size})
        try:
            store.change(save)
            return True
        except (OSError, ValueError) as exc:
            logger.warning('Could not save reading position to %s: %s', store.path, exc)
            return False

    while True:
        position_saved = save_position()
        clear()
        write(f'READER {Path(key).name[:max(1,columns-9)]}\r\n')
        write('\r\n'.join(lines[page*page_size:(page+1)*page_size]) + '\r\n\r\n')
        status=f'Page {page+1}/{max(1,(len(lines)+page_size-1)//page_size)} {notice}'
        write(status[:columns-1]+'\r\n\r\n')
        if not position_saved:
            write('Reading position not saved.\r\n')
        write('Enter=Next B=Back F=Find N=Next match\r\nM=Bookmark R=Recall G=Page Q=Back\r\n\r\nReader: ')
        choice = read().strip()
        upper = choice.upper()
        notice = ''
        if upper in ('Q','ATM','EXIT'):
            save_position()
            return
        if upper == 'B':
            page = max(0,page-1)
        elif upper in ('F','N'):
            if upper == 'F':
                write('Find text (Enter cancels): ')
                query = read().strip()
            if query:
                start = (match_line+1) if upper == 'N' and match_line >= 0 else page*page_size
                found = find_next_match(lines, query, start)
                if found is None:
                    notice = 'Not found.'
                else:
                    match_line = found
                    page = found // page_size
                    notice = f'Match on line {found+1}.'
        elif upper == 'M':
            bookmark = page; notice = 'Bookmark set.'
        elif upper == 'R':
            page = min(bookmark,max(0,(len(lines)-1)//page_size))
        elif upper == 'G':
            write('Page number: ')
            value = read().strip()
            if value.isdigit():
                page = max(0,min(int(value)-1,max(0,(len(lines)-1)//page_size)))
        elif not choice:
            if (page+1)*page_size >= len(lines):
                notice = 'End of document. Q returns.'
            else:
                page += 1
