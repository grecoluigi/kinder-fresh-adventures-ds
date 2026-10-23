#!/usr/bin/env python3
"""Lossless evidence-first WESTKA W02 map/script exporter. No gameplay inferred."""
import argparse, collections, hashlib, json, re, struct
from pathlib import Path

def u16(b,o): return struct.unpack_from('<H',b,o)[0]
def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def export_map(path,out):
 b=path.read_bytes(); assert b[4:].startswith(b'WESTKA MultiFile/Pool File V 1.0\0')
 count=u16(b,279); cursor=281; entries=[]; target=out/path.name;target.mkdir(parents=True,exist_ok=True)
 for index in range(count):
  size=u32(b,cursor);assert u16(b,cursor+4)==2;start=cursor+6;d=b[start:start+size];assert len(d)==size
  tw,th,w,h=struct.unpack_from('<4H',d,270);ts,os=struct.unpack_from('<II',d,306);layers=d[347]
  assert ts==w*h*layers*3
  assert len(d)==374+ts+os
  tiles=d[348:348+ts];(target/f'{index:02}.tiles.bin').write_bytes(tiles)
  assert u32(d,348+ts)==os
  object_prefix=d[352+ts:374+ts];objects=d[374+ts:374+ts+os];(target/f'{index:02}.objects.bin').write_bytes(objects)
  records=[]
  if os:
   assert os%186==0 and u16(object_prefix,0)==os//186
   for n in range(os//186):
    record=objects[n*186:(n+1)*186]
    records.append({'index':n,'obj_nr':u16(record,0),'x_px':u16(record,2),'y_px':u16(record,4),'raw_hex':record.hex()})
  planes=[]
  for layer in range(layers):
   cells=list(struct.iter_unpack('<BH',tiles[layer*w*h*3:(layer+1)*w*h*3]))
   planes.append({'layer':layer,'nonempty':sum(t!=65535 for bank,t in cells),'raw_flag_counts':dict(collections.Counter(flags for flags,t in cells if t!=65535)),'bank_counts':dict(collections.Counter(flags&7 for flags,t in cells if t!=65535)),'max_index_by_bank':{str(bank):max(t&511 for flags,t in cells if flags&7==bank and t!=65535) for bank in set(flags&7 for flags,t in cells if t!=65535)},'tile_metadata_counts':dict(collections.Counter(t>>9 for flags,t in cells if t!=65535))})
  entry={'index':index,'body_offset':start,'body_size':size,'tile_width':tw,'tile_height':th,'width_cells':w,'height_cells':h,'layers':layers,'tile_byte_length':ts,'object_byte_length':os,'candidate_object_count':len(records),'header_hex':d[:348].hex(),'object_prefix_hex':object_prefix.hex(),'tile_bank_selection':list(struct.unpack_from('<4H',d,260)),'planes':planes,'objects':records}
  (target/f'{index:02}.json').write_text(json.dumps(entry,indent=2)+'\n');entries.append({k:v for k,v in entry.items() if k not in ('objects','header_hex','object_prefix_hex')})
  cursor=start+size
 offsets=list(struct.iter_unpack('<I',b[cursor:]));assert len(offsets)==count
 expected=[e['body_offset'] for e in entries];assert [x[0] for x in offsets]==expected
 return {'file':path.name,'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b),'pool_count':count,'index_offsets':expected,'entries':entries}

def export_scripts(path,out):
 scripts={};annotations={}
 for f in sorted(path.iterdir()):
  txt=f.read_bytes().decode('cp1252')
  if f.suffix.lower()=='.jrs':
   fields={}
   for line in txt.splitlines():
    m=re.match(r'\s*(\w+)\s*=\s*(.*?)\s*$',line)
    if not m:continue
    key,value=m.groups();value=value.rstrip(';').strip();fields[key]=value[1:-1] if value.startswith('"') and value.endswith('"') else int(value) if re.fullmatch(r'-?\d+',value) else value
   scripts[f.name]=fields
  else:annotations[f.name]=txt
 (out/'scripts.json').write_text(json.dumps(scripts,indent=2,ensure_ascii=False)+'\n')
 (out/'script_annotations.json').write_text(json.dumps(annotations,indent=2,ensure_ascii=False)+'\n')
 return scripts

def main():
 p=argparse.ArgumentParser();p.add_argument('--gdata',type=Path,default=Path('original/extracted/ausf_hrende_Dateien/GData'));p.add_argument('--out',type=Path,default=Path('generated/maps'));a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 inventory=[export_map(f,a.out) for f in sorted((a.gdata/'Maps').iterdir()) if f.suffix.lower()=='.w02']
 scripts=export_scripts(a.gdata/'Scripts',a.out)
 (a.out/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
 print(json.dumps({'map_pools':len(inventory),'map_entries':sum(f['pool_count'] for f in inventory),'aom_scripts':len(scripts),'tile_bytes':sum(e['tile_byte_length'] for f in inventory for e in f['entries']),'object_records':sum(e['candidate_object_count'] for f in inventory for e in f['entries'])}))
if __name__=='__main__':main()
