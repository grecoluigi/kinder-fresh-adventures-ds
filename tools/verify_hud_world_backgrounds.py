"""Baked backdrop plus unchanged HUD vs independent original-PNG composition."""
from pathlib import Path
import ctypes as C,subprocess,tempfile,json,struct,shutil
import numpy as np
from PIL import Image
from tile_storage import packet
from verify_hud_bottom import expected,State,states
R=Path(__file__).resolve().parents[1]
NATIVE_PRODUCT=(R/'ds/source/native_bottom.c').exists()
HUD_SOURCE=R/'research/hud/legacy-reference/hud.c'if NATIVE_PRODUCT else R/'ds/source/hud.c'
HUD_ASSETS=R/'research/hud/legacy-reference/assets'if NATIVE_PRODUCT else R/'ds/nitrofs'

with tempfile.TemporaryDirectory(prefix='kinder-hud-background-') as td:
 t=Path(td)
 for p in (HUD_ASSETS/'hud_backgrounds').glob('*.bin'):shutil.copyfile(p,t/p.name)
 src=t/'hud.c';src.write_text('#include "'+str(HUD_SOURCE)+'"\nint background_loaded(void){return background!=NULL;}\n')
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),f'-DHUD_PATH="{HUD_ASSETS}/hud_bottom.bin"',f'-DHUD_BACKGROUND_ROOT="{t}"',str(src),'-o',str(t/'test.dylib')],check=True)
 lib=C.CDLL(str(t/'test.dylib'));lib.hud_open.restype=lib.hud_set_world_background.restype=C.c_bool;lib.hud_set_world_background.argtypes=[C.c_uint];lib.hud_draw_bottom.argtypes=[C.c_void_p,C.POINTER(State)];cases=0
 assert lib.hud_open();buf=np.full(49152+32,0x1234,dtype=np.uint16)
 for world,(name,asset)in enumerate([('jungle','Welt1'),('ice','Welt2'),('factory','WELT3'),('fantasy','WELT4')]):
  raw=np.asarray(Image.open(R/f'generated/assets/frames/Maps/{asset}/004.png').convert('RGB').crop((0,0,800,600)).resize((256,192),Image.Resampling.NEAREST),dtype=np.uint16)*3//4
  im=Image.fromarray(raw.astype('u1'));assert lib.hud_set_world_background(world)
  path=t/(name+'.bin');initial=path.read_bytes();path.unlink() # redraws must use only resident pixels
  for original in states:
   for arena in (False,True):
    state=State.from_buffer_copy(original);state.world=world+(4 if arena else 0)
    want,_=expected(state,im);buf.fill(0x1234);lib.hud_draw_bottom(buf[16:].ctypes.data,C.byref(state))
    assert np.array_equal(buf[16:-16],np.asarray(want,dtype=np.uint16)),(world,arena,state.score)
    assert np.all(buf[:16]==0x1234)and np.all(buf[-16:]==0x1234);cases+=1
  path.write_bytes(initial)
 assert not lib.hud_set_world_background(4);assert not lib.background_loaded()
 path=t/'jungle.bin';good=path.read_bytes();bad=[]
 bad.extend([b'',good[:11],good[:-1],good+b'x',b'BAD!'+good[4:]])
 for at,value in [(4,255),(6,191)]:
  b=bytearray(good);struct.pack_into('<H',b,at,value);bad.append(bytes(b))
 for size in (0,7,110001):
  b=bytearray(good);struct.pack_into('<I',b,8,size);bad.append(bytes(b))
 encoded,_=packet(bytes(98304));bad.append(struct.pack('<4sHHI',b'KHB1',256,192,len(encoded))+encoded)
 for fixture in bad:
  path.write_bytes(fixture);assert not lib.hud_set_world_background(0);assert not lib.background_loaded()
  state=states[0];want,_=expected(state);lib.hud_draw_bottom(buf[16:].ctypes.data,C.byref(state));assert np.array_equal(buf[16:-16],want)
 path.write_bytes(good);assert lib.hud_set_world_background(0);lib.hud_close();assert not lib.background_loaded()
 result={'scope':__doc__,'implementation_source':str(HUD_SOURCE),'archived_reference':NATIVE_PRODUCT,'composition_cases':cases,'malformed_or_transparent_files':len(bad),'file_removed_after_load_redraws_exact':True,'all_world_and_arena_ids':list(range(8)),'guards_intact':True,'fallback_gray_exact':True,'overlay_black_percent':25,'limits':['Host exact pixels/lifecycle; DS runtime publication and timing verified separately.']}
 (R/'research/hud/world-background-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
