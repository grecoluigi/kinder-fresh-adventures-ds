#!/usr/bin/env python3
"""Execute original snake callback; compare all entity bytes and emitted calls."""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/enemies';OUT.mkdir(exist_ok=True)
path=Path(tempfile.gettempdir())/'kinder_enemies_verify.dylib'
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/enemies.c'),str(ROOT/'ds/source/entities.c'),'-o',str(path)],check=True)
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
lib.enemy_snake_callback.argtypes=[C.POINTER(Entity),C.POINTER(Globals),C.POINTER(Env)];lib.enemy_snake_callback.restype=C.c_bool
pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'))
u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x200000,0x10000);u.mem_map(0x300000,0x10000);u.mem_map(0x4000,0x1000)
OBJ=0x300000;RESOURCE=0x301000;SP=0x208000
# Shipped CRT initializer43cd5c selects53bit precision via43fe53.
u.reg_write(UC_X86_REG_FPCW,0x37f);u.mem_write(SP,struct.pack("<I",0x4000));u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(0x43cd5c,0x4000,count=1000);assert u.reg_read(UC_X86_REG_FPCW)==0x23f
native_events=[];shot=False
ranges=[(0,8)]*18;ranges[17]=(9,16)
u.mem_write(RESOURCE+0x39,b''.join(struct.pack('<hh',*v) for v in ranges))
u.mem_write(0x4dac42,struct.pack('<h',123));u.mem_write(0x4e0aa6,struct.pack('<h',456))
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def ret(value=0,pop=0):
 esp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,word(esp));u.reg_write(UC_X86_REG_ESP,esp+4+pop)
def hook(uc,at,size,context):
 esp=uc.reg_read(UC_X86_REG_ESP)
 if at==0x4446ea:ret(RESOURCE,pop=4)
 elif at in (0x41a3e0,0x41a5e0):
  native_events.append(('contact' if at==0x41a3e0 else 'shot',struct.unpack('<5i',uc.mem_read(esp+4,20))));ret(int(shot) if at==0x41a5e0 else 0)
 elif at==0x412e20:native_events.append(('popup',struct.unpack('<3i',uc.mem_read(esp+4,12))));ret()
 elif at==0x422b60:
  channel,sound,unused=struct.unpack('<3i',uc.mem_read(esp+4,12));native_events.append(('sound',(channel,C.c_int16(sound).value)));ret(pop=12)
u.hook_add(UC_HOOK_CODE,hook)
records=[bytes.fromhex(o['raw_hex']) for o in json.load(open(ROOT/'generated/maps/Welt1.W02/00.json'))['objects'] if o['obj_nr']==4]
rng=random.Random(415);cases=0
for state in (0,1,100,101,200,-1):
 for shot in (False,True):
  for mode in range(12):
   for sample in range(8):
    raw=bytearray(rng.choice(records));struct.pack_into('<h',raw,98,state);raw[28]=sample%2;raw[39]=mode;raw[41]=sample%3;raw[43]=sample%2;raw[44]=sample%2
    struct.pack_into('<hhh',raw,10,9,16,rng.choice([9,16]));struct.pack_into('<i',raw,116,rng.choice([0,1,120]));struct.pack_into('<4f',raw,148,100.0,200.0,-1.0,rng.choice([-12.0,19.75,20.0]));struct.pack_into('<h',raw,6,1)
    entity=Entity.from_buffer_copy(raw);g=Globals();g.score=1234;host=[]
    @Contact
    def contact(x,y,w,h,d,c):host.append(('contact',(x,y,w,h,d)));return False
    @Contact
    def projectile(x,y,w,h,d,c):host.append(('shot',(x,y,w,h,d)));return shot
    @Popup
    def popup(x,y,s,c):host.append(('popup',(x,y,s)))
    @Sound
    def sound(ch,s,c):host.append(('sound',(ch,s)))
    env=Env(((C.c_int16*2)*18)(*( (C.c_int16*2)(*v) for v in ranges)),contact,projectile,popup,sound,123,456,None)
    assert lib.enemy_snake_callback(C.byref(entity),C.byref(g),C.byref(env))
    u.mem_write(OBJ,bytes(raw));u.mem_write(0x45ed2c,struct.pack('<i',1234));u.mem_write(SP,struct.pack('<4I',0x4000,4,0,OBJ));u.reg_write(UC_X86_REG_ESP,SP);native_events.clear();u.emu_start(0x41b3e0,0x4000,count=10000)
    actual=bytes(u.mem_read(OBJ,186));assert bytes(entity)==actual,(state,mode,sample,[(i,a,b) for i,(a,b) in enumerate(zip(bytes(entity),actual)) if a!=b])
    assert g.score==struct.unpack('<i',u.mem_read(0x45ed2c,4))[0];assert host==native_events,(host,native_events)
    cases+=1
result={'snake_callback':'0x41b3e0','cases':cases,'entity_bytes_compared':186,'events_compared':['contact with damage','projectile contact','score popup','sounds'],'limitations':['Resource ranges substituted using original AOM asset descriptors','Player damage and projectile outcomes supplied; callback call arguments verified','Kong/parrot covered by separate verifiers; world integration still required']}
(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
