"""Native arena HUD/camera gate and camera-origin segments, stage4..7."""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EDX
R=Path(__file__).resolve().parents[1]
class Startup(C.Structure):_fields_=[('boss',C.c_int),('locked',C.c_int),('x',C.c_int),('y',C.c_int)]
with tempfile.TemporaryDirectory(prefix='kinder-arena-startup-') as tmp:
 so=Path(tmp)/'routes.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/world_routes.c'),'-o',str(so)],check=True);c=C.CDLL(str(so));c.world_arena_startup.argtypes=[C.c_uint,C.POINTER(Startup)];c.world_arena_startup.restype=C.c_bool
 p=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,p.get_memory_mapped_image());u.mem_map(0x200000,0x10000);coords=[]
 def hook(uc,address,size,context):
  if address==0x434650:
   sp=uc.reg_read(UC_X86_REG_ESP);_,x,y=struct.unpack('<3i',uc.mem_read(sp+4,12));coords[:]=[x,y];uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook);cases=[]
 for world in range(4,8):
  got=Startup();assert c.world_arena_startup(world,C.byref(got));u.mem_write(0x4dabd4,struct.pack('<I',world));u.reg_write(UC_X86_REG_EBX,0);u.reg_write(UC_X86_REG_ESI,1);u.reg_write(UC_X86_REG_EDI,9);u.reg_write(UC_X86_REG_EDX,world);u.emu_start(0x4125a9,0x412626,count=200)
  boss=struct.unpack('<h',u.mem_read(0x45ecbc,2))[0];locked=struct.unpack('<i',u.mem_read(0x4e1018,4))[0];energy=struct.unpack('<i',u.mem_read(0x45ed24,4))[0];ingredients=struct.unpack('<6h',u.mem_read(0x45efd4,12));assert (got.boss,got.locked)==(boss,locked) and energy==9 and ingredients==(1,)*6
  coords.clear();u.reg_write(UC_X86_REG_ESP,0x208000);u.emu_start(0x411964,0x4119cd,count=100);assert coords==[got.x,got.y],(world,coords,got.x,got.y)
  cases.append({'stage':world,'boss_energy':energy,'ingredients':list(ingredients),'camera_locked':locked,'camera_origin':coords.copy()})
 result={'scope':__doc__,'cases':cases,'limits':['Original HUD initializer before these segments separately resets ammo10, health100 and actor HUD flag0; projectile variant4e1044 resets0 in412672.','Native camera initialization subsequently clamps origins to map bounds.']};(R/'research/gameplay/arena-startup-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
