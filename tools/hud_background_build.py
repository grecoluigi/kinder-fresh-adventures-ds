"""Four static256x192original backdrops with baked25%black, RGB555/adaptive LZ10."""
from pathlib import Path
import argparse,json,hashlib,struct
from decoded_assets import DecodedAssets
import numpy as np
from PIL import Image
from tile_storage import packet
WORLDS=(('jungle','Welt1'),('ice','Welt2'),('factory','WELT3'),('fantasy','WELT4'))
def build(decoded,out):
 out.mkdir(parents=True,exist_ok=False);previews=out;assets=DecodedAssets(decoded);manifest=[]
 for name,asset in WORLDS:
  source=assets.inventory[f'maps/{asset.lower()}.w01']['frames'][4]
  rgb=np.asarray(assets.image(source,'RGB').crop((0,0,800,600)).resize((256,192),Image.Resampling.NEAREST),dtype=np.uint16)*3//4
  words=(0x8000|(rgb[:,:,0]>>3)|((rgb[:,:,1]>>3)<<5)|((rgb[:,:,2]>>3)<<10)).astype('<u2');encoded,bits=packet(words.tobytes())
  data=struct.pack('<4sHHI',b'KHB1',256,192,len(encoded))+encoded;path=out/(name+'.bin');path.write_bytes(data)
  display=np.stack(((words&31)*255//31,((words>>5)&31)*255//31,((words>>10)&31)*255//31),axis=2).astype('u1');Image.fromarray(display).save(previews/(name+'-background.png'))
  manifest.append({'world':name,'source':source['png'],'file':path.name,'bytes':len(data),'dimensions':[256,192],'bits':bits,'baked_black_percent':25,'decoded_bytes':words.nbytes,'sha256':hashlib.sha256(data).hexdigest(),'pixels_sha256':hashlib.sha256(words.tobytes()).hexdigest()})
 (out/'background-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'files':4,'total_rom_bytes':sum(x['bytes']for x in manifest),'resident_background_bytes':98304,'maximum_load_packet_bytes':max(x['bytes']-12 for x in manifest)}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.assets,a.output)
