#!/usr/bin/env python3
"""Native kong-shot callback, pool allocator and draw placement evidence."""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/enemies';path=Path(tempfile.gettempdir())/'kinder_enemy_shots.dylib'
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/world_enemies.c'),str(ROOT/'ds/source/entities.c'),'-o',str(path)],check=True);lib=C.CDLL(str(path))
class Shot(C.Structure):_fields_=[('resource',C.c_uint32),('owner',C.c_uint32),('opaque08',C.c_uint32)]+[(k,C.c_float) for k in ('x','y','vx','vy')]+[('opaque1c',C.c_uint32),('opaque20',C.c_uint32)]+[(k,C.c_int32) for k in ('repeats','mode','frame','first','last','timer','delay','active','lifetime')]+[(k,C.c_uint32) for k in ('opaque48','opaque4c','opaque50','opaque54','opaque58','opaque5c','callback')]
Solid=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_int,C.c_int);Property=C.CFUNCTYPE(C.c_uint,C.c_void_p,C.c_int,C.c_int);Obstacle=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.c_int,C.c_int);Contact=C.CFUNCTYPE(C.c_bool,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_void_p)
class Env(C.Structure):_fields_=[('solid',Solid),('property',Property),('obstacle',Obstacle),('contact',Contact),('context',C.c_void_p)]
lib.world_enemy_shot_callback.argtypes=[C.POINTER(Shot),C.POINTER(Env)]
pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x200000,0x10000);u.mem_map(0x300000,0x10000);u.mem_map(0x4000,0x1000)
SP=0x208000;OBJ=0x300000;FRAME=0x301000;native=[]
def word(at):return struct.unpack('<I',u.mem_read(at,4))[0]
def ret(value=0,pop=0):
 esp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,word(esp));u.reg_write(UC_X86_REG_ESP,esp+4+pop)
u.reg_write(UC_X86_REG_FPCW,0x37f);u.mem_write(SP,struct.pack('<I',0x4000));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(0x43cd5c,0x4000,count=1000);assert u.reg_read(UC_X86_REG_FPCW)==0x23f
solid_value=0;property_value=0;contact_value=False;obstacle_value=False;full_obstacle=False
@Solid
def solid(c,x,y):host.append(('solid',(2,x,y)));return solid_value
@Property
def prop(c,x,y):host.append(('property',(2,x,y)));return property_value
@Contact
def contact(x,y,w,h,d,c):host.append(('contact',(x,y,w,h,d)));return contact_value
@Obstacle
def obstacle(c,x,y):host.append(('obstacle',(x,y)));return obstacle_value
env=Env(solid,prop,obstacle,contact,None)
def hook(uc,at,size,c):
 esp=uc.reg_read(UC_X86_REG_ESP)
 if at in (0x434180,0x434200):
  native.append(('solid' if at==0x434180 else 'property',struct.unpack('<3i',uc.mem_read(esp+4,12))));ret(solid_value if at==0x434180 else property_value,pop=12)
 elif at==0x41a3e0:native.append(('contact',struct.unpack('<5i',uc.mem_read(esp+4,20))));ret(contact_value)
 elif at==0x412bf0 and not full_obstacle:native.append(('obstacle',struct.unpack('<2i',uc.mem_read(esp+4,8))));ret(obstacle_value)
 elif at==0x430b90:
  descriptor=bytearray(22);struct.pack_into('<I',descriptor,12,FRAME);uc.mem_write(word(esp+12),bytes(descriptor));ret(pop=12)
 elif at==0x41d615:
  frame,x,y=struct.unpack('<3i',uc.mem_read(esp+4,12));native.append(('draw',(x,y,False)));ret(pop=12)
 elif at==0x41dbd4:
  frame,x,y,flags=struct.unpack('<4i',uc.mem_read(esp+4,16));assert flags==2;native.append(('draw',(x,y,True)));ret(pop=16)
u.hook_add(UC_HOOK_CODE,hook)
rng=random.Random(41370);cases=0
for i in range(18000):
 raw=bytearray(rng.randbytes(100));p=Shot.from_buffer_copy(raw);p.x=rng.choice([-1.,0.,17.25,0.00001,1000.,350.]);p.y=rng.choice([-1.,0.,97.75,1000.]);p.vx=rng.choice([-11.,11.]);p.vy=rng.choice([-3.,0.,.001,19.75,20.,21.]);p.lifetime=rng.choice([-1,0,1,2,120]);p.active=1;p.callback=[0x41b770,0x41a910,0x40fd70][i%3]
 solid_value=rng.choice([-1,0,1]);property_value=rng.randrange(128);contact_value=bool(rng.randrange(2));obstacle_value=bool(rng.randrange(2));native.clear();host=[];u.mem_write(OBJ,bytes(p));lib.world_enemy_shot_callback(C.byref(p),C.byref(env));u.mem_write(SP,struct.pack('<2I',0x4000,OBJ));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(p.callback,0x4000,count=2000)
 assert bytes(p)==bytes(u.mem_read(OBJ,100)),(i,[(n,a,b) for n,(a,b) in enumerate(zip(bytes(p),bytes(u.mem_read(OBJ,100)))) if a!=b]);assert host==native,(host,native);cases+=1
result={'callbacks':['0x41b770','0x41a910','0x40fd70'],'callback_cases':cases,'record_bytes_compared':100,'limits':['Tile/player/obstacle provider outcomes supplied; ordered query arguments checked','Pool update/draw integration handled separately']};(OUT/'world_shots_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
