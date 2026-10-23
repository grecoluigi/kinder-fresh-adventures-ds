"""Compare native 431ce0 and 4128e0 with C; builder animation bounds supplied at 431300."""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EIP,UC_X86_REG_EAX
ROOT=Path(__file__).resolve().parents[1]
MAN,DATA,STACK,STOP,OBJ,CON,OUT=0x300000,0x310000,0x201000,0x4000,0x320000,0x330000,0x340000
class Rect(C.Structure):_fields_=[(n,C.c_int32) for n in ('left','right','top','bottom','flags','reserved20','object_index','reserved28')]
class Object(C.Structure):_fields_=[(n,C.c_int16) for n in ('id','x','y','active','width','height','align_x','align_y')]+[('solid',C.c_uint8),('top_trim',C.c_uint8),('object_index',C.c_int32)]
def main():
 pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image)
 for p,n in [(MAN,4096),(DATA,65536),(OBJ,65536),(CON,4096),(OUT,65536),(0x200000,12288),(STOP,4096)]:u.mem_map(p,n)
 bounds={}
 def ret(cleanup,value):
  sp=u.reg_read(UC_X86_REG_ESP);target=struct.unpack('<I',bytes(u.mem_read(sp,4)))[0];u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_ESP,sp+4+cleanup);u.reg_write(UC_X86_REG_EIP,target)
 def hook(uc,address,size,user):
  if address==0x4308c0:ret(0,CON)
  elif address==0x431300:
   sp=u.reg_read(UC_X86_REG_ESP);obj,*outputs=struct.unpack('<5I',bytes(u.mem_read(sp+4,20)))
   for ptr,v in zip(outputs,bounds[obj]):u.mem_write(ptr,struct.pack('<h',v))
   ret(20,1)
 u.hook_add(UC_HOOK_CODE,hook)
 def run(address,args):
  u.mem_write(STACK,struct.pack('<'+'I'*(len(args)+1),STOP,*[v&0xffffffff for v in args]));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ECX,MAN);u.emu_start(address,STOP,count=100000);assert u.reg_read(UC_X86_REG_EIP)==STOP;return u.reg_read(UC_X86_REG_EAX)
 rng=random.Random(4310);queries=builds=0
 with tempfile.TemporaryDirectory() as tmp:
  lib=Path(tmp)/'geometry.dylib';subprocess.run(['cc','-dynamiclib','-std=c11','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/geometry.c'),'-o',str(lib)],check=True);port=C.CDLL(str(lib));port.geometry_query.argtypes=[C.POINTER(Rect),C.c_int32,C.c_int32,C.c_int32,C.c_uint32];port.geometry_query.restype=C.c_uint32;port.geometry_build.argtypes=[C.POINTER(Rect),C.c_int32,C.POINTER(Object),C.c_int32,*[C.c_int32]*4]
  for case in range(500):
   n=rng.randrange(20);rects=(Rect*max(1,n))()
   for r in rects:
    r.left=rng.randrange(-200,200);r.right=r.left+rng.randrange(-4,100);r.top=rng.randrange(-200,200);r.bottom=r.top+rng.randrange(-4,100);r.flags=rng.getrandbits(32)
   u.mem_write(DATA,struct.pack('<i',n)+bytes(rects));null=case%51==0;u.mem_write(MAN+0x6c,struct.pack('<I',0 if null else DATA))
   for mode in list(range(17))+[0xffffffff,0x10000003]:
    for x,y in [(rng.randrange(-200,300),rng.randrange(-200,300)),(rects[0].left,rects[0].top),(rects[0].right,rects[0].bottom),(rects[0].right-1,rects[0].bottom-1)]:
     native=run(0x431ce0,[x,y,mode]);actual=port.geometry_query(None if null else rects,n,x,y,mode);assert native==actual,(case,mode,x,y,native,actual);queries+=1
  for case in range(1000):
   n=rng.randrange(1,50);objects=(Object*n)();bounds.clear();raw=bytearray(n*186)
   for i,o in enumerate(objects):
    o.id=rng.randrange(70,95);o.x=rng.randrange(-100,100);o.y=rng.randrange(-100,100);o.active=rng.randrange(2);o.solid=rng.randrange(2);o.width=rng.randrange(0,100);o.height=rng.randrange(0,100);o.align_x=rng.randrange(-40,40);o.align_y=rng.randrange(-40,40);o.top_trim=rng.randrange(256);o.object_index=i
    struct.pack_into('<4h',raw,i*186,o.id,o.x,o.y,o.active);raw[i*186+26]=o.solid;raw[i*186+42]=o.top_trim;bounds[OBJ+i*186]=(o.width,o.height,o.align_x,o.align_y)
   u.mem_write(OBJ,bytes(raw));u.mem_write(CON,struct.pack('<HI',n,OBJ));u.mem_write(0x51d6ec,struct.pack('<I',MAN));u.mem_write(0x4e0aac,struct.pack('<I',n));u.mem_write(0x4dac78,struct.pack('<'+'I'*n,*range(n)))
   region=[rng.randrange(-100,0),rng.randrange(-100,0),rng.randrange(0,150),rng.randrange(0,150)];capacity=rng.randrange(0,50);out=(Rect*50)();u.mem_write(OUT,b'\0'*1600)
   native=run(0x4128e0,[OUT,capacity,*region]);actual=port.geometry_build(out,capacity,objects,n,*region);assert native==actual,(case,native,actual);native_bytes=bytes(u.mem_read(OUT,native*32));assert native_bytes==bytes(out)[:actual*32],(case,native_bytes.hex(),bytes(out)[:actual*32].hex());builds+=1
 result=dict(query_cases=queries,builder_cases=builds,failures=0,native_query='0x431ce0',native_builder='0x4128e0',builder_stubs={'0x4308c0':'returns supplied map object container','0x431300':'supplies animation width,height,alignment; asset resolution not covered'})
 (ROOT/'research/gameplay/geometry_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
