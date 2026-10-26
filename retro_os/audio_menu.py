"""Compact audio player menus with navigation confined to the file browser."""
import shlex

from retro_os.core import Shell

MAIN = ("[1] Browse files   [2] Play queue\n"
        "[3] Pause/resume   [4] Stop\n"
        "[5] Next track     [6] Previous\n"
        "[7] Volume         [8] Queue/playlists\n"
        "\n[Q] Return to Main Menu")
PLAYLISTS = ("[1] Show queue   [2] Save playlist\n"
             "[3] List playlists  [4] Load playlist\n"
             "[5] Edit queue    [6] Repeat on/off\n"
             "[7] Shuffle       [8] Radio / music folder\n"
             "\n[Q] Back to player")
BROWSER = ("Number=Open folder / Play file\n"
           "D=Drives B=Parent H=Shared G=Go to path\n"
           "F=Filter V=Favorites A=Queue P=Path Q=Back")


def run_audio_menu(execute, read, write, render, clear, rows=24):
    """Callbacks keep terminal IO and the player's existing CLI in one session."""
    screen = 'main'
    result = execute('audio info')
    notice = ''

    def command(args):
        return execute(shlex.join(['audio', *args]))

    def ask(prompt):
        write(prompt + ' (Enter cancels): ')
        value = read().strip()
        return '' if value.upper() in ('Q','ATM') else value

    while True:
        clear()
        write('\r\n--- AUDIO ' + ('BROWSER' if screen == 'browser' else 'QUEUE / PLAYLISTS' if screen == 'playlists' else 'PLAYER') + ' ---\r\n')
        if screen == 'browser':
            body=str(result) + ('\n\n'+notice if notice else '')
            notice=''
            render(body, page_lines=max(1,rows-10))
            write('\r\n'+BROWSER.replace('\n','\r\n')+'\r\n')
        elif screen == 'radio':
            write('[1] Play stream URL [2] Saved stations\r\n[3] Play station    [4] Save station\r\n[5] Delete station  [6] Save music folder\r\n[7] Open music folder\r\n\r\n[Q] Back to player\r\n\r\n')
            render(result, page_lines=max(1,rows-15))
        elif screen == 'queue':
            write('[1] Remove track [2] Reorder track\r\n\r\n[Q] Back to player\r\n\r\n')
            render(result,page_lines=max(1,rows-11))
        else:
            # Draw controls first so they never scroll the last command's result away.
            write((PLAYLISTS if screen == 'playlists' else MAIN).replace('\n', '\r\n') + '\r\n\r\n')
            render(result, page_lines=max(1, rows - 14))
        write('\r\nChoice (or command): ')
        choice = read().strip()
        upper = choice.upper()
        if upper in ('ATM', 'QUIT', 'EXIT'):
            return False
        if not choice or upper == 'Q':
            if screen == 'main':
                return False
            screen = 'main'
            result = command(['info'])
            continue
        args = None
        if screen == 'browser':
            if choice.isdigit():
                result = command(['open', choice])
                # A file selection starts playback and returns to player controls.
                if not str(result).startswith(('Audio directory:', 'Could not complete')):
                    screen = 'main'
                continue
            if upper in ('D', 'B', 'H'):
                result = command([{'D': 'drives', 'B': 'parent', 'H': 'home'}[upper]])
                continue
            if upper == 'F':
                value = ask('Filename filter (* clears)')
                if value:
                    execute(__import__('shlex').join(['fileman','filter',value]))
                    result = command(['list'])
                continue
            if upper == 'V':
                render(execute('fileman favorites'), page_lines=max(1,rows-11))
                write('A=Add current G=Go D=Delete Q=Back\r\nFavorites: ')
                action = read().strip().upper()
                if action in ('A','G','D'):
                    value = ask('Favorite name')
                    if value:
                        notice = str(execute(__import__('shlex').join(['fileman','favorite',{'A':'add','G':'go','D':'delete'}[action],value])))
                        result = command(['list'])
                continue
            if upper in ('G', 'P', 'A'):
                value = ask({'G': 'Folder path', 'P': 'Audio file path', 'A': 'File number/path'}[upper])
                if not value:
                    continue
                action = {'G': 'cd', 'P': 'play', 'A': 'queue'}[upper]
                output = command([action, value])
                if action == 'queue':
                    notice = str(output)
                else:
                    result = output
                    if action == 'play':
                        screen = 'main'
                continue
        elif screen == 'radio':
            if choice == '2':
                args = ['station','list']
            elif choice == '7':
                screen = 'browser'; result = command(['musicfolder']); continue
            elif choice in ('1','3','4','5','6'):
                value = ask({'1':'Stream URL','3':'Station name','4':'Station name','5':'Station name','6':'Music folder path'}[choice])
                if not value:
                    continue
                if choice == '4':
                    url = ask('Stream URL')
                    if not url:
                        continue
                    args = ['station','add',value,url]
                else:
                    args = {'1':['radio',value],'3':['station','play',value],
                            '5':['station','delete',value],'6':['musicfolder',value]}[choice]
        elif screen == 'queue':
            if choice in ('1','2'):
                value = ask('Queue number')
                if not value:
                    continue
                args = ['remove' if choice == '1' else 'reorder',value]
                if choice == '2':
                    position = ask('New position')
                    if not position:
                        continue
                    args.append(position)
        elif screen == 'playlists':
            if choice == '5':
                screen = 'queue'; result = command(['tracks']); continue
            if choice == '8':
                screen = 'radio'; result = command(['station','list']); continue
            if choice in ('6','7'):
                args = ['repeat' if choice == '6' else 'shuffle']

            elif choice in ('1', '3'):
                args = ['tracks' if choice == '1' else 'playlists']
            elif choice in ('2', '4'):
                name = ask('Playlist name')
                if not name:
                    continue
                args = ['save' if choice == '2' else 'load', name]
        else:
            if choice == '1':
                screen = 'browser'
                result = command(['musicfolder'])
                if str(result).startswith('No saved music folder'):
                    result = command(['list'])
                continue
            if choice == '8':
                screen = 'playlists'
                result = command(['tracks'])
                continue
            if choice == '3':
                # The backend decides atomically which pause action is appropriate.
                args = ['toggle']
            elif choice in ('2', '4', '5', '6'):
                args = [{'2': 'play', '4': 'stop', '5': 'next', '6': 'prev'}[choice]]
            elif choice == '7':
                value = ask('Volume (0-100)')
                if not value:
                    continue
                args = ['volume', value]
        if args is None:
            try:
                args = Shell.split_line(choice)
            except ValueError as exc:
                result = str(exc)
                continue
            if args and args[0].lower() in ('audio', 'player'):
                args = args[1:]
        result = command(args)
