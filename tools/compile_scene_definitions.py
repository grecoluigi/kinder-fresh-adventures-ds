"""Compile native scene dispatch directly from decoded original maps and alpha masks.

Only whether a static pass contains a visible pixel is needed to preserve its
ordinal. No scene framebuffer, atlas, legacy index or research input is used.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
from PIL import Image
from native_resources import asset_source, frame_metadata

HEADER = struct.Struct('<4s7I')
EVENT = struct.Struct('<BBHI')
DYNAMIC_IDS = frozenset(range(6, 19)) | frozenset(range(48, 60)) | {
    60, 75, 76, 77, 78, 79, 80, 82, 83, 84, 85, 86, 87, 88, 89,
    200, 201, 202, 210, 220, 230, 231, 232, 233, 265, 352, 354, 355, 356, 414,
}
JUNGLE_ENEMIES = {'Welt1.W02', 'Welt1t.W02'}

def ceildiv(n, d):
    return -(-n // d)

class Compiler:
    def __init__(self, assets, maps):
        self.assets_root = assets.resolve()
        self.maps = maps
        self.assets = {a['source'].lower(): a for a in json.loads((assets/'inventory.json').read_text()) if 'frames' in a}
        self.scripts = {s['ObjNr']: s for s in json.loads((maps/'scripts.json').read_text()).values() if 'ObjNr' in s}
        self.alpha = {}

    def frame(self, meta):
        path = Path(meta['png']).resolve()
        if not path.is_relative_to(self.assets_root):
            raise ValueError('Decoded frame lies outside the supplied asset directory: ' + str(path))
        if path not in self.alpha:
            with Image.open(path) as image:
                self.alpha[path] = image.convert('RGBA').getchannel('A')
        return self.alpha[path]

    def compile(self, name):
        map_root = self.maps/name
        metadata = json.loads((map_root/'00.json').read_text())
        data = (map_root/'00.tiles.bin').read_bytes()
        w, h, layers = (metadata[k] for k in ('width_cells', 'height_cells', 'layers'))
        if (metadata['tile_width'], metadata['tile_height']) != (32, 32) or len(data) != layers*w*h*3:
            raise ValueError('Unsupported scene cell layout: ' + name)
        width, height = w*32, h*32
        stem = Path(name).stem
        if stem.lower().endswith('e'):
            stem = stem[:-1]
        sheet = self.assets[f'maps/{stem}.w01'.lower()]['frames']
        tile_visible = {}
        events, order, visible = [], 0, False

        def flush():
            nonlocal visible, order
            if visible:
                order += 1
                visible = False

        def objects(layer, group):
            nonlocal visible
            for index, obj in enumerate(metadata['objects']):
                kind = obj['obj_nr']
                raw = bytes.fromhex(obj['raw_hex'])
                if kind == 1000 or raw[25] != layer or raw[23] != group:
                    continue
                if kind in DYNAMIC_IDS or name in JUNGLE_ENEMIES and 3 <= kind <= 5:
                    flush()
                    events.append((1, order, 0, index))
                    continue
                if visible:
                    continue  # Further static alpha cannot empty an existing pass.
                script = self.scripts.get(kind)
                if not script or not script.get('FileName'):
                    continue
                asset = self.assets.get(asset_source(script))
                if not asset:
                    continue
                mirror = bool(raw[43])
                meta = frame_metadata(script, asset, script.get('StartAnimLeft', script.get('FileAnimStart', 0)), mirror)
                alpha = self.frame(meta)
                if mirror:
                    alpha = alpha.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                x, y = obj['x_px']+meta['x'], obj['y_px']+meta['y']
                box = (max(0, -x), max(0, -y), min(alpha.width, width-x), min(alpha.height, height-y))
                if box[0] < box[2] and box[1] < box[3]:
                    visible = alpha.crop(box).getbbox() is not None

        for layer in range(layers):
            objects(layer, 1)
            # Tiles are wholly within the map. Flipping does not change whether
            # they have any alpha, so cache that predicate per bank/cell.
            if not visible:
                for flags, packed in struct.iter_unpack('<BH', data[layer*w*h*3:(layer+1)*w*h*3]):
                    if packed == 65535 or flags & 64 or packed >> 9 > 50:
                        continue
                    bank, tile = metadata['tile_bank_selection'][flags & 7], packed & 511
                    key = bank, tile
                    if key not in tile_visible:
                        atlas = self.frame(sheet[bank])
                        columns = atlas.width//32
                        x, y = tile % columns*32, tile//columns*32
                        tile_visible[key] = atlas.crop((x, y, x+32, y+32)).getbbox() is not None
                    if tile_visible[key]:
                        visible = True
                        break
            objects(layer, 0)
            if layer == 2:
                flush()
                events.append((2, order, 0, 2))
            objects(layer, 2)
        flush()
        if not 0 < order <= 255 or len(events) > 4096:
            raise ValueError('Dispatch exceeds native definition limits: ' + name)
        ds_width = ceildiv(ceildiv(width*16-25, 50), 16)*16
        ds_height = ceildiv(ceildiv(height*16-25, 50), 16)*16
        blob = HEADER.pack(b'KNS1', width, height, ds_width, ds_height, order, len(events), 0)
        blob += b''.join(EVENT.pack(*event) for event in events)
        filename = name + ('.enemy' if name in JUNGLE_ENEMIES else '') + '.nsc'
        return filename, blob, {'map': name, 'static_orders': order, 'callbacks': len(events),
                                'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--maps', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    compiler = Compiler(args.assets, args.maps)
    names = [row['file'] for row in json.loads((args.maps/'inventory.json').read_text())]
    if not names or len(names) != len(set(names)):
        parser.error('Map inventory must be nonempty and unique')
    if args.output.exists():
        parser.error('Output directory must not already exist')
    args.output.mkdir(parents=True)
    rows = []
    for name in names:
        filename, blob, row = compiler.compile(name)
        (args.output/filename).write_bytes(blob)
        rows.append(row)
    report = {'scope': __doc__, 'maps': rows, 'callbacks': sum(r['callbacks'] for r in rows),
              'definition_bytes': sum(r['bytes'] for r in rows),
              'inputs': ['decoded original frames', 'exported original maps/scripts'],
              'asset_generation_complete': False}
    (args.output/'scene-definitions.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('scope', 'maps')}))

if __name__ == '__main__':
    main()
