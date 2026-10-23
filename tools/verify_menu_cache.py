"""Check all cached original menu states and focus transitions pixel for pixel."""
import argparse,ctypes as C,json,subprocess,tempfile
from pathlib import Path
from decoded_assets import DecodedAssets
from menu_build import render_screens
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--decoded-assets',type=Path,required=True,help='Decoded original menu artwork');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
expected_screens,_=render_screens(DecodedAssets(args.decoded_assets))
names=['menu_normal_lz']+[f'menu_focus_{i}_patch' for i in range(6)]
with tempfile.TemporaryDirectory(prefix='kinder-menu-cache-') as temporary:
 t=Path(temporary);definitions=[]
 for name in names:
  data=(args.assets/f'{name}.bin').read_bytes();symbol=name+'_bin'
  (t/(symbol+'.h')).write_text(f'extern const unsigned char {symbol}[];\nextern const unsigned int {symbol}_size;\n')
  definitions.append(f'const unsigned char {symbol}[] __attribute__((aligned(4)))={{'+','.join(map(str,data))+'};\n'+f'const unsigned int {symbol}_size={len(data)};\n')
 (t/'assets.c').write_text(''.join(definitions));so=t/'menu.dylib'
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(t),str(R/'ds/source/menu_graphics.c'),str(t/'assets.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.menu_graphics_pixels.argtypes=[C.c_int];c.menu_graphics_pixels.restype=C.POINTER(C.c_uint16)
 visits=0
 for previous in range(-1,6):
  for focus in range(-1,6):
   assert c.menu_graphics_pixels(previous)
   p=c.menu_graphics_pixels(focus);assert p and C.addressof(p.contents)%32==0
   expected=expected_screens[focus+1]
   assert C.string_at(p,98304)==expected,(previous,focus)
   assert C.string_at(c.menu_graphics_pixels(focus),98304)==expected
   visits+=1
 for focus in (-100,-2,6,100):assert not c.menu_graphics_pixels(focus)
 result={'scope':__doc__,'focus_transitions':visits,'cached_repeat_checks':visits,'pixels_per_screen':49152,'all_RGB555_bytes_equal':True,'invalid_focus_checks':4,'limits':['Host decoder and patch validation; DS BIOS execution and DMA presentation need runtime checks.']}
 args.output.parent.mkdir(parents=True,exist_ok=True)
 args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
