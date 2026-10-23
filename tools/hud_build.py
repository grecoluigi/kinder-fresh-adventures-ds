"""Build bottom HUD patches and level backdrops from decoded original artwork.

RGB555 patches are offline inputs to the native indexed packer; the obsolete
full-screen HUD format is not generated.
"""
from pathlib import Path
import argparse,json,struct
from PIL import Image
from decoded_assets import DecodedAssets

NAMES=['INTERFACEITALY.W01','Boss/BOSSINTERFACE.W01']+[f'Item{i}.w01' for i in range(1,7)]+['ENERGY.W01','SCHUSS.W01','SCHUSSD.W01','ACTORS.W01','Boss/ENERGY.W01','Boss/BOSSPICS.W01','SCHRIFT.W01']

def build(decoded,output):
 output.mkdir(parents=True,exist_ok=False)
 assets=DecodedAssets(decoded)
 inv={item['source']:item for item in assets.inventory.values()}
 base='Animation/Interface/Ingame/';names=NAMES
 # DS bottom-screen adaptation. Each cluster uses one uniform scale, preserving
 # its original sprite alignment. Original native HUD command semantics stay intact.
 bottom_records=[];bottom_data=bytearray();bottom_manifest=[]
 def bottom_patch(rid,frame,im,left,top):
  pixels=im.load();w,h=im.size
  bottom_records.append(struct.pack('<IHHhhHH',len(bottom_data)//2,w,h,left,top,rid,frame))
  for yy in range(h):
   xx=0;cursor=0
   while xx<w:
    if not pixels[xx,yy][3]: xx+=1;continue
    start=xx;run=[]
    while xx<w and pixels[xx,yy][3]:
     r,g,b,_=pixels[xx,yy];run.append(0x8000|(r>>3)|((g>>3)<<5)|((b>>3)<<10));xx+=1
    bottom_data.extend(struct.pack('<HH',start-cursor,len(run)))
    bottom_data.extend(struct.pack('<'+'H'*len(run),*run));cursor=xx
   bottom_data.extend(struct.pack('<HH',0,0))
  bottom_manifest.append(dict(resource=rid,frame=frame,width=w,height=h,x=left,y=top))
 def sample_positioned(im,x,y,scale,origin):
  # Center sampling on a shared cluster lattice keeps overlapping frame borders aligned.
  left=round(x*scale);top=round(y*scale);right=round((x+im.width)*scale);end=round((y+im.height)*scale)
  out=Image.new('RGBA',(right-left,end-top));ip=im.load();op=out.load()
  for yy in range(out.height):
   sy=min(im.height-1,max(0,int((top+yy+.5)/scale)-y))
   for xx in range(out.width):
    sx=min(im.width-1,max(0,int((left+xx+.5)/scale)-x));op[xx,yy]=ip[sx,sy]
  return out,left+origin[0],top+origin[1]
 for rid,name in enumerate(names):
  for f in inv[base+name]['frames']:
   im=assets.image(f);x,y=f['x'],f['y']
   if rid==0: im=im.crop((0,0,140,229));x=y=0;scale=192/229;origin=(0,0)
   elif rid==1 or rid in (12,13): scale=.5;origin=(-144,86)
   elif 2<=rid<=7:
    slot=rid-2;scale=1.;origin=(122+(slot%3)*45-544-38*slot,72+(slot//3)*48)
    # Retain small per-frame movement within each original slot.
    x=f['x'];y=f['y']
   elif rid==14:
    bottom_patch(rid,f['index'],im,0,0)
    for resource,scale in ((16,1.5),(17,2.)):
     enlarged=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST)
     bottom_patch(resource,f['index'],enlarged,0,0)
    continue
   else: scale=192/229;origin=(0,0)
   out,left,top=sample_positioned(im,x,y,scale,origin);bottom_patch(rid,f['index'],out,left,top)
 baseim=assets.image(inv[base+names[0]]['frames'][0])
 # Original PUNTI tab, cropped from the long header. No new text or colors.
 label=baseim.crop((342,0,520,32)).resize((134,24),Image.Resampling.NEAREST)
 bottom_patch(15,0,label,122,0)
 target=output/'hud_bottom.bin';target.write_bytes(b'KFH2'+struct.pack('<II',len(bottom_records),len(bottom_data)//2)+b''.join(bottom_records)+bottom_data)
 (output/'hud-manifest.json').write_text(json.dumps(dict(bytes=target.stat().st_size,pixel_bytes=len(bottom_data),frames=bottom_manifest),indent=2)+'\n')
 print(f'{len(bottom_records)} bottom patches; {len(bottom_data)} resident pixel bytes')

 from hud_background_build import build as build_backgrounds
 build_backgrounds(decoded,output/'hud_backgrounds')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.assets,a.output)
