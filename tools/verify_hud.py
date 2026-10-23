#!/usr/bin/env python3
"""Execute original 4089c0, intercept only resource/renderer/font/CRT boundaries."""
import argparse,ctypes as C,json,random,struct,subprocess
from pathlib import Path
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_ESP,UC_X86_REG_EIP
import pefile
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-dir',type=Path,default=R/'ds/source');args=parser.parse_args();sources=[args.source_dir/'hud.c'];native=args.source_dir/'native_bottom.c'
if native.exists():sources.append(native)
class State(C.Structure):_fields_=[(n,C.c_int32) for n in ['score','health','ammo','actor','shot_variant','boss','boss_energy','world']]+[('letters',C.c_int16*6)]
class Command(C.Structure):_fields_=[('resource',C.c_int32),('frame',C.c_int32)]
subprocess.run(['cc','-Wall','-Wextra','-Werror','-shared','-fPIC',*map(str,sources),'-o','/tmp/kinder_hud.dylib'],check=True)
lib=C.CDLL('/tmp/kinder_hud.dylib');lib.hud_layout.argtypes=[C.POINTER(State),C.POINTER(Command)];lib.hud_layout.restype=C.c_uint
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'))
u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x100000,0x100000);u.mem_map(0x300000,0x10000)
def write(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def read(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def signed(a):return struct.unpack('<i',u.mem_read(a,4))[0]
slots={0:0x4daae0,1:0x4daae4,8:0x4daaa4,9:0x4daab0,10:0x4daaa8,11:0x4daab8,12:0x4daaac}
slots.update({2+i:0x4daabc+i*4 for i in range(6)})
handles={0x180000+rid*256:rid for rid in slots};frameptr={}
for handle,rid in handles.items():
 write(slots[rid],handle)
 for f in range(16):
  ptr=0x100000+rid*0x1000+f*64;frameptr[ptr]=(rid,f);u.mem_write(ptr+0x21,struct.pack('<hh',rid*13+f,rid*3+f))
commands=[]
def ret(clean=0,value=0):
 sp=u.reg_read(UC_X86_REG_ESP);pc=read(sp);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_ESP,sp+4+clean);u.reg_write(UC_X86_REG_EIP,pc)
def hook(uc,a,size,_):
 sp=uc.reg_read(UC_X86_REG_ESP)
 if a==0x439554:
  value=signed(sp+12);uc.mem_write(read(sp+4),str(value).encode()+b'\0');ret()
 elif a==0x41ecbc:
  rid=handles[read(sp+4)];f=signed(sp+8);ret(8,0x100000+rid*0x1000+f*64 if 0<=f<16 else 0)
 elif a==0x41d615:
  ptr=read(sp+4);rid,f=frameptr[ptr];commands.append((rid,f));assert signed(sp+8)==rid*13+f and signed(sp+12)==rid*3+f;ret(12)
 elif a==0x4012f0:
  text=bytes(uc.mem_read(read(sp+4),16)).split(b'\0')[0];commands.append((14,int(text)));assert [read(sp+8),read(sp+12),read(sp+16)]==[1,440,7];ret(16)
u.hook_add(UC_HOOK_CODE,hook)
rng=random.Random(4089);cases=[]
for health in [-1,0,1,20,21,40,41,60,61,80,81,100,1000]:
 for ammo in [0,1,10]:
  for boss in [0,1]:cases.append(State(123,health,ammo,0,0,boss,9,0,(C.c_int16*6)(0,1,0,1,0,1)))
for _ in range(400):cases.append(State(rng.randrange(0,2**31),rng.randrange(-10,120),rng.randrange(0,11),rng.randrange(2),rng.randrange(-1,2),rng.randrange(-1,2),rng.randrange(-1,10),rng.randrange(4),(C.c_int16*6)(*[rng.randrange(-1,3) for i in range(6)])))
for s in cases:
 for addr,v in [(0x45ed2c,s.score),(0x45f014,s.health),(0x45ed34,s.ammo),(0x45ed1c,s.actor),(0x4e1044,s.shot_variant),(0x45ed24,s.boss_energy)]:write(addr,v)
 u.mem_write(0x45ecbc,struct.pack('<h',s.boss));u.mem_write(0x45efd4,bytes(s.letters))
 ptr=0x100000+13*0x1000+s.world*64;frameptr[ptr]=(13,s.world);u.mem_write(ptr+0x21,struct.pack('<hh',13*13+s.world,13*3+s.world));write(0x4daaf4,ptr)
 commands.clear();write(0x308000,0x1f0000);u.reg_write(UC_X86_REG_ESP,0x308000);u.emu_start(0x4089c0,0x1f0000,count=10000)
 out=(Command*16)();n=lib.hud_layout(C.byref(s),out);expected=[(out[i].resource,out[i].frame) for i in range(n)]
 assert commands==expected,(list(s.letters),s.health,s.ammo,s.boss,commands,expected)
result=dict(source_dir=str(args.source_dir.resolve()),native_address='0x4089c0',cases=len(cases),passed=True,scope='Original HUD draw resource/frame/order, health threshold boundaries, score text and placement, actor, ammo variants, six letters, boss energy/portrait. Native resource lookup and drawing mocked; all expected assets present.')
(R/'research/hud/verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
