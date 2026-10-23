"""At a stopped frame boundary, compare actual sub-screen VRAM and loaded backdrop."""
from pathlib import Path
import ctypes as C,struct,subprocess,tempfile,hashlib
from scenery_codec import unpack
from emulator_counters import ROOT,ARTIFACT_DIR,module_bss_symbol

def check(rsp,sym):
 def read32(at):return struct.unpack('<I',rsp.read(at,4))[0]
 if 'hud_native_state' in sym:
  context=rsp.read(module_bss_symbol('hud','indexed_hud'),2584)
  if context[2580]:
   import numpy as np
   from stage_native_bottom_assets import decode_patches
   from verify_native_bottom import compose
   from tile_storage import unlz
   from emulator_counters import ARTIFACT_DIR
   raw=rsp.read(module_bss_symbol('world','rendered_hud'),44);state=struct.unpack('<8i6h',raw);world=state[7]%4
   name=('jungle','ice','factory','fantasy')[world];root=ARTIFACT_DIR/'nitrofs/native_bottom'
   blob=(root/(name+'.nbh')).read_bytes();back=unlz(blob[524:]);count,size,loaded_world,data,background=struct.unpack_from('<5I',context,2048)
   assert loaded_world==world and rsp.read(background,49152)==back,'Native backdrop mismatch'
   hud_blob=(root/'hud.nhp').read_bytes();assert rsp.read(data,size)==hud_blob[16+count*16:],'Native HUD run payload mismatch'
   items=decode_patches(hud_blob);want=compose(items,np.frombuffer(back,dtype='u1').reshape(192,256),state).tobytes()
   indexed=bool(rsp.read(module_bss_symbol('hud','indexed_enabled'),1)[0])
   if not indexed:
    palette=np.frombuffer(blob,dtype='<u2',count=256,offset=12);rgb=palette[np.frombuffer(want,dtype='u1')].astype('<u2').tobytes()
    actual=rsp.read(read32(sym['bottom_pixels']),98304);assert actual==rgb,'CPU bitmap HUD differs from indexed-asset expansion'
    return {'world':world,'pixels':49152,'indexed':False,'sub_screen_vram_byte_equal':True,'sha256':hashlib.sha256(actual).hexdigest()}
   actual=rsp.read(read32(sym['bottom_pixels']),49152);assert actual==want,'Indexed DS HUD differs from independent composition'
   palette=rsp.read(0x05000400,512);got=np.frombuffer(palette,dtype='<u2')&32767;expected=np.frombuffer(blob,dtype='<u2',count=256,offset=12)&32767
   assert np.array_equal(got,expected),'Indexed HUD palette mismatch'
   native_scene='native_scene_render' in sym
   cache_address=0x06010000 if native_scene else 0x06030000
   has_row_cache='static uint16_t *decoded_arena' in (ARTIFACT_DIR/'source/scene.c').read_text()
   if has_row_cache:assert read32(module_bss_symbol('scene','decoded_arena'))==cache_address,'Live H/I row-cache alias'
   else:cache_address=None
   assert rsp.read(0x04000242,1)[0]==(0x81 if native_scene else 0x89),'Unexpected main BG C mapping'
   assert rsp.read(0x04000248,2)==bytes((0x81,0x81)),'H/I must map sub BG'
   return {'world':world,'pixels':49152,'indexed':True,'sub_screen_vram_byte_equal':True,'palette_colors_exact':True,'row_cache_address':hex(cache_address)if cache_address else None,'sha256':hashlib.sha256(actual).hexdigest()}

 state=rsp.read(module_bss_symbol('world','rendered_hud'),44);world=struct.unpack_from('<i',state,28)[0]%4
 name=('jungle','ice','factory','fantasy')[world];pack=(ROOT/'ds/nitrofs/hud_backgrounds'/(name+'.bin')).read_bytes();assert pack[:4]==b'KHB1'
 expected=unpack(pack[12:])[:49152].astype('<u2').tobytes()
 background=rsp.read(read32(module_bss_symbol('legacy_hud'if 'hud_native_state'in sym else 'hud','background')),len(expected));assert background==expected,'DS decoded HUD backdrop differs'
 with tempfile.TemporaryDirectory(prefix='kinder-ds-hud-check-')as td:
  so=Path(td)/'hud.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DHUD_PATH="{ROOT}/ds/nitrofs/hud_bottom.bin"',f'-DHUD_BACKGROUND_ROOT="{ROOT}/ds/nitrofs/hud_backgrounds"',str(ROOT/'ds/source/hud.c'),'-o',str(so)],check=True)
  lib=C.CDLL(str(so));lib.hud_open.restype=lib.hud_set_world_background.restype=C.c_bool;lib.hud_draw_bottom.argtypes=[C.c_void_p,C.c_void_p];assert lib.hud_open()and lib.hud_set_world_background(world)
  output=(C.c_uint16*49152)();raw=C.create_string_buffer(state);lib.hud_draw_bottom(output,raw);lib.hud_close()
  actual=rsp.read(read32(sym['bottom_pixels']),98304);assert actual==bytes(output),'DS bottom-screen VRAM differs from expected HUD'
 return {'world':world,'pixels':49152,'loaded_background_byte_equal':True,'sub_screen_vram_byte_equal':True,'sha256':hashlib.sha256(actual).hexdigest()}
