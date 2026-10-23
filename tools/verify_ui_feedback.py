"""Original menu/highscore hover gates, channel mapping, volume and PCM backend.
Original frame-sound trigger also executes on all4722 disabled map sound slots.
External audio calls are captured; this is not an audible DS or complete UI check.
"""
from pathlib import Path
import ctypes as C,json,struct,random,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EBX,UC_X86_REG_EBP,UC_X86_REG_EDI,UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EIP
R=Path(__file__).resolve().parents[1]
class State(C.Structure):_fields_=[('focus',C.c_int*2),('latched',C.c_uint8*2)]
CALL=C.CFUNCTYPE(None,C.c_uint,C.c_uint,C.c_uint,C.c_int,C.c_void_p)
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x60000);u.mem_map(0x2000,4096)
native=[];portable=[]
def ret(pop):
 sp=u.reg_read(UC_X86_REG_ESP);address=struct.unpack('<I',u.mem_read(sp,4))[0];u.reg_write(UC_X86_REG_ESP,sp+4+pop);u.reg_write(UC_X86_REG_EIP,address)
def hook(uc,address,size,ctx):
 if address==0x422b60:
  sp=uc.reg_read(UC_X86_REG_ESP);channel,handle,repeat=struct.unpack('<3I',u.mem_read(sp+4,12));assert handle==1
  native.append((channel,0x4553cc,repeat));ret(12)
u.hook_add(UC_HOOK_CODE,hook)
@CALL
def capture(channel,key,repeat,volume,context):portable.append((channel,key,repeat,volume))
# Entries follow actual UI focus order: jungle,valley,mountain,factory.
main=[(0x40473f,0x40476f,0x4da7d0,0x4da7d6,1),(0x4049f8,0x404a28,0x4da7bc,0x4da7c2,4),(0x404827,0x404858,0x4da7dc,0x4da7e2,2),(0x404910,0x404940,0x4da750,0x4da756,3)]
scores=[(0x403263,0x403293,0x4da680,0x4da686,1),(0x40348d,0x4034bd,0x4da6ec,0x4da6f2,4),(0x403320,0x403350,0x4da728,0x4da72e,2),(0x4033d6,0x403407,0x4da674,0x4da67a,3)]
with tempfile.TemporaryDirectory(prefix='kinder-ui-sounds-')as tmp:
 so=Path(tmp)/'feedback.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DSOUND_PACK="{R}/ds/nitrofs/sounds/samples.hw"',str(R/'ds/source/ui_feedback.c'),str(R/'ds/source/sound_events.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.ui_feedback_tick.argtypes=[C.POINTER(State),C.c_bool,C.c_int,C.c_int,CALL,C.c_void_p];c.ui_feedback_init.argtypes=[C.POINTER(State)];c.ui_feedback_attenuation.argtypes=[C.c_int];c.sound_play.restype=C.c_bool;c.sound_events_mix.argtypes=[C.POINTER(C.c_int16),C.c_uint,C.c_uint]
 db_values={}
 for pct in range(101):
  u.reg_write(UC_X86_REG_ESP,0x208000);u.reg_write(UC_X86_REG_EAX,pct);u.emu_start(0x4099f2,0x409a1d,count=100)
  db=struct.unpack('<i',u.mem_read(0x45f018,4))[0];assert c.ui_feedback_attenuation(pct)==db;db_values[pct]=db
 cases=0;rng=random.Random(40473)
 for surface,entries in enumerate((main,scores)):
  state=State();c.ui_feedback_init(C.byref(state));previous=-1
  for step in range(2048):
   focus=rng.randrange(-1,6);pct=rng.choice((0,1,25,75,100));portable.clear();native.clear()
   if focus!=previous:
    for _,_,_,latch,_ in entries:u.mem_write(latch,b'\0'*4)
   if 0<=focus<4:
    entry,end,handle,latch,channel=entries[focus];u.mem_write(handle,struct.pack('<HI',1,channel));u.mem_write(0x45efe4,struct.pack('<i',pct))
    u.reg_write(UC_X86_REG_ESP,0x208000);u.reg_write(UC_X86_REG_EBX,0);u.reg_write(UC_X86_REG_EBP,0 if surface else 1);u.reg_write(UC_X86_REG_EDI,1)
    u.emu_start(entry,end,count=500)
   c.ui_feedback_tick(C.byref(state),bool(surface),focus,pct,capture,None)
   assert [(a,b,d)for a,b,d,_ in portable]==native,(surface,step,focus,pct,portable,native)
   assert all(v==db_values[pct]for _,_,_,v in portable)
   previous=focus;cases+=1
 # Actual PCM path/gain for the recovered cue; ignore BGM by using zero input.
 manifest=json.loads((R/'research/audio/effects_manifest.json').read_text());a=next(v for v in manifest['assets']if v['va']==0x4553cc);raw=(R/'generated/audio-lossless/reference.pcm').read_bytes()[a['offset']:a['offset']+a['frames']*2]
 assert c.sound_play(4,0x4553cc,0);c.sound_channel_volume(4,-10);out=(C.c_int16*1024)();c.sound_events_mix(out,1024,127)
 expected=[int(v*10362/32768)for v in struct.unpack('<1024h',raw[:2048])];assert list(out)==expected
 c.sound_events_stop()
 # Native dispatcher must not try to play disabled serialized sound slots.
 u.mem_write(0x240000+0x185f,struct.pack('<h',1));u.mem_write(0x240000+0x610,struct.pack('<h',1));u.mem_write(0x240000+0x612,struct.pack('<I',0x210000));slots=0
 for item in json.loads((R/'generated/maps/inventory.json').read_text()):
  data=(R/'ds/nitrofs/scenes'/f"{item['file']}.entities").read_bytes();n=struct.unpack_from('<I',data,4)[0]
  for i in range(n):
   record=data[8+i*186:8+(i+1)*186];u.mem_write(0x210000,record)
   for slot in range(3):
    assert struct.unpack_from('<h',record,73+slot*2)[0]==-1
    native.clear();u.mem_write(0x208000,struct.pack('<5I',0x2000,0,slot,0xffffffff,0));u.reg_write(UC_X86_REG_ESP,0x208000);u.reg_write(UC_X86_REG_ECX,0x240000);u.emu_start(0x433ac0,0x2000,count=1000);assert not native;slots+=1
 result={'scope':__doc__,'native_hover_cases':cases,'native_volume_cases':101,'PCM_prefix_samples':1024,'disabled_original_map_sound_slots':slots,'cue_path':a['path'],'cue_key':'0x4553cc','limits':['DS direction/touch focus adapts original hover gates; no full Windows or DS UI playback captured.','Initial map sound slots are disabled; later runtime arming of an engine slot is outside this audit.','Original zero-percentage highscore retrigger condition is preserved; invalid persisted percentages safely clamp.']}
 (R/'research/audio/ui-feedback-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
