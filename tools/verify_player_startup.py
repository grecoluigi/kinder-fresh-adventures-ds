"""Compare production character startup with executed original x86 writes.
Isolated initialization proof; not a gameplay or DS timing test.
"""
from pathlib import Path
import ast, ctypes as C, hashlib, json, struct, subprocess, tempfile
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ESI
R=Path(__file__).resolve().parents[1]
exe=R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'
pe=pefile.PE(str(exe));u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image())
u.mem_map(0x200000,0x2000);u.mem_map(0x300000,0x1000);u.mem_map(0x4000,0x1000)
for address,resource,count in [(0x4e0f30,0x300000,289),(0x4e0fa8,0x300100,297)]:
 u.mem_write(resource,struct.pack('<I',count))
 u.mem_write(0x201000,struct.pack('<5I',0x4000,address,resource,0,0))
 u.reg_write(UC_X86_REG_ESP,0x201000);u.emu_start(0x40adc0,0x4000,count=1000)
u.reg_write(UC_X86_REG_EAX,13);u.reg_write(UC_X86_REG_EBX,1);u.reg_write(UC_X86_REG_ESI,0)
u.emu_start(0x417238,0x4172c2,count=1000);u.emu_start(0x4172fe,0x417304,count=10)
native=[]
for address,handle in [(0x4e0f30,1),(0x4e0fa8,2)]:
 words=list(struct.unpack('<25I',u.mem_read(address,100)));words[0]=handle;native+=words
native+=list(struct.unpack('<I',u.mem_read(0x4e1074,4)))+list(struct.unpack('<I',u.mem_read(0x4e1028,4)))
source=(R/'tools/verify_world_tutorials.py').read_text()
names=ast.literal_eval(next(x.strip().split('=',1)[1] for x in source.splitlines() if x.strip().startswith('names=')))
with tempfile.TemporaryDirectory(prefix='kinder-startup-proof-') as tmp:
 t=Path(tmp);wrapper=t/'probe.c';lib=t/'probe.dylib'
 wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\nvoid probe(uint32_t *v){Player p={0};player_animation_startup(&p);memcpy(v,&p.penguin,100);memcpy(v+25,&p.milk,100);v[50]=p.puff_frame;v[51]=p.state;}\n')
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(wrapper),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(lib)],check=True)
 c=C.CDLL(str(lib));port=(C.c_uint32*52)();c.probe(port)
 failures=[{'word':i,'native':a,'port':b} for i,(a,b) in enumerate(zip(native,port)) if a!=b]
result={'scope':__doc__,'original_ranges':['40adc0 initializer','417238..4172bc overrides','4172fe player state'],'compared_animation_bytes':200,'resource_pointer_normalization':'Only resource word normalized to DS handle 1/2','puff_frame':native[50],'player_state':native[51],'failures':failures,'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'world_sha256':hashlib.sha256((R/'ds/source/world.c').read_bytes()).hexdigest()}
(R/'research/gameplay/player-startup-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert not failures
