"""Native412e20/412dd0 constructor and motion, with allocator/initializer boundaries.
General animation initializer and pool/render routines have separate checks.
"""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile,random
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX
R=Path(__file__).resolve().parents[1];pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));data=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(data)+4095)&~4095);u.mem_write(0x400000,data);u.mem_map(0x200000,0x20000)
SLOT=0x210000;STACK=0x208000;STOP=0x200000;available=True
class Record(C.Structure):_fields_=[('raw',C.c_ubyte*100)]
def ret(v=0):
 sp=u.reg_read(UC_X86_REG_ESP);pc=struct.unpack('<I',u.mem_read(sp,4))[0];u.reg_write(UC_X86_REG_EAX,v);u.reg_write(UC_X86_REG_ESP,sp+4);u.reg_write(UC_X86_REG_EIP,pc)
def hook(uc,a,size,ctx):
 if a==0x410fb0:ret(SLOT if available else 0)
 elif a==0x40adc0:
  sp=u.reg_read(UC_X86_REG_ESP);slot,resource,x,y=struct.unpack('<IIff',u.mem_read(sp+4,16));assert slot==SLOT and resource==0
  raw=bytearray(100);struct.pack_into('<2f',raw,12,x,y);struct.pack_into('<ii',raw,36,-1,1);struct.pack_into('<ii',raw,56,2,2);u.mem_write(slot,bytes(raw));ret();u.reg_write(UC_X86_REG_ESP,u.reg_read(UC_X86_REG_ESP)+16)
u.hook_add(UC_HOOK_CODE,hook);u.mem_write(0x4e0b00,struct.pack('<I',1))
def call(at,args):
 u.mem_write(STACK,struct.pack('<I',STOP)+args);u.reg_write(UC_X86_REG_ESP,STACK);u.emu_start(at,STOP,count=1000)
with tempfile.TemporaryDirectory(prefix='kinder-score-popups-')as tmp:
 so=Path(tmp)/'popup.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/enemy_shots.c'),str(R/'ds/source/animation.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.enemy_shots_slots.restype=C.POINTER(Record);c.enemy_score_popup_tick.argtypes=[C.POINTER(Record)];c.enemy_shots_spawn_record.argtypes=[C.POINTER(Record)];c.enemy_shots_spawn_record.restype=C.c_bool
 rng=random.Random(412e20);ticks=0;constructors=0
 for score in (100,1000,10000,0,50,101,-1,2147483647):
  for case in range(64):
   x,y=rng.randrange(-20000,20000),rng.randrange(-20000,20000);available=True
   c.enemy_shots_init();u.mem_write(SLOT,bytes(100));call(0x412e20,struct.pack('<iii',x,y,score));c.enemy_score_popup(x,y,score,None)
   assert bytes(c.enemy_shots_slots()[0])==bytes(u.mem_read(SLOT,100)),(score,case,[(i,a,b)for i,(a,b)in enumerate(zip(bytes(c.enemy_shots_slots()[0]),bytes(u.mem_read(SLOT,100))))if a!=b]);constructors+=1
   if score not in (100,1000,10000):continue
   for tick in range(20):
    call(0x412dd0,struct.pack('<I',SLOT));c.enemy_score_popup_tick(c.enemy_shots_slots())
    assert bytes(c.enemy_shots_slots()[0])==bytes(u.mem_read(SLOT,100)),(score,case,tick);ticks+=1
 full=bytearray(100);struct.pack_into('<i',full,64,1);record=Record.from_buffer_copy(full);c.enemy_shots_init()
 for _ in range(200):assert c.enemy_shots_spawn_record(C.byref(record))
 before=C.string_at(c.enemy_shots_slots(),20000);c.enemy_score_popup(1,2,100,None);assert C.string_at(c.enemy_shots_slots(),20000)==before
 available=False;u.mem_write(SLOT,bytes(100));call(0x412e20,struct.pack('<iii',1,2,100));assert bytes(u.mem_read(SLOT,100))==bytes(100)
 result={'scope':__doc__,'constructors':constructors,'native_motion_ticks':ticks,'shared_pool_full_no_spawn':True,'lifetime_ticks':20,'gravity':1,'initial_vy':-12,'limits':['Allocator and zero-resource initializer are supplied boundaries; this is not a full combat/playthrough or hardware FPS proof.']}
 (R/'research/gameplay/score-popup-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
