"""Fast-path equivalence to previous production collision and tile queries.
Includes shipped dimensions and generic fallback sizes; not hardware timing.
"""
from pathlib import Path
import ctypes as C,json,random,subprocess,tempfile,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'research/gameplay'));from verify_collision import Map,Atlas
rng=random.Random(434240)
with tempfile.TemporaryDirectory(prefix='kinder-collision-fast-')as tmp:
 libs=[]
 for label,paths in [('before',['/tmp/kinder-collision-before-fast.c','/tmp/kinder-tile-queries-before-fast.c']),('after',[str(R/'ds/source/collision.c'),str(R/'ds/source/tile_queries.c')])]:
  so=Path(tmp)/(label+'.dylib');subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),*paths,'-o',str(so)],check=True);c=C.CDLL(str(so))
  for fn in ('collision_point','map_tile_solid','map_tile_property'):getattr(c,fn).argtypes=[C.POINTER(Map),C.c_uint,C.c_int,C.c_int];getattr(c,fn).restype=C.c_int
  libs.append(c)
 cases=0;dimensions=[]
 for tw,th,aw,ah in [(32,32,640,480),(32,32,512,256),(24,24,480,240),(16,8,320,160),(64,48,640,480),(8,16,192,128)]:
  data=(C.c_uint8*(4*4*3*3)).from_buffer_copy(rng.randbytes(4*4*3*3));m=Map(4,4,tw,th,3,data);mask=(C.c_uint8*((aw*ah+7)//8)).from_buffer_copy(rng.randbytes((aw*ah+7)//8))
  for bank in range(4):m.atlas[bank]=Atlas(aw,ah,mask)
  for i in range(4096):
   layer=rng.randrange(5);x=rng.randrange(-tw,tw*5);y=rng.randrange(-th,th*5)
   for fn in ('collision_point','map_tile_solid','map_tile_property'):
    a=getattr(libs[0],fn)(C.byref(m),layer,x,y);b=getattr(libs[1],fn)(C.byref(m),layer,x,y);assert a==b,(tw,th,aw,fn,layer,x,y,a,b);cases+=1
  dimensions.append([tw,th,aw,ah])
 result={'scope':__doc__,'comparisons':cases,'dimensions':dimensions,'extra_memory_bytes':0,'limits':['Random valid full-array map fixtures compare previous/current production behavior; native shipped-map checks are separate.','ARM9 fast branches avoid runtime division; no measured DS FPS gain.']};(R/'research/gameplay/collision-fast-paths-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
