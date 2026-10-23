#!/usr/bin/env python3
"""Complete isolated valley callbacks:186bytes,globals,orderedcalls,100byteshots."""
import ctypes as C,json,random,struct,subprocess,tempfile
from pathlib import Path
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/boss_valley.c'),str(ROOT/'ds/source/entities.c'),'-o','/tmp/boss_valley_verify.dylib'],check=True)
l=C.CDLL('/tmp/boss_valley_verify.dylib')
class Entity(C.Structure):_fields_=[('bytes',C.c_uint8*186)]
class Shot(C.Structure):_fields_=[('bytes',C.c_uint8*100)]
class Globals(C.Structure):_fields_=[(n,C.c_int32) for n in ('score','boss_energy','completed')]
Service=C.CFUNCTYPE(C.c_int32,C.c_uint32,C.POINTER(C.c_int32),C.c_uint,C.c_void_p)
class Env(C.Structure):_fields_=[('ranges',(C.c_int16*2)*19),('player_x',C.c_int32),('player_y',C.c_int32)]+[(n,C.c_int16) for n in ('hit_sound','fall_sound','bear_idle_sound','bear_throw_sound','octopus_sound','octopus_throw_sound')]+[('owner_handle',C.c_uint32),('shot',C.POINTER(Shot)),('service',Service),('context',C.c_void_p)]
for name in ('boss_valley_bear_tick','boss_valley_octopus_tick'):getattr(l,name).argtypes=[C.POINTER(Entity),C.POINTER(Globals),C.POINTER(Env)];getattr(l,name).restype=C.c_bool
l.boss_valley_shot_tick.argtypes=[C.POINTER(Shot),C.POINTER(Env)]
pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x300000,0x10000);u.mem_map(0x200000,0x10000);u.mem_map(0x4000,0x1000)
OBJ=0x300000;RESOURCE=0x301000;SP=0x208000;SHOT=0x302000
u.reg_write(UC_X86_REG_FPCW,0x37f);u.mem_write(SP,struct.pack('<I',0x4000));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(0x43cd5c,0x4000,count=1000)
rng=random.Random(401518);native=[];host=[];random_initial=0;random_native=0;random_host=0;px=py=0;hit=busy=allocated=False;voice_result=0;solid=property_value=0;contact_result=obstacle_result=False
sounds=[123,456,234,345,567,678]
for at,val in zip((0x4dac42,0x4e0aa6,0x4dabcc,0x4dac6e,0x4dac6c,0x4e0afc),sounds):u.mem_write(at,struct.pack('<h',val))
map_globals=(0x45ed2c,0x45ed24,0x4dab18)
def word(at):return struct.unpack('<I',u.mem_read(at,4))[0]
def ret(value=0,pop=0):
 esp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,value&0xffffffff);u.reg_write(UC_X86_REG_EIP,word(esp));u.reg_write(UC_X86_REG_ESP,esp+4+pop)
def result(at):
 global random_native
 if at==0x4395b0:random_native=(random_native*214013+2531011)&0xffffffff;return (random_native>>16)&32767
 if at in (0x41a3e0,0x41a5e0):return int(hit) if at==0x41a5e0 else int(contact_result)
 if at==0x4231e5:return int(busy)
 if at==0x410fb0:return SHOT if allocated else 0
 if at==0x4243b1:return voice_result
 if at==0x434180:return solid
 if at==0x434200:return property_value
 if at==0x412bf0:return int(obstacle_result)
 return 0
counts={0x41a3e0:5,0x41a5e0:5,0x412e20:3,0x422b60:3,0x422e04:1,0x4231e5:1,0x42339e:2,0x4243b1:4,0x434180:3,0x434200:3,0x4395b0:0,0x410fb0:0,0x41a8c0:0,0x412bf0:2}
pops={0x422b60:12,0x4231e5:4,0x4243b1:16,0x434180:12,0x434200:12}
def hook(uc,at,size,context):
 esp=uc.reg_read(UC_X86_REG_ESP)
 if at==0x4446ea:ret(RESOURCE,pop=4)
 elif at==0x430b20:native.append((at,tuple(struct.unpack('<2i',uc.mem_read(esp+8,8)))))
 elif at==0x40adc0:native.append((at,tuple(struct.unpack('<3i',uc.mem_read(esp+8,12)))))
 elif at in counts:
  n=counts[at];args=tuple(struct.unpack('<'+'i'*n,uc.mem_read(esp+4,n*4))) if n else ()
  if at==0x422b60:args=(args[0],C.c_int16(args[1]).value,args[2])
  native.append((at,args))
  if at==0x41a8c0:uc.mem_write(word(esp+4),struct.pack('<i',px));uc.mem_write(word(esp+8),struct.pack('<i',py))
  ret(result(at),pops.get(at,0))
u.hook_add(UC_HOOK_CODE,hook)
@Service
def service(at,args,n,ctx):
 global random_host
 host.append((at,tuple(args[i] for i in range(n))))
 if at==0x4395b0:random_host=(random_host*214013+2531011)&0xffffffff;return(random_host>>16)&32767
 if at==0x410fb0:return int(allocated)
 return result(at)
scripts={s['ObjNr']:s for s in json.load(open(ROOT/'generated/maps/scripts.json')).values() if 'ObjNr'in s};records={}
for item in json.load(open(ROOT/'generated/maps/inventory.json')):
 for o in json.load(open(ROOT/'generated/maps'/item['file']/'00.json'))['objects']:
  if o['obj_nr']in(15,18):records.setdefault(o['obj_nr'],bytes.fromhex(o['raw_hex']))
keys=('Left','Right','Up','Do','LeftUp','LeftDo','RightUp','RightDo','IdleLeft','IdleRight','IdleUp','IdleDo','IdleLeftUp','IdleLeftDo','IdleRightUp','IdleRightDo','Attack','Freeze','KO');total=0
for id,entry,states,frames in [(15,0x40b1f0,(0,1,2,3,10,100,101,200,-1),(0,47,54,61,62,65,74,77)),(18,0x40cd70,(0,1,2,50,51,52,101,110,200,-1),(0,7,8,10,35,36,40,41,42,46,49))]:
 ranges=[(scripts[id].get('StartAnim'+k,0),scripts[id].get('EndAnim'+k,0)) for k in keys];u.mem_write(RESOURCE+0x39,b''.join(struct.pack('<hh',*a) for a in ranges));tested=0
 for state in states:
  for sample in range(256):
   raw=bytearray(records[id]);struct.pack_into('<h',raw,98,state);struct.pack_into('<hhh',raw,10,rng.choice([0,54,62]),rng.choice([10,35,41,49,61,74,77]),rng.choice(frames));struct.pack_into('<hh',raw,16,rng.choice([1,2,3]),rng.choice([0,1,2,3]));raw[22]=rng.choice([1,2]);raw[28]=sample%2;raw[42]=sample%3;raw[43]=sample%2;struct.pack_into('<h',raw,6,rng.choice([1,2,255]));
   for at in (116,120,124,140,144):struct.pack_into('<i',raw,at,rng.choice([0,1,2,120]))
   struct.pack_into('<4f',raw,148,100.125,200.375,rng.choice([-3.0,0,3.0]),rng.choice([-12.,0,19.75,20.]));struct.pack_into('<hh',raw,31,0,0);struct.pack_into('<hh',raw,35,300,300)
   px=entityx=struct.unpack_from('<h',raw,2)[0]+rng.choice([-500,-100,0,100,500]);py=struct.unpack_from('<h',raw,4)[0]+rng.choice([0,50,300,500]);hit=sample%5==0;busy=sample%3==0;allocated=sample%4!=0;voice_result=-1 if sample%3==0 else 7;random_initial=rng.getrandbits(32);random_native=random_host=random_initial
   e=Entity.from_buffer_copy(raw);shot=Shot();g=Globals(rng.choice([0,1234,0x7fffffff]),rng.choice([-1,0,1,9]),0);initial=[g.score,g.boss_energy,g.completed];env=Env(((C.c_int16*2)*19)(*((C.c_int16*2)(*a)for a in ranges)),px,py,*sounds,OBJ,C.pointer(shot),service,None)
   host.clear();native.clear();assert getattr(l,'boss_valley_bear_tick' if id==15 else'boss_valley_octopus_tick')(C.byref(e),C.byref(g),C.byref(env));u.mem_write(OBJ,bytes(raw));u.mem_write(SHOT,bytes(100));u.mem_write(SP,struct.pack('<4I',0x4000,4,0,OBJ));u.reg_write(UC_X86_REG_ESP,SP)
   for at,value in zip(map_globals,initial):u.mem_write(at,struct.pack('<i',value))
   u.emu_start(entry,0x4000,count=100000)
   actual=bytes(u.mem_read(OBJ,186));assert bytes(e)==actual,(id,state,sample,[(i,a,b)for i,(a,b)in enumerate(zip(bytes(e),actual))if a!=b]);assert list((g.score,g.boss_energy,g.completed))==[struct.unpack('<i',u.mem_read(at,4))[0]for at in map_globals],(id,state,sample,'globals');assert host==native,(id,state,sample,'events',host,native);assert bytes(shot)==bytes(u.mem_read(SHOT,100)),(id,state,sample,'shot',[(i,a,b)for i,(a,b)in enumerate(zip(bytes(shot),u.mem_read(SHOT,100)))if a!=b]);tested+=1
 print('Verified',id,tested,flush=True);total+=tested
shot_cases=0
for entry in (0x413b70,0x40cc60):
 for sample in range(1536):
  raw=bytearray(100);struct.pack_into('<6f',raw,12,rng.choice([-1.,0,100.125]),rng.choice([-1.,0,200.375]),rng.choice([-11.,11.]),rng.choice([-3.,0,19.9,20.]),rng.choice([0.07,0.2,0.3]),0);struct.pack_into('<I',raw,64,1);struct.pack_into('<i',raw,68,rng.choice([-1,0,1,2,120]));struct.pack_into('<I',raw,96,entry)
  solid=rng.choice([-1,0,1]);property_value=rng.choice([0,2,4]);contact_result=sample%3==0;obstacle_result=sample%5==0;shot=Shot.from_buffer_copy(raw);host.clear();native.clear();env=Env();env.service=service
  l.boss_valley_shot_tick(C.byref(shot),C.byref(env));u.mem_write(SHOT,bytes(raw));u.mem_write(SP,struct.pack('<2I',0x4000,SHOT));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(entry,0x4000,count=100000)
  actual=bytes(u.mem_read(SHOT,100));assert bytes(shot)==actual,(hex(entry),sample,'projectile',[(i,a,b)for i,(a,b)in enumerate(zip(bytes(shot),actual))if a!=b]);assert host==native,(hex(entry),sample,'projectileevents',host,native);shot_cases+=1
print('Verifiedprojectilehelpers',shot_cases,flush=True)
result={'callback_cases':total,'projectile_helper_cases':shot_cases,'entity_bytes':186,'shot_bytes':100,'globals':['score45ed2c','bossenergy45ed24','completed4dab18'],'ordered_native_services':True,'limits':['Isolated native callbacks with contact/shot outcomes and sound/allocator services supplied','World integration and full playthrough still require evidence','Resource lookup supplies originalAOMranges;430b20 and40adc0 execute native code']};(ROOT/'research/bosses/valley-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
