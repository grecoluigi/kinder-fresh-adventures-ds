"""Actual original map reset/path initialization for random records and all12 maps.
This compares retained native430ca0/430c30/430cf0 instructions, without mocked calls.
"""
from pathlib import Path
import ctypes as C,json,struct,random,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EIP
R=Path(__file__).resolve().parents[1]
class Entity(C.Structure):_fields_=[('bytes',C.c_uint8*186)]
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x60000);u.mem_map(0x2000,4096)
def run(entry,args=(),ecx=0x240000):
 u.mem_write(0x208000,struct.pack('<'+'I'*(1+len(args)),0x2000,*args));u.reg_write(UC_X86_REG_ESP,0x208000);u.reg_write(UC_X86_REG_ECX,ecx);u.emu_start(entry,0x2000,count=1000000);assert u.reg_read(UC_X86_REG_EIP)==0x2000
with tempfile.TemporaryDirectory(prefix='kinder-map-start-')as tmp:
 so=Path(tmp)/'entities.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/entities.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.entity_path_init.argtypes=[C.POINTER(Entity)];c.entities_reset_map.argtypes=[C.POINTER(Entity),C.c_size_t]
 rng=random.Random(0x430cf0);fixtures=0
 for i in range(2048):
  raw=bytearray(rng.randbytes(186));raw[28]=rng.choice((0,1,128));x,y,left,top,right,bottom=[rng.choice((-32768,-1,0,1,32767,rng.randrange(-32768,32768)))for _ in range(6)]
  struct.pack_into('<hh',raw,2,x,y);struct.pack_into('<hhhh',raw,31,left,top,right,bottom)
  e=Entity.from_buffer_copy(raw);u.mem_write(0x210000,bytes(raw));run(0x430cf0,[0x210000]);c.entity_path_init(C.byref(e));assert bytes(e)==u.mem_read(0x210000,186),i;fixtures+=1
 maps=[];total=0;directions={}
 for item in json.loads((R/'generated/maps/inventory.json').read_text()):
  name=item['file'];data=(R/'ds/nitrofs/scenes'/f'{name}.entities').read_bytes();count=struct.unpack_from('<I',data,4)[0];raw=data[8:];assert len(raw)==count*186
  array=(Entity*count).from_buffer_copy(raw);u.mem_write(0x210000,raw);u.mem_write(0x240000+12,struct.pack('<HI',count,0x210000));run(0x430ca0);c.entities_reset_map(array,count)
  assert bytes(array)==u.mem_read(0x210000,len(raw)),name
  initialized=[]
  for i,e in enumerate(array):
   id=struct.unpack_from('<H',e.bytes)[0]
   if e.bytes[28] and e.bytes[29] and e.bytes[39]:initialized.append({'index':i,'id':id,'direction':e.bytes[39]})
  maps.append({'map':name,'records':count,'initialized_moving_records':initialized});total+=count
 result={'scope':__doc__,'random_path_fixtures':fixtures,'serialized_records_compared':total,'maps':maps,'limits':['Native byte parity proves startup fields, not full support/carry/playthrough behavior.']}
 (R/'research/gameplay/entity-startup-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
