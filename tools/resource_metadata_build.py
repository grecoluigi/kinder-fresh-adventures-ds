"""Compile native AOM frame geometry directly from decoded originals/scripts."""
from pathlib import Path
import argparse,hashlib,json,struct
from decoded_assets import DecodedAssets
from native_resources import asset_source,frame_alignment

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--maps',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 assets=DecodedAssets(a.assets);scripts={s['ObjNr']:s for s in json.loads((a.maps/'scripts.json').read_text()).values() if 'ObjNr' in s};resources=[];frames=[]
 for id,script in sorted(scripts.items()):
  if not script.get('FileName'):continue
  asset=assets.inventory.get(asset_source(script))
  if not asset or not asset.get('frames'):continue
  resources.append(struct.pack('<4H',id,len(frames),len(asset['frames']),script.get('ReferenceSprWidth',0)))
  for i,frame in enumerate(asset['frames']):frames.append(struct.pack('<HHhh',frame['width'],frame['height'],*frame_alignment(script,asset,i)))
 data=struct.pack('<4sHH',b'KFOG',len(resources),len(frames))+b''.join(resources)+b''.join(frames);(a.output/'objects.geometry').write_bytes(data)
 result={'resources':len(resources),'frames':len(frames),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()};(a.output/'geometry-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
