#!/usr/bin/env python3
from pathlib import Path
from PIL import Image
import argparse,json,struct,hashlib
from decoded_assets import DecodedAssets
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();assets=DecodedAssets(args.assets);out=args.output;out.mkdir(parents=True,exist_ok=False);inventory=assets.inventory
manifest=[]
for name,source,index in [('kong','animation/kong02.w01',16),('yeti','animation/kleiner_yeti.w01',25),('snowman','animation/schneemann.w01',54),('egg','animation/eier_roboter.w01',23),('gorilla','animation/gorilla.w01',87),('factory','animation/roboter.w01',188),('bear','animation/b_r.w01',53),('octopus','animation/krake.w01',50)]:
 asset=inventory[source];frame=asset['frames'][index];image=assets.image(frame)
 pixels=[((r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000) if a else 0 for r,g,b,a in image.get_flattened_data()]
 data=struct.pack('<4sHH',b'KFE1',*image.size)+struct.pack('<'+'H'*len(pixels),*pixels);(out/(name+'.bin')).write_bytes(data)
 manifest.append({'source':asset['source'],'frame':index,'size':list(image.size),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'surface_alignment':[0,0],'alignment_evidence':'Native41d179 clears surface descriptor; generic40af50 uses surface alignment, independently of AOM collision alignment.'})
(out/'enemy-shot-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
