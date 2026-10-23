"""Execute original433ac0 validation, repeat, spatial dispatch and ownership.
Spatial projection/channel allocation/audio backend are supplied service boundaries.
"""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX,UC_X86_REG_EIP
R=Path(__file__).resolve().parents[1]
class Entity(C.Structure):_fields_=[('raw',C.c_uint8*186)]
class Owner(C.Structure):_fields_=[('object',C.c_int16),('slot',C.c_int16)]
Allocate=C.CFUNCTYPE(C.c_uint,C.c_void_p)
Spatial=C.CFUNCTYPE(None,C.c_int,C.c_int,C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.c_void_p)
Value=C.CFUNCTYPE(None,C.c_uint,C.c_int32,C.c_void_p)
Play=C.CFUNCTYPE(None,C.c_uint,C.c_int16,C.c_uint32,C.c_void_p)
class Environment(C.Structure):_fields_=[('enabled',C.c_bool),('handles',C.POINTER(C.c_int16)),('sample_count',C.c_size_t),('owners',C.POINTER(Owner)),('allocate',Allocate),('spatial',Spatial),('pan',Value),('volume',Value),('play',Play),('context',C.c_void_p)]
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x60000);u.mem_map(0x2000,4096)
OBJ=0x210000;ENGINE=0x230000;STACK=0x208000;native=[];allocated=0;spatial_pan=0;attenuation=0;allocator_stage=False;active_values=[]

def hook(uc,at,size,ctx):
 if at==0x2000:uc.emu_stop();return
 if allocator_stage and at==0x431450:return
 if at not in (0x431450,0x433e60,0x423307,0x42339e,0x422b60,0x4231e5):return
 sp=uc.reg_read(UC_X86_REG_ESP);pc=struct.unpack('<I',uc.mem_read(sp,4))[0];value=0
 if at==0x4231e5:
  channel=struct.unpack('<I',uc.mem_read(sp+4,4))[0];native.append(('active',channel));value=int(active_values[channel%256]);pop=4
 elif at==0x431450:native.append(('allocate',));value=allocated;pop=0
 elif at==0x433e60:
  x,y,ap,pp=struct.unpack('<iiII',uc.mem_read(sp+4,16));native.append(('spatial',x,y));uc.mem_write(ap,struct.pack('<i',attenuation));uc.mem_write(pp,struct.pack('<i',spatial_pan));pop=16
 elif at in (0x423307,0x42339e):
  channel,val=struct.unpack('<Ii',uc.mem_read(sp+4,8));native.append(('pan'if at==0x423307 else'volume',channel,val));pop=0
 else:
  channel,sample,repeat=struct.unpack('<3I',uc.mem_read(sp+4,12));sample=C.c_int16(sample&65535).value;native.append(('play',channel,sample,repeat));pop=12
 uc.reg_write(UC_X86_REG_ESP,sp+4+pop);uc.reg_write(UC_X86_REG_EAX,value);uc.reg_write(UC_X86_REG_EIP,pc)
u.hook_add(UC_HOOK_CODE,hook)
rng=random.Random(433000)
cases=0
with tempfile.TemporaryDirectory(prefix='kinder-sound-owner-')as tmp:
 so=Path(tmp)/'sound.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/entities.c'),'-o',str(so)],check=True);c=C.CDLL(str(so));c.entity_sound_playback.argtypes=[C.POINTER(Entity),C.c_size_t,C.c_int,C.c_int,C.c_uint32,C.POINTER(Environment)]
 for case in range(4096):
  count=8;raw=bytearray(rng.randbytes(count*186));index=rng.choice((-1,0,1,3,7,8));slot=rng.choice((-1,0,1,2,3));enabled=case%9!=0;repeat=rng.choice((0,0,1,2,255,0xffffffff));allocated=rng.randrange(256);attenuation=rng.randrange(-100,1);spatial_pan=rng.randrange(-10,11)
  for i in range(count):
   for k in range(3):
    struct.pack_into('<h',raw,i*186+73+k*2,rng.choice((-1,0,1,17,31)));struct.pack_into('<h',raw,i*186+61+k*2,rng.choice((-1,0,1,2,-2)));raw[i*186+91+k]=rng.choice((0,1,255))
  handles=(C.c_int16*32)(*[rng.choice((-1,0,1,7,93))for _ in range(32)]);owners=(Owner*256)(*[Owner(rng.choice((-1,0,3,7)),rng.randrange(3))for _ in range(256)]);owner_before=bytes(owners);e=(Entity*count).from_buffer_copy(raw);portable=[]
  @Allocate
  def allocate(ctx):portable.append(('allocate',));return allocated
  @Spatial
  def spatial(x,y,a,p,ctx):portable.append(('spatial',x,y));a[0]=attenuation;p[0]=spatial_pan
  @Value
  def pan(channel,value,ctx):portable.append(('pan',channel,value))
  @Value
  def volume(channel,value,ctx):portable.append(('volume',channel,value))
  @Play
  def play(channel,sample,repeats,ctx):portable.append(('play',channel,sample,repeats))
  env=Environment(enabled,handles,32,owners,allocate,spatial,pan,volume,play,None);c.entity_sound_playback(e,count,index,slot,repeat,C.byref(env))
  u.mem_write(OBJ,bytes(raw));u.mem_write(ENGINE+0x185f,struct.pack('<h',enabled));u.mem_write(ENGINE+0x610,struct.pack('<h',count));u.mem_write(ENGINE+0x612,struct.pack('<I',OBJ));u.mem_write(ENGINE+0xd36,owner_before)
  for i in range(32):u.mem_write(ENGINE+0xa06+i*4,struct.pack('<h',handles[i]))
  native=[];u.mem_write(STACK,struct.pack('<IiiII',0x2000,index,slot,0xffffffff,repeat));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ECX,ENGINE);u.emu_start(0x433ac0,0x2000,count=10000)
  assert bytes(e)==bytes(u.mem_read(OBJ,count*186)),(case,'records',portable,native)
  assert bytes(owners)==bytes(u.mem_read(ENGINE+0xd36,1024)),(case,'owners')
  assert portable==native,(case,portable,native);cases+=1
 # Run allocator instructions instead of supplying its service boundary.
 allocator_stage=True;Active=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
 c.entity_sound_allocate.argtypes=[C.POINTER(C.c_int16),C.c_int16,C.c_int16,Active,C.c_void_p];c.entity_sound_allocate.restype=C.c_uint
 allocation_cases=0
 for case in range(4096):
  first=rng.randrange(-20,220);count=rng.randrange(-2,30);current=rng.choice((first,first+count-1,-32768,32767,rng.randrange(-32768,32768)));active_values=[bool(rng.randrange(2))if case%3 else True for _ in range(256)];portable=[]
  @Active
  def active(channel,ctx):portable.append(('active',channel));return active_values[channel%256]
  actual=C.c_int16(current);result=c.entity_sound_allocate(C.byref(actual),first,count,active,None)
  u.mem_write(ENGINE+0x604+0x72c,struct.pack('<hhh',current,first,count));u.mem_write(STACK,struct.pack('<I',0x2000));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ECX,ENGINE+0x604);native=[];u.emu_start(0x431450,0x2000,count=10000)
  expected=struct.unpack('<h',u.mem_read(ENGINE+0x604+0x72c,2))[0]
  assert actual.value==expected and result==u.reg_read(UC_X86_REG_EAX) and portable==native,(case,'allocator',first,count,current,actual.value,expected,portable,native);allocation_cases+=1
 result={'scope':__doc__,'native_cases':cases,'allocator_native_cases':allocation_cases,'all_object_bytes_and_owner_table_match':True,'ordered_service_calls_match':True,'limits':['Spatial function and allocator/audio backend are supplied services. Native ownership and validation execute fully.','Negative/out-of-range sample indices and corrupt owner indices are safely rejected in C; native unsafe memory access is not reproduced.','Not yet wired to DS audio; no emulator/listening/full-gameplay proof.']};(R/'research/gameplay/entity-sound-playback-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
