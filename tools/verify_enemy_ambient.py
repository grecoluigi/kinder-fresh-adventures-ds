#!/usr/bin/env python3
"""Original412ee0 minimum accumulator and41139b attenuation instruction loop."""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1];path=Path(tempfile.gettempdir())/'kinder_world_enemies_ambient.dylib'
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/world_enemies.c'),str(ROOT/'ds/source/entities.c'),'-o',str(path)],check=True)
lib=C.CDLL(str(path))
class State(C.Structure):_fields_=[('squared_distance',C.c_int32*16),('camera_offset_x',C.c_int32),('camera_offset_y',C.c_int32)]
lib.enemy_ambient_reset.argtypes=[C.POINTER(State),C.c_int32,C.c_int32];lib.enemy_ambient_contribute.argtypes=[C.POINTER(State),C.c_int32,C.c_int32,C.c_uint];lib.enemy_ambient_volume.argtypes=[C.POINTER(State),C.c_uint]
p=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,p.get_memory_mapped_image());u.mem_map(0x200000,0x10000);u.mem_map(0x4000,0x1000);SP=0x208000
volumes=[]
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def ret(pop=0):
 esp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EIP,word(esp));u.reg_write(UC_X86_REG_ESP,esp+4+pop)
def hook(uc,at,size,ctx):
 esp=u.reg_read(UC_X86_REG_ESP)
 if at==0x434510:
  layer,x,y,xp,yp=struct.unpack('<5I',uc.mem_read(esp+4,20));assert(layer,x,y)==(2,0,0);uc.mem_write(xp,struct.pack('<i',state.camera_offset_x));uc.mem_write(yp,struct.pack('<i',state.camera_offset_y));ret(20)
 elif at==0x42339e:volumes.append(struct.unpack('<2i',uc.mem_read(esp+4,8)));ret()
u.hook_add(UC_HOOK_CODE,hook)
rng=random.Random(901);cases=0
for batch in range(100):
 state=State();lib.enemy_ambient_reset(C.byref(state),rng.randrange(-15000,5000),rng.randrange(-15000,5000));u.mem_write(0x4dbc20,bytes(state.squared_distance))
 cx=400-state.camera_offset_x;cy=300-state.camera_offset_y
 for i in range(100):
  slot=rng.randrange(16);x=cx+rng.choice([-1200,-1199,-350,0,350,1199,1200,rng.randrange(-1500,1500)]);y=cy+rng.choice([-900,-899,0,899,900,rng.randrange(-1200,1200)])
  lib.enemy_ambient_contribute(C.byref(state),x,y,slot);u.mem_write(SP,struct.pack('<4i',0x4000,x,y,slot));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(0x412ee0,0x4000,count=1000)
  assert bytes(state.squared_distance)==bytes(u.mem_read(0x4dbc20,64));cases+=1
for i in range(1000):
 state=State();vals=[rng.choice([122499,122500,122501,1130000,1130001,rng.randrange(2200000)]) for _ in range(16)];state.squared_distance[:]=vals;u.mem_write(0x4dbc20,struct.pack('<16i',*vals));u.mem_write(0x4e0ab8,struct.pack('<16i',*([1]*16)));u.reg_write(UC_X86_REG_ESP,SP);u.reg_write(UC_X86_REG_EBX,0);volumes.clear();u.emu_start(0x41139b,0x4113f4,count=3000)
 assert volumes==[(s,lib.enemy_ambient_volume(C.byref(state),s)) for s in range(16)],(vals,volumes)
result={'accumulator':'0x412ee0','accumulator_cases':cases,'attenuation_loop':'0x41139b..4113f4','attenuation_cases':16000,'startup':'0x412626..4126e3','startup_evidence':'Byte-verified startup mapping; no DirectSound playback executed','limits':['Camera layer conversion supplied','Native helper receiver device volume not executed']};(ROOT/'research/enemies/ambient_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
