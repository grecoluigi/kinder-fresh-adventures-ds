#!/usr/bin/env python3
"""Actual original40adc0 initializer followed by owner7/8/12 native overwrites."""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1];path=Path(tempfile.gettempdir())/'kinder_world_shot_spawn.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/world_enemies.c'),str(ROOT/'ds/source/entities.c'),'-o',str(path)],check=True);lib=C.CDLL(str(path))
class Shot(C.Structure):_fields_=[('bytes',C.c_uint8*100)]
lib.world_enemy_shot_init.argtypes=[C.POINTER(Shot),C.c_uint,C.c_uint32,C.c_float,C.c_float,C.c_float,C.c_float];lib.world_enemy_shot_init.restype=C.c_bool
pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x200000,0x10000);u.mem_map(0x300000,0x10000);u.mem_map(0x4000,0x1000);SP=0x208000;OBJ=0x300000;DEST=0x302000
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def ret(value=0,pop=0):
 esp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,word(esp));u.reg_write(UC_X86_REG_ESP,esp+4+pop)
def hook(uc,at,size,c):
 if at==0x410fb0:ret(DEST)
 elif at==0x422b60:ret(pop=12)
 elif at in(0x41a3e0,0x41a5e0):ret()
u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_X86_REG_FPCW,0x37f);u.mem_write(SP,struct.pack('<I',0x4000));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(0x43cd5c,0x4000,count=1000);cases=0
for id,callback,frame in [(7,0x41b8b0,19),(8,0x41aa50,32),(12,0x40feb0,14)]:
 for facing in (0,1):
  for n in range(120):
   raw=bytearray(186);struct.pack_into('<3h',raw,0,id,n*32,n*4);raw[43]=facing;struct.pack_into('<h',raw,98,10);struct.pack_into('<hhh',raw,12,60,frame,3);struct.pack_into('<h',raw,18,3);u.mem_write(OBJ,bytes(raw));u.mem_write(DEST,bytes([0xa5])*100);u.mem_write(SP,struct.pack('<4I',0x4000,4,0,OBJ));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(callback,0x4000,count=10000);original=bytes(u.mem_read(DEST,100));x,y,vx,vy=struct.unpack_from('<4f',original,12);p=Shot();assert lib.world_enemy_shot_init(C.byref(p),id,OBJ,x,y,vx,vy);assert bytes(p)==original,(id,facing,n,[(i,a,b) for i,(a,b) in enumerate(zip(bytes(p),original)) if a!=b]);cases+=1
result={'owner_callbacks':['0x41b8b0','0x41aa50','0x40feb0'],'native_initializer':'0x40adc0','cases':cases,'bytes_compared':100,'limits':['Original allocator supplied a writable slot; playback/player queries substituted']};(ROOT/'research/enemies/world_shot_spawn_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
