"""Verify real ndstool output versus compacted DS/DSi image, including loader sections."""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import hashlib,json,struct,subprocess,tempfile
from deduplicate_nds import compact,crc16
R=Path(__file__).resolve().parents[1]
SDK=Path.home()/'.local/share/wonderful/thirdparty/blocksds/core'
with tempfile.TemporaryDirectory(prefix='kinder-nds-dedup-')as tmp:
 source=Path(tmp)/'source.nds'
 subprocess.run([str(SDK/'tools/ndstool/ndstool'),'-c',str(source),'-7',str(SDK/'sys/arm7/main_core/arm7_maxmod.elf'),'-9',str(R/'ds/build/kinder_fresh.elf'),'-b',str(R/'ds/icon.png'),'Kinder Fresh Adventures;Nintendo DS port;v'+(R/'VERSION').read_text().strip()+'','-d',str(R/'ds/nitrofs')],check=True,capture_output=True)
 original=source.read_bytes();result,report=compact(original);twice,_=compact(result);assert twice==result
 assert (resolve_rom(R / 'ds')).read_bytes()==result,'Canonical ROM differs from verified pack'
 read=lambda b,a:struct.unpack_from('<I',b,a)[0]
 sections=[]
 for label,offset,size in [('ARM9',0x20,0x2c),('ARM7',0x30,0x3c),('FNT',0x40,0x44),('ARM9i',0x1c0,0x1cc),('ARM7i',0x1d0,0x1dc),('banner',0x68,0x208)]:
  a,n=read(original,offset),read(original,size);x,m=read(result,offset),read(result,size)
  assert n==m and original[a:a+n]==result[x:x+m],label
  sections.append({'name':label,'bytes':n,'sha256':hashlib.sha256(result[x:x+m]).hexdigest()})
 first=min(struct.unpack_from('<I',original,read(original,0x48)+i)[0]for i in range(0,read(original,0x4c),8))
 a=bytearray(original[:first]);b=bytearray(result[:first])
 for start,size in [(0x14,1),(0x80,4),(0x15e,2),(0x1c0,4),(0x1d0,4),(0x210,4),(0xfec,20),(read(original,0x48),read(original,0x4c))]:a[start:start+size]=b'\0'*size;b[start:start+size]=b'\0'*size
 assert a==b,'Unexpected modification outside FAT and size/offset/checksum fields'
 rejected=[]
 def reject(name,offset,value):
  data=bytearray(original);struct.pack_into('<I',data,offset,value);struct.pack_into('<H',data,0x15e,crc16(data[:0x15e]))
  try:compact(bytes(data))
  except AssertionError:rejected.append(name)
  else:raise AssertionError(name+' was accepted')
 reject('overlays',0x50,0x1000);reject('digest table',0x1e0,0x1000);reject('modcrypt',0x220,0x1000);reject('out-of-range payload',read(original,0x48)+4,len(original)+1)
 result_report={'scope':__doc__,'packing':report,'idempotent':True,'preserved_sections':sections,'unchanged_prefix_except_declared_fields':True,'rejected_layouts':rejected,'limits':['Proves byte/header preservation and package identity; emulator/hardware loading and NitroFS reads are separate checks.','Only unsigned ndstool homebrew layouts without overlays/digests/encryption are supported.']}
 (R/'research/rendering/nitrofs-deduplication-verification.json').write_text(json.dumps(result_report,indent=2)+'\n');print(json.dumps(result_report,indent=2))
