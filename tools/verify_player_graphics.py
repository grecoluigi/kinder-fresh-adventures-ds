"""Verify original alignment, mirror and uniform viewport sampling of packed character frames."""
from pathlib import Path
import ctypes,struct,json,subprocess,random
from PIL import Image
root=Path(__file__).resolve().parents[1]
subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DPLAYER_ROOT="{root}/ds/nitrofs/players"',str(root/'ds/source/player_graphics.c'),'-o','/tmp/kinder_player_graphics.dylib'],check=True)
c=ctypes.CDLL('/tmp/kinder_player_graphics.dylib');c.player_graphics_open.restype=ctypes.c_bool;c.player_graphics_draw.restype=ctypes.c_bool;assert c.player_graphics_open()
inventory=json.loads((root/'generated/assets/inventory.json').read_text());rng=random.Random(20020117);cases=0
for character,name in enumerate(['PINGUIN','MILCHSCHNITTE']):
 asset=next(a for a in inventory if a['source']==f'Animation/{name}.W01')
 for frame in sorted(set([0,47,75,len(asset['frames'])-1]+[rng.randrange(len(asset['frames'])) for _ in range(20)])):
  meta=asset['frames'][frame];sprite=Image.open(root/meta['png']).convert('RGBA')
  for facing in [0,1]:
   bx,by,cx,cy=500,550,87,24
   expected=Image.new('RGBA',(800,600),(0,0,0,255));im=sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if facing==0 else sprite
   x=bx+(-meta['x']-im.width if facing==0 else meta['x'])-cx;y=by+meta['y']-cy
   expected.alpha_composite(im,(x,y));expected=expected.resize((256,192),Image.Resampling.NEAREST)
   raw=struct.pack('<'+'H'*49152,*[(r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000 for r,g,b,a in expected.get_flattened_data()])
   output=(ctypes.c_uint16*49152)(*([0x8000]*49152));assert c.player_graphics_draw(output,character,frame,facing,bx,by,cx,cy)
   assert bytes(output)==raw,(name,frame,facing);cases+=1
c.player_graphics_close();result=dict(cases=cases,failures=[],scope='Packed original pixels, native alignment/mirror equations and exact uniform256x192 nearest sampling against independent Pillow viewport composition; no native drawing or DS performance claim.')
(root/'research/rendering/player_graphics_verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
