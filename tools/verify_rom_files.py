"""Read the actual NDS filename/allocation tables and verify every NitroFS file.
Also checks that an asset-only edit schedules ROM repacking in the Makefile.
"""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import struct,hashlib,json,subprocess
R=Path(__file__).resolve().parents[1];rom=resolve_rom(R / 'ds');base=R/'ds/nitrofs'
with rom.open('rb')as stream:
 header=stream.read(512);fnt_offset,fnt_size,fat_offset,fat_size=struct.unpack_from('<4I',header,0x40)
 stream.seek(fnt_offset);names=stream.read(fnt_size);stream.seek(fat_offset);fat=stream.read(fat_size)
 assert len(names)==fnt_size and len(fat)==fat_size and fat_size%8==0
 directories=struct.unpack_from('<H',names,6)[0];assert directories>0 and directories*8<=len(names)
 files={};visited=set()
 def directory(index,prefix):
  assert 0<=index<directories and index not in visited;visited.add(index)
  cursor,file_id,parent=struct.unpack_from('<IHH',names,index*8)
  while True:
   assert cursor<len(names);length=names[cursor];cursor+=1
   if not length:return
   count=length&127;assert count and cursor+count<=len(names)
   name=names[cursor:cursor+count].decode('utf-8');cursor+=count;assert name not in ('.','..') and '/'not in name
   path=prefix/name
   if length&128:
    child=struct.unpack_from('<H',names,cursor)[0];cursor+=2;directory(child-0xf000,path)
   else:
    assert file_id*8+8<=len(fat);start,end=struct.unpack_from('<II',fat,file_id*8);assert start<=end<=rom.stat().st_size
    assert path not in files;files[path]=(start,end);file_id+=1
 directory(0,Path('.'))
 expected={p.relative_to(base)for p in base.rglob('*')if p.is_file()};assert set(files)==expected,(set(files)-expected,expected-set(files))
 verified=[]
 for path in sorted(expected):
  start,end=files[path];source=base/path;assert end-start==source.stat().st_size,path
  packaged=hashlib.sha256();original=hashlib.sha256();stream.seek(start);remaining=end-start
  with source.open('rb')as asset:
   while remaining:
    count=min(1048576,remaining);chunk=stream.read(count);reference=asset.read(count);assert len(chunk)==len(reference)==count
    packaged.update(chunk);original.update(reference);remaining-=count
  assert packaged.digest()==original.digest(),path
  verified.append({'path':str(path),'bytes':end-start,'sha256':packaged.hexdigest()})
 dry=subprocess.check_output(['make','-C',str(R/'ds'),'-n','-W','nitrofs/end_titles/0.bin'],text=True)
 assert 'NDSTOOL' in dry or 'ndstool' in dry,dry
 assert 'deduplicate_nds.py' in dry,dry
 stream.seek(0);rom_hash=hashlib.file_digest(stream,'sha256').hexdigest()
 result={'scope':__doc__,'rom_sha256':rom_hash,'verified_files':len(verified),'verified_bytes':sum(v['bytes']for v in verified),'asset_only_change_repackages':True,'default_build_deduplicates':True,'physical_payload_bytes':sum(b-a for a,b in set(files.values())),'aliased_files':len(files)-len(set(files.values())),'files':verified}
 (R/'research/rendering/rom-files-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='files'}))
