"""Compile pickup frames and preserve original per-map object records."""
from pathlib import Path
import argparse,hashlib,json,struct
from pickup_scaled_build import build

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--maps',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 data,stats=build(a.assets,a.maps);(a.output/'pickups.frames').write_bytes(data);rows=[]
 for item in json.loads((a.maps/'inventory.json').read_text()):
  name=item['file'];metadata=json.loads((a.maps/name/'00.json').read_text());records=[bytes.fromhex(o['raw_hex'])for o in metadata['objects']]
  blob=b'KFE1'+struct.pack('<I',len(records))+b''.join(records);(a.output/(name+'.entities')).write_bytes(blob)
  rows.append({'map':name,'objects':len(records),'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
 result={'pickups':stats,'maps':rows};(a.output/'entity-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'pickup_frames':stats['frames'],'pickup_bytes':len(data),'maps':len(rows),'objects':sum(r['objects']for r in rows)}))

if __name__=='__main__':main()
