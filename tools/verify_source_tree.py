"""Check the single repository's publishable Git file inventory without staging it."""
from pathlib import Path
import re
import subprocess
import sys
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
EXACT = {'.gitignore', 'README.md', 'requirements-assets.txt', 'ds/Makefile',
         'ds/README.md', 'tools/PLAYTEST.md', 'VERSION', 'CHANGELOG.md',
         '.github/workflows/source-checks.yml'}
WEBP_DIMENSIONS = {'docs/images/jungle-framed.webp': (866, 907)}
PNG_DIMENSIONS = {'ds/icon.png': (32, 32)}

def allowed(name):
    path = Path(name)
    return (name in EXACT or name in PNG_DIMENSIONS or name in WEBP_DIMENSIONS or
            path.parent in {Path('docs'), Path('docs/releases')} and path.suffix == '.md' or
            path.parent == Path('ds/source') and path.suffix in {'.c', '.h', '.inc', '.s', '.S'} or
            path.parent == Path('ds/tests') and path.suffix == '.c' or
            path.parent == Path('tools') and path.suffix == '.py')

def main():
    result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                            cwd=ROOT, capture_output=True, check=True)
    names = sorted(set(result.stdout.decode().split('\0')) - {''})
    errors = []
    for name in names:
        path = ROOT / name
        if not allowed(name):
            errors.append(name + ': outside the source allowlist')
        if path.is_symlink():
            errors.append(name + ': symlink can expose private local data')
        if not path.exists():
            continue  # A staged deletion has no publishable contents.
        if name in WEBP_DIMENSIONS:
            data = path.read_bytes()
            try:
                assert len(data) <= 256 * 1024, 'framed screenshot exceeds 256 KiB'
                assert data[:4] == b'RIFF' and data[8:12] == b'WEBP', 'not a WebP'
                assert struct.unpack_from('<I', data, 4)[0] + 8 == len(data), 'WebP size mismatch'
                assert data[12:16] == b'VP8X', 'expected extended WebP header'
                dimensions = tuple(int.from_bytes(data[start:start+3], 'little') + 1 for start in (24, 27))
                assert dimensions == WEBP_DIMENSIONS[name], 'unexpected WebP dimensions'
                offset = 12
                while offset < len(data):
                    size = struct.unpack_from('<I', data, offset+4)[0]
                    offset += 8 + size + (size & 1)
                    assert offset <= len(data), 'truncated WebP chunk'
                assert offset == len(data), 'trailing WebP contents'
            except (AssertionError, ValueError, struct.error) as error:
                errors.append(name + ': ' + str(error))
            continue
        if name in PNG_DIMENSIONS:
            data = path.read_bytes()
            try:
                assert data[:8] == b'\x89PNG\r\n\x1a\n', 'not a PNG'
                assert len(data) <= 512 * 1024, 'screenshot exceeds 512 KiB'
                assert data[12:16] == b'IHDR' and struct.unpack('>II', data[16:24]) == PNG_DIMENSIONS[name], 'unexpected PNG dimensions'
                offset = 8
                while offset < len(data):
                    size = struct.unpack_from('>I', data, offset)[0]
                    chunk = data[offset+4:offset+8+size]
                    crc = struct.unpack_from('>I', data, offset+8+size)[0]
                    assert zlib.crc32(chunk) == crc, 'PNG checksum mismatch'
                    offset += 12 + size
                    if chunk[:4] == b'IEND':
                        assert offset == len(data), 'trailing PNG contents'
                        break
                else:
                    raise ValueError('missing PNG terminator')
            except (AssertionError, ValueError, struct.error) as error:
                errors.append(name + ': ' + str(error))
            continue
        try:
            data = path.read_bytes()
            text = data.decode('utf-8')
            if b'\0' in data:
                raise ValueError('NUL bytes')
        except (UnicodeError, ValueError):
            errors.append(name + ': binary contents')
            continue
        # Assemble the pattern so this checker does not flag its own source.
        titles = ('mar' + 'io', 'castle' + 'vania', 'castel' + 'vania')
        if re.search('|'.join(titles), text, re.IGNORECASE):
            errors.append(name + ': private third-party study reference')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'PASS: {len(names)} publishable files; source inventory plus approved icon and gameplay screenshots; no private assets, study titles or symlinks.')
    print('This checks repository contents, not clean asset regeneration or release readiness.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
