"""KFB4: offline uniform8/25 Lanczos backgrounds with compressed256-pixel RGB555 rows."""
from pathlib import Path
import argparse,json,struct,numpy as np
from decoded_assets import DecodedAssets
from PIL import Image
from tile_storage import lz10
def build(decoded,out):
 out.mkdir(parents=True,exist_ok=False);rows=[];hashes={};assets=DecodedAssets(decoded)
 for a in assets.inventory.values():
  if not a['source'].lower().startswith('maps/') or len(a.get('frames',[]))<5:continue
  im=assets.image(a['frames'][4]);assert im.width==800 and im.height>=600
  rgb=np.asarray(im.crop((0,0,800,600)).resize((256,192),Image.Resampling.LANCZOS),dtype=np.uint16)
  assert np.all(rgb[:,:,3]==255)
  pixels=((rgb[:,:,0]>>3)|((rgb[:,:,1]>>3)<<5)|((rgb[:,:,2]>>3)<<10)|0x8000).astype('<u2')
  directory=[];payload=bytearray()
  for row in pixels:
   packed=lz10(row.tobytes());directory.append(struct.pack('<II',len(payload),len(packed)));payload.extend(packed);payload.extend(bytes(-len(payload)%4))
  data=b'KFB4'+struct.pack('<HH',256,192)+b''.join(directory)+payload
  name=Path(a['source']).stem.lower()+'.par';(out/name).write_bytes(data)
  checksum=2166136261
  for value in pixels.reshape(-1):checksum=((checksum^int(value))*16777619)&0xffffffff
  for _ in range(64*256):checksum=(checksum*16777619)&0xffffffff
  hashes[name]=checksum
  rows.append({'source':a['source'],'file':name,'bytes':len(data),'format':'KFB4','cache_pixels':49152,'projection':'uniform8/25 Lanczos; half-speed native camera origin rounded once to DS pixels'})
 (out/'background-vram-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
 (out/'background-manifest.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({'files':len(rows),'bytes':sum(x['bytes']for x in rows)}))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.assets,a.output)
if __name__=='__main__':main()
