"""Replay native initialization434650 and follow4349c0/434ab0/434560 against C camera; no native calls mocked."""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EIP
ROOT=Path(__file__).resolve().parents[1];ENGINE,RECT,STACK,STOP=0x300000,0x310000,0x201000,0x4000
class Layer(C.Structure):_fields_=[(n,C.c_int16) for n in ('tile_x','tile_y','offset_x','offset_y','factor_x','factor_y')]
class Camera(C.Structure):_fields_=[('layers',Layer*8),*[(n,C.c_int32) for n in ('max_x','max_y','left','top','right','bottom')],('reference_layer',C.c_int16)]
def main():
 pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image)
 for p,n in [(ENGINE,0x3000),(RECT,0x1000),(0x200000,0x3000),(STOP,0x1000)]:u.mem_map(p,n)
 rng=random.Random(20020117);cases=0;fail=[]
 with tempfile.TemporaryDirectory() as tmp:
  lib=Path(tmp)/'camera.dylib';subprocess.run(['cc','-dynamiclib','-std=c11','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/camera.c'),'-o',str(lib)],check=True);port=C.CDLL(str(lib));port.camera_init.argtypes=[C.POINTER(Camera),C.c_int,C.c_int,C.c_int,C.c_int,C.POINTER(C.c_int16),C.c_int];port.camera_follow.argtypes=[C.POINTER(Camera),C.c_int,C.c_int,C.c_int,C.c_int]
  for item in json.loads((ROOT/'generated/maps/inventory.json').read_text()):
   info=item['entries'][0];w,h=info['width_cells'],info['height_cells']
   for unequal in [False,True]:
    f=(C.c_int16*8)(*([2]*8 if not unequal else list(range(2,18,2))));c=Camera();port.camera_init(C.byref(c),w,h,w*9,h*7,f,2)
    initial=bytearray(0x3000)
    struct.pack_into('<B',initial,0x16d2,8);struct.pack_into('<hhhh',initial,0x1685,32,32,w,h)
    for l,v in enumerate(c.layers):
     struct.pack_into('<9h',initial,0x14d5+l*18,1,0,0,0,0,v.factor_x,v.factor_y,c.max_x//32,c.max_y//32)
     struct.pack_into('<hh',initial,0x183b+l*4,v.factor_x,v.factor_y)
    u.mem_write(ENGINE,bytes(initial));u.mem_write(STACK,struct.pack('<4I',STOP,RECT,w*9,h*7));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ECX,ENGINE);u.emu_start(0x434650,STOP,count=10000);assert u.reg_read(UC_X86_REG_EIP)==STOP
    initial_native=[struct.unpack('<4h',bytes(u.mem_read(ENGINE+0x14d7+l*18,8))) for l in range(8)]
    initial_port=[(v.tile_x,v.tile_y,v.offset_x,v.offset_y) for v in c.layers];cases+=1
    if initial_native!=initial_port:fail.append(dict(map=item['file'],operation='initialization',unequal=unequal,native=initial_native,port=initial_port))
    for i in range(128):
     state=bytearray(0x3000)
     def put(off,fmt,*v):struct.pack_into(fmt,state,off,*v)
     put(0x16d2,'B',8);put(0x1685,'hhhh',32,32,w,h);put(0x169f,'h',2);put(0x1817,'4i',130,280,670,480);disabled=i%23==0;put(0x1861,'h',int(disabled))
     for l,v in enumerate(c.layers):put(0x14d5+l*18,'9h',1,v.tile_x,v.tile_y,v.offset_x,v.offset_y,v.factor_x,v.factor_y,0,0)
     put(0x14d1+8*18,'hh',c.max_x//32,c.max_y//32)
     px=rng.randrange(-80,w*32+80);py=rng.randrange(-80,h*32+80);selector=rng.randrange(3)
     rect=struct.pack('<4i4h',px-10,py-10,px+10,py+10,10,0,0,selector)
     u.mem_write(ENGINE,bytes(state));u.mem_write(RECT,rect);u.mem_write(STACK,struct.pack('<II',STOP,RECT));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ECX,ENGINE);u.emu_start(0x4349c0,STOP,count=10000);assert u.reg_read(UC_X86_REG_EIP)==STOP
     native=[struct.unpack('<4h',bytes(u.mem_read(ENGINE+0x14d7+l*18,8))) for l in range(8)]
     port.camera_follow(C.byref(c),px,py,selector,int(disabled));actual=[(v.tile_x,v.tile_y,v.offset_x,v.offset_y) for v in c.layers];cases+=1
     if native!=actual:fail.append(dict(map=item['file'],unequal=unequal,case=i,player=[px,py],selector=selector,native=native,port=actual));break
 result=dict(cases=cases,failures=fail,pass_count=cases-len(fail),scope=__doc__,native_functions=['0x4349c0','0x434ab0','0x434560','0x434650'])
 (ROOT/'research/gameplay/camera_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result)[:2000]);assert not fail
if __name__=='__main__':main()
