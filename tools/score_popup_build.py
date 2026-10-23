"""Deduplicate exact 4x4 RGB555 tiles across original POINTS sprites."""
from pathlib import Path
import argparse,hashlib,json,struct
from decoded_assets import DecodedAssets
from PIL import Image
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();assets=DecodedAssets(args.assets);args.output.mkdir(parents=True,exist_ok=False);atlas={};indices=[];frames=[]
for frame,width in enumerate((90,120,152)):
 image=assets.image(assets.inventory['animation/points.w01']['frames'][frame]);assert image.size==(width,41)
 frames.append((width,41,len(indices)))
 for top in range(0,41,4):
  for left in range(0,width,4):
   values=[]
   for y in range(4):
    for x in range(4):
     if left+x>=width or top+y>=41:values.append(0);continue
     r,g,b,a=image.getpixel((left+x,top+y));values.append((r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000 if a else 0)
   tile=struct.pack('<16H',*values);atlas.setdefault(tile,len(atlas));indices.append(atlas[tile])
assert len(atlas)==371 and len(indices)==1001
packed=b'KFP2'+struct.pack('<4H',4,3,len(atlas),len(indices))+b''.join(struct.pack('<HHI',*f)for f in frames)+struct.pack('<1001H',*indices)+b''.join(atlas)
(args.output/'points.bin').write_bytes(packed)
result={'original_pixel_bytes':29684,'resident_tile_bytes':len(atlas)*32,'resident_index_bytes':len(indices)*2,'resident_bytes':13874,'resident_bytes_saved':15810,'tile_size':4,'tiles':371,'indices':1001,'file_bytes':len(packed),'lossless':True}
(args.output/'score-popup-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
