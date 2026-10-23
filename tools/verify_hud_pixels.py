#!/usr/bin/env python3
import ctypes as C, json,struct,subprocess,sys
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[1]
NATIVE_PRODUCT=(R/'ds/source/native_bottom.c').exists()
HUD_SOURCE=R/'research/hud/legacy-reference/hud.c'if NATIVE_PRODUCT else R/'ds/source/hud.c'
HUD_ASSETS=R/'research/hud/legacy-reference/assets'if NATIVE_PRODUCT else R/'ds/nitrofs'
sys.path.insert(0,str(R/'tools'))
# Independent full original-resolution composition then global center sampling.
class State(C.Structure):_fields_=[(n,C.c_int32) for n in ['score','health','ammo','actor','shot_variant','boss','boss_energy','world']]+[('letters',C.c_int16*6)]
class Command(C.Structure):_fields_=[('resource',C.c_int32),('frame',C.c_int32)]
subprocess.run(['cc','-shared','-fPIC','-I'+str(R/'ds/source'),f'-DHUD_PATH="{HUD_ASSETS}/hud.bin"',str(HUD_SOURCE),'-o','/tmp/kinder_hud_pixels.dylib'],check=True)
lib=C.CDLL('/tmp/kinder_hud_pixels.dylib');lib.hud_open.restype=C.c_bool;lib.hud_draw.argtypes=[C.POINTER(C.c_uint16),C.POINTER(State)];assert lib.hud_open()
base='Animation/Interface/Ingame/';names=['INTERFACEITALY.W01','Boss/BOSSINTERFACE.W01']+[f'Item{i}.w01' for i in range(1,7)]+['ENERGY.W01','SCHUSS.W01','SCHUSSD.W01','ACTORS.W01','Boss/ENERGY.W01','Boss/BOSSPICS.W01','SCHRIFT.W01']
inv={a['source']:a for a in json.loads((R/'generated/assets/inventory.json').read_text())}
def compose(s):
 canvas=Image.new('RGBA',(800,600),(24,72,120,255))
 def draw(r,f,x=None,y=None):
  meta=inv[base+names[r]]['frames'][f];im=Image.open(R/meta['png']).convert('RGBA');canvas.paste(im,(meta['x'] if x is None else x,meta['y'] if y is None else y),im)
 draw(0,0);x=440
 for digit in str(s.score):
  f=int(digit);draw(14,f,x,7);x+=inv[base+names[14]]['frames'][f]['width']
 if s.boss>0:
  draw(1,0)
  if s.boss_energy>=0:draw(12,s.boss_energy)
  draw(13,s.world%4)
 else:
  for i,v in enumerate(s.letters):draw(2+i,int(v>0))
 if s.health>0:draw(8,min(4,(s.health-1)//20))
 if s.ammo>0:draw(10 if s.shot_variant>0 else 9,s.ammo-1)
 draw(11,s.actor)
 px=canvas.load();words=[];preview=Image.new('RGB',(256,192));op=preview.load()
 for y in range(192):
  for x in range(256):
   r,g,b,_=px[((2*x+1)*25)//16,((2*y+1)*25)//16];words.append(0x8000|(r>>3)|((g>>3)<<5)|((b>>3)<<10));op[x,y]=(r,g,b)
 return words,preview
states=[State(0,100,10,0,0,0,9,0,(C.c_int16*6)()),State(1234567890,81,1,1,1,1,0,3,(C.c_int16*6)())]
for i in range(10):states.append(State(i*98765,i*11,i, i%2,i%2,i%2,i-1,i%4,(C.c_int16*6)(*[int(j%2==i%2) for j in range(6)])))
for i,s in enumerate(states):
 expected,im=compose(s);pixels=(C.c_uint16*(256*192))(*([0x8000|3|(9<<5)|(15<<10)]*(256*192)));lib.hud_draw(pixels,C.byref(s));assert list(pixels)==expected,i
 if i==0:im.save(R/'research/hud/initial.png')
lib.hud_close();result=dict(implementation_source=str(HUD_SOURCE),archived_reference=NATIVE_PRODUCT,cases=len(states),pixels_per_case=49152,passed=True,scope='C packed HUD overlay compared byte for byte with independently composed 800x600 original PNG canvas globally sampled to 256x192.')
(R/'research/hud/pixel_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
