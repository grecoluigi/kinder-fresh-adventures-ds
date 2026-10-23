"""Pack native GPU pages and frame lookups; never modifies NitroFS."""
from pathlib import Path
import argparse,hashlib,json,struct,zlib
def build(A,output_report):
 manifest=json.loads((A/'manifest.json').read_text());pages=manifest['pages'];indices={p['key']:i for i,p in enumerate(pages)}
 def pad(data,n):data.extend(b'\0'*((-len(data))%n))
 blob=bytearray(32+32*len(pages));palettes={}
 for p in pages:
  name=p['palette']
  if name and name not in palettes:
   pad(blob,16);palettes[name]=len(blob);blob.extend((A/name).read_bytes())
 for i,p in enumerate(pages):
  tex=(A/p['texels']).read_bytes();pal=(A/p['palette']).read_bytes() if p['palette'] else b''
  pad(blob,8);offset=len(blob);blob.extend(tex)
  record=struct.pack('<IIHHBBHIIII',offset,palettes.get(p['palette'],0),p['width'],p['height'],p['bits'],int(p['bits']<16),0,len(tex),len(pal),zlib.crc32(tex),zlib.crc32(pal))
  blob[32+i*32:64+i*32]=record
 version=4 if any(p['height']>32 for p in pages) else 2 if any(p['height']!=8 for p in pages) else 1
 blob[:32]=struct.pack('<4s7I',b'KGP1',version,len(pages),32,32,len(blob),0,0)
 (A/'pages.gpu').write_bytes(blob)
 lookups=[]
 for name,bindings in manifest['bindings'].items():
  frames=bytearray();refs=bytearray()
  for binding in sorted(bindings.values(),key=lambda b:(b['kind'],b['frame_id'])):
   first=len(refs)//12
   for p in binding['pages']:refs.extend(struct.pack('<I4H',indices[p['key']],p['source_x'],p['source_y'],p['draw_width'],p['draw_height']))
   frames.extend(struct.pack('<IIHHIII',binding['kind'],binding['frame_id'],binding['width'],binding['height'],first,len(binding['pages']),0))
  out=struct.pack('<4s7I',b'KAF1',1,len(bindings),len(refs)//12,32,32+len(frames),32+len(frames)+len(refs),0)+frames+refs
  path=A/(name+'.gpi');path.write_bytes(out)
  lookups.append({'map':name,'file':path.name,'bytes':len(out),'frame_records':len(bindings),'page_references':len(refs)//12,'sha256':hashlib.sha256(out).hexdigest()})
 report={'scope':__doc__,'source_manifest_sha256':hashlib.sha256((A/'manifest.json').read_bytes()).hexdigest(),'pack_bytes':len(blob),'pack_sha256':hashlib.sha256(blob).hexdigest(),'page_records':len(pages),'shared_palettes':len(palettes),'map_lookups':lookups,'limits':['Coverage is defined by the input manifest; missing frames require the existing source path.','Texture pages are native linear GPU formats; this pack has no outer ROM compression.','Pack file offsets are storage locations, not proposed physical VRAM addresses.','Not integrated into the ROM.']}
 output_report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='map_lookups'}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--asset-dir',type=Path,required=True);p.add_argument('--output-report',type=Path,required=True);a=p.parse_args();build(a.asset_dir,a.output_report)
