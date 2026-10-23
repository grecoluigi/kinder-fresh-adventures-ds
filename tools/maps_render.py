#!/usr/bin/env python3
"""Render extracted WESTKA scenes; camera and animation time remain explicit assumptions."""
import argparse, json, struct, re
from pathlib import Path
from PIL import Image,ImageDraw
from native_resources import frame_metadata,asset_source

class Renderer:
 def __init__(self,assets=Path('generated/assets'),maps=Path('generated/maps')):
  self.maps=maps;self.assets={x['source'].lower():x for x in json.loads((assets/'inventory.json').read_text()) if 'frames' in x};self.scripts={x['ObjNr']:x for x in json.loads((maps/'scripts.json').read_text()).values() if 'ObjNr' in x};self.cache={}
 def frame(self,meta):
  p=meta['png']
  if p not in self.cache:self.cache[p]=Image.open(p).convert('RGBA')
  return self.cache[p]
 def render(self,name,index=0,camera=None,layout='row',objects=True):
  base=self.maps/name;j=json.loads((base/f'{index:02}.json').read_text());data=(base/f'{index:02}.tiles.bin').read_bytes();w,h=j['width_cells'],j['height_cells'];tw,th=j['tile_width'],j['tile_height'];count=w*h
  starts=[o for o in j['objects'] if o['obj_nr']==1000]
  sx,sy=(starts[0]['x_px'],starts[0]['y_px']) if starts else(400,300)
  cx,cy=camera if camera else(max(0,min(sx-400,w*tw-800)),max(0,min(sy-380,h*th-600)))
  stem=Path(name).stem
  if stem.lower().endswith('e'):stem=stem[:-1]
  sheet=self.assets[f'maps/{stem}.w01'.lower()]['frames']
  out=Image.new('RGBA',(800,600),'black');background=self.frame(sheet[4]);out.alpha_composite(background,(0,0))
  def draw_objects(layer,subgroup):
   if not objects:return
   for o in j['objects']:
    raw=bytes.fromhex(o['raw_hex'])
    if o['obj_nr']==1000:continue # Native411900 deactivates the spawn-marker art.
    if raw[25]!=layer or raw[23]!=subgroup:continue
    script=self.scripts.get(o['obj_nr'])
    if not script or not script.get('FileName'):continue
    source=asset_source(script);asset=self.assets.get(source)
    if not asset:continue
    # Static first named animation frame. State-specific range selection needs native gameplay.
    frame=script.get('StartAnimLeft',script.get('FileAnimStart',0));mirror=bool(raw[43]);meta=frame_metadata(script,asset,frame,mirror);im=self.frame(meta)
    if mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    ox,oy=o['x_px']+meta['x']-cx,o['y_px']+meta['y']-cy
    if ox+im.width>0 and oy+im.height>0 and ox<800 and oy<600:out.alpha_composite(im,(ox,oy))
  # Tile IDs address row-major32px cells within640px-wide W01 sprite sheets.
  for layer in range(j['layers']):
   draw_objects(layer,1)
   for y in range(max(0,cy//th),min(h,(cy+600+th-1)//th)):
    for x in range(max(0,cx//tw),min(w,(cx+800+tw-1)//tw)):
     cell=(y*w+x) if layout=='row' else(x*h+y)
     bank,tile=struct.unpack_from('<BH',data,(layer*count+cell)*3)
     if tile==65535 or bank&0x40 or ((tile>>9)&127)>50:continue
     meta=sheet[j['tile_bank_selection'][bank&7]];im=self.frame(meta);cols=im.width//tw;tile&=511;tx,ty=tile%cols*tw,tile//cols*th
     part=im.crop((tx,ty,tx+tw,ty+th))
     if bank&8:part=part.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
     if bank&16:part=part.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
     out.alpha_composite(part,(x*tw-cx,y*th-cy))
   draw_objects(layer,0)
   draw_objects(layer,2)
  return out.convert('RGB'),{'map':name,'camera_x':cx,'camera_y':cy,'start_x':sx,'start_y':sy,'layout':layout,'objects':objects,'sprite_state':'StartAnimLeft or FileAnimStart'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('generated/maps/previews'));a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);r=Renderer();inventory=json.loads((r.maps/'inventory.json').read_text());records=[];contact=Image.new('RGB',(800,4*224),'#222222');draw=ImageDraw.Draw(contact)
 for k,item in enumerate(inventory):
  name=item['file'];im,meta=r.render(name);target=a.out/(Path(name).stem+'_start_800.png');im.save(target);im.resize((256,192),Image.Resampling.NEAREST).save(a.out/(Path(name).stem+'_start_ds.png'));records.append(meta)
  thumb=im.resize((256,192),Image.Resampling.NEAREST);x=(k%3)*266;y=(k//3)*224;contact.paste(thumb,(x,y));draw.text((x+3,y+195),name,fill='white');draw.text((x+3,y+208),f"camera {meta['camera_x']},{meta['camera_y']}",fill='white')
 contact.save(a.out/'worlds_contact.png')
 for layout in ['row','column']:
  im,_=r.render('Welt1.W02',layout=layout,objects=False);im.save(a.out/f'welt1_{layout}_tiles.png')
 (a.out/'render_manifest.json').write_text(json.dumps(records,indent=2)+'\n');print('Rendered',len(records),'scenes and row/column comparison')
if __name__=='__main__':main()
