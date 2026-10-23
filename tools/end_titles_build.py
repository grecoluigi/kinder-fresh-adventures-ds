"""Pack both original END TITLES sprites without resampling or alpha loss."""
from pathlib import Path
import argparse,hashlib,json,struct
from decoded_assets import DecodedAssets
from PIL import Image
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();assets=DecodedAssets(args.assets);out=args.output;out.mkdir(parents=True,exist_ok=False);rows=[]
for frame,width in enumerate((418,392)):
 image=assets.image(assets.inventory['animation/endtitles.w01']['frames'][frame])
 assert image.size==(width,51)
 data=bytearray(b'KFT1'+struct.pack('<HH',width,51))
 for r,g,b,a in image.get_flattened_data():data.extend(struct.pack('<H',(r>>3)|((g>>3)<<5)|((b>>3)<<10)|(0x8000 if a else 0)))
 (out/f'{frame}.bin').write_bytes(data)
 rows.append({'frame':frame,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(out/'end-titles-manifest.json').write_text(json.dumps({'frames':rows},indent=2)+'\n')
print(json.dumps({'frames':2,'bytes':sum(r['bytes']for r in rows)}))
