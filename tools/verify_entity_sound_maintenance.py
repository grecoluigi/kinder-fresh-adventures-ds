"""Original433c60 spatial maintenance and433dd0 stop-all.
Frame metadata/spatial/audio services are supplied; ownership logic executes natively.
"""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX,UC_X86_REG_EIP
R=Path(__file__).resolve().parents[1]
class Entity(C.Structure):_fields_=[('raw',C.c_uint8*186)]
class Owner(C.Structure):_fields_=[('object',C.c_int16),('slot',C.c_int16)]
Size=C.CFUNCTYPE(C.c_bool,C.POINTER(Entity),C.POINTER(C.c_int16),C.POINTER(C.c_int16),C.c_void_p)
Spatial=C.CFUNCTYPE(None,C.c_int,C.c_int,C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.c_void_p)
Value=C.CFUNCTYPE(None,C.c_uint,C.c_int32,C.c_void_p)
Stop=C.CFUNCTYPE(None,C.c_uint,C.c_void_p)
class Environment(C.Structure):_fields_=[('enabled',C.c_bool),('owners',C.POINTER(Owner)),('size',Size),('spatial',Spatial),('pan',Value),('volume',Value),('stop',Stop),('context',C.c_void_p)]
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x60000);u.mem_map(0x2000,4096)
OBJ=0x210000;ENGINE=0x230000;CON=0x240000;STACK=0x208000;native=[];sizes=[];valid=[];last=0;attenuation=0;spatial_pan=0

def hook(uc,at,size,ctx):
 global last
 if at==0x2000:uc.emu_stop();return
 if at not in (0x430b90,0x431510,0x433e60,0x423307,0x42339e,0x422e04):return
 sp=uc.reg_read(UC_X86_REG_ESP);pc=struct.unpack('<I',uc.mem_read(sp,4))[0];value=0
 if at==0x430b90:
  entity,frame,out=struct.unpack('<3I',uc.mem_read(sp+4,12));last=(entity-OBJ)//186;frame=C.c_int32(frame).value;native.append(('size',last,frame));uc.mem_write(out,struct.pack('<h',2 if valid[last]else 0)+bytes(22));pop=12
 elif at==0x431510:
  _,wp,hp=struct.unpack('<3I',uc.mem_read(sp+4,12));uc.mem_write(wp,struct.pack('<h',sizes[last][0]));uc.mem_write(hp,struct.pack('<h',sizes[last][1]));pop=12
 elif at==0x433e60:
  x,y,ap,pp=struct.unpack('<iiII',uc.mem_read(sp+4,16));native.append(('spatial',x,y));uc.mem_write(ap,struct.pack('<i',attenuation));uc.mem_write(pp,struct.pack('<i',spatial_pan));pop=16
 elif at==0x422e04:
  channel=struct.unpack('<I',uc.mem_read(sp+4,4))[0];native.append(('stop',channel));pop=0
 else:
  channel,val=struct.unpack('<Ii',uc.mem_read(sp+4,8));native.append(('pan'if at==0x423307 else'volume',channel,val));pop=0
 uc.reg_write(UC_X86_REG_ESP,sp+4+pop);uc.reg_write(UC_X86_REG_EAX,value);uc.reg_write(UC_X86_REG_EIP,pc)
u.hook_add(UC_HOOK_CODE,hook);rng=random.Random(433060);checks=[0,0]
with tempfile.TemporaryDirectory(prefix='kinder-sound-maintenance-')as tmp:
 so=Path(tmp)/'maintenance.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/entities.c'),'-o',str(so)],check=True);c=C.CDLL(str(so))
 for name in ('entity_sound_maintain','entity_sound_stop_all'):getattr(c,name).argtypes=[C.POINTER(Entity),C.c_size_t,C.c_int,C.c_int,C.POINTER(Environment)]
 for case in range(4096):
  count=8;raw=bytearray(rng.randbytes(count*186));enabled=case%7!=0;first=rng.randrange(240);channels=rng.randrange(-2,12);attenuation=rng.choice((-100,-99,-44,-43,-1,0));spatial_pan=rng.randrange(-10,11);sizes=[(rng.randrange(-800,801),rng.randrange(-600,601))for _ in range(count)];valid=[bool(rng.randrange(2))for _ in range(count)]
  for i in range(count):
   for slot in range(3):raw[i*186+91+slot]=rng.choice((0,1,255))
  initial_owners=(Owner*256)(*[Owner(rng.choice((-1,0,3,7)),rng.randrange(3))for _ in range(256)]);owner_before=bytes(initial_owners)
  for stop_all in (False,True):
   e=(Entity*count).from_buffer_copy(raw);owners=(Owner*256).from_buffer_copy(owner_before);portable=[];base=C.addressof(e)
   @Size
   def size(entity,w,h,ctx):
    index=(C.addressof(entity.contents)-base)//186;frame=struct.unpack_from('<h',bytes(entity.contents),10)[0];portable.append(('size',index,frame));w[0]=sizes[index][0];h[0]=sizes[index][1];return valid[index]
   @Spatial
   def spatial(x,y,a,p,ctx):portable.append(('spatial',x,y));a[0]=attenuation;p[0]=spatial_pan
   @Value
   def pan(channel,value,ctx):portable.append(('pan',channel,value))
   @Value
   def volume(channel,value,ctx):portable.append(('volume',channel,value))
   @Stop
   def stop(channel,ctx):portable.append(('stop',channel))
   env=Environment(enabled,owners,size,spatial,pan,volume,stop,None);getattr(c,'entity_sound_stop_all'if stop_all else'entity_sound_maintain')(e,count,first,channels,C.byref(env))
   u.mem_write(OBJ,bytes(raw));u.mem_write(CON+2,struct.pack('<I',OBJ));u.mem_write(ENGINE+0x14d1,struct.pack('<I',CON));u.mem_write(ENGINE+0x185f,struct.pack('<h',enabled));u.mem_write(ENGINE+0xd32,struct.pack('<hh',first,channels));u.mem_write(ENGINE+0xd36,owner_before);u.mem_write(STACK,struct.pack('<I',0x2000));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ECX,ENGINE);native=[];u.emu_start(0x433dd0 if stop_all else 0x433c60,0x2000,count=10000)
   assert bytes(e)==bytes(u.mem_read(OBJ,count*186)),(case,stop_all,'records',portable,native)
   assert bytes(owners)==bytes(u.mem_read(ENGINE+0xd36,1024)),(case,stop_all,'owners',portable,native)
   assert portable==native,(case,stop_all,'order',portable,native);checks[int(stop_all)]+=1
 result={'scope':__doc__,'native_maintenance_cases':checks[0],'native_stop_all_cases':checks[1],'all_records_owners_ordered_calls_match':True,'limits':['Frame-info/dimensions and spatial/backend services supplied. Their separate native checks do not constitute a full engine replay.','Corrupt owners/channel ranges safely skipped in C instead of reproducing native memory faults.','No DS mixer binding, listening or full gameplay proof.']};(R/'research/gameplay/entity-sound-maintenance-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
