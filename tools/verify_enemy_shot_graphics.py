#!/usr/bin/env python3
"""Independent original PNG sampling matches bounded DS shot renderer."""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];path=Path(tempfile.gettempdir())/'kinder_enemy_shot_graphics.dylib'
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-DENEMY_SHOT_ROOT="'+str(ROOT/'ds/nitrofs/enemy_shots')+'"',str(ROOT/'ds/source/enemy_shots.c'),str(ROOT/'ds/source/animation.c'),'-o',str(path)],check=True);lib=C.CDLL(str(path));lib.enemy_shot_graphics_open.restype=C.c_bool;assert lib.enemy_shot_graphics_open();lib.enemy_shots_spawn.argtypes=[C.c_uint32,C.c_float,C.c_float,C.c_float,C.c_float];lib.enemy_shots_spawn.restype=C.c_bool;lib.enemy_shots_draw.argtypes=[C.POINTER(C.c_uint16),C.c_int,C.c_int];lib.enemy_shots_draw.restype=C.c_bool
class Record(C.Structure):_fields_=[('bytes',C.c_ubyte*100)]
lib.enemy_shots_spawn_record.argtypes=[C.POINTER(Record)];lib.enemy_shots_spawn_record.restype=C.c_bool
cases=[];count=0
for source,frame,callback in [('KONG02',16,0x413b70),('KLEINER_YETI',25,0x41b770),('SCHNEEMANN',54,0x41a910),('EIER_ROBOTER',23,0x40fd70),('GORILLA',87,0x40c2c0),('ROBOTER',188,0x40d5c0),('B_r',53,0x413b70),('KRAKE',50,0x40cc60),('POINTS',0,0x412dd0),('POINTS',1,0x412dd0),('POINTS',2,0x412dd0)]:
 im=Image.open(ROOT/f'generated/assets/frames/Animation/{source}/{frame:03}.png').convert('RGBA');original=list(im.get_flattened_data());width,height=im.size
 for flip in (False,True):
  for phase in range(25):
   for sx,sy in [(1234.75+phase,755.25),(1023.75+phase,620.25),(1830.5+phase,1200.75),(1010.5+phase,1205.75)]:
    lib.enemy_shots_init();raw=bytearray(100);struct.pack_into('<2f',raw,12,sx,sy);struct.pack_into('<I',raw,44,frame);struct.pack_into('<I',raw,64,1);struct.pack_into('<I',raw,80,2 if flip else 0);struct.pack_into('<I',raw,96,callback);record=Record.from_buffer_copy(raw);assert lib.enemy_shots_spawn_record(C.byref(record))
    cx,cy=1024,624;dest=(C.c_uint16*(256*192))(*([0x8000]*(256*192)));assert lib.enemy_shots_draw(dest,cx,cy);expected=[0x8000]*(256*192);left=int(sx)-(width if flip else 0);top=int(sy)
    for y in range(192):
     yy=cy+((2*y+1)*25)//16-top
     if not 0<=yy<height:continue
     for x in range(256):
      xx=cx+((2*x+1)*25)//16-left
      if not 0<=xx<width:continue
      if flip:xx=width-1-xx
      r,g,b,a=original[yy*width+xx]
      if a:expected[y*256+x]=(r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000
    assert list(dest)==expected,(source,flip,phase,sx,sy);count+=1
 cases.append({'source':source,'frame':frame,'callback':hex(callback),'size':[width,height]})
result={'original_frames':cases,'viewport_cases':count,'pixels_compared_per_case':49152,'sampling':'source-space centered25/16 proportional800x600->256x192','cache_bytes':27638};(ROOT/'research/enemies/shot_graphics_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
