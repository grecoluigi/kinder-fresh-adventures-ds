#!/usr/bin/env python3
"""Check intentional DS layout against independent positioned PNG composition."""
import ctypes as C,json,subprocess
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[1]
NATIVE_PRODUCT=(R/'ds/source/native_bottom.c').exists()
HUD_SOURCE=R/'research/hud/legacy-reference/hud.c'if NATIVE_PRODUCT else R/'ds/source/hud.c'
HUD_ASSETS=R/'research/hud/legacy-reference/assets'if NATIVE_PRODUCT else R/'ds/nitrofs'

class State(C.Structure):_fields_=[(n,C.c_int32) for n in ['score','health','ammo','actor','shot_variant','boss','boss_energy','world']]+[('letters',C.c_int16*6)]
subprocess.run(['cc','-shared','-fPIC','-I'+str(R/'ds/source'),'-Wall','-Wextra','-Werror',f'-DHUD_PATH="{HUD_ASSETS}/hud_bottom.bin"',str(HUD_SOURCE),'-o','/tmp/kinder_hud_bottom.dylib'],check=True)
lib=C.CDLL('/tmp/kinder_hud_bottom.dylib');lib.hud_open.restype=C.c_bool;lib.hud_draw_bottom.argtypes=[C.POINTER(C.c_uint16),C.POINTER(State)];assert lib.hud_open()
base='Animation/Interface/Ingame/';names=['INTERFACEITALY.W01','Boss/BOSSINTERFACE.W01']+[f'Item{i}.w01' for i in range(1,7)]+['ENERGY.W01','SCHUSS.W01','SCHUSSD.W01','ACTORS.W01','Boss/ENERGY.W01','Boss/BOSSPICS.W01','SCHRIFT.W01']
inv={a['source']:a for a in json.loads((R/'generated/assets/inventory.json').read_text())}
def asset(r,f):
 m=inv[base+names[r]]['frames'][f];return Image.open(R/m['png']).convert('RGBA'),m

def expected(s,backdrop=None):
 out=Image.new('RGBA',(256,192),(165,166,165,255)) if backdrop is None else backdrop.convert('RGBA').copy()
 def positioned(r,f,scale,origin,crop=None):
  im,m=asset(r,f);x,y=m['x'],m['y']
  if crop:im=im.crop(crop);x=y=0
  # Independently paste at integer original coordinates and sample a complete
  # source coordinate canvas, rather than reading the packed patch records.
  canvas=Image.new('RGBA',(1000,600));canvas.paste(im,(x,y))
  l,t=round(x*scale),round(y*scale);rr,bb=round((x+im.width)*scale),round((y+im.height)*scale)
  for dy in range(t,bb):
   sy=min(y+im.height-1,max(y,int((dy+.5)/scale)))
   for dx in range(l,rr):
    sx=min(x+im.width-1,max(x,int((dx+.5)/scale)));p=canvas.getpixel((sx,sy));xx=origin[0]+dx;yy=origin[1]+dy
    if p[3] and 0<=xx<256 and 0<=yy<192:out.putpixel((xx,yy),p)
 im,_=asset(0,0);label=im.crop((342,0,520,32)).resize((134,24),Image.Resampling.NEAREST);out.paste(label,(122,0),label)
 positioned(0,0,192/229,(0,0),(0,0,140,229))
 x=124;digits=[asset(14,int(d))[0]for d in str(s.score)if d.isdigit()]
 scale=next(scale for scale in (2.,1.5,1.)if sum(round(im.width*scale)for im in digits)<=128)
 for im in digits:
  im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST)
  out.paste(im,(x,33),im);x+=im.width
 if s.boss>0:
  positioned(1,0,.5,(-144,86))
  if s.boss_energy>=0:positioned(12,s.boss_energy,.5,(-144,86))
  positioned(13,s.world%4,.5,(-144,86))
 else:
  for slot,v in enumerate(s.letters):positioned(slot+2,int(v>0),1.,(122+slot%3*45-544-38*slot,72+slot//3*48))
 if s.health>0:positioned(8,min(4,(s.health-1)//20),192/229,(0,0))
 if s.ammo>0:positioned(10 if s.shot_variant else 9,s.ammo-1,192/229,(0,0))
 positioned(11,s.actor,192/229,(0,0))
 words=[0x8000|(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b,a in out.get_flattened_data()]
 return words,out
states=[State(0,100,10,0,0,0,9,0,(C.c_int16*6)()),State(1234567890,100,10,1,1,0,9,3,(C.c_int16*6)(1,1,1,1,1,1))]
for i in range(10):states.append(State(i*98765,i*11,i,i%2,i%2,i%2,i-1,i%4,(C.c_int16*6)(*[int(j%2==i%2) for j in range(6)])))
for score in (1,99999,888888,111111,88888888,2147483647,-2147483648):states.append(State(score,100,10,0,0,0,9,0,(C.c_int16*6)()))
for i,s in enumerate(states):
 want,im=expected(s);px=(C.c_uint16*49152)(*([0x801F]*49152));lib.hud_draw_bottom(px,C.byref(s));assert list(px)==want,i
 if i<2:im.convert('RGB').save(R/f'research/hud/bottom_{i}.png')
layout=json.loads((R/'research/hud/bottom_assets.json').read_text())['frames']
for patch in layout:
 if patch['resource'] in (14,16,17):continue
 assert not(patch['x']<252 and patch['x']+patch['width']>124 and patch['y']<59 and patch['y']+patch['height']>33),patch
lib.hud_close();result=dict(implementation_source=str(HUD_SOURCE),archived_reference=NATIVE_PRODUCT,cases=len(states),pixels_per_case=49152,passed=True,score_lane=[124,33,252,59],font_scales=[2,1.5,1],no_other_patch_rectangle_overlap=True,scope='Intentional bottom-screen DS adaptation; C row-run renderer compared with independently positioned original PNG sprites at declared cluster scales, including palette gray clearing and original HUD state selection.')
(R/'research/hud/bottom_pixel_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
