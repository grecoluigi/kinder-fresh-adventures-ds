"""Execute original4111e5..41135b motion and independently sample original PNGs.
This proves banner physics/art; full victory/death playthroughs remain unverified.
"""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
from PIL import Image
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EBX
R=Path(__file__).resolve().parents[1]
class Title(C.Structure):_fields_=[('action',C.c_int32),('frame',C.c_int32),('x',C.c_float),('y',C.c_float),('vy',C.c_float)]
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));im=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(im)+4095)&~4095);u.mem_write(0x400000,im)
def stop(uc,address,size,context):
 if address in (0x41134a,0x41135b):uc.emu_stop()
u.hook_add(UC_HOOK_CODE,stop)
with tempfile.TemporaryDirectory(prefix='kinder-titles-')as tmp:
 so=Path(tmp)/'titles.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DEND_TITLE_ROOT="{R}/ds/nitrofs/end_titles"',str(R/'ds/source/end_titles.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.end_title_tick.argtypes=[C.POINTER(Title)];c.end_title_draw.argtypes=[C.POINTER(Title),C.POINTER(C.c_uint16)];c.end_title_draw.restype=C.c_bool
 motion=images=0
 for action in (1,2):
  t=Title(action,0,0,0,0);u.mem_write(0x4dab68,b'\0'*100);u.mem_write(0x4daba8,struct.pack('<i',action))
  png=Image.open(R/f'generated/assets/frames/Animation/ENDTITLES/{action-1:03}.png').convert('RGBA');source=list(png.get_flattened_data());width,height=png.size
  for tick in range(240):
   u.reg_write(UC_X86_REG_EBX,0);u.emu_start(0x4111e5,0x41135b,count=1000);c.end_title_tick(C.byref(t))
   native_action=struct.unpack('<i',u.mem_read(0x4daba8,4))[0];x,y,vy=struct.unpack('<fff',u.mem_read(0x4dab74,8)+u.mem_read(0x4dab80,4));frame=struct.unpack('<i',u.mem_read(0x4dab94,4))[0]
   assert (t.action,t.frame,t.x,t.y,t.vy)==(native_action,frame,x,y,vy),(tick,tuple((t.action,t.frame,t.x,t.y,t.vy)),(native_action,frame,x,y,vy))
   motion+=1
   pixels=(C.c_uint16*49152)(*([0x9abc]*49152));assert c.end_title_draw(C.byref(t),pixels)
   expected=[0x9abc]*49152
   for dy in range(192):
    sy=((2*dy+1)*25)//16-int(y)
    if not 0<=sy<height:continue
    for dx in range(256):
     sx=((2*dx+1)*25)//16-int(x)
     if not 0<=sx<width:continue
     r,g,b,a=source[sy*width+sx]
     if a:expected[dy*256+dx]=0x8000|(r>>3)|((g>>3)<<5)|((b>>3)<<10)
   assert list(pixels)==expected,(action,tick);images+=1
  assert t.action==100
  c.end_title_close()
 result={'scope':__doc__,'native_motion_ticks':motion,'original_image_comparisons':images,'lazy_cache_bytes':418*51*2}
 (R/'research/highscores/end-titles-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
