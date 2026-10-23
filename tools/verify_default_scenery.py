"""Original default-map records: animation stage and default movement preserve art.
Native sound-event preamble and general engine dispatch are outside this proof.
"""
from pathlib import Path
import sys,ctypes as C,json,struct,subprocess,tempfile,collections
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EIP,UC_X86_REG_EBP,UC_X86_REG_ESI
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from native_resources import asset_source
class Entity(C.Structure):_fields_=[('bytes',C.c_uint8*186)]
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x60000);u.mem_map(0x2000,4096)
registry={v['id']for v in json.loads((R/'research/coverage_registry.json').read_text())['registry']}
scripts={v.get('ObjNr'):v for v in json.loads((R/'generated/maps/scripts.json').read_text()).values()}
assets={v['source'].lower():v for v in json.loads((R/'generated/assets/inventory.json').read_text())if 'frames'in v}
def art_fields(raw):return tuple(raw[at:end]for at,end in ((2,8),(14,16),(43,44),(185,186)))
with tempfile.TemporaryDirectory(prefix='kinder-default-scenery-')as tmp:
 so=Path(tmp)/'default.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/entities.c'),str(R/'ds/source/blocks.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.entities_reset_map.argtypes=[C.POINTER(Entity),C.c_size_t];c.entity_advance_animation.argtypes=[C.POINTER(Entity),C.c_int16];c.block_default_movement.argtypes=[C.POINTER(Entity),C.c_void_p,C.c_void_p]
 records=[];counts=collections.Counter();steps=0
 for item in json.loads((R/'generated/maps/inventory.json').read_text()):
  name=item['file'];data=(R/'ds/nitrofs/scenes'/f'{name}.entities').read_bytes();n=struct.unpack_from('<I',data,4)[0]
  for index in range(n):
   raw=data[8+index*186:8+(index+1)*186];id=struct.unpack_from('<H',raw)[0]
   if id in registry or id==1000:continue
   script=scripts.get(id);resource=asset_source(script)if script and script.get('FileName')else None
   if resource:assert len(assets[resource]['frames'])==1,(id,resource)
   e=Entity.from_buffer_copy(raw);c.entities_reset_map(C.byref(e),1);before=art_fields(bytes(e));assert not e.bytes[39],(name,index,id)
   u.mem_write(0x210000,bytes(e))
   for tick in range(12):
    sp=0x208000;u.mem_write(sp,b'\0'*128);u.mem_write(sp+0x50,struct.pack('<I',4));u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EBP,0x220000);u.reg_write(UC_X86_REG_ESI,0x210000)
    u.emu_start(0x4337a1,0x43383f,count=1000);native_event=struct.unpack('<I',u.mem_read(sp+0x50,4))[0]
    assert c.entity_advance_animation(C.byref(e),0)==native_event
    u.mem_write(sp,struct.pack('<4I',0x2000,native_event,0,0x210000));u.reg_write(UC_X86_REG_ESP,sp);u.emu_start(0x430d90,0x2000,count=1000)
    c.block_default_movement(C.byref(e),None,None)
    assert bytes(e)==u.mem_read(0x210000,186),(name,index,tick)
    assert art_fields(bytes(e))==before,(name,index,tick,'visible mutation');steps+=1
   counts[id]+=1;records.append({'map':name,'index':index,'id':id,'resource':resource,'path_direction':0,'visible_fields_unchanged':True})
 result={'scope':__doc__,'default_ids':len(counts),'default_records':len(records),'native_tick_comparisons':steps,'instances_by_id':dict(counts),'records':records,'limits':['Static art equivalence covers shipped default records; a changed/new script or runtime mutation invalidates that conclusion.','Original frame-sound preamble, engine callback events and full-game audio remain separate audit work.','This does not claim full native engine coverage.']}
 (R/'research/gameplay/default-scenery-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ('records','instances_by_id')}))
