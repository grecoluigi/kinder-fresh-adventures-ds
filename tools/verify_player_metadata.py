"""Verify compact player geometry and the actual native-only runtime loader/draw.

Requires full generated KFP3 intermediates, not proprietary files in source.
Compiles a small ASan/UBSan host fixture; no emulator is launched.
"""
from pathlib import Path
import argparse, json, os, shutil, struct, subprocess, tempfile
from player_metadata import player_metadata

ROOT = Path(__file__).resolve().parents[1]


def verify(players, runtime, source):
    names = ('pinguin.frames', 'milchschnitte.frames')
    blobs = {name: player_metadata((players / name).read_bytes()) for name in names}
    for name, blob in blobs.items():
        assert (runtime / name).read_bytes() == blob, name
        raw = (players / name).read_bytes()
        count, = struct.unpack_from('<I', blob, 4)
        for frame in range(count):
            a, b = 8 + frame * 40, 8 + frame * 24
            assert blob[b:b+8] == raw[a:a+8]
            for facing in range(2):
                assert blob[b+8+facing*8:b+16+facing*8] == raw[a+16+facing*16:a+24+facing*16]
    raw = (players / names[0]).read_bytes()
    invalid_sources = [b'', b'KFP3', b'KFP4'+raw[4:],
                       b'KFP3'+struct.pack('<I', 0),
                       b'KFP3'+struct.pack('<I', 513), raw[:47]]
    for at, fmt, value in ((8, '<H', 0), (16, '<I', 0xffffffff),
                           (20, '<I', 0xffffffff), (20, '<I', 3),
                           (24, '<H', 0), (26, '<H', 0)):
        b = bytearray(raw)
        struct.pack_into(fmt, b, at, value)
        invalid_sources.append(bytes(b))
    for bad in invalid_sources:
        try:
            player_metadata(bad)
        except ValueError:
            continue
        raise AssertionError('Malformed source bank accepted')
    with tempfile.TemporaryDirectory(prefix='kinder-player-metadata-') as temporary:
        t = Path(temporary)
        banks = t / 'players'
        shutil.copytree(runtime, banks)
        binary = t / 'verify'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-DKF_HOST_GPU_ACTORS', '-DPLAYER_ROOT=' + json.dumps(str(banks)),
                        '-I' + str(source), str(source / 'player_graphics.c'),
                        str(ROOT / 'ds/tests/native_player_metadata.c'), '-o', str(binary)], check=True)
        env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0', 'UBSAN_OPTIONS': 'halt_on_error=1'}
        result = json.loads(subprocess.check_output([str(binary), str(players)], env=env, text=True))
        invalid = [b'', b'KFP4', b'KFP3'+blobs[names[0]][4:],
                   b'KFP4'+struct.pack('<I', 0), b'KFP4'+struct.pack('<I', 513),
                   blobs[names[0]][:-1], blobs[names[0]]+b'\0']
        for at in (8, 16, 24):
            b = bytearray(blobs[names[0]])
            struct.pack_into('<H', b, at, 0)
            invalid.append(bytes(b))
            struct.pack_into('<HH', b, at, 65535, 65535)
            invalid.append(bytes(b))
        for bad in invalid:
            (banks / names[0]).write_bytes(bad)
            subprocess.run([str(binary), str(players), '0'], env=env, check=True)
        (banks / names[0]).write_bytes(blobs[names[0]])
        (banks / names[1]).unlink()
        subprocess.run([str(binary), str(players), '0'], env=env, check=True)
        result.update(invalid_banks_rejected=len(invalid)+1,
                      invalid_source_banks_rejected=len(invalid_sources),
                      runtime_bytes=sum(map(len, blobs.values())),
                      original_bytes=sum((players/name).stat().st_size for name in names),
                      all_geometry_exact=True, sanitizers='ASan + UBSan')
        return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--players', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--source-dir', type=Path, default=ROOT/'ds/source')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = verify(a.players.resolve(), a.runtime.resolve(), a.source_dir.resolve())
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
