"""Shared file chooser used by file management, transfers, archives, and documents."""
import shlex


def run_file_browser(files, execute, read, write, render, clear, dispatch, purpose='files', rows=24, initial=None):
    result, notice = (files.command(['ls']) if initial is None else initial), ''
    def command(name, *args):
        output = execute(shlex.join([name, *map(str,args)]))
        render(output, page_lines=max(1,rows-8))
        dispatch()
        write('\r\nEnter to return: ')
        read()
        return output
    def ask(label):
        write(label + ' (Enter cancels): ')
        value = read().strip()
        return '' if value.upper() in ('Q','ATM') else value
    def safe(operation):
        try:
            return operation()
        except (OSError, ValueError, RuntimeError) as exc:
            return 'Could not complete: ' + str(exc)
    while True:
        clear()
        write('\r\n--- ' + {'files':'FILE MANAGER','transfer':'FILE TRANSFERS','archive':'ARCHIVE BROWSER','view':'DOCUMENT VIEWER','find':'FIND FILES'}.get(purpose,purpose.upper()) + ' ---\r\n')
        body=str(result) + ('\n\n'+str(notice) if notice else '')
        notice=''
        render(body,page_lines=max(1,rows-11))
        write('\r\nNumber=Open D=Drives B=Parent H=Shared\r\nG=Path F=Filter V=Favorites M=Marked\r\nO=Other operations P=Previous Q=Back\r\n\r\nChoice (or command): ')
        choice = read().strip(); upper = choice.upper()
        if upper in ('Q','ATM','EXIT'):
            return False
        if not choice:
            result = safe(lambda: files.command(['ls'])); continue
        if upper in ('D','B','H','P'):
            result = safe(lambda: files.command([{'D':'drives','B':'parent','H':'home','P':'previous'}[upper]])); continue
        if upper in ('G','F'):
            value = ask('Folder path' if upper == 'G' else 'Filename filter (* clears)')
            if value:
                result = safe(lambda: files.command(['cd' if upper == 'G' else 'filter',value]))
            continue
        if upper == 'V':
            clear(); render(files.command(['favorites']), page_lines=max(1,rows-8))
            write('A=Add current folder G=Go D=Delete Q=Back\r\nFavorites: ')
            action = read().strip().upper()
            if action in ('A','G','D'):
                value = ask('Favorite name')
                if value:
                    notice = safe(lambda: files.command(['favorite', {'A':'add','G':'go','D':'delete'}[action],value]))
                    result = files.command(['ls'])
            continue
        if upper == 'M':
            clear(); render('\n'.join(str(p) for p in sorted(files.marked)) or 'No marked items.', page_lines=max(1,rows-7))
            write('C=Copy M=Move U=Unmark all Q=Back\r\nMarked: ')
            action = read().strip().upper()
            if action == 'U':
                result = files.command(['unmark'])
            elif action in ('C','M'):
                value = ask('Destination folder (=last: ' + files.last_destination + ')')
                if value == '=':
                    value = files.last_destination
                if value:
                    result = safe(lambda: files.command(['copy' if action == 'C' else 'move','marked',value]))
            continue
        if upper == 'O':
            clear()
            write('A=Create folder B=Upload C=Protocol\r\nD=Find E=Enter URL F=Read messages\r\nQ=Back\r\nOperation: ')
            action = read().strip().upper()
            if action in ('A','B','C','D','E'):
                value = ask({'A':'Folder name','B':'Upload filename','C':'Protocol (XMODEM/YMODEM/ASCII)', 'D':'Search pattern','E':'URL'}[action])
                if value:
                    if action == 'A':
                        result = safe(lambda: files.command(['mkdir',value]))
                    elif action == 'B':
                        command('xrecv', files.cwd / value)
                    elif action == 'C':
                        notice = command('machine','protocol',value)
                    elif action == 'D':
                        result = execute(shlex.join(['findfiles',value,str(files.cwd)]))
                    else:
                        command('read',value)
            elif action == 'F':
                notice = command('notifications')
            continue
        if choice.isdigit():
            try:
                path = files.path(choice)
                if path.is_dir():
                    result = files.command(['cd',str(path)]); continue
                clear(); render(files.command(['info',str(path)]), page_lines=max(1,rows-10))
                audio = path.suffix.lower() in {'.mp3','.wav','.wma','.flac','.ogg','.m4a','.aac','.aiff'}
                picture = path.suffix.lower() in {'.png','.jpg','.jpeg','.gif','.bmp','.webp'}
                write(('A=Image' if picture else 'A=View') + (' B=Play' if audio else '') + ' C=Copy D=Move\r\nE=Rename F=Transfer' + (' G=ZIP' if path.suffix.lower() == '.zip' else '') + ' H=Mark\r\nQ=Back\r\n\r\nAction: ')
                action = read().strip().upper()
                if action in ('A','B'):
                    command('audio','play',str(path)) if action == 'B' and audio else command('ascii' if picture else 'read',str(path))
                elif action in ('C','D','E'):
                    value = ask('Destination / new name (=last: ' + files.last_destination + ')')
                    if value == '=' and action != 'E':
                        value = files.last_destination
                    if value:
                        result = files.command([{'C':'copy','D':'move','E':'rename'}[action],str(path),value])
                elif action == 'F':
                    terminal = getattr(files.context.host_env, 'terminal', None)
                    protocol = getattr(terminal, '_rsh_transfer_mode', 'XMODEM')
                    command({'XMODEM':'xsend','YMODEM':'ysend','ASCII':'asend'}[protocol],str(path))
                elif action == 'G' and path.suffix.lower() == '.zip':
                    opened = command('archive','open',str(path))
                    if str(opened).startswith('Could not complete'):
                        notice = str(opened).splitlines()[0]
                        continue
                    notice = 'Archive opened: ' + path.name
                    write('Extract member number / all (Enter cancels): ')
                    member = read().strip()
                    if member:
                        destination = ask('New destination folder')
                        if destination:
                            notice = command('archive','extract',member,destination)
                elif action == 'H':
                    result = files.command(['mark',str(path)])
            except (OSError, ValueError, RuntimeError) as exc:
                notice = str(exc)
            if purpose != 'find':
                result = safe(lambda: files.command(['ls']))
            continue
        try:
            from .core import Shell
            args = Shell.split_line(choice)
            if args and args[0].lower() in ("fileman","fm"):
                args = args[1:]
            if args:
                output = command('fileman', *args)
                notice = str(output).splitlines()[0] if output else ''
                result = files.command(['ls'])
        except ValueError as exc:
            notice = str(exc)
