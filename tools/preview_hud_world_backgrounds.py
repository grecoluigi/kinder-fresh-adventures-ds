"""Compose the unchanged production HUD over static, darkened original map backgrounds."""
from pathlib import Path
import ctypes as C,subprocess,tempfile,json
import numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1]
class State(C.Structure):
 _fields_=[(n,C.c_int32)for n in ['score','health','ammo','actor','shot_variant','boss','boss_energy','world']]+[('letters',C.c_int16*6)]
with tempfile.TemporaryDirectory(prefix='kinder-hud-preview-') as td:
 t=Path(td);src=t/'hud.c';code=(R/'ds/source/hud.c').read_text();assert code.count('pixels[i]=0xd294;')==1
 src.write_text(code.replace('pixels[i]=0xd294;','pixels[i]=0;'))
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),f'-DHUD_PATH="{R}/ds/nitrofs/hud_bottom.bin"',str(src),'-o',str(t/'hud.dylib')],check=True)
 lib=C.CDLL(str(t/'hud.dylib'));lib.hud_open.restype=C.c_bool;lib.hud_draw_bottom.argtypes=[C.c_void_p,C.POINTER(State)];assert lib.hud_open()
 out=R/'research/hud/world-background-previews';out.mkdir(exist_ok=True);sheet=Image.new('RGB',(1024,816),(40,40,40));draw=ImageDraw.Draw(sheet);manifest=[]
 for world,(name,asset)in enumerate([('Jungle','Welt1'),('Ice','Welt2'),('Factory','WELT3'),('Fantasy','WELT4')]):
  source=R/f'generated/assets/frames/Maps/{asset}/004.png';im=Image.open(source).convert('RGB').crop((0,0,800,600)).resize((256,192),Image.Resampling.NEAREST)
  # The requested25%black overlay is applied once, before RGB555 conversion.
  rgb=np.asarray(im,dtype=np.uint16)*3//4
  words=(0x8000|(rgb[:,:,0]>>3)|((rgb[:,:,1]>>3)<<5)|((rgb[:,:,2]>>3)<<10)).astype(np.uint16)
  state=State(12340,80,6,0,0,0,9,world,(C.c_int16*6)(1,0,1,0,1,0));hud=np.zeros(49152,dtype=np.uint16);lib.hud_draw_bottom(hud.ctypes.data,C.byref(state));hud=hud.reshape(192,256);pixels=np.where(hud&0x8000,hud,words)
  color=np.stack(((pixels&31)*255//31,((pixels>>5)&31)*255//31,((pixels>>10)&31)*255//31),axis=2).astype('u1');preview=Image.fromarray(color);preview.save(out/(name.lower()+'.png'))
  x=world%2*512;y=world//2*408;draw.text((x+8,y+7),name+' — 25% black',fill='white');sheet.paste(preview.resize((512,384),Image.Resampling.NEAREST),(x,y+24))
  manifest.append({'world':name,'source':str(source.relative_to(R)),'preview':str((out/(name.lower()+'.png')).relative_to(R)),'overlay':'25% black baked before RGB555','dimensions':[256,192],'hud':'Unchanged production patch renderer; sample score/health/ammo/ingredients.'})
 sheet.save(out/'contact-sheet.png');(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');lib.hud_close();print(out/'contact-sheet.png')
