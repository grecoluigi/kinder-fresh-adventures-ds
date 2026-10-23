"""Validate staged entity packets against independent sampling of original PNGs."""
from pathlib import Path
import ctypes,struct,json,subprocess,numpy as np
from maps_render import Renderer
from native_resources import asset_source
R=Path(__file__).resolve().parents[1]
source=Path('/tmp/kinder-sprite-codec.c');source.write_text('#include "sprite_codec.h"\nint decode(const uint8_t*p,size_t n,uint16_t*d,unsigned count){return sprite_codec_decode(p,n,d,count);}\n')
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),str(source),'-o','/tmp/kinder-sprite-codec.dylib'],check=True)
c=ctypes.CDLL('/tmp/kinder-sprite-codec.dylib');c.decode.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_uint]
pack=(R/'generated/ds-scaled/enemies.frames').read_bytes();old=(R/'ds/nitrofs/scenes/enemies.frames').read_bytes()
old_stride=16 if old[:4]==b'KFEN' else 40
n,frames,payload=struct.unpack_from('<HHI',pack,4);assert pack[:4]==b'KFES';base=12+n*84+frames*40;assert base+payload==len(pack)
assert pack[12:12+n*84]==old[12:12+n*84]
r=Renderer(R/'generated/assets',R/'generated/maps');cases=0;pixels_checked=0
for ri in range(n):
 id,start,count,reference=struct.unpack_from('<4H',pack,12+ri*84);asset=r.assets[asset_source(r.scripts[id])]
 for i,original in enumerate(asset['frames']):
  at=12+n*84+(start+i)*40;w,h,fx,fy=struct.unpack_from('<HHhh',pack,at)
  old_at=12+n*84+(start+i)*old_stride+(8 if old_stride==16 else 0)
  assert pack[at:at+8]==old[old_at:old_at+8]
  rgba=np.asarray(r.frame(original).convert('RGBA'),dtype=np.uint16)
  rgb=np.where(rgba[:,:,3],(rgba[:,:,0]>>3)|((rgba[:,:,1]>>3)<<5)|((rgba[:,:,2]>>3)<<10)|0x8000,0).astype(np.uint16)
  for mirror in (0,1):
   offset,size,dw,dh,dx,dy=struct.unpack_from('<IIHHhh',pack,at+8+mirror*16);assert offset%4==0 and offset+size<=payload
   encoded=ctypes.create_string_buffer(pack[base+offset:base+offset+size]);guard=np.full(dw*dh+32,0x1234,dtype=np.uint16)
   assert c.decode(encoded,size,guard[16:].ctypes.data,dw*dh)
   x=np.floor((np.arange(dw)+dx+.5)*25/8).astype(int)-(reference-w-fx if mirror else fx)
   y=np.floor((np.arange(dh)+dy+.5)*25/8).astype(int)-fy
   valid=(x[None,:]>=0)&(x[None,:]<w)&(y[:,None]>=0)&(y[:,None]<h)
   source=rgb[:,::-1] if mirror else rgb
   expected=np.where(valid,source[np.clip(y,0,h-1)[:,None],np.clip(x,0,w-1)[None,:]],0)
   assert np.array_equal(guard[16:-16].reshape(dh,dw),expected),(id,i,mirror)
   assert np.all(guard[:16]==0x1234) and np.all(guard[-16:]==0x1234)
   cases+=1;pixels_checked+=dw*dh
result={'resources':n,'frames':frames,'rasters':cases,'pixels_checked':pixels_checked,'failures':[],'scope':'All staged KFES rasters decoded using production sprite codec; independent original-PNG sample equations, native metadata/ranges byte identity and buffer guards. Runtime renderer integration not covered.'}
(R/'research/rendering/enemy-scaled-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
