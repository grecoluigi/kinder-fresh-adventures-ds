"""Compare every streamed/resident map cell to its original extracted three bytes."""
import ctypes as C,json,os,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];out=Path(os.environ.get('KF_SCENE_OUTPUT_ROOT',str(R/'ds/nitrofs/scenes')))
with tempfile.TemporaryDirectory(prefix='kinder-cell-reader-') as temporary:
 so=Path(temporary)/'scene.dylib'
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DSCENE_ROOT="{out}"',*[str(R/'ds/source'/f'{n}.c') for n in ('scene','composite','collision')],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.scene_open.argtypes=[C.c_char_p];c.scene_open.restype=C.c_bool
 c.scene_collision_map.restype=C.c_void_p
 c.collision_cell.argtypes=[C.c_void_p,C.c_uint,C.c_uint,C.c_uint];c.collision_cell.restype=C.POINTER(C.c_uint8)
 cases=[]
 for item in json.loads((R/'generated/maps/inventory.json').read_text()):
  name=item['file'];d=json.loads((R/'generated/maps'/name/'00.json').read_text());raw=(R/'generated/maps'/name/'00.tiles.bin').read_bytes()
  w,h,layers=d['width_cells'],d['height_cells'],d['layers'];assert c.scene_open(name.encode());m=c.scene_collision_map()
  checked=0
  for layer in range(layers):
   for y in range(h):
    for x in range(w):
     p=c.collision_cell(m,layer,x,y);expected=raw[3*((layer*h+y)*w+x):3*((layer*h+y)*w+x)+3]
     assert p and C.string_at(p,3)==expected,(name,layer,x,y);checked+=1
  assert not c.collision_cell(m,layers,0,0) and not c.collision_cell(m,0,w,0) and not c.collision_cell(m,0,0,h)
  cases.append({'map':name,'cells_checked':checked,'all_layers_equal':True});c.scene_close()
 result={'scope':__doc__,'asset_root':str(out),'maps':cases,'cells_checked':sum(x['cells_checked'] for x in cases),'limits':['Host file-backed cell reader and bounds, not DS storage timing.']}
 (R/'research/gameplay/scene_cell_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
