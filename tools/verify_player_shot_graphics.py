"""Independent original projectile images, screen-edge clipping and ten-shot ordering."""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
from PIL import Image
R=Path(__file__).resolve().parents[1]
class Pool(C.Structure):_fields_=[('bytes',C.c_uint8*1000)]
asset=next(a for a in json.loads((R/'generated/assets/inventory.json').read_text()) if a['source']=='Animation/PINGUIN.W01')
with tempfile.TemporaryDirectory(prefix='kinder-player-shot-pixels-') as tmp:
 so=Path(tmp)/'shots.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DPROJECTILE_ROOT="{R}/ds/nitrofs/projectiles"',str(R/'ds/source/projectiles.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.projectile_graphics_open.restype=c.projectiles_draw.restype=C.c_bool;c.projectiles_draw.argtypes=[C.POINTER(Pool),C.POINTER(C.c_uint16),C.c_int,C.c_int];assert c.projectile_graphics_open();pixels=(C.c_uint16*49152)();cases=0
 for count in (1,10):
  for phase in range(25):
   for anchor in [(1234,755),(1014,620),(1820,1215),(1820,620)]:
    raw=bytearray(1000);canvas=Image.new('RGBA',(800,600),(0,0,0,255));cx,cy=1024,624
    for i in range(count):
     frame=261 if (phase+i)%2==0 else 232;f=asset['frames'][frame];image=Image.open(R/f['png']).convert('RGBA');assert set(image.getchannel('A').get_flattened_data())<={0,255}
     px=anchor[0]+phase+i*3-f['x']+.75;py=anchor[1]+phase-i*2-f['y']+.25
     struct.pack_into('<2f',raw,i*100+12,px,py);struct.pack_into('<I',raw,i*100+44,frame);struct.pack_into('<I',raw,i*100+64,1+i%2)
     canvas.alpha_composite(image,(int(px)+f['x']-cx,int(py)+f['y']-cy))
    pool=Pool.from_buffer_copy(raw);C.memset(pixels,0,49152*2)
    for i in range(49152):pixels[i]=0x8000
    assert c.projectiles_draw(C.byref(pool),pixels,cx,cy)
    expected=struct.pack('<49152H',*[(r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000 for r,g,b,a in canvas.resize((256,192),Image.Resampling.NEAREST).get_flattened_data()])
    assert bytes(pixels)==expected,(count,phase,anchor);cases+=1
 result={'scope':__doc__,'images':cases,'source_frames':[261,232],'pool_sizes':[1,10],'horizontal_vertical_sampling_phases':25,'pixels_per_image':49152,'limits':['Host original PNG/placement/occlusion comparison; device drawing cost and gameplay remain separate.']};(R/'research/projectiles/graphics-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
