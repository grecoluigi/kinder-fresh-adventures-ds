from pathlib import Path
import ctypes,json,subprocess,numpy as np,struct
from PIL import Image
R=Path(__file__).resolve().parents[1]
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DPLAYER_ROOT="{R}/ds/nitrofs/players"',str(R/'ds/source/player_graphics.c'),'-o','/tmp/player-scaled.dylib'],check=True)
c=ctypes.CDLL('/tmp/player-scaled.dylib');c.player_graphics_open.restype=c.player_graphics_draw.restype=ctypes.c_bool
assert c.player_graphics_open()
inv=json.loads((R/'generated/assets/inventory.json').read_text());cases=0
for char,name in enumerate(('PINGUIN','MILCHSCHNITTE')):
 asset=next(a for a in inv if a['source']==f'Animation/{name}.W01')
 pack=(R/'ds/nitrofs/players'/f'{name.lower()}.frames').read_bytes()
 assert pack[:4]==b'KFP3' and struct.unpack_from('<I',pack,4)[0]==len(asset['frames'])
 for frame,m in enumerate(asset['frames']):
  rgba=np.asarray(Image.open(R/m['png']).convert('RGBA'),dtype=np.uint16);h,w=rgba.shape[:2]
  assert struct.unpack_from('<HHhh',pack,8+frame*40)==(w,h,m['x'],m['y'])
  rgb=np.where(rgba[:,:,3],(rgba[:,:,0]>>3)|((rgba[:,:,1]>>3)<<5)|((rgba[:,:,2]>>3)<<10)|0x8000,0).astype(np.uint16)
  for facing in (0,1):
   positions=[(500,550,87,24)]
   if frame%19==0: positions += [(500,550,87+phase,24+phase)for phase in range(25)]
   if frame%19==0: positions += [(0,0,87,24),(800,600,0,0),(-200,-200,0,0),(100,100,400,400),(799,599,12,13)]
   for bx,by,cx,cy in positions:
    originx=(bx*8+12)//25-(cx*8+12)//25;originy=(by*8+12)//25-(cy*8+12)//25
    left=m['x'] if facing else -m['x']-w
    # Independent full-screen sampling from original PNG; no packed raster metadata.
    sx=np.floor((np.arange(256)-originx+0.5)*25/8).astype(int)-left
    sy=np.floor((np.arange(192)-originy+0.5)*25/8).astype(int)-m['y']
    valid=(sy[:,None]>=0)&(sy[:,None]<h)&(sx[None,:]>=0)&(sx[None,:]<w)
    source=rgb if facing else rgb[:,::-1]
    sampled=np.where(valid,source[np.clip(sy,0,h-1)[:,None],np.clip(sx,0,w-1)[None,:]],0)
    expected=np.where(sampled&0x8000,sampled,0x8000).astype('<u2')
    guarded=np.full(49152+32,0x1234,dtype=np.uint16);guarded[16:-16]=0x8000
    assert c.player_graphics_draw(guarded[16:].ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)),char,frame,facing,bx,by,cx,cy)
    assert np.array_equal(guarded[16:-16].reshape(192,256),expected),(name,frame,facing,positions)
    bounds=(ctypes.c_int*4)();c.player_graphics_last_bounds(bounds)
    left,top,right,bottom=bounds
    assert 0<=left<=256 and 0<=top<=192 and 0<=right<=256 and 0<=bottom<=192
    bound_mask=(np.arange(192)[:,None]>=top)&(np.arange(192)[:,None]<bottom)&(np.arange(256)[None,:]>=left)&(np.arange(256)[None,:]<right)
    assert not np.any((sampled&0x8000).astype(bool)&~bound_mask),(name,frame,facing,'reported bounds')
    assert np.all(guarded[:16]==0x1234) and np.all(guarded[-16:]==0x1234)
    cases+=1
c.player_graphics_close()
result={'frames':586,'facings':2,'cases':cases,'failures':[], 'reported_bounds_contain_all_original_opaque_samples':True, 'scope':'All original player PNGs sampled independently at uniform 8/25 around separately quantized world body/camera origins; native metadata preserved; clipped/offscreen framebuffer guards. New DS projection intentionally differs from legacy camera-phase sampling. No hardware FPS claim.'}
(R/'research/rendering/player-scaled-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
