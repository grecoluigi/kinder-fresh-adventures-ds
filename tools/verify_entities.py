#!/usr/bin/env python3
"""Compare pickup callback bytes/effects and animation stage with shipped x86."""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/entities';OUT.mkdir(exist_ok=True)
libpath=Path(tempfile.gettempdir())/'kinder_entities_verify.dylib'
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/entities.c'),'-o',str(libpath)],check=True)
lib=C.CDLL(str(libpath))
class Entity(C.Structure):_fields_=[('bytes',C.c_uint8*186)]
class Globals(C.Structure):_fields_=[(k,C.c_int32) for k in ('score','health','ammo','shoot_latch','pickup_sound')]+[('letters',C.c_uint16*6)]
Overlap=C.CFUNCTYPE(C.c_bool,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_void_p)
Popup=C.CFUNCTYPE(None,C.c_int,C.c_int,C.c_int,C.c_void_p)
class Env(C.Structure):_fields_=[(k,C.c_int16) for k in ('first','last','width','height')]+[('overlap',Overlap),('popup',Popup),('context',C.c_void_p)]
lib.entity_pickup_callback.argtypes=[C.POINTER(Entity),C.POINTER(Globals),C.POINTER(Env)];lib.entity_pickup_callback.restype=C.c_bool
lib.entity_advance_animation.argtypes=[C.POINTER(Entity),C.c_int16];lib.entity_advance_animation.restype=C.c_uint
callbacks={i:(0x40edb0 if i<=50 else [0x40eeb0,0x40efe0,0x40f110,0x40f220,0x40f330,0x40f440,0x40f550,0x40f660][i-51]) for i in range(48,59)}
pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'))
u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x200000,0x10000);u.mem_map(0x300000,0x10000);u.mem_map(0x4000,0x1000)
OBJ=0x300000;RESOURCE=0x301000;SP=0x208000
native_events=[];native_contact=False;dimensions=(40,40);interval=(0,5)
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def ret(value=0,pop=0):
 esp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,word(esp));u.reg_write(UC_X86_REG_ESP,esp+4+pop)
def hook(uc,at,size,context):
 esp=uc.reg_read(UC_X86_REG_ESP)
 if at==0x430b90:
  uc.mem_write(word(esp+12),bytes(22));ret(pop=12)
 elif at==0x431510:
  uc.mem_write(word(esp+8),struct.pack('<h',dimensions[0]));uc.mem_write(word(esp+12),struct.pack('<h',dimensions[1]));ret(pop=12)
 elif at==0x4446ea:
  uc.mem_write(RESOURCE+0x39,struct.pack('<hh',*interval));ret(RESOURCE,pop=4)
 elif at==0x41a3e0:
  args=struct.unpack('<5i',uc.mem_read(esp+4,20));native_events.append(('overlap',args));ret(int(native_contact))
 elif at==0x412e20:
  args=struct.unpack('<3i',uc.mem_read(esp+4,12));native_events.append(('popup',args));ret()
u.hook_add(UC_HOOK_CODE,hook)
map_globals={'score':0x45ed2c,'health':0x45f014,'ammo':0x45ed34,'shoot_latch':0x4e1044,'pickup_sound':0x4dac48}
assets=json.loads((ROOT/'generated/assets/inventory.json').read_text());scripts=json.load(open(ROOT/'generated/maps/scripts.json'));scripts={v['ObjNr']:v for v in scripts.values() if 'ObjNr' in v}
records={}
for item in json.load(open(ROOT/'generated/maps/inventory.json')):
 for obj in json.load(open(ROOT/'generated/maps'/item['file']/'00.json'))['objects']:
  if obj['obj_nr'] in callbacks:records.setdefault(obj['obj_nr'],bytes.fromhex(obj['raw_hex']))
rng=random.Random(512);tested=0
for id in callbacks:
 source='/'.join(p for p in scripts[id]['FileName'].replace('\\','/').split('/') if p).removeprefix('GData/').lower();asset=next(v for v in assets if v['source'].lower()==source);dimensions=(asset['frames'][0]['width'],asset['frames'][0]['height']);interval=(scripts[id].get('StartAnimLeft',0),scripts[id].get('EndAnimLeft',0))
 for state in (0,1,2,3,-1):
  for native_contact in (False,True):
   for timer in (0,1,1199,1200,-1):
    for sample in range(3):
     raw=bytearray(records[id]);struct.pack_into('<h',raw,98,state);struct.pack_into('<i',raw,116,timer)
     values=[rng.randint(-1000,1000),rng.choice([-40,0,59,60,80,100,120,0x7ffffff0]),rng.randint(0,100),rng.randint(-10,10),rng.randint(0,3)];letters=[rng.randint(0,1) for _ in range(6)]
     entity=Entity.from_buffer_copy(raw);g=Globals(*values,(C.c_uint16*6)(*letters));host_events=[]
     @Overlap
     def overlap(x,y,w,h,mode,context):host_events.append(('overlap',(x,y,w,h,mode)));return native_contact
     @Popup
     def popup(x,y,score,context):host_events.append(('popup',(x,y,score)))
     env=Env(*interval,*dimensions,overlap,popup,None)
     assert lib.entity_pickup_callback(C.byref(entity),C.byref(g),C.byref(env))
     u.mem_write(OBJ,bytes(raw));u.mem_write(SP,struct.pack('<4I',0x4000,4,0,OBJ));u.reg_write(UC_X86_REG_ESP,SP)
     for k,v in zip(map_globals,values):u.mem_write(map_globals[k],struct.pack('<i',v))
     u.mem_write(0x45efd4,struct.pack('<6H',*letters));native_events.clear();u.emu_start(callbacks[id],0x4000,count=10000)
     actual=bytes(u.mem_read(OBJ,186));assert bytes(entity)==actual,(id,state,timer,'record',[(i,a,b) for i,(a,b) in enumerate(zip(bytes(entity),actual)) if a!=b])
     for k in map_globals:assert getattr(g,k)==struct.unpack('<i',u.mem_read(map_globals[k],4))[0],(id,state,timer,k)
     assert list(g.letters)==list(struct.unpack('<6H',u.mem_read(0x45efd4,12)))
     assert host_events==native_events,(id,state,timer,host_events,native_events)
     tested+=1
# Execute only the independently recovered native animation stage, stopping before
# actual callbackdispatch; ESI suppliesrecord and EBP engine extradelay+1735.
animation_cases=0
for _ in range(1000):
 raw=bytearray(186);first=rng.randint(0,20);last=first+rng.randint(0,20)
 struct.pack_into('<hhhhh',raw,10,first,last,rng.randint(first-1,last+1),rng.randint(-1,4),rng.randint(-1,4));struct.pack_into('<h',raw,6,rng.choice([-1,0,1,2,255]));raw[22]=rng.choice([0,1,2,3]);extra=rng.randint(-1,2)
 entity=Entity.from_buffer_copy(raw);event=lib.entity_advance_animation(C.byref(entity),extra)
 u.mem_write(OBJ,bytes(raw));u.mem_write(0x303000+0x1735,struct.pack('<h',extra));u.reg_write(UC_X86_REG_ESI,OBJ);u.reg_write(UC_X86_REG_EBP,0x303000);u.reg_write(UC_X86_REG_ESP,SP);u.mem_write(SP+0x50,struct.pack('<I',4));u.emu_start(0x4337a1,0x43383f,count=1000)
 assert bytes(entity)==bytes(u.mem_read(OBJ,186)),('animation',raw.hex());assert event==word(SP+0x50)
 animation_cases+=1
result={'native_pickup_callback_cases':tested,'native_animation_stage_cases':animation_cases,'record_bytes_compared':186,'globals_compared':list(map_globals)+['letters[6]'],'event_arguments_compared':True,'callbacks':{str(k):hex(v) for k,v in callbacks.items()},'limitations':['Resource descriptor and frame-0 dimensions substituted with decoded original assets','41a3e0 contact outcome supplied; arguments verified, full player contact provider still needs wiring','Score popup renderer replaced by event capture','Native animation stage only; sound triggers and spatial update gating not fully integrated']}
(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
