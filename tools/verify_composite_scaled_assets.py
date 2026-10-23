"""Independent pixel lookup in native sparse passes for every staged DS scenery tile."""
from pathlib import Path
import ctypes as C,subprocess,tempfile,struct,json,numpy as np
from tile_storage import unpack_packet
R=Path(__file__).resolve().parents[1];oldroot=R/'generated/native-composite' if (R/'generated/native-composite').exists()else R/'ds/nitrofs/composite';newroot=R/'generated/ds-scaled/composite';checked=0;pixels=0;maps=[]
with tempfile.TemporaryDirectory() as td:
 t=Path(td);src=t/'codec.c';src.write_text('#include "sprite_codec.h"\nint decode(const uint8_t*p,size_t n,uint16_t*d,unsigned count){return sprite_codec_decode(p,n,d,count);}\n')
 subprocess.run(['cc','-dynamiclib','-O2','-I'+str(R/'ds/source'),str(src),'-o',str(t/'codec.dylib')],check=True)
 lib=C.CDLL(str(t/'codec.dylib'));lib.decode.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint]
 for path in sorted(newroot.glob('*.atlas')):
  old=(oldroot/path.name).read_bytes();n=struct.unpack_from('<I',old,4)[0];oldbase=8+n*8;native=[]
  for i in range(n):
   off,size=struct.unpack_from('<II',old,8+i*8);native.append(np.frombuffer(unpack_packet(old[oldbase+off:oldbase+off+size]),dtype='<u2').reshape(32,32))
  packed=path.read_bytes();n=struct.unpack_from('<I',packed,4)[0];base=8+n*8;tiles=[]
  for i in range(n):
   off,size=struct.unpack_from('<II',packed,8+i*8);blob=C.create_string_buffer(packed[base+off:base+off+size]);out=np.full(288,0x1234,dtype=np.uint16)
   assert lib.decode(blob,size,out[16:].ctypes.data,256);assert np.all(out[:16]==0x1234)and np.all(out[-16:]==0x1234);tiles.append(out[16:-16].copy().reshape(16,16))
  oi=(oldroot/(path.name[:-6]+'.index')).read_bytes();ni=(newroot/(path.name[:-6]+'.index')).read_bytes();_,ow,oh,ncmd,_=struct.unpack_from('<4sHHII',oi);_,nw,nh,newcmd,_=struct.unpack_from('<4sHHII',ni);assert ncmd==newcmd and struct.unpack_from('<HH',ni,16)==(ow,oh)
  for ci in range(ncmd):
   oc=struct.unpack_from('<III',oi,16+ci*12);nc=struct.unpack_from('<III',ni,20+ci*12);assert oc[0]==nc[0]
   if oc[0]:assert oc==nc;continue
   refs=dict(struct.unpack_from('<HH',oi,16+ncmd*12+i*4)for i in range(oc[1],oc[1]+oc[2]))
   expected_cells=set()
   allxs=np.floor((np.arange(nw*16)+.5)*25/8).astype(int)
   allys=np.floor((np.arange(nh*16)+.5)*25/8).astype(int)
   for cell,nativeid in refs.items():
    left=(cell%ow)*32;top=(cell//ow)*32
    x0,x1=np.searchsorted(allxs,[left,left+32]);y0,y1=np.searchsorted(allys,[top,top+32])
    image=native[nativeid][(allys[y0:y1]-top)[:,None],(allxs[x0:x1]-left)[None,:]]
    yy,xx=np.nonzero(image)
    expected_cells.update(int((y+y0)//16*nw+(x+x0)//16)for y,x in zip(yy,xx))
   actual_cells=[struct.unpack_from('<H',ni,20+ncmd*12+i*4)[0]for i in range(nc[1],nc[1]+nc[2])]
   assert len(set(actual_cells))==len(actual_cells)
   assert set(actual_cells)==expected_cells,(path.name,ci,'missing or extra nonempty tiles')
   for i in range(nc[1],nc[1]+nc[2]):
    cell,id=struct.unpack_from('<HH',ni,20+ncmd*12+i*4);x0=(cell%nw)*16;y0=(cell//nw)*16
    xs=np.floor((np.arange(16)+x0+.5)*25/8).astype(int);ys=np.floor((np.arange(16)+y0+.5)*25/8).astype(int)
    cells=(ys[:,None]//32)*ow+xs[None,:]//32;valid=(ys[:,None]<oh*32)&(xs[None,:]<ow*32);expected=np.zeros((16,16),dtype=np.uint16)
    for nativecell in np.unique(cells[valid]):
     if int(nativecell)not in refs:continue
     select=(cells==nativecell)&valid;values=native[refs[int(nativecell)]][ys[:,None]%32,xs[None,:]%32];expected[select]=values[select]
    assert np.array_equal(expected,tiles[id]),(path.name,ci,cell,id);checked+=1;pixels+=256
  maps.append(path.name)
result={'scope':__doc__,'maps':maps,'tile_placements':checked,'pixels':pixels,'failures':[],'limits':['Checks every stored tile placement, complete nonempty-cell coverage, native callback identity and codec guards; runtime renderer integration still requires separate checks.','DS world-grid sampling intentionally differs from legacy camera-phase sampling; no hardware performance claim.']}
(R/'research/rendering/composite-scaled-asset-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
