"""Original433e60 panning/attenuation after supplied camera434510 projection.
Source viewport800x600 and alternate valid dimensions; no DS listening proof.
"""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EIP,UC_X86_REG_EAX
R=Path(__file__).resolve().parents[1]
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x50000);u.mem_map(0x2000,4096)
ENGINE=0x230000;STACK=0x208000;OUT=0x210000;projected=(0,0)
def hook(uc,at,size,ctx):
 if at==0x2000:uc.emu_stop();return
 if at!=0x434510:return
 sp=uc.reg_read(UC_X86_REG_ESP);pc,layer,x,y,xp,yp=struct.unpack('<6I',uc.mem_read(sp,24));uc.mem_write(xp,struct.pack('<i',projected[0]));uc.mem_write(yp,struct.pack('<i',projected[1]));uc.reg_write(UC_X86_REG_ESP,sp+24);uc.reg_write(UC_X86_REG_EIP,pc);uc.reg_write(UC_X86_REG_EAX,0)
u.hook_add(UC_HOOK_CODE,hook);rng=random.Random(433060)
with tempfile.TemporaryDirectory(prefix='kinder-spatial-')as tmp:
 so=Path(tmp)/'spatial.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/entities.c'),'-o',str(so)],check=True);c=C.CDLL(str(so));c.entity_sound_spatial.argtypes=[C.c_int32,C.c_int32,C.c_int16,C.c_int16,C.POINTER(C.c_int32),C.POINTER(C.c_int32)];cases=0
 fixtures=[(x,y,800,600)for x in (-1000,-1,0,1,399,400,401,799,800,801,1764,1765,2000)for y in (-1000,0,299,300,301,600,1470,2000)]
 fixtures +=[(rng.randrange(-1000000,1000000),rng.randrange(-1000000,1000000),rng.choice((256,640,800,1024,32766)),rng.choice((192,480,600,768,32766)))for _ in range(8192)]
 for x,y,w,h in fixtures:
  projected=(x,y);u.mem_write(ENGINE+0x14b5,struct.pack('<h',w));u.mem_write(ENGINE+0x14b9,struct.pack('<h',h));u.mem_write(ENGINE+0x169f,struct.pack('<h',2));u.mem_write(OUT,bytes(8));u.mem_write(STACK,struct.pack('<6I',0x2000,0,0,OUT,OUT+4,0));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ECX,ENGINE);u.emu_start(0x433e60,0x2000,count=10000)
  attenuation=C.c_int32();pan=C.c_int32();c.entity_sound_spatial(x,y,w,h,C.byref(attenuation),C.byref(pan));expected=struct.unpack('<ii',u.mem_read(OUT,8));assert (attenuation.value,pan.value)==expected,(x,y,w,h,attenuation.value,pan.value,expected);cases+=1
 result={'scope':__doc__,'native_cases':cases,'exact_attenuation_and_pan':True,'limits':['Camera projection434510 is supplied; camera geometry has separate native checks.','Invalid dimensions that make native division fail are safely muted in C.','No mixer integration, audible hardware check or full-gameplay proof.']};(R/'research/gameplay/entity-sound-spatial-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
