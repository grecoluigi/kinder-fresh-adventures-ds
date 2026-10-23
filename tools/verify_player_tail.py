"""Execute original damage-tail instructions, mirror sync and no-op state branches.
Spatial/body/animation/projectile/camera routines have separate verifiers.
"""
from pathlib import Path
import sys,ctypes as C,json,struct,random,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'research/gameplay'))
from verify_player import Player,Env,Random,Particle,CONTROL
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x20000)
values=[];native_rng=port_rng=0;native_events=[];port_events=[]
def ret(value=0):
 sp=u.reg_read(UC_X86_REG_ESP);pc=struct.unpack('<I',u.mem_read(sp,4))[0];u.reg_write(UC_X86_REG_EAX,value&0xffffffff);u.reg_write(UC_X86_REG_ESP,sp+4);u.reg_write(UC_X86_REG_EIP,pc)
def hook(uc,address,size,ctx):
 global native_rng
 if address==0x4395b0:
  value=values[native_rng];native_rng+=1;ret(value)
 elif address==0x430470:
  sp=uc.reg_read(UC_X86_REG_ESP);native_events.append(struct.unpack('<iiff',u.mem_read(sp+4,16)));ret()
u.hook_add(UC_HOOK_CODE,hook)
@Random
def random_value(ctx):
 global port_rng
 value=values[port_rng];port_rng+=1;return value
@Particle
def particle(ctx,x,y,vx,vy):port_events.append((x,y,vx,vy))
with tempfile.TemporaryDirectory(prefix='kinder-player-tail-')as tmp:
 so=Path(tmp)/'tail.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/player.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.player_damage_effects_tick.argtypes=[C.POINTER(Player),C.POINTER(C.c_int32),C.POINTER(Env)];c.player_damage_effects_tick.restype=C.c_bool;c.player_sync_facing.argtypes=[C.POINTER(Player)]
 c.player_dispatch.argtypes=[C.POINTER(Player),C.POINTER(C.c_int32),C.POINTER(C.c_uint),C.POINTER(Env)];c.player_dispatch.restype=C.c_bool
 rng=random.Random(419e76);rng_calls=0;events=0
 for case in range(512):
  p=Player();body=(C.c_int32*33)();body[9]=rng.randrange(-2147483648,2147483648);body[10]=rng.randrange(-2147483648,2147483648)
  for i in range(3):p.controls[32+i]=rng.choice([0,1,5,20,-1,-2147483648,2147483647])
  values=[rng.randrange(32768)for _ in range(120)];native_rng=port_rng=0;native_events.clear();port_events.clear()
  u.mem_write(0x4e0f38,struct.pack('<I',0x210000));u.mem_write(0x210000,bytes(body))
  for i,a in enumerate((0x4e0fa0,0x4e0f98,0x4e0b40)):u.mem_write(a,struct.pack('<i',p.controls[32+i]))
  u.reg_write(UC_X86_REG_ESP,0x208000);u.reg_write(UC_X86_REG_EBX,0);u.emu_start(0x419e76,0x41a0ee,count=20000)
  env=Env();env.random=random_value;env.particle=particle
  assert c.player_damage_effects_tick(C.byref(p),body,C.byref(env))
  expected=[struct.unpack('<i',u.mem_read(a,4))[0]for a in (0x4e0fa0,0x4e0f98,0x4e0b40)]
  assert list(p.controls[32:35])==expected,(case,p.controls[32:35],expected)
  assert native_rng==port_rng and native_events==port_events,(case,native_rng,port_rng,native_events[:2],port_events[:2])
  rng_calls+=native_rng;events+=len(native_events)
 for facing in (0,1,-1,2147483647):
  p=Player();p.controls[2]=facing;u.mem_write(0x4e0f94,struct.pack('<i',facing));u.reg_write(UC_X86_REG_EBX,0);u.reg_write(UC_X86_REG_ESI,2);u.reg_write(UC_X86_REG_EAX,facing&0xffffffff)
  u.emu_start(0x419dc1,0x419de0,count=50);c.player_sync_facing(C.byref(p))
  assert p.penguin[20]==struct.unpack('<i',u.mem_read(0x4e0f80,4))[0]
  assert p.milk[20]==struct.unpack('<i',u.mem_read(0x4e0ff8,4))[0]
 states=(-1,26,27,-2,42,100,2147483647,-2147483648)
 for state in states:
  p=Player();p.controls[0]=state;before=bytes(p);body=(C.c_int32*33)();keys=C.c_uint(255);env=Env()
  u.mem_write(0x4e1028,struct.pack('<i',state));u.reg_write(UC_X86_REG_ESP,0x208000);u.emu_start(0x41782f,0x419d8f,count=100)
  assert c.player_dispatch(C.byref(p),body,C.byref(keys),C.byref(env)) and bytes(p)==before and keys.value==255
 result={'scope':__doc__,'damage_fixtures':512,'random_calls_compared':rng_calls,'particle_requests_compared':events,'mirror_cases':4,'native_no_op_states':list(states),'released_particle_opcode':pe.get_data(0x430470-0x400000,1).hex(),'limits':['Only retained tail branches are executed here; not a full level/combat or hardware performance check.','Particle requests are compared, but released430470 is RET and intentionally produces no drawn effect.']}
 assert result['released_particle_opcode']=='c3'
 (R/'research/gameplay/player-tail-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
