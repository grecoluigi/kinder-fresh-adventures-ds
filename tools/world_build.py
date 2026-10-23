"""Compile scene metadata, original tile layers and collision file placement.

Static sprite IDs remain stable metadata only. No software graphics banks or
scene renderer are generated. Other entity/texture stages are separate.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,struct
from PIL import Image
from decoded_assets import DecodedAssets
from native_resources import frame_metadata,asset_source

def rgb555(image):
 return struct.pack('<49152H',*[(r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000 if a else 0 for r,g,b,a in image.convert('RGBA').get_flattened_data()])

def build(decoded,maps,collision,out):
 out.mkdir(parents=True,exist_ok=False);assets=DecodedAssets(decoded)
 scripts={s['ObjNr']:s for s in json.loads((maps/'scripts.json').read_text()).values()if 'ObjNr' in s}
 sprite_ids={};manifest=[];backgrounds={}
 for item in json.loads((maps/'inventory.json').read_text()):
  name=item['file'];metadata=json.loads((maps/name/'00.json').read_text());stem=Path(name).stem
  if stem.lower().endswith('e'):stem=stem[:-1]
  key=stem.lower();sheet=assets.inventory[f'maps/{key}.w01']['frames']
  assert(metadata['tile_width'],metadata['tile_height'],metadata['layers'])==(32,32,8)
  image=Image.new('RGBA',(800,600),'black');image.alpha_composite(assets.image(sheet[4]),(0,0))
  blob=rgb555(image.resize((256,192),Image.Resampling.NEAREST));filename=key+'.bg'
  if filename in backgrounds:assert backgrounds[filename]==blob
  else:backgrounds[filename]=blob;(out/filename).write_bytes(blob)
  records=[]
  for obj in metadata['objects']:
   raw=bytes.fromhex(obj['raw_hex']);script=scripts.get(obj['obj_nr'])
   if not script or not script.get('FileName'):continue
   asset=assets.inventory.get(asset_source(script))
   if not asset:continue
   frame=script.get('StartAnimLeft',script.get('FileAnimStart',0));mirror=bool(raw[43]);meta=frame_metadata(script,asset,frame,mirror)
   identity=(meta['png'],mirror)
   if identity not in sprite_ids:sprite_ids[identity]=len(sprite_ids)
   records.append(struct.pack('<HBBiiIHH',obj['obj_nr'],raw[25],raw[23],obj['x_px']+meta['x'],obj['y_px']+meta['y'],sprite_ids[identity],meta['width'],meta['height']))
  start=next((o for o in metadata['objects']if o['obj_nr']==1000),{'x_px':400,'y_px':300})
  tiles=(maps/name/'00.tiles.bin').read_bytes();count=len(records);offset=64+count*20
  assert len(tiles)==metadata['width_cells']*metadata['height_cells']*8*3
  header=struct.pack('<4s7H2i2I28s2x',b'KFS1',metadata['width_cells'],metadata['height_cells'],8,32,32,count,0,start['x_px'],start['y_px'],offset,len(tiles),key.encode())
  data=header+b''.join(records)+tiles;(out/(name+'.scene')).write_bytes(data)
  manifest.append({'map':name,'objects':count,'original_objects':len(metadata['objects']),'start':[start['x_px'],start['y_px']],'tile_bytes':len(tiles),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 collision_files=sorted([*collision.glob('*.mask'),*collision.glob('*.collision')]);assert collision_files
 assert {p.name[:-10] for p in collision.glob('*.collision')}=={r['map']for r in manifest}
 for path in collision_files:shutil.copyfile(path,out/path.name)
 result={'maps':manifest,'stable_static_metadata_ids':len(sprite_ids),'backgrounds':len(backgrounds),'collision_files':len(collision_files),'scope':__doc__}
 (out/'scene-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in('maps','scope')}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--maps',type=Path,required=True);p.add_argument('--collision',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.assets,a.maps,a.collision,a.output)
