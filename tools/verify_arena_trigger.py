"""Native411365..41139b six-ingredient arena trigger, all masks and signed values."""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile,random
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EBX
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-arena-trigger-') as tmp:
 so=Path(tmp)/'routes.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/world_routes.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_arena_target.argtypes=[C.c_uint,C.POINTER(C.c_int16)]
 p=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,p.get_memory_mapped_image());rng=random.Random(411365);cases=0
 for world in range(8):
  for mask in range(64):
   for variant in range(4):
    values=[rng.choice([-32768,-1,1,32767]) if mask&(1<<i) else 0 for i in range(6)]
    u.mem_write(0x4dabd4,struct.pack('<I',world));u.mem_write(0x45efd4,struct.pack('<6h',*values));u.mem_write(0x45f008,struct.pack('<I',1));u.mem_write(0x4dab5c,struct.pack('<i',-1));u.reg_write(UC_X86_REG_EBX,0);u.emu_start(0x411365,0x41139b,count=200)
    target=c.world_arena_target(world,(C.c_int16*6)(*values));native=struct.unpack('<i',u.mem_read(0x4dab5c,4))[0];mode=struct.unpack('<I',u.mem_read(0x45f008,4))[0]
    assert target==native and mode==(20 if target>=0 else 1),(world,mask,values,target,native,mode);cases+=1
 result={'scope':__doc__,'cases':cases,'stage_ids':list(range(8)),'ingredient_masks':64,'nonzero_values':[-32768,-1,1,32767],'limits':['Only the native trigger segment; map loading, boss combat and completion are separate checks.']}
 (R/'research/gameplay/arena-trigger-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
