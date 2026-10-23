#!/usr/bin/env python3
"""The original projectile slots share the penguin's frame resource."""
import argparse,json,struct,hashlib
from decoded_assets import DecodedAssets
from pathlib import Path
from PIL import Image
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();assets=DecodedAssets(args.assets);args.output.mkdir(parents=True,exist_ok=False)
a=assets.inventory['animation/pinguin.w01']
out=bytearray(b'KFS1')
for index in [261,232]:
 f=a['frames'][index];im=assets.image(f)
 out.extend(struct.pack('<HHhh',im.width,im.height,f['x'],f['y']))
 out.extend(struct.pack('<'+'H'*(im.width*im.height),*[((r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000) if alpha else 0 for r,g,b,alpha in im.get_flattened_data()]))
p=args.output/'shots.bin';p.write_bytes(out)
(args.output/'projectile-manifest.json').write_text(json.dumps(dict(source=a['source'],frames=[261,232],bytes=len(out),sha256=hashlib.sha256(out).hexdigest()),indent=2)+'\n')
print('Projectile pack:',len(out),'bytes')
