"""Independent exposed-region oracle, failed-upload recovery and coordinate bounds."""
from pathlib import Path
import ctypes as C, subprocess, tempfile, random, json
import numpy as np
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-texture-window-')as td:
 t=Path(td);src=t/'window.c';src.write_text('''#include "texture_window.h"
static TextureWindow window;
static unsigned char coverage[256*192];
static int view_x,view_y,fail_call,calls;
static bool upload(int x,int y,unsigned width,unsigned height,void *context){
 (void)context;calls++;if(calls==fail_call)return false;
 if(x<view_x||y<view_y||x-view_x+(int)width>256||y-view_y+(int)height>192)return false;
 for(unsigned row=0;row<height;row++)for(unsigned col=0;col<width;col++)coverage[(y-view_y+(int)row)*256+x-view_x+(int)col]++;
 return true;
}
void reset(void){window=(TextureWindow){0};}
bool update(int x,int y,int fail){view_x=x;view_y=y;calls=0;fail_call=fail;for(unsigned i=0;i<256*192;i++)coverage[i]=0;return texture_window_update(&window,x,y,upload,0);}
bool valid(void){return window.valid;}
const unsigned char *mask(void){return coverage;}
''')
 so=t/'window.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),str(src),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.update.argtypes=[C.c_int,C.c_int,C.c_int];c.update.restype=c.valid.restype=C.c_bool;c.mask.restype=C.POINTER(C.c_uint8)
 rng=random.Random(2001);old=None;cases=0
 path=[(0,0),(1,0),(0,0),(255,191),(256,192),(511,383),(512,384),(512,384),(2**31-257,2**31-193),(0,0)]
 x=y=500
 for i in range(2000):
  x=max(0,x+rng.choice([-300,-193,-17,-16,-1,0,1,16,17,193,300]));y=max(0,y+rng.choice([-257,-192,-16,-1,0,1,16,192,257]));path.append((x,y))
 for x,y in path:
  assert c.update(x,y,0)and c.valid()
  xx=np.arange(256,dtype=np.int64)+x;yy=np.arange(192,dtype=np.int64)+y
  expected=np.ones((192,256),dtype=np.uint8)if old is None else (~((xx[None,:]>=old[0])&(xx[None,:]<old[0]+256)&(yy[:,None]>=old[1])&(yy[:,None]<old[1]+192))).astype(np.uint8)
  actual=np.ctypeslib.as_array(c.mask(),shape=(49152,)).reshape(192,256)
  assert np.array_equal(actual,expected),(old,(x,y),'exposed-region set difference')
  old=(x,y);cases+=1
 # Abort on each possible rectangle, then require a complete next publication.
 recovery=0
 for fail in range(1,5):
  c.reset();assert c.update(500,500,0)
  # Four rectangles are impossible in a single translated equal-size viewport;
  # at most one vertical and one horizontal strip are needed. Exercise every
  # actually emitted rectangle for both diagonal directions instead.
  for target in [(503,507),(497,493)]:
   c.reset();assert c.update(500,500,0)
   ok=c.update(*target,fail)
   if fail<=2:
    assert not ok and not c.valid();assert c.update(*target,0)and c.valid()
    assert np.all(np.ctypeslib.as_array(c.mask(),shape=(49152,))==1);recovery+=1
   else:assert ok and c.valid()
 for x,y in [(-1,0),(0,-1),(2**31-256,0),(0,2**31-192)]:
  assert not c.update(x,y,0);assert c.valid() # Last valid publication remains intact.
 result={'scope':__doc__,'set_difference_cases':cases,'failed_upload_recoveries':recovery,'invalid_coordinate_cases':4,'all_masks_exact':True,'limits':['Host scheduling correctness, not DS VRAM access or display timing.']}
 (R/'research/rendering/texture-window-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
