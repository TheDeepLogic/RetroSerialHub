"""Shared JSON storage, safe starter defaults, and migration from older releases."""
from pathlib import Path
import shutil
import threading

BASE_DIR = Path(__file__).resolve().parent
_LOCK = threading.RLock()
ROOT_FILES = (
    'ai_config.json', 'bbs_directory.json', 'browser_bookmarks.json',
    'ftp_bookmarks.json', 'telnet_bookmarks.json', 'keyboard_profiles.json',
    'scheduled_tasks.json', 'scheduler_tasks.json', 'user_shortcuts.json',
    'terminal_columns.json', 'terminal_ansi_translation.json',
    'telnet_allowlist.json', 'host_settings.json', 'welcome_banner.json',
)


def settings_dir(base=None):
    """Move legacy JSON once, then seed missing live files from public defaults.

    Existing live settings win. Different legacy copies are preserved under
    local/legacy rather than discarded or silently replacing live data.
    Explicit base directories keep standalone runtimes and tests isolated.
    """
    base = Path(base) if base is not None else BASE_DIR
    local = base / 'settings' / 'local'
    with _LOCK:
        local.mkdir(parents=True, exist_ok=True)
        sources = [base / name for name in ROOT_FILES]
        for folder in ('mail', 'hub_tools', 'retro_os'):
            sources.extend(sorted((base / folder).glob('*.json')))
        for source in sources:
            if not source.is_file():
                continue
            target = local / source.name
            if target.exists():
                if source.read_bytes() == target.read_bytes():
                    source.unlink()
                    continue
                backups = local / 'legacy'
                backups.mkdir(exist_ok=True)
                target = backups / f'{source.parent.name}-{source.name}'
                index = 1
                while target.exists():
                    target = backups / f'{source.parent.name}-{index}-{source.name}'
                    index += 1
            source.rename(target)
        for default in sorted((base / 'settings' / 'defaults').glob('*.json')):
            if default.name.endswith('.example.json'):
                continue
            target = local / default.name
            if not target.exists():
                # Exclusive creation also protects against another hub process.
                try:
                    with target.open('xb') as output, default.open('rb') as source:
                        shutil.copyfileobj(source, output)
                except FileExistsError:
                    pass
    return local


def settings_path(name, base=None):
    if Path(name).name != name or not name.endswith('.json'):
        raise ValueError('Settings names must be plain JSON filenames.')
    return settings_dir(base) / name
