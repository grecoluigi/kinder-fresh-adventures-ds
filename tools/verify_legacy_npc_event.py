"""Original409050 plus430b20 for legacy NPC ID0, including lookup failure/nulls.
Only4446ea resource lookup is supplied; no shipped map contains this NPC.
"""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EAX,UC_X86_REG_EIP
R=Path(__file__).resolve().parents[1];pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x40000);u.mem_map(0x2000,4096)
class Entity(C.Structure):_fields_=[('raw',C.c_uint8*186)]
Ranges=(C.c_int16*2)*2;available=True;lookups=0

def hook(uc,address,size,context):
 global lookups
 if address==0x4446ea:
  lookups+=1;sp=uc.reg_read(UC_X86_REG_ESP);pc=struct.unpack('<I',uc.mem_read(sp,4))[0];uc.reg_write(UC_X86_REG_EAX,0x220000 if available else 0);uc.reg_write(UC_X86_REG_ESP,sp+8);uc.reg_write(UC_X86_REG_EIP,pc)
u.hook_add(UC_HOOK_CODE,hook)
with tempfile.TemporaryDirectory(prefix='kinder-legacy-npc-')as tmp:
 so=Path(tmp)/'entity.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/entities.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.entity_legacy_npc_event.argtypes=[C.POINTER(Entity),C.c_uint,C.POINTER(C.c_int16*2)];c.entity_legacy_npc_event.restype=C.c_bool
 rng=random.Random(409050);cases=0
 for event in list(range(64))+[0xffffffff,0x80000000,0x10000010,0x10000020]:
  for scenario in range(32):
   raw=bytearray(rng.randbytes(186));struct.pack_into('<H',raw,0,0xffff if scenario%8==0 else 0);e=Entity.from_buffer_copy(raw);ranges=Ranges(*[(C.c_int16*2)(rng.randrange(-32768,32768),rng.randrange(-32768,32768))for _ in range(2)])
   available=scenario%4!=0;pointer=0 if scenario%16==0 else 0x210000
   u.mem_write(0x210000,bytes(e));u.mem_write(0x220000+0x39,bytes(ranges));u.mem_write(0x208000,struct.pack('<4I',0x2000,event,0,pointer));u.reg_write(UC_X86_REG_ESP,0x208000);u.emu_start(0x409050,0x2000,count=1000)
   assert u.reg_read(UC_X86_REG_EIP)==0x2000 and u.reg_read(UC_X86_REG_EAX)==1
   assert c.entity_legacy_npc_event(C.byref(e)if pointer else None,event,ranges if available else None)
   assert bytes(e)==bytes(u.mem_read(0x210000,186)),(event,scenario);cases+=1
 # Retain explicit real script ranges as a source fixture.
 script=next(v for v in json.loads((R/'generated/maps/scripts.json').read_text()).values()if v.get('ObjNr')==0)
 actual=[[script['StartAnimLeft'],script['EndAnimLeft']],[script['StartAnimRight'],script['EndAnimRight']]];assert actual==[[45,48],[53,56]]
 instances=sum(1 for entry in json.loads((R/'generated/maps/inventory.json').read_text())for o in json.loads((R/'generated/maps'/entry['file']/'00.json').read_text())['objects']if o['obj_nr']==0);assert instances==0
 result={'scope':__doc__,'native_cases':cases,'original_lookup_calls':lookups,'all186_object_bytes_equal':True,'native_return_one':True,'source_ranges':actual,'shipped_map_instances':instances,'limits':['No current world-loop/graphics binding was added for this unused NPC.','Zero map instances do not alone prove every possible indirect/runtime creator path unreachable.','Reconstructing all registered callback bodies is not full engine/gameplay completion.']}
 (R/'research/gameplay/legacy-npc-event-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
