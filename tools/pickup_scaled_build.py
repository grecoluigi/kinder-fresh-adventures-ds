"""Compile KFSP pickup metadata and both facings from decoded originals/scripts."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,struct
import numpy as np
from decoded_assets import DecodedAssets
from native_resources import asset_source,frame_alignment
from player_scaled_build import raster
from tile_storage import packet,lz10

def build(decoded,maps):
 assets=DecodedAssets(decoded)
 scripts={s['ObjNr']:s for s in json.loads((maps/'scripts.json').read_text()).values() if 'ObjNr' in s}
 resources=[];records=[];payload=bytearray();lookup={};modes=Counter();native_offset=0;source_pixels=stored_pixels=0
 for id in range(48,59):
  script=scripts[id];asset=assets.inventory[asset_source(script)];reference=script.get('ReferenceSprWidth',0)
  resources.append(struct.pack('<6H',id,len(records),len(asset['frames']),script['StartAnimLeft'],script['EndAnimLeft'],reference))
  for i,frame in enumerate(asset['frames']):
   rgba=np.asarray(assets.image(frame),dtype=np.uint16)
   rgb=np.where(rgba[:,:,3],0x8000|(rgba[:,:,0]>>3)|((rgba[:,:,1]>>3)<<5)|((rgba[:,:,2]>>3)<<10),0).astype('<u2')
   h,w=rgb.shape;source_pixels+=w*h;fx,fy=frame_alignment(script,asset,i)
   # The KFSP ABI retains these original metadata fields. Recompute their
   # values from source pixels; no original-size pixel pack is persisted.
   native_bytes=len(lz10(rgb.tobytes()))
   record=bytearray(struct.pack('<IIHHhh',native_offset,native_bytes,w,h,fx,fy));native_offset+=native_bytes
   for mirror in (False,True):
    pixels,x,y=raster(rgb,fx-reference if mirror else fx,fy,not mirror);key=pixels.tobytes();stored_pixels+=pixels.size
    if key not in lookup:
     encoded,bits=packet(key);lookup[key]=(len(payload),len(encoded));modes[bits]+=1
     payload.extend(encoded);payload.extend(bytes(-len(payload)%4))
    off,size=lookup[key];dh,dw=pixels.shape
    record.extend(struct.pack('<IIHHhh',off,size,dw,dh,x,y))
   assert len(record)==48;records.append(record)
 data=struct.pack('<4sHHI',b'KFSP',len(resources),len(records),len(payload))+b''.join(resources)+b''.join(records)+payload
 stats={'bytes':len(data),'resources':len(resources),'frames':len(records),'rasters':len(records)*2,'unique_packets':len(lookup),'packet_modes':dict(modes),'native_pixels':source_pixels,'scaled_pixels_both_facings':stored_pixels,'sha256':hashlib.sha256(data).hexdigest(),'scope':__doc__}
 return data,stats

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--maps',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);data,stats=build(a.assets,a.maps);(a.output/'pickups.frames').write_bytes(data);(a.output/'pickup-manifest.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats))
