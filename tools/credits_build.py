"""Pack all four original credit pages, Lanczos-resampled to the DS screen.
256x192 preserves original800x600 proportions. No generated/recreated artwork.
"""
from pathlib import Path
import argparse,hashlib,json,struct
from decoded_assets import DecodedAssets
from PIL import Image
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();assets=DecodedAssets(args.assets);inventory=assets.inventory;out=args.output;out.mkdir(parents=True,exist_ok=False);records=[]
for page in range(4):
 item=inventory[f'pics/credit{page+1}.bmp'];image=assets.image(item,'RGB');assert image.size==(800,600)
 values=[(r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000 for r,g,b in image.resize((256,192),Image.Resampling.LANCZOS).get_flattened_data()]
 data=struct.pack('<4sHH',b'KFC1',256,192)+struct.pack('<49152H',*values);path=out/f'{page}.bin';path.write_bytes(data)
 records.append({'page':page,'original':item['source'],'original_sha256':item['sha256'],'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(out/'credits-manifest.json').write_text(json.dumps({'pages':records,'sampling':'Lanczos;256x192;RGB555'},indent=2)+'\n');print(json.dumps({'pages':4,'packed_bytes':sum(v['bytes']for v in records)}))
