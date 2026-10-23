"""Build the original menu's seven states, lossless patches and touch hitboxes."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
from PIL import Image
from decoded_assets import DecodedAssets
from menu_cache_build import encode_menu

NAMES = ('GIUNGLA','VALLE','MONTAGNA','FABBRICA','CLASSIFICA','ESCI')

def render_screens(assets):
    background = assets.image(assets.inventory['pics/startbg.bmp'])
    if background.size != (800,600):
        raise ValueError('Unexpected menu background dimensions')
    screens, hitboxes = [], []
    for focus in range(-1,6):
        image = background.copy()
        for index,name in enumerate(NAMES):
            frames = assets.inventory[f'animation/interface/{name.lower()}.w01']['frames']
            frame = frames[(2 if index<4 else 0)+int(index==focus)]
            image.alpha_composite(assets.image(frame),(frame['x'],frame['y']))
        # Keep the existing menu adaptation exactly; gameplay/score assets have
        # separate sampling rules. This does not change its rendered pixels.
        image = image.convert('RGB').resize((256,192),Image.Resampling.LANCZOS)
        values = [0x8000|(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b in image.get_flattened_data()]
        screens.append(struct.pack('<49152H',*values))
    for name in NAMES:
        frame = assets.inventory[f'animation/interface/{name.lower()}.w01']['frames'][0]
        hitboxes.append([int(frame['x']*.32),int(frame['y']*.32),
                         round((frame['x']+frame['width'])*.32),round((frame['y']+frame['height'])*.32)])
    return screens,hitboxes

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must not already exist')
    assets = DecodedAssets(args.assets)
    screens,hitboxes = render_screens(assets)
    files,rows = encode_menu(screens)
    args.output.mkdir(parents=True)
    for name,data in files.items():
        (args.output/name).write_bytes(data)
    header = '/* Generated from original menu placements; half-open DS pixel bounds. */\nstatic const int menu_hitboxes[6][4] = {\n'
    header += ''.join('    {'+', '.join(map(str,bounds))+'},\n' for bounds in hitboxes)+'};\n'
    (args.output/'menu_hitboxes.h').write_text(header)
    manifest = {'states':7,'hitboxes':hitboxes,'patches':rows,
                'payload_bytes':sum(map(len,files.values())),
                'sha256':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
                'sampling':'Existing 800x600 to 256x192 Lanczos menu adaptation',
                'music':'Generated separately by audio_build.py'}
    (args.output/'menu-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'states':7,'payload_bytes':manifest['payload_bytes']}))

if __name__=='__main__':
    main()
