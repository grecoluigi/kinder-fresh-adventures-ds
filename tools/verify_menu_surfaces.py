"""Compile production menu draw helpers with deterministic graphics/DMA providers.
Verify root/pause destinations; menu art and controller have separate checks.
"""
from pathlib import Path
import ctypes as C,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1];source=(R/'ds/source/main.c').read_text();helpers=source[source.index('static void render_bottom_menu'):source.index('static void play_menu_music')]
with tempfile.TemporaryDirectory(prefix='kinder-menu-surfaces-')as tmp:
 t=Path(tmp);wrapper=t/'surfaces.c';wrapper.write_text('''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
static uint16_t top[49152],bottom[49152],image[49152];static uint16_t*top_pixels=top,*bottom_pixels=bottom;
static int menu_focus_index(void){return 0;}
static const uint16_t*menu_graphics_pixels(int focus){(void)focus;return image;}
static void frame_transfer(uint16_t*destination,const uint16_t*source){memcpy(destination,source,49152*2);}
static void dmaFillHalfWords(uint16_t color,uint16_t*destination,size_t bytes){for(size_t i=0;i<bytes/2;i++)destination[i]=color;}
'''+helpers+'''
void test_prepare(void){for(unsigned i=0;i<49152;i++){top[i]=0x9234;bottom[i]=0x9456;image[i]=(uint16_t)(0x8000|(i&0x7fff));}}
void test_root(void){render_menu();}void test_pause(void){render_bottom_menu();}
const uint16_t*test_top(void){return top;}const uint16_t*test_bottom(void){return bottom;}const uint16_t*test_image(void){return image;}
''');so=t/'surfaces.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(wrapper),'-o',str(so)],check=True);c=C.CDLL(str(so))
 for fn in ('test_top','test_bottom','test_image'):getattr(c,fn).restype=C.POINTER(C.c_uint16)
 c.test_prepare();c.test_root();assert list(c.test_top()[:49152])==[0x8000]*49152;assert list(c.test_bottom()[:49152])==list(c.test_image()[:49152])
 c.test_prepare();c.test_pause();assert list(c.test_top()[:49152])==[0x9234]*49152;assert list(c.test_bottom()[:49152])==list(c.test_image()[:49152])
 assert 'if ((down & KEY_TOUCH) && (!active_world || bottom_visible))'in source
 assert 'if (active_world && (down & KEY_START))'in source
 assert 'showing_scores=true;scores_on_bottom=true;'in source
 assert 'scores_on_bottom=false;'in source # Completion/name flow remains top/keyboard.
 result={'scope':__doc__,'root_menu_bottom_top_blank':True,'pause_menu_preserves_top_scene':True,'pixel_destination_checks':49152*4,'root_touch_enabled':True,'pause_toggle_only_during_gameplay':True,'menu_highscore_viewer_on_bottom':True,'completion_name_flow_retained':True,'limits':['Draw providers replace SDK DMA and menu graphics; actual menu asset pixels/controller checked separately.','Main routing assertions are source checks,not complete DS UI execution; hardware verification pending.']};(R/'research/gameplay/menu-surfaces-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
