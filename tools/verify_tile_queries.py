"""Original tile-presence/property routines execute without mocked native calls."""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile,sys,pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'research/gameplay'));from verify_collision import Map
pe=pefile.PE(str(root/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image)
for address,size in [(0x200000,0x2000),(0x300000,0x2000),(0x600000,0x100000),(0x4000,0x1000)]:u.mem_map(address,size)
def setup(w,h,layers,data):
 for offset,value in [(0x1685,32),(0x1687,32),(0x1689,w),(0x168b,h)]:u.mem_write(0x300000+offset,struct.pack('<H',value))
 u.mem_write(0x30172f,struct.pack('<I',w*h*3));u.mem_write(0x301717,struct.pack('<I',0x600000));u.mem_write(0x600000,data)
 buffer=(C.c_uint8*len(data)).from_buffer_copy(data);return Map(w,h,32,32,layers,buffer),buffer
with tempfile.TemporaryDirectory(prefix='kinder-tile-query-') as tmp:
 lib=Path(tmp)/'queries.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(root/'ds/source/tile_queries.c'),str(root/'ds/source/collision.c'),'-o',str(lib)],check=True);c=C.CDLL(str(lib))
 for name in ['map_tile_solid','map_tile_property']:getattr(c,name).argtypes=[C.POINTER(Map),C.c_uint,C.c_int,C.c_int];getattr(c,name).restype=C.c_int
 cases=0;rng=random.Random(20020117)
 def check(m,layer,x,y):
  global cases
  for address,name in [(0x434180,'map_tile_solid'),(0x434200,'map_tile_property')]:
   u.mem_write(0x201000,struct.pack('<4I',0x4000,layer,x&0xffffffff,y&0xffffffff));u.reg_write(UC_X86_REG_ESP,0x201000);u.reg_write(UC_X86_REG_ECX,0x300000);u.emu_start(address,0x4000,count=1000)
   actual=C.c_int32(u.reg_read(UC_X86_REG_EAX)).value;want=getattr(c,name)(C.byref(m),layer,x,y);assert actual==want,(name,layer,x,y,actual,want);cases+=1
 for folder in sorted((root/'generated/maps').glob('*.W02')):
  j=json.loads((folder/'00.json').read_text());data=(folder/'00.tiles.bin').read_bytes();w,h=j['width_cells'],j['height_cells'];m,buffer=setup(w,h,8,data)
  for i in range(128):check(m,rng.randrange(8),rng.randrange(-32,w*32+32),rng.randrange(-32,h*32+32))
 for flags in range(256):
  for packed in [0,1,511,512,1024,1536,65024,65535]:
   m,buffer=setup(1,1,1,struct.pack('<BH',flags,packed));check(m,0,17,31)
 result=dict(cases=cases,failures=[],native_functions=['0x434180','0x434200'],scope=__doc__);(root/'research/gameplay/tile_queries_verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
