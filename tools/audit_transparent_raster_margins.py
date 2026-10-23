"""Measure removable transparent margins in current DS rasters; do not modify assets.
Native animation/collision records would remain separate and unchanged; a crop
would shift the raster descriptor origin by the removed left/top pixels.
"""
from pathlib import Path
import json,struct
import numpy as np
from scenery_codec import unpack
R=Path(__file__).resolve().parents[1]
rows=[]
paths=[R/'ds/nitrofs/players/pinguin.frames',R/'ds/nitrofs/players/milchschnitte.frames',R/'ds/nitrofs/scenes/enemies.frames',R/'ds/nitrofs/scenes/pickups.frames']
for p in paths:
 b=p.read_bytes();magic=b[:4]
 if magic==b'KFP3':nf=struct.unpack_from('<I',b,4)[0];start=8;stride=40;delta=8
 else:
  nr,nf,_=struct.unpack_from('<HHI',b,4);assert magic in (b'KFES',b'KFSP');start=12+nr*(84 if magic==b'KFES'else 12);stride=40 if magic==b'KFES'else 48;delta=8 if magic==b'KFES'else 16
 base=start+nf*stride;cache={};before=after=changed=empty=0;max_before=max_after=0
 for i in range(nf):
  for d in range(2):
   off,size,w,h,x,y=struct.unpack_from('<IIHHhh',b,start+i*stride+delta+d*16);key=(off,size,w,h)
   if key not in cache:
    image=unpack(b[base+off:base+off+size])[:w*h].reshape(h,w);opaque=(image&32768)!=0;ys,xs=np.nonzero(opaque)
    if len(xs):nw=int(xs.max()-xs.min()+1);nh=int(ys.max()-ys.min()+1)
    else:nw=nh=1
    cache[key]=(nw*nh,len(xs)==0)
   n,is_empty=cache[key];before+=w*h;after+=n;changed+=n!=w*h;empty+=is_empty;max_before=max(max_before,w*h*2);max_after=max(max_after,n*2)
 row=dict(file=str(p.relative_to(R)),rasters=nf*2,unique_raster_shapes=len(cache),croppable_rasters=changed,empty_rasters=empty,decoded_bytes_before=before*2,decoded_bytes_after_crop=after*2,decoded_bytes_reduction_percent=round(100*(1-after/before),2),max_frame_bytes_before=max_before,max_frame_bytes_after_crop=max_after);rows.append(row);print(json.dumps(row),flush=True)
report=dict(scope=__doc__,files=rows,decoded_bytes_before=sum(x['decoded_bytes_before']for x in rows),decoded_bytes_after_crop=sum(x['decoded_bytes_after_crop']for x in rows),limits=['Decoded-pixel work/cache feasibility only; encoded byte saving and runtime FPS are not measured.','Raster trim is not implemented. Integration must preserve each native frame/resource record and reconstruct exactly the same visible pixels at every camera phase and facing.'])
(R/'research/rendering/transparent-raster-margin-audit.json').write_text(json.dumps(report,indent=2)+'\n')
