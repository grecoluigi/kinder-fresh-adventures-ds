"""Check native-only scene actor metadata, actual loaders and draw submission.

Compiles production scene.c with display services stubbed; tests all original
frames/facings, geometry, ranges, culling bounds and malformed banks under
ASan/UBSan. Optional previous-source comparison covers geometry/static matching
on every map; GPU rendering and full playthroughs require separate checks.
"""
from pathlib import Path
import argparse, hashlib, json, os, struct, subprocess, tempfile
from scene_actor_metadata import scene_actor_metadata

ROOT = Path(__file__).resolve().parents[1]


def mutated(blob, at, fmt, value):
    result = bytearray(blob)
    struct.pack_into(fmt, result, at, value)
    return bytes(result)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(args):
    source, runtime = args.source_dir.resolve(), args.runtime.resolve()
    raw = {'enemies.frames': args.enemies.read_bytes(), 'pickups.frames': args.pickups.read_bytes()}
    compact = {}
    for name, blob in raw.items():
        enemies = name == 'enemies.frames'
        result = scene_actor_metadata(blob, enemies)
        assert (runtime/name).read_bytes() == result, name
        compact[name] = result
        resources, count = struct.unpack_from('<HH', blob, 4)
        resource_stride, stride, original, raster = (84, 40, 0, 16) if enemies else (12, 48, 8, 24)
        frames = 12+resources*resource_stride
        assert blob[12:frames] == result[12:frames]
        for frame in range(count):
            before, after = frames+frame*stride, frames+frame*24
            assert result[after:after+8] == blob[before+original:before+original+8]
            for facing in range(2):
                assert result[after+8+facing*8:after+16+facing*8] == blob[before+raster+facing*16:before+raster+facing*16+8]
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    with tempfile.TemporaryDirectory(prefix='kinder-scene-metadata-') as temporary:
        t = Path(temporary)
        banks, originals = t/'scenes', t/'raw'
        banks.mkdir()
        originals.mkdir()
        for path in runtime.iterdir():
            if path.name not in compact:
                (banks/path.name).symlink_to(path, target_is_directory=path.is_dir())
        for name, blob in compact.items():
            (banks/name).write_bytes(blob)
            (originals/name).write_bytes(raw[name])

        def compile_fixture(directory, bank_path, name, baseline=False):
            binary = t/name
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                            '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                            '-DKF_HOST_GPU_ACTORS', *(['-DKF_METADATA_BASELINE'] if baseline else []),
                            '-DSCENE_ROOT='+json.dumps(str(bank_path)), '-I'+str(directory),
                            str(ROOT/'ds/tests/native_scene_metadata.c'), str(directory/'collision.c'),
                            '-o', str(binary)], check=True)
            return binary

        binary = compile_fixture(source, banks, 'verify')
        report = json.loads(subprocess.check_output([str(binary), str(originals)], env=env, text=True))
        malformed_runtime = malformed_source = 0
        for name, blob in compact.items():
            enemies = name == 'enemies.frames'
            resources, count = struct.unpack_from('<HH', blob, 4)
            resource_stride, old_stride, original, raster = (84, 40, 0, 8) if enemies else (12, 48, 8, 16)
            frames = 12+resources*resource_stride
            invalid = [b'', blob[:11], b'FAIL'+blob[4:], blob[:-1], blob+b'\0',
                       mutated(blob, 4, '<H', 0), mutated(blob, 4, '<H', 65),
                       mutated(blob, 6, '<H', 0), mutated(blob, 6, '<H', 2049),
                       mutated(blob, 8, '<I', len(blob)+1),
                       mutated(blob, 12, '<H', 1024),
                       mutated(blob, 12+resource_stride, '<H', struct.unpack_from('<H', blob, 12)[0]),
                       mutated(blob, 14, '<H', count+1), mutated(blob, 16, '<H', 0),
                       mutated(blob, 16, '<H', count+1)]
            for frame in (0, count-1):
                at = frames+frame*24
                for offset in (0, 2, 8, 10, 16, 18):
                    invalid.append(mutated(blob, at+offset, '<H', 0))
                invalid.extend([mutated(blob, at+8, '<H', 65535),
                                mutated(blob, at+12, '<h', 32767)])
            if not enemies:
                invalid.extend([mutated(blob, 12, '<H', 47), mutated(blob, 18, '<H', count)])
            subprocess.run([str(binary), '--open', name, '1'], env=env, check=True)
            for bad in invalid:
                (banks/name).write_bytes(bad)
                subprocess.run([str(binary), '--open', name, '0'], env=env, check=True)
            (banks/name).write_bytes(blob)
            malformed_runtime += len(invalid)
            old = raw[name]
            source_invalid = [b'', old[:11], b'FAIL'+old[4:], old[:-16],
                              mutated(old, 4, '<H', 0), mutated(old, 6, '<H', 0),
                              mutated(old, 8, '<I', 0xffffffff),
                              mutated(old, 14, '<H', count+1), mutated(old, 16, '<H', 0),
                              mutated(old, frames+original, '<H', 0)]
            for frame in (0, count-1):
                at = frames+frame*old_stride+raster
                source_invalid.extend([mutated(old, at, '<I', 0xffffffff),
                                       mutated(old, at+4, '<I', 0xffffffff),
                                       mutated(old, at+4, '<I', 7),
                                       mutated(old, at+8, '<H', 0)])
            for bad in source_invalid:
                try:
                    scene_actor_metadata(bad, enemies)
                except ValueError:
                    continue
                raise AssertionError('Malformed source actor bank accepted')
            malformed_source += len(source_invalid)

        maps = sorted(path.stem for path in runtime.glob('*.entities'))
        trace = t/'candidate-geometry.bin'
        with trace.open('wb') as output:
            subprocess.run([str(binary), '--maps', *maps], env=env, stdout=output, check=True)
        comparison = {'maps': maps, 'trace_bytes': trace.stat().st_size, 'sha256': digest(trace),
                      'geometry_and_static_matching_equal_to_previous': None}
        if args.baseline_source_dir:
            before = compile_fixture(args.baseline_source_dir.resolve(), args.baseline_runtime.resolve(), 'baseline', True)
            previous = t/'previous-geometry.bin'
            with previous.open('wb') as output:
                subprocess.run([str(before), '--maps', *maps], env=env, stdout=output, check=True)
            assert previous.read_bytes() == trace.read_bytes(), 'Original-world geometry or static matching changed'
            comparison['geometry_and_static_matching_equal_to_previous'] = True
        report.update(all_resource_records_and_geometry_exact=True,
                      malformed_runtime_banks_rejected=malformed_runtime,
                      malformed_source_banks_rejected=malformed_source,
                      runtime_bytes=sum(map(len, compact.values())),
                      previous_bytes=sum(map(len, raw.values())),
                      sanitizers='ASan + UBSan', map_geometry=comparison,
                      scene_source_sha256=digest(source/'scene.c'),
                      metadata_parser_sha256=digest(source/'scene_actor_metadata.h'),
                      scope=__doc__.strip())
        return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--enemies', type=Path, required=True, help='Complete regenerated KFES bank')
    p.add_argument('--pickups', type=Path, required=True, help='Complete regenerated KFSP bank')
    p.add_argument('--runtime', type=Path, required=True, help='Assembled runtime scenes directory')
    p.add_argument('--source-dir', type=Path, default=ROOT/'ds/source')
    p.add_argument('--baseline-source-dir', type=Path)
    p.add_argument('--baseline-runtime', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if bool(a.baseline_source_dir) != bool(a.baseline_runtime):
        p.error('Supply both baseline source and runtime directories')
    result = verify(a)
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
