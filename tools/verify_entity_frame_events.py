"""Original frame-sound dispatch and animation-stage instructions.
Playback/channel bookkeeping is supplied, not a full 433ac0/audio proof.
"""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ESI,UC_X86_REG_EBP,UC_X86_REG_EBX,UC_X86_REG_EAX,UC_X86_REG_EIP
R=Path(__file__).resolve().parents[1]
class Entity(C.Structure):_fields_=[('raw',C.c_uint8*186)]
Active=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
Request=C.CFUNCTYPE(None,C.POINTER(Entity),C.c_uint,C.c_void_p)
class Environment(C.Structure):_fields_=[('enabled',C.c_bool),('owners',C.POINTER(C.c_int16)),('active',Active),('request',Request),('context',C.c_void_p)]
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));data=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(data)+4095)&~4095);u.mem_write(0x400000,data);u.mem_map(0x200000,0x50000)
OBJ=0x210000;ENGINE=0x230000;STACK=0x208000;native_calls=[];native_queries=[];active_bits=[];stage=0
def hook(uc,at,size,ctx):
 if at==(0x4337a1 if stage==0 else 0x43383f):uc.emu_stop();return
 if at not in (0x4231e5,0x433ac0):return
 sp=uc.reg_read(UC_X86_REG_ESP);pc=struct.unpack('<I',uc.mem_read(sp,4))[0]
 if at==0x4231e5:
  channel=struct.unpack('<I',uc.mem_read(sp+4,4))[0];native_queries.append(channel);value=int(active_bits[channel]);pop=4
 else:
  index,slot,sample,repeat=struct.unpack('<4I',uc.mem_read(sp+4,16));assert sample==0xffffffff and repeat==0
  native_calls.append(slot);value=0;pop=16
 uc.reg_write(UC_X86_REG_ESP,sp+4+pop);uc.reg_write(UC_X86_REG_EAX,value);uc.reg_write(UC_X86_REG_EIP,pc)
u.hook_add(UC_HOOK_CODE,hook)
rng=random.Random(433716);sound_cases=animation_cases=0
with tempfile.TemporaryDirectory(prefix='kinder-frame-events-')as tmp:
 so=Path(tmp)/'events.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/entities.c'),'-o',str(so)],check=True);c=C.CDLL(str(so));c.entity_frame_sound_step.argtypes=[C.POINTER(Entity),C.c_uint,C.POINTER(Environment)];c.entity_advance_animation.argtypes=[C.POINTER(Entity),C.c_int16];c.entity_advance_animation.restype=C.c_uint
 for case in range(8192):
  raw=bytearray(rng.randbytes(186));frame=rng.choice((-3,-2,-1,0,1,27,32767,-32768));timer=rng.choice((0,0,0,1,-1,32767,-32768));struct.pack_into('<h',raw,14,frame);struct.pack_into('<h',raw,18,timer)
  for slot in range(3):
   struct.pack_into('<h',raw,67+2*slot,rng.choice((frame,-1,-2,-3,8)));raw[79+slot]=rng.choice((0,1,255));raw[82+slot]=rng.randrange(256)
  index=rng.randrange(1000);enabled=case%7!=0;owners=(C.c_int16*256)(*[rng.choice((-1,index,index+1))for _ in range(256)]);active_bits=[bool(rng.randrange(2))for _ in range(256)]
  calls=[];queries=[]
  @Active
  def active(channel,ctx):queries.append(channel);return active_bits[channel]
  @Request
  def request(entity,slot,ctx):calls.append(slot)
  e=Entity.from_buffer_copy(raw);env=Environment(enabled,owners,active,request,None);c.entity_frame_sound_step(C.byref(e),index,C.byref(env))
  stage=0;native_calls=[];native_queries=[];u.mem_write(OBJ,bytes(raw));u.mem_write(ENGINE+0x185f,struct.pack('<h',int(enabled)))
  for channel in range(256):u.mem_write(ENGINE+0xd36+4*channel,struct.pack('<h',owners[channel]))
  u.mem_write(STACK,bytes(256));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ESI,OBJ);u.reg_write(UC_X86_REG_EBP,ENGINE);u.reg_write(UC_X86_REG_EBX,index);
  try:u.emu_start(0x4336f4,0x4337a1,count=1000)
  except Exception:print(case,hex(u.reg_read(UC_X86_REG_EIP)),hex(u.reg_read(UC_X86_REG_ESP)),native_calls,native_queries,flush=True);raise
  assert bytes(e)==bytes(u.mem_read(OBJ,186)) and calls==native_calls and queries==native_queries,(case,calls,native_calls,queries,native_queries);sound_cases+=1
  # Independently verify signed timing, repeat wrap and callback event flags.
  raw=bytearray(rng.randbytes(186));extra=rng.randrange(-32768,32768);e=Entity.from_buffer_copy(raw);event=c.entity_advance_animation(C.byref(e),extra)
  stage=1;u.mem_write(OBJ,bytes(raw));u.mem_write(ENGINE+0x1735,struct.pack('<h',extra));u.mem_write(STACK,bytes(256));u.mem_write(STACK+0x50,struct.pack('<I',4));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ESI,OBJ);u.reg_write(UC_X86_REG_EBP,ENGINE);u.emu_start(0x4337a1,0x43383f,count=1000)
  assert bytes(e)==bytes(u.mem_read(OBJ,186)) and event==struct.unpack('<I',u.mem_read(STACK+0x50,4))[0],(case,'animation');animation_cases+=1
 result={'scope':__doc__,'frame_sound_cases':sound_cases,'animation_cases':animation_cases,'all186_bytes_and_ordered_requests_match':True,'limits':['433ac0 playback/allocation/ownership side effects are supplied services, not reconstructed by this helper.','Helper is not wired to ROM sound playback; shipped initial slots are disabled, but runtime arming remains an audit gap.','No emulator, DS listening or complete playthrough evidence.']};(R/'research/gameplay/entity-frame-events-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
