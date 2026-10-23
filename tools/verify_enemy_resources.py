#!/usr/bin/env python3
"""Native alignment normalization and static AOM range-index mapping."""
from pathlib import Path
import json,random,re,struct
import capstone,pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/enemies';pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image()
u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,image);u.mem_map(0x300000,0x10000)
RESOURCE=0x300000;TABLE=0x301000;BP=0x308000
u.reg_write(UC_X86_REG_EBP,BP);u.mem_write(BP+8,struct.pack('<I',RESOURCE));u.mem_write(BP-0x14,struct.pack('<I',TABLE))
rng=random.Random(443);cases=0
assets=json.load(open(ROOT/'generated/assets/inventory.json'));original=[]
for a in assets:
 if a['source'].lower() in ['animation/kong02.w01','animation/parrot02.w01','animation/snake02.w01']:original.append([(f['x'],f['y']) for f in a['frames']])
for values in original+[[(rng.randint(-32768,32767),rng.randint(-32768,32767)) for _ in range(rng.randint(1,100))] for _ in range(1000)]:
 for enabled in (False,True):
  data=b''.join(struct.pack('<hh',*v) for v in values);u.mem_write(TABLE,data);u.mem_write(RESOURCE+0x33,struct.pack('<h',enabled));u.mem_write(RESOURCE+0x0d,struct.pack('<h',len(values)));u.mem_write(0x4f169c,bytes(2));u.emu_start(0x443e9d,0x443f4a,count=10000)
  base=values[0];expected=b''.join(struct.pack('<HH',(x-base[0])&65535,(y-base[1])&65535) for x,y in values) if enabled else data
  assert bytes(u.mem_read(TABLE,len(data)))==expected;cases+=1
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);names=[]
for i in md.disasm(image[0x371c0:0x373ec],0x4371c0):
 if i.mnemonic=='push' and i.op_str.startswith('0x45'):
  at=int(i.op_str,16)-0x400000;names.append(image[at:image.index(b'\0',at)].decode())
fields=[]
for index,name in enumerate(names):
 if not name.startswith(('StartAnim','EndAnim')):continue
 at=struct.unpack_from('<I',image,0x37108+index*4)[0];instructions=list(md.disasm(image[at-0x400000:at-0x400000+64],at));store=next(i for i in instructions if i.mnemonic=='mov' and i.op_str.startswith('word ptr [esp +'))
 offset=int(re.search(r'\+ (0x[0-9a-f]+)',store.op_str)[1],16)-0x20;resource_offset=offset+0x21;range_index=(resource_offset-0x39)//4
 assert range_index>=0 and range_index<=18
 fields.append(dict(name=name,enum=index,handler=hex(at),source_offset=hex(offset),resource_offset=hex(resource_offset),range_index=range_index))
result={'native_alignment_fragment':['0x443e9d','0x443f4a'],'cases':cases,'original_tables':len(original),'transform':'If CorrectAlignToNull, subtract original first frame alignment from every frame with signed16 wrapping','range_mapping':fields,'limitations':['Alignment fragment only; full resource file loader not executed','Range mapping observed static stores and resource-table copy4435d0..4435f8']}
(OUT/'resource_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='range_mapping'},indent=2))
