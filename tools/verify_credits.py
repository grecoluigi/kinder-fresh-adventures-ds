"""Current credits pages match independently resized original images.
Controller page/end/back behavior is a DS adaptation; not a native fade proof.
"""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
from PIL import Image
R=Path(__file__).resolve().parents[1]
class State(C.Structure):_fields_=[('page',C.c_uint),('active',C.c_bool)]
with tempfile.TemporaryDirectory(prefix='kinder-credits-')as tmp:
 so=Path(tmp)/'credits.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-DCREDITS_ROOT="'+str(R/'ds/nitrofs/credits')+'"',str(R/'ds/source/credits.c'),'-o',str(so)],check=True);c=C.CDLL(str(so));c.credits_draw.restype=c.credits_step.restype=C.c_bool;c.credits_draw.argtypes=[C.POINTER(C.c_uint16),C.c_uint];c.credits_begin.argtypes=[C.POINTER(State)];c.credits_step.argtypes=[C.POINTER(State),C.c_bool,C.c_bool];pixels=(C.c_uint16*49152)();inventory={v['source'].lower():v for v in json.loads((R/'generated/assets/inventory.json').read_text())};comparisons=0
 for page in range(4):
  assert c.credits_draw(pixels,page);item=inventory[f'pics/credit{page+1}.bmp'];image=Image.open(R/item['png']).convert('RGB').resize((256,192),Image.Resampling.NEAREST)
  expected=[(r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000 for r,g,b in image.get_flattened_data()];assert list(pixels)==expected,page;comparisons+=49152
 assert not c.credits_draw(pixels,4) and not c.credits_draw(None,0)
 s=State();c.credits_begin(C.byref(s));assert s.active and s.page==0
 for page in range(4):
  assert s.page==page and s.active;assert not c.credits_step(C.byref(s),False,False);assert c.credits_step(C.byref(s),True,False)
 assert not s.active and s.page==4 and not c.credits_step(C.byref(s),True,False)
 for page in range(4):
  c.credits_begin(C.byref(s))
  for i in range(page):assert c.credits_step(C.byref(s),True,False)
  assert c.credits_step(C.byref(s),True,True) and not s.active and s.page==page
 result={'scope':__doc__,'pages':4,'original_pixel_comparisons':comparisons,'all_pages_return_after_last':True,'back_preempts_advance_each_page':True,'invalid_page_and_null_buffer_rejected':True,'limits':['Original four page images/order preserved. Desktop fade renderer/quit behavior not reproduced; DS returns to its own menu.','Host pixels/controller verified; actual DS button/touch presentation and timings unverified.']};(R/'research/rendering/credits-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
