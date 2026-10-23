"""Original persisted menu-music curve, three native menu loader volume calls,
and the actual main.c wrapper with production Option.ini loading. No audible DS proof.
"""
from pathlib import Path
import ctypes as C,json,math,re,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_EDI,UC_X86_REG_EIP
R=Path(__file__).resolve().parents[1];pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));data=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(data)+4095)&~4095);u.mem_write(0x400000,data);u.mem_map(0x200000,0x20000);calls=[]
def hook(uc,a,size,ctx):
 if a==0x42339e:
  sp=uc.reg_read(UC_X86_REG_ESP);calls.append(struct.unpack('<2i',uc.mem_read(sp+4,8)));pc=struct.unpack('<I',uc.mem_read(sp,4))[0];uc.reg_write(UC_X86_REG_ESP,sp+4);uc.reg_write(UC_X86_REG_EIP,pc)
u.hook_add(UC_HOOK_CODE,hook)
main=(R/'ds/source/main.c').read_text();wrapper=re.search(r'static void play_menu_music\(void\)\{.*?\n\}',main,re.S).group();assert main.count('play_menu_music();')==4 and main.count('audio_play_menu()')==1
with tempfile.TemporaryDirectory(prefix='kinder-menu-volume-')as tmp:
 t=Path(tmp);source=t/'wrapper.c';source.write_text('''
#include "audio.h"
#include "ui_feedback.h"
#include "game_save.h"
static unsigned volume=999,plays;static bool load_ok=true;
bool audio_play_menu(void){plays++;return load_ok;}
void audio_set_volume(unsigned v){volume=v;}
'''+wrapper+'''
unsigned test_play(void){volume=999;play_menu_music();return volume;}
void test_fail(void){load_ok=false;}
''')
 so=t/'volume.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),str(source),*[str(R/'ds/source'/f'{n}.c')for n in ('ui_feedback','game_save','persistence','persistence_store','save_archive')],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.ui_feedback_music_volume.restype=c.test_play.restype=C.c_uint;c.game_save_open_directory.argtypes=[C.c_char_p];c.game_save_open_directory.restype=C.c_bool
 c.game_save_init();assert c.test_play()==40
 native_calls=0
 defaults=[203,205,200,208,30,31,33,32,0,0,0,1,0,3,0,2,0,0,0,1,75,100]
 storage=t/'save';storage.mkdir()
 for pct in range(101):
  u.reg_write(UC_X86_REG_ESP,0x208000);u.reg_write(UC_X86_REG_EAX,pct);u.emu_start(0x4099bf,0x4099ed,count=100);db=struct.unpack('<i',u.mem_read(0x45ecf4,4))[0]
  assert db==c.ui_feedback_attenuation(pct)
  amplitude=math.floor(127*10**(db/20)+0.5);assert c.ui_feedback_music_volume(pct)==amplitude
  for entry,end in ((0x408e32,0x408e58),(0x41274f,0x412773),(0x4127b6,0x4127db)):
   calls.clear();u.reg_write(UC_X86_REG_ESP,0x208000);u.reg_write(UC_X86_REG_EAX,0);u.reg_write(UC_X86_REG_EBX,0);u.reg_write(UC_X86_REG_EDI,0);u.emu_start(entry,end,count=100);assert calls==[(16,db)],(pct,hex(entry),calls);native_calls+=1
  defaults[20]=pct;(storage/'Option.ini').write_bytes('\r\n'.join(map(str,defaults)).encode());assert c.game_save_open_directory(str(storage).encode());assert c.test_play()==amplitude
 for invalid,clamped in ((-2147483648,0),(-1,0),(101,100),(2147483647,100)):
  assert c.ui_feedback_music_volume(invalid)==c.ui_feedback_music_volume(clamped)
 c.test_fail();assert c.test_play()==999
 result={'scope':__doc__,'native_percentage_cases':101,'native_loader_volume_calls':native_calls,'production_persisted_option_wrapper_cases':101,'default_percentage':75,'default_native_db':-10,'default_DS_amplitude':40,'main_wrapper_call_sites':4,'failed_loader_keeps_volume_untouched':True,'limits':['Maxmod0..127 amplitude quantizes the native decibel curve; rounded amplitude checked independently.','Native normal-world/boss loader attenuation overrides remain unchanged. No option-slider UI or audible hardware proof.']}
 (R/'research/audio/menu-music-volume-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
