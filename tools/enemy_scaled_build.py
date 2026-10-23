#!/usr/bin/env python3
"""Compile DS-sized enemy/object sprites directly from decoded originals and scripts.
KFES:12-byte header,84-byte resource records,40-byte frame records,aligned packets.
Frame: native w/h/x/y (8bytes),then two16-byte raster descriptors (normal,mirror).
No previous packed assets or research data are read.
"""
from pathlib import Path
import argparse,json,struct,hashlib
import numpy as np
from decoded_assets import DecodedAssets
from native_resources import asset_source,frame_alignment
from player_scaled_build import raster
from tile_storage import packet
RESOURCE_IDS=(3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,59,200,201,202,210,220,230,231,232,233,76,77,78,83,86,87,60,75,79,80,82,84,85,88,89,265,352,354,355,356,414)
ANIMATION_RANGES=('Left','Right','Up','Do','LeftUp','LeftDo','RightUp','RightDo','IdleLeft','IdleRight','IdleUp','IdleDo','IdleLeftUp','IdleLeftDo','IdleRightUp','IdleRightDo','Attack','Freeze','KO')

def build(decoded,maps,out):
 out.mkdir(parents=True,exist_ok=False)
 assets=DecodedAssets(decoded)
 scripts={s['ObjNr']:s for s in json.loads((maps/'scripts.json').read_text()).values() if 'ObjNr' in s}
 resource_records=[];start=0
 for id in RESOURCE_IDS:
  script=scripts[id];asset=assets.inventory[asset_source(script)]
  ranges=[value for key in ANIMATION_RANGES for value in (script.get('StartAnim'+key,0),script.get('EndAnim'+key,0))]
  resource_records.append(struct.pack('<HHHH38h',id,start,len(asset['frames']),script.get('ReferenceSprWidth',0),*ranges))
  start+=len(asset['frames'])
 resources=b''.join(resource_records);count=len(resource_records);frames=start
 records=[];payload=bytearray();lookup={};stats=[]
 for ri in range(count):
  res=resources[ri*84:(ri+1)*84];id,start,n,reference=struct.unpack_from('<4H',res)
  assert start==len(records)
  script=scripts[id];asset=assets.inventory[asset_source(script)];assert len(asset['frames'])==n
  for i,f in enumerate(asset['frames']):
   native=(f['width'],f['height'],*frame_alignment(script,asset,i))
   w,h,fx,fy=native
   rgba=np.asarray(assets.image(f),dtype=np.uint16);assert rgba.shape[:2]==(h,w)
   rgb=np.where(rgba[:,:,3],(rgba[:,:,0]>>3)|((rgba[:,:,1]>>3)<<5)|((rgba[:,:,2]>>3)<<10)|0x8000,0).astype('<u2')
   record=bytearray(struct.pack('<HHhh',*native))
   for mirrored in (False,True):
    # Native mirror alignment is referenceWidth-width-alignX.
    effective_x=fx-reference if mirrored else fx
    pixels,x,y=raster(rgb,effective_x,fy,not mirrored)
    key=pixels.tobytes()
    if key not in lookup:
     packed,bits=packet(key);lookup[key]=(len(payload),len(packed))
     payload.extend(packed);payload.extend(bytes(-len(payload)%4))
    offset,size=lookup[key];height,width=pixels.shape
    record.extend(struct.pack('<IIHHhh',offset,size,width,height,x,y))
   records.append(record)
  stats.append({'id':id,'frames':n})
 assert len(records)==frames
 data=struct.pack('<4sHHI',b'KFES',count,frames,len(payload))+resources+b''.join(records)+payload
 path=out/'enemies.frames';path.write_bytes(data)
 result={'file':path.name,'bytes':len(data),'resources':count,'frames':frames,'unique_packets':len(lookup),'sha256':hashlib.sha256(data).hexdigest(),'scope':'Direct original-script/frame compilation with uniform8/25 sprite sampling; both mirrored alignments; native metadata and 19 animation ranges retained.','resource_inventory':stats}
 (out/'enemy-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='resource_inventory'}))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--maps',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.assets,a.maps,a.output)
if __name__=='__main__':main()
