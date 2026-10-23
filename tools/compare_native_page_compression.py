"""Compare native-page storage probes with the published uncompressed renderer."""
import argparse
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def samples(path, end):
    with path.open() as source:
        return [row for row in csv.DictReader(source) if 120 <= int(row['tick']) <= end]


def summarize(rows):
    costs = sorted(int(row['render']) + int(row['transfer']) for row in rows)
    result = {
        'frames': len(rows),
        'median_fps': statistics.median(float(row['fps']) for row in rows),
        'median_render_plus_transfer_us': statistics.median(costs),
        'p95_render_plus_transfer_us': costs[min(len(costs)-1, int(len(costs)*.95))],
    }
    for key in ('gpu_native_io_reads', 'gpu_native_io_bytes',
                'gpu_native_decoded_cache_hits', 'gpu_native_decoded_bytes'):
        if key in rows[0]:
            result[key] = sum(int(row[key]) for row in rows)
    return result


def compare(candidate, baseline):
    run = json.loads((candidate / 'run.json').read_text())
    isolation = json.loads((candidate / 'isolation.json').read_text())
    assert isolation['completed'] and isolation['canonical_unchanged']
    cases = {}
    for path in sorted(candidate.glob('*.frames.csv')):
        case = path.name.removesuffix('.frames.csv')
        reference = baseline / path.name
        if not reference.exists():
            continue
        with path.open() as source:
            candidate_end = max(int(row['tick']) for row in csv.DictReader(source))
        with reference.open() as source:
            baseline_end = max(int(row['tick']) for row in csv.DictReader(source))
        end = min(candidate_end, baseline_end)
        current = summarize(samples(path, end))
        previous = summarize(samples(reference, end))
        proof = json.loads((candidate / (case + '.json')).read_text())
        assert proof['render_check']['mismatches'] == 0, case
        assert proof['statistics']['music_underruns'] == 0, case
        assert proof['statistics']['effect_underruns'] == 0, case
        cases[case] = {
            'tick_window': [120, end],
            'candidate': current,
            'published': previous,
            'median_cost_change_percent': round(100 * (
                current['median_render_plus_transfer_us'] /
                previous['median_render_plus_transfer_us'] - 1), 2),
            'issues': proof['issues'],
        }
    assert cases, 'No matching completed frame traces'
    baseline_run = json.loads((baseline / 'run.json').read_text())
    return {
        'scope': __doc__,
        'candidate': str(candidate.relative_to(ROOT)),
        'baseline': str(baseline.relative_to(ROOT)),
        'candidate_rom_sha256': run['rom_sha256'],
        'candidate_rom_bytes': run['rom_bytes'],
        'published_rom_sha256': baseline_run['rom_sha256'],
        'published_rom_bytes': baseline_run['rom_bytes'],
        'rom_bytes_saved': baseline_run['rom_bytes'] - run['rom_bytes'],
        'cases': cases,
        'limits': [
            'Bounded emulator routes; this does not establish physical DS speed.',
            'Per-frame file and decode counters describe native GPU preparation only.',
            'A matching tick window does not guarantee identical cache history or frame count.',
            'Raster/audio checks cover sampled frames and exercised routes, not full completion.',
        ],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--baseline', type=Path,
                        default=ROOT / 'research/playtests/gpu-native-hybrid-all')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.candidate.resolve(), args.baseline.resolve())
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
