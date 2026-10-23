"""Verify optional RGB residency survives skipped views and actor-row overwrites.

Dirty actor rows are resampled instead of discarding a lagging window; the
previous invalidate-on-Y policy is replayed alongside to count avoided pixels.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
C=r'''
#include "native_scenery_cache.h"
#include <assert.h>
#include <stdio.h>
static uint16_t texture[256*256];static NativeSceneryWindow cache;
#define window cache.window
static TextureWindow legacy;static unsigned legacy_pixels;
static bool count_legacy(int x,int y,unsigned w,unsigned h,void *ctx){(void)x;(void)y;(void)ctx;legacy_pixels+=w*h;return true;}
static unsigned writes,pixels,checks;
static uint16_t color(unsigned x,unsigned y){return ((x+y)%11u)?(uint16_t)(32768u|((x*3u)&31u)|(((y*5u)&31u)<<5)|(((x^y)&31u)<<10)):0;}
static bool upload(int x,int y,unsigned width,unsigned height,void *ctx){
 (void)ctx;assert(x>=0&&y>=0&&width&&height&&width<=256&&height<=192);
 for(unsigned yy=0;yy<height;yy++)for(unsigned xx=0;xx<width;xx++)texture[(((unsigned)y+yy)&255u)*256u+(((unsigned)x+xx)&255u)]=color((unsigned)x+xx,(unsigned)y+yy);
 writes++;pixels+=width*height;return true;
}
static void check(int x,int y){
 assert(window.valid&&window.x==x&&window.y==y);
 for(unsigned yy=0;yy<192;yy++)for(unsigned xx=0;xx<256;xx++)assert(texture[(((unsigned)y+yy)&255u)*256u+(((unsigned)x+xx)&255u)]==color((unsigned)x+xx,(unsigned)y+yy));checks++;
}
int main(void){
 int x=0,y=0,dx=3,dy=2;unsigned needed_frames=0,skipped_frames=0;
 assert(!native_scenery_cache_prepare(NULL,false,0,0,upload,NULL));assert(!native_scenery_cache_prepare(&cache,false,-1,0,upload,NULL));
 for(unsigned frame=0;frame<4096;frame++){
  /* Long quiet spans and Y reversals expose stale windows after actor data
   * occupied rows which used to contain immutable scenery. */
  bool needed=frame%97u>=55u||frame%13u==0u;
  unsigned before=writes;assert(native_scenery_cache_prepare(&cache,needed,x,y,upload,NULL));
  if(!needed){if(legacy.valid&&legacy.y!=y)legacy.valid=false;}else assert(texture_window_update(&legacy,x,y,count_legacy,NULL));
  if(needed){check(x,y);needed_frames++;}else{assert(writes==before);skipped_frames++;}
  for(unsigned yy=192;yy<256;yy++)for(unsigned xx=0;xx<256;xx++)texture[(((unsigned)y+yy)&255u)*256u+xx]=0x8bad;
  native_scenery_cache_overwrite(&cache,y);
  if(needed)check(x,y);
  if(frame%17u==0u){native_scenery_cache_invalidate(&cache);legacy.valid=false;} /* capture/bitmap/palette invalidation */
  x+=dx;y+=dy;if(x>1024){x=1024;dx=-3;}else if(x<0){x=0;dx=3;}
  if(y>768){y=768;dy=-2;}else if(y<0){y=0;dy=2;}
  if(frame%101u==0u)y=(int)((frame*37u)%769u);
 }
 assert(needed_frames&&skipped_frames&&checks==needed_frames*2);
 printf("{\"views\":4096,\"needed_views\":%u,\"skipped_views\":%u,\"complete_pixel_checks\":%u,\"upload_rectangles\":%u,\"uploaded_pixels\":%u,\"legacy_policy_pixels\":%u}\n",needed_frames,skipped_frames,checks*49152u,writes,pixels,legacy_pixels);
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--source-dir',type=Path,default=R/'ds/source');a=p.parse_args();header=a.source_dir/'native_scenery_cache.h'
 with tempfile.TemporaryDirectory(prefix='kinder-optional-scenery-')as td:
  d=Path(td);source=d/'test.c';source.write_text(C);exe=d/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(header.parent),str(source),'-o',str(exe)],check=True);r=subprocess.run([str(exe)],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
  report=json.loads(r.stdout)
 report.update(scope=__doc__,source_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),sanitizers=['address','undefined'],limits=['Host wrapping-texture model; actual GPU rendering and game timing have separate tests.']);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
