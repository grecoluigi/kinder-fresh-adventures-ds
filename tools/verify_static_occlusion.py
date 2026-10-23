"""Whole-map last-static-writer oracle: removed pixels are always overwritten later, for arbitrary live opaque callbacks."""
from pathlib import Path
import json,struct,ctypes as C,subprocess,tempfile
import numpy as np
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-occlusion-')as temporary:
 t=Path(temporary);src=t/'codec.c';src.write_text('#include "sprite_codec.h"\nint decode(const uint8_t*p,size_t n,uint16_t*d){return sprite_codec_decode(p,n,d,256);}')
 so=t/'codec.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),str(src),'-o',str(so)],check=True);c=C.CDLL(str(so));c.decode.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p]
 def load(root,name):
  data=(root/name).read_bytes();assert data[:4]==b'KFC4';n=struct.unpack_from('<I',data,4)[0];base=8+n*8;tiles=[]
  for i in range(n):
   off,size=struct.unpack_from('<II',data,8+i*8);buf=C.create_string_buffer(data[base+off:base+off+size]);out=np.full(288,0x1234,dtype=np.uint16)
   assert c.decode(buf,size,out[16:].ctypes.data);assert np.all(out[:16]==0x1234)and np.all(out[-16:]==0x1234);tiles.append(out[16:-16].copy())
  idx=(root/Path(name).with_suffix('.index')).read_bytes();nc=struct.unpack_from('<I',idx,8)[0];commands=[struct.unpack_from('<III',idx,20+i*12)for i in range(nc)];placements=[struct.unpack_from('<HH',idx,20+nc*12+i*4)for i in range(struct.unpack_from('<I',idx,12)[0])];return idx[:8]+idx[16:20],tiles,commands,placements
 maps=[];pixels=removed=0
 for p in sorted((R/'generated/ds-scaled/composite').glob('*.atlas')):
  header,tiles,commands,placements=load(p.parent,p.name);nh,nt,nc,npairs=load(R/'generated/ds-occluded/composite',p.name);assert header==nh and len(commands)==len(nc)
  owners={}
  for ci,(kind,begin,count)in enumerate(commands):
   if kind:continue
   for cell,id in placements[begin:begin+count]:
    owner=owners.setdefault(cell,np.zeros(256,dtype=np.uint16));owner[(tiles[id]&32768)!=0]=ci+1
  kept=gone=0
  for ci,(kind,begin,count)in enumerate(commands):
   nk,nb,nn=nc[ci];assert kind==nk
   if kind:assert commands[ci]==nc[ci];continue
   actual=dict(npairs[nb:nb+nn]);assert len(actual)==nn;expected_cells=set()
   for cell,id in placements[begin:begin+count]:
    image=np.where(owners[cell]==ci+1,tiles[id],0).astype(np.uint16);pixels+=256
    removed+=int(np.count_nonzero(((tiles[id]&32768)!=0)&(owners[cell]!=ci+1)))
    if np.any(image):expected_cells.add(cell);assert np.array_equal(nt[actual[cell]],image),(p.name,ci,cell);kept+=1
    else:assert cell not in actual;gone+=1
   assert set(actual)==expected_cells
  maps.append({'map':p.name,'kept_placements':kept,'fully_hidden_placements':gone})
 result={'scope':__doc__,'pixels_checked':pixels,'removed_opaque_pixels':removed,'maps':maps,'codec_guards':True,'limits':['All source pixel positions and original callback positions are covered; callbacks must use opaque overwrite/color-key drawing, as production currently does.','Does not authorize removing collision geometry or treating intermediate framebuffer contents as invariant.','Final viewport and runtime checks remain separate.']};(R/'research/rendering/static-occlusion-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
