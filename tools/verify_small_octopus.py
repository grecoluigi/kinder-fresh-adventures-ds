#!/usr/bin/env python3
"""Execute original small_octopus callback; compare all entity bytes and emitted calls."""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/enemies';OUT.mkdir(exist_ok=True)
path=Path(tempfile.gettempdir())/'kinder_small_octopus_verify.dylib'
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/world_enemies.c'),str(ROOT/'ds/source/entities.c'),'-o',str(path)],check=True)
lib=C.CDLL(str(path))
class Entity(C.Structure):_fields_=[('bytes',C.c_uint8*186)]
class Globals(C.Structure):_fields_=[(k,C.c_int32) for k in ('score','health','ammo','shoot_latch','pickup_sound')]+[('letters',C.c_uint16*6)]
Contact=C.CFUNCTYPE(C.c_bool,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_void_p)
Popup=C.CFUNCTYPE(None,C.c_int,C.c_int,C.c_int,C.c_void_p)
Sound=C.CFUNCTYPE(None,C.c_int,C.c_int,C.c_void_p)
Random=C.CFUNCTYPE(C.c_int,C.c_void_p)
Allocate=C.CFUNCTYPE(C.c_bool,C.c_void_p)
Spawn=C.CFUNCTYPE(None,C.POINTER(Entity),C.c_float,C.c_float,C.c_float,C.c_float,C.c_void_p)
class Env(C.Structure):_fields_=[('ranges',(C.c_int16*2)*18),('contact',Contact),('projectile',Contact),('popup',Popup),('sound',Sound),('hit_sound',C.c_int16),('fall_sound',C.c_int16),('context',C.c_void_p),('player_x',C.c_int32),('player_y',C.c_int32),('random',Random),('allocate',Allocate),('spawn',Spawn),('throw_sound',C.c_int16)]
lib.enemy_small_octopus_callback.argtypes=[C.POINTER(Entity),C.POINTER(Globals),C.POINTER(Env)];lib.enemy_small_octopus_callback.restype=C.c_bool
pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'))
u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x200000,0x10000);u.mem_map(0x300000,0x10000);u.mem_map(0x4000,0x1000)
OBJ=0x300000;RESOURCE=0x301000;SP=0x208000
# Shipped CRT initializer43cd5c selects53bit precision via43fe53.
u.reg_write(UC_X86_REG_FPCW,0x37f);u.mem_write(SP,struct.pack("<I",0x4000));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(0x43cd5c,0x4000,count=1000);assert u.reg_read(UC_X86_REG_FPCW)==0x23f
native_events=[];shot=False
ranges=[(0,35)]*18;ranges[16]=(9,35);ranges[17]=(36,43)
u.mem_write(RESOURCE+0x39,b''.join(struct.pack('<hh',*v) for v in ranges))
u.mem_write(0x4dac42,struct.pack('<h',123));u.mem_write(0x4e0aa6,struct.pack('<h',456))
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def ret(value=0,pop=0):
 esp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,word(esp));u.reg_write(UC_X86_REG_ESP,esp+4+pop)
def hook(uc,at,size,context):
 esp=uc.reg_read(UC_X86_REG_ESP)

 if at==0x4446ea:ret(RESOURCE,pop=4)
 elif at in (0x41a3e0,0x41a5e0):
  native_events.append(('contact' if at==0x41a3e0 else 'shot',struct.unpack('<5i',uc.mem_read(esp+4,20))));ret(int(shot and (sample%2==0 or sum(t[0]=='shot' for t in native_events)>1)) if at==0x41a5e0 else 0)
 elif at==0x412e20:native_events.append(('popup',struct.unpack('<3i',uc.mem_read(esp+4,12))));ret()
 elif at==0x41a8c0:
  uc.mem_write(word(esp+4),struct.pack('<i',px));uc.mem_write(word(esp+8),struct.pack('<i',py));ret()
 elif at==0x4395b0:native_events.append(('random',()));ret(random_sample)
 elif at==0x410fb0:native_events.append(('allocate',()));ret(0x302000 if available else 0)
 elif at==0x40adc0:
  # Capture initializer inputs; generic animation initializer verified separately.
  assert word(esp+4)==0x302000
  initial_x,initial_y=struct.unpack('<ff',uc.mem_read(esp+12,8));uc.mem_write(0x302000+12,struct.pack('<ff',initial_x,initial_y));ret(pop=16)
 elif at==0x4141f5 and available and ('allocate',()) in native_events:
  ax,ay,vx,vy=struct.unpack('<4f',uc.mem_read(0x302000+12,16));native_events.append(('spawn',(ax,ay,vx,vy)))
 elif at==0x422b60:
  channel,sound,unused=struct.unpack('<3i',uc.mem_read(esp+4,12));native_events.append(('sound',(channel,C.c_int16(sound).value)));ret(pop=12)
u.hook_add(UC_HOOK_CODE,hook)

records=[bytes.fromhex(o['raw_hex']) for o in json.load(open(ROOT/'generated/maps/Welt4.W02/00.json'))['objects'] if o['obj_nr']==17]
rng=random.Random(513);cases=0;observed={}
for state in (0,1,100,101,200,-1):
 for shot in (False,True):
  for sample in range(320):
   raw=bytearray(rng.choice(records));struct.pack_into('<h',raw,98,state);raw[28]=sample%2;raw[43]=sample%2;raw[42]=sample%3
   struct.pack_into('<hhh',raw,10,3,30 if state==10 else 39,rng.randrange(8));struct.pack_into('<hh',raw,16,3,rng.choice([0,1,3]));struct.pack_into('<ii',raw,116,rng.choice([0,1,120]),rng.choice([0,1,120]));struct.pack_into('<4f',raw,148,float(struct.unpack_from('<h',raw,2)[0]),float(struct.unpack_from('<h',raw,4)[0]),rng.choice([-3.,0.,3.]),rng.choice([-12.,0.,19.75,20.]));struct.pack_into('<h',raw,6,rng.choice([1,2,255]))
   entity=Entity.from_buffer_copy(raw);g=Globals();g.score=1234;host=[];random_sample=rng.randrange(32768);available=sample%3!=0
   x,y=struct.unpack_from('<hh',raw,2);px=x+rng.choice([-500,50,600]);py=y+rng.choice([0,100,350,500])
   @Contact
   def contact(x,y,w,h,d,c):host.append(('contact',(x,y,w,h,d)));return False
   @Contact
   def projectile(x,y,w,h,d,c):host.append(('shot',(x,y,w,h,d)));return shot and (sample%2==0 or sum(t[0]=='shot' for t in host)>1)
   @Popup
   def popup(x,y,s,c):host.append(('popup',(x,y,s)))
   @Sound
   def sound(ch,s,c):host.append(('sound',(ch,s)))
   @Random
   def random_call(c):host.append(('random',()));return random_sample
   @Allocate
   def allocate(c):host.append(('allocate',()));return available
   @Spawn
   def spawn(owner,x,y,vx,vy,c):host.append(('spawn',(x,y,vx,vy)))
   env=Env(((C.c_int16*2)*18)(*((C.c_int16*2)(*v) for v in ranges)),contact,projectile,popup,sound,123,456,None,px,py,random_call,allocate,spawn,789)
   assert lib.enemy_small_octopus_callback(C.byref(entity),C.byref(g),C.byref(env))
   u.mem_write(OBJ,bytes(raw));u.mem_write(0x302000,bytes(100));u.mem_write(0x45ed2c,struct.pack('<i',1234));u.mem_write(0x4e0a90,struct.pack('<h',789));u.mem_write(SP,struct.pack('<4I',0x4000,4,0,OBJ));u.reg_write(UC_X86_REG_ESP,SP);native_events.clear();u.emu_start(0x412f70,0x4000,count=10000)
   # Native initializer and field overwrites complete after sound; collect spawn.
   if available and ('allocate',()) in native_events:
    ax,ay,vx,vy=struct.unpack('<4f',u.mem_read(0x302000+12,16))
    assert word(0x302000+0x40)==1 and word(0x302000+0x44)==120 and word(0x302000+0x60)==0x413b70
    assert all(word(0x302000+o)==16 for o in (0x2c,0x30,0x34)) and word(0x302000+4)==OBJ
   actual=bytes(u.mem_read(OBJ,186));assert bytes(entity)==actual,(state,sample,[(i,a,b) for i,(a,b) in enumerate(zip(bytes(entity),actual)) if a!=b])
   assert g.score==struct.unpack('<i',u.mem_read(0x45ed2c,4))[0];assert host==native_events,(state,sample,host,native_events)
   cases+=1
   for name,args in host:observed[name]=observed.get(name,0)+1
result={'small_octopus_callback':'0x412f70','cases':cases,'entity_bytes_compared':186,'observed_events':observed,'events_compared':['player contact','projectile contact','score popup','sounds'],'limitations':['Resource ranges and player position substituted from caller','Damage/projectile providers supplied outcomes','No projectile allocation occurs in this callback']}
(OUT/'small_octopus_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
