#!/usr/bin/env python3
"""Verify demand-sampled occluder texels in a wrapping 256x256 texture.

Random camera walks (including long jumps and reversals) request random clipped
occluder rectangles; actor uploads scribble the 64 rows below each view. Every
requested texel must equal the world colour afterwards. Also counts how many
pixels a full-view mirror would have refilled, for comparison.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
C=r'''
#include "native_scenery_cache.h"
#include <assert.h>
#include <stdio.h>
static uint16_t texture[256*256];static NativeOccluderCells cells;
static unsigned long long sampled_pixels,checked;static int view_x,view_y;
static uint32_t seed=7;static uint32_t next(void){seed=seed*1664525u+1013904223u;return seed>>8;}
static uint16_t color(unsigned x,unsigned y){return ((x*7u+y*3u)%13u)?(uint16_t)(32768u|((x*3u)&31u)|(((y*5u)&31u)<<5)|(((x^y)&31u)<<10)):0;}
static bool sample(int wx,int wy,int l,int t,int r,int b,void *ctx){
 (void)ctx;assert(l>=0&&t>=0&&r<=256&&b<=192&&l<r&&t<b);
 assert(view_x+l>=wx&&view_x+r<=wx+8&&view_y+t>=wy&&view_y+b<=wy+8);
 for(int y=t;y<b;y++)for(int x=l;x<r;x++)texture[(((unsigned)(view_y+y))&255u)*256u+(((unsigned)(view_x+x))&255u)]=color((unsigned)(view_x+x),(unsigned)(view_y+y));
 sampled_pixels+=(unsigned)((r-l)*(b-t));return true;
}
int main(void){
 native_scenery_cache_invalidate(&cells);
 int x=300,y=200;unsigned long long requests=0;
 assert(!native_scenery_cache_need(NULL,0,0,NULL,0,sample,NULL,NULL));
 for(unsigned frame=0;frame<20000;frame++){
  view_x=x;view_y=y;unsigned rects=next()%7;ClippedOccluder list[8];
  for(unsigned k=0;k<rects;k++){
   int l=(int)(next()%300)-20,t=(int)(next()%230)-20,w=1+(int)(next()%90),h=1+(int)(next()%70);
   list[k]=(ClippedOccluder){(int16_t)l,(int16_t)t,(int16_t)(l+w),(int16_t)(t+h),0};requests++;
  }
  assert(native_scenery_cache_need(&cells,x,y,list,rects,sample,NULL,NULL));
  for(unsigned k=0;k<rects;k++){
   int l=list[k].l,t=list[k].t,w=list[k].r-l,h=list[k].b-t;
   int cl=l<0?0:l,ct=t<0?0:t,cr=l+w>256?256:l+w,cb=t+h>192?192:t+h;
   for(int yy=ct;yy<cb;yy++)for(int xx=cl;xx<cr;xx++){
    assert(texture[(((unsigned)(y+yy))&255u)*256u+(((unsigned)(x+xx))&255u)]==color((unsigned)(x+xx),(unsigned)(y+yy)));checked++;}
  }
  for(unsigned yy=192;yy<256;yy++)for(unsigned xx=0;xx<256;xx++)texture[(((unsigned)y+yy)&255u)*256u+xx]=0x8bad;
  native_scenery_cache_overwrite(&cells,y);
  if(frame%499u==0u)native_scenery_cache_invalidate(&cells);
  unsigned mode=next()%100;
  if(mode<70){x+=(int)(next()%9)-4;y+=(int)(next()%7)-3;}
  else if(mode<95){x+=(int)(next()%41)-20;y+=(int)(next()%21)-10;}
  else{x=(int)(next()%4000);y=(int)(next()%2000);}
  if(x<0)x=0;
  if(y<0)y=0;
 }
 printf("{\"views\":20000,\"rect_requests\":%llu,\"texel_checks\":%llu,\"sampled_pixels\":%llu}\n",requests,checked,sampled_pixels);
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--source-dir',type=Path,default=R/'ds/source');a=p.parse_args()
 header=a.source_dir/'native_scenery_cache.h'
 with tempfile.TemporaryDirectory(prefix='kinder-occluder-cells-')as td:
  d=Path(td);(d/'test.c').write_text(C);exe=d/'test'
  subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(header.parent),str(d/'test.c'),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
  report=json.loads(r.stdout)
 report.update(scope=__doc__.strip().splitlines()[0],source_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),sanitizers=['address','undefined'],limits=['Host texture model; DS GPU output is checked separately by the NATIVE_VERIFY_SCENERY build.'])
 a.output.write_text(json.dumps(report,indent=1)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
