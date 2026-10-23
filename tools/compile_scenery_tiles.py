"""Bake immutable scenery passes from original artwork into DS-sized tile inputs.

Offline conversion only: dynamic objects remain ordered callback slots. No
runtime software renderer, original-size tile bank or static sprite pack is used.
"""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from PIL import Image
from decoded_assets import DecodedAssets
from native_resources import asset_source,frame_metadata
from compile_scene_definitions import DYNAMIC_IDS,JUNGLE_ENEMIES
from tile_storage import packet

def ceildiv(n,d):return -(-n//d)

class Compiler:
 def __init__(self,decoded,maps):
  self.assets=DecodedAssets(decoded);self.maps=maps
  self.scripts={s['ObjNr']:s for s in json.loads((maps/'scripts.json').read_text()).values()if 'ObjNr'in s}
  self.images={}
 def image(self,frame):
  if frame['png']not in self.images:self.images[frame['png']]=self.assets.image(frame)
  return self.images[frame['png']]
 def compile(self,name):
  metadata=json.loads((self.maps/name/'00.json').read_text());data=(self.maps/name/'00.tiles.bin').read_bytes()
  w,h=metadata['width_cells'],metadata['height_cells'];n=w*h
  dw=ceildiv(w*32*16-25,50);dh=ceildiv(h*32*16-25,50);gw=ceildiv(dw,16);gh=ceildiv(dh,16);assert gw*gh<65536
  xs=((2*np.arange(dw)+1)*25)//16;ys=((2*np.arange(dh)+1)*25)//16
  stem=Path(name).stem
  if stem.lower().endswith('e'):stem=stem[:-1]
  sheet=self.assets.inventory['maps/'+stem.lower()+'.w01']['frames']
  canvas=Image.new('RGBA',(w*32,h*32));dirty=False;commands=[];passes={};tiles={}
  def flush():
   nonlocal canvas,dirty
   if not dirty:return
   if canvas.getchannel('A').getbbox()is not None:
    rgba=np.asarray(canvas)[ys[:,None],xs[None,:]].astype(np.uint16)
    sampled=np.where(rgba[:,:,3],0x8000|(rgba[:,:,0]>>3)|((rgba[:,:,1]>>3)<<5)|((rgba[:,:,2]>>3)<<10),0).astype('<u2')
    padded=np.zeros((gh*16,gw*16),dtype='<u2');padded[:dh,:dw]=sampled
    grid=padded.reshape(gh,16,gw,16).transpose(0,2,1,3);cells=[]
    for y,x in zip(*np.nonzero(np.any(grid,axis=(2,3)))):cells.append((int(y*gw+x),grid[y,x].reshape(256).copy()))
    passes[len(commands)]=cells;commands.append((0,0,0))
   canvas=Image.new('RGBA',(w*32,h*32));dirty=False
  def objects(layer,group):
   nonlocal dirty
   for index,obj in enumerate(metadata['objects']):
    raw=bytes.fromhex(obj['raw_hex']);id=obj['obj_nr']
    if id==1000 or raw[25]!=layer or raw[23]!=group:continue
    if id in DYNAMIC_IDS or(name in JUNGLE_ENEMIES and 3<=id<=5):flush();commands.append((1,index,0));continue
    script=self.scripts.get(id)
    if not script or not script.get('FileName'):continue
    asset=self.assets.inventory.get(asset_source(script))
    if not asset:continue
    mirror=bool(raw[43]);frame=frame_metadata(script,asset,script.get('StartAnimLeft',script.get('FileAnimStart',0)),mirror)
    image=self.image(frame)
    if mirror:image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    canvas.alpha_composite(image,(obj['x_px']+frame['x'],obj['y_px']+frame['y']));dirty=True
  for layer in range(metadata['layers']):
   objects(layer,1)
   for y in range(h):
    for x in range(w):
     flags,value=struct.unpack_from('<BH',data,(layer*n+y*w+x)*3)
     if value==65535 or flags&64 or value>>9>50:continue
     key=(flags&31,value&511)
     if key not in tiles:
      atlas=self.image(sheet[metadata['tile_bank_selection'][flags&7]]);i=value&511;columns=atlas.width//32;tx=i%columns*32;ty=i//columns*32;image=atlas.crop((tx,ty,tx+32,ty+32))
      if flags&8:image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
      if flags&16:image=image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
      tiles[key]=image
     canvas.alpha_composite(tiles[key],(x*32,y*32));dirty=True
   objects(layer,0)
   if layer==2:flush();commands.append((2,2,0))
   objects(layer,2)
  flush()
  # Remove covered static pixels while retaining every static ordinal and
  # callback position. Later layers cannot change collision/object data.
  coverage={};kept={}
  for ci in reversed(range(len(commands))):
   if commands[ci][0]:continue
   cells=[]
   for cell,tile in passes[ci]:
    opaque=(tile&32768)!=0;covered=coverage.get(cell);keep=opaque if covered is None else opaque&~covered
    coverage[cell]=opaque.copy()if covered is None else covered|opaque
    if np.any(keep):cells.append((cell,np.where(keep,tile,0).astype('<u2').tobytes()))
   kept[ci]=cells
  pairs=[];unique=[bytes(512)];lookup={unique[0]:0};ordered=[]
  for ci,(kind,arg,count)in enumerate(commands):
   if kind:ordered.append((kind,arg,count));continue
   start=len(pairs)
   for cell,tile in kept[ci]:
    if tile not in lookup:lookup[tile]=len(unique);unique.append(tile)
    pairs.append((cell,lookup[tile]))
   ordered.append((0,start,len(pairs)-start))
  index=struct.pack('<4sHHIIHH',b'KFLD',gw,gh,len(ordered),len(pairs),w,h)+b''.join(struct.pack('<III',*c)for c in ordered)+b''.join(struct.pack('<HH',*p)for p in pairs)
  payload=bytearray();records=[]
  for tile in unique:
   encoded,_=packet(tile);records.append((len(payload),len(encoded)));payload.extend(encoded);payload.extend(bytes(-len(payload)%4))
  atlas=struct.pack('<4sI',b'KFC4',len(unique))+b''.join(struct.pack('<II',*r)for r in records)+payload
  return name+('.enemy'if name in JUNGLE_ENEMIES else ''),index,atlas

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--maps',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--map',action='append');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 compiler=Compiler(a.assets,a.maps);rows=[]
 for item in json.loads((a.maps/'inventory.json').read_text()):
  name=item['file']
  if a.map and name not in a.map:continue
  stem,index,atlas=compiler.compile(name);(a.output/(stem+'.index')).write_bytes(index);(a.output/(stem+'.atlas')).write_bytes(atlas)
  row={'map':name,'index_bytes':len(index),'atlas_bytes':len(atlas),'index_sha256':hashlib.sha256(index).hexdigest(),'atlas_sha256':hashlib.sha256(atlas).hexdigest()};rows.append(row);print(json.dumps(row),flush=True)
 if not rows:p.error('No maps selected')
 (a.output/'manifest.json').write_text(json.dumps({'scope':__doc__,'maps':rows},indent=2)+'\n')

if __name__=='__main__':main()
