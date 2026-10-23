"""Replay original 4395b0 RNG against its portable unsigned32-bit implementation."""
from pathlib import Path
import ctypes as C,struct,subprocess,tempfile,json,pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EAX
root=Path(__file__).resolve().parents[1];pe=pefile.PE(str(root/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));im=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(im)+4095)&~4095);u.mem_write(0x400000,im);u.mem_map(0x200000,0x2000);u.mem_map(0x4000,0x1000)
with tempfile.TemporaryDirectory(prefix='kinder-rng-') as tmp:
 lib=Path(tmp)/'rng.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(root/'ds/source/native_rng.c'),'-o',str(lib)],check=True);c=C.CDLL(str(lib));c.native_rng_seed.argtypes=[C.c_uint32];cases=0
 for seed in [0,1,0x7fffffff,0x80000000,0xffffffff,20020117]:
  c.native_rng_seed(seed);u.mem_write(0x45ad24,struct.pack('<I',seed))
  for i in range(1000):
   u.mem_write(0x201000,struct.pack('<I',0x4000));u.reg_write(UC_X86_REG_ESP,0x201000);u.emu_start(0x4395b0,0x4000,count=1000);assert u.reg_read(UC_X86_REG_EAX)==c.native_rng_next();cases+=1
 result=dict(cases=cases,failures=[],native_function='0x4395b0',scope=__doc__);(root/'research/gameplay/rng_verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
