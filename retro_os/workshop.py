"""Portable host-assisted preparation tools; all source files remain unchanged."""
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re


def _source(value):
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError('Choose a regular file.')
    return path


def _new(path, data):
    path = Path(path).expanduser().resolve()
    with path.open('xb') as output:
        output.write(data)
    return f'Created {path} ({len(data)} bytes).'


def _small(path, limit=8 * 1024 * 1024):
    if path.stat().st_size > limit:
        raise ValueError('This operation accepts files up to 8 MiB.')
    return path.read_bytes()


def hexdump(data, offset=0):
    return '\n'.join(f'{offset+i:08X}  ' + ' '.join(f'{b:02X}' for b in data[i:i+16]).ljust(47)
                     + '  ' + ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
                     for i in range(0, len(data), 16))


def renumber_line(line, mapping, missing):
    def reference(match):
        value = int(match[0])
        if value not in mapping:
            missing.add(value)
        return str(mapping.get(value,value))
    def code(text):
        return re.sub(r'\b(GOTO|GO\s+TO|GOSUB|THEN|RESTORE|RUN|RESUME)\s*(\d+(?:\s*,\s*\d+)*)',
                      lambda m: m[1] + ' ' + re.sub(r'\d+',reference,m[2]),text,flags=re.I)
    output, pending, index = [], '', 0
    while index < len(line):
        if line[index] == '"':
            output.append(code(pending)); pending = ''
            end = line.find('"',index+1)
            end = len(line)-1 if end < 0 else end
            output.append(line[index:end+1]); index = end+1
        elif re.match(r'REM\b',line[index:],flags=re.I) and (index == 0 or not line[index-1].isalnum()):
            output.extend((code(pending),line[index:])); return ''.join(output)
        elif re.match(r'DATA\b',line[index:],flags=re.I) and (index == 0 or not line[index-1].isalnum()):
            output.append(code(pending)); pending = ''
            end, quoted = index, False
            while end < len(line):
                if line[end] == '"':
                    quoted = not quoted
                if line[end] == ':' and not quoted:
                    break
                end += 1
            output.append(line[index:end]); index = end
        else:
            pending += line[index]; index += 1
    output.append(code(pending))
    return ''.join(output)


class Workshop:
    HELP = ('workshop <disk|hex|hash|text|basic|split|join|encode|decode|compare> ...\n'
            'Outputs are new files; existing files are never replaced.\n'
            'Each Workshop menu has help with its exact arguments.')

    def command(self, args):
        if not args or args[0] == 'help':
            return self.HELP
        action, *args = args
        if action == 'disk':
            if not args:
                return 'diskinfo <image> [sector-size=256] [sector=0]\nInspect size and a raw sector; no filesystem writes.'
            path = _source(args[0])
            size = int(args[1]) if len(args) > 1 else 256
            sector = int(args[2]) if len(args) > 2 else 0
            if size not in (128, 256, 512, 1024, 2048, 4096) or sector < 0:
                raise ValueError('Sector size: 128/256/512/1024/2048/4096; sector must be nonnegative.')
            total = path.stat().st_size
            with path.open('rb') as source:
                magic = source.read(4)
                source.seek(sector * size)
                data = source.read(size)
            if not data:
                raise ValueError('Sector is beyond the end of the image.')
            kind = '2IMG container (raw view includes container header)' if magic == b'2IMG' else 'Raw/unknown image'
            hints = {143360: 'Size matches a 140 KiB image', 163840: 'Size matches a 160 KiB image',
                     184320: 'Size matches a 180 KiB image', 368640: 'Size matches a 360 KiB image',
                     737280: 'Size matches a 720 KiB image', 1474560: 'Size matches a 1.44 MiB image'}
            return f'{path}\n{kind}\nSize: {total} bytes\n{hints.get(total, "No size hint")}\n' + f'{total // size} complete {size}-byte sectors; {total % size} extra bytes\nSize hints do not identify the filesystem.\n' + hexdump(data, sector * size)
        if action == 'diskextract':
            if len(args) != 5:
                return 'diskinfo extract <image> <new-output> <sector-size> <first-sector> <sector-count>\nRaw byte-sector extraction, not filesystem extraction.'
            path = _source(args[0])
            size, first, count = map(int,args[2:])
            if size not in (128,256,512,1024,2048,4096) or first < 0 or count < 1 or count*size > 16*1024*1024:
                raise ValueError('Choose a valid sector range up to 16 MiB.')
            with path.open('rb') as source:
                source.seek(first*size)
                data = source.read(count*size)
            if len(data) != count*size:
                raise ValueError('Sector range extends beyond the image.')
            return _new(args[1],data)
        if action == 'hex':
            if not args:
                return 'hexview <file> [offset=0] [count=256]\nOffsets accept decimal or 0x hex; maximum count 4096.'
            path = _source(args[0])
            offset = int(args[1], 0) if len(args) > 1 else 0
            count = int(args[2], 0) if len(args) > 2 else 256
            if offset < 0 or not 1 <= count <= 4096:
                raise ValueError('Offset must be nonnegative; count 1-4096.')
            with path.open('rb') as source:
                source.seek(offset)
                data = source.read(count)
            return hexdump(data, offset) or '(end of file)'
        if action == 'hash':
            if not args:
                return 'checksum <file> [sha256|sha1|md5|crc32]\nDefault SHA-256; streams large files.'
            path = _source(args[0])
            algorithm = args[1].lower() if len(args) > 1 else 'sha256'
            if algorithm not in ('sha256', 'sha1', 'md5', 'crc32'):
                raise ValueError('Choose sha256, sha1, md5, or crc32.')
            digest = hashlib.new(algorithm) if algorithm != 'crc32' else None
            crc = 0
            with path.open('rb') as source:
                for block in iter(lambda: source.read(65536), b''):
                    if digest:
                        digest.update(block)
                    else:
                        crc = binascii.crc32(block, crc)
            return f'{path}\n{algorithm.upper()}: {digest.hexdigest() if digest else format(crc & 0xffffffff, "08x")}'
        if action == 'text':
            if len(args) < 2:
                return 'textconvert <source> <new-output> [lf|crlf|cr] [keep|upper|lower] [input-encoding=utf-8] [output-encoding=ascii]\nStrict encoding prevents silent character loss.'
            source, output = _source(args[0]), args[1]
            newline = args[2].lower() if len(args) > 2 else 'crlf'
            case = args[3].lower() if len(args) > 3 else 'keep'
            if newline not in ('lf', 'crlf', 'cr') or case not in ('keep', 'upper', 'lower'):
                raise ValueError('Newline: lf/crlf/cr. Case: keep/upper/lower.')
            text = _small(source).decode(args[4] if len(args) > 4 else 'utf-8')
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            if case != 'keep':
                text = getattr(text, case)()
            return _new(output, text.replace('\n', {'lf':'\n','crlf':'\r\n','cr':'\r'}[newline]).encode(args[5] if len(args) > 5 else 'ascii'))
        if action == 'basic':
            if not args:
                return 'basicprep <listing> [new-output] [start=10] [step=10]\nWithout output: validate line numbers. With output: renumber GOTO/GOSUB/THEN/RESTORE/RUN/RESUME and ON lists. Text listings only; inspect dialect-specific references before loading.'
            text = _small(_source(args[0])).decode('ascii')
            lines, numbers = [], []
            for index, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                match = re.match(r'^\s*(\d+)\s*(.*)$', line)
                if not match:
                    raise ValueError(f'Listing line {index} has no BASIC line number.')
                numbers.append(int(match[1]))
                lines.append(match[2])
            if len(numbers) != len(set(numbers)) or numbers != sorted(numbers):
                raise ValueError('BASIC line numbers must be unique and increasing.')
            if len(args) < 2:
                return f'Validated {len(lines)} numbered ASCII lines.\nNo tokenization or dialect conversion is performed.'
            start, step = (int(args[2]) if len(args) > 2 else 10), (int(args[3]) if len(args) > 3 else 10)
            if start < 0 or step < 1 or (lines and start + step * (len(lines)-1) > 63999):
                raise ValueError('Resulting numbers must be 0-63999; positive step required.')
            mapping = {old: start + step * i for i, old in enumerate(numbers)}
            missing = set()
            output = []
            for old,line in zip(numbers,lines):
                output.append(str(mapping[old]) + ' ' + renumber_line(line,mapping,missing))
            if missing:
                raise ValueError('Unresolved line references: ' + ', '.join(map(str, sorted(missing))))
            return _new(args[1], ('\r\n'.join(output) + '\r\n').encode('ascii'))
        if action == 'split':
            if len(args) != 3:
                return 'chunks split <file> <new-output-folder> <chunk-bytes>\nWrites numbered parts and SHA-256 manifest for verified join.'
            path = _source(args[0]); folder = Path(args[1]).expanduser().resolve(); size = int(args[2])
            if not 128 <= size <= 16 * 1024 * 1024:
                raise ValueError('Chunk size must be 128 bytes to 16 MiB.')
            folder.mkdir(exist_ok=False)
            parts = []
            with path.open('rb') as source:
                for i, data in enumerate(iter(lambda: source.read(size), b''), 1):
                    name = f'part-{i:06}.bin'
                    (folder / name).write_bytes(data)
                    parts.append({'name':name, 'size':len(data), 'sha256':hashlib.sha256(data).hexdigest()})
            (folder / 'manifest.json').write_text(json.dumps({'name':path.name, 'parts':parts}, indent=2), encoding='utf-8')
            return f'Split into {len(parts)} parts in {folder}.\nParts require a compatible reassembly tool on the destination.'
        if action == 'join':
            if len(args) != 2:
                return 'chunks join <manifest.json> <new-output>\nVerifies every part before creating output.'
            manifest = _source(args[0]); data = json.loads(_small(manifest).decode('utf-8')); parts = []
            for part in data['parts']:
                path = (manifest.parent / part['name']).resolve()
                if path.parent != manifest.parent:
                    raise ValueError('Part path escapes the manifest folder.')
                if path.stat().st_size != part['size']:
                    raise ValueError('Part size mismatch: ' + path.name)
                digest = hashlib.sha256()
                with path.open('rb') as source:
                    for block in iter(lambda: source.read(65536), b''):
                        digest.update(block)
                if digest.hexdigest() != part['sha256']:
                    raise ValueError('Part checksum mismatch: ' + path.name)
                parts.append(path)
            with Path(args[1]).expanduser().open('xb') as output:
                for path in parts:
                    with path.open('rb') as source:
                        for block in iter(lambda: source.read(65536), b''):
                            output.write(block)
            return f'Joined {len(parts)} verified parts into {args[1]}.'
        if action in ('encode', 'decode'):
            if len(args) != 3:
                return 'encoding <encode|decode> <hex|base64> <source> <new-output>'
            kind, source, output = args[0], _source(args[1]), args[2]
            data = _small(source)
            if kind == 'hex':
                converted = (data.hex().encode('ascii') + b'\n') if action == 'encode' else bytes.fromhex(data.decode('ascii'))
            elif kind == 'base64':
                converted = base64.encodebytes(data) if action == 'encode' else base64.b64decode(b''.join(data.split()), validate=True)
            else:
                raise ValueError('Choose hex or base64.')
            return _new(output, converted)
        if action == 'compare':
            if len(args) != 2:
                return 'compare <first-file> <second-file>\nReports sizes and first differing byte; streams large files.'
            first, second = map(_source, args)
            offset = 0
            with first.open('rb') as a, second.open('rb') as b:
                while True:
                    aa, bb = a.read(65536), b.read(65536)
                    if aa != bb:
                        index = next((i for i, (x,y) in enumerate(zip(aa, bb)) if x != y), min(len(aa),len(bb)))
                        return f'Files differ at byte {offset+index} (0x{offset+index:X}).\nSizes: {first.stat().st_size}, {second.stat().st_size} bytes.'
                    if not aa:
                        return f'Files are identical ({offset} bytes).'
                    offset += len(aa)
        return self.HELP
