"""Check per-depth foreground bounds against independent actor/rectangle intersections."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
C=r'''
#include "native_occlusion.h"
#include <assert.h>
#include <stdio.h>
static unsigned seed=2001;
static unsigned random_value(void){seed=seed*1664525u+1013904223u;return seed;}
static ActorAtlas atlas;static NativeDraw draws[64];
static struct {unsigned before[8];ActorRegion regions[256];unsigned after[8];} guarded;
int main(void){
 unsigned queries=0,intersections=0;unsigned long long old_area=0,new_area=0;
 for(unsigned trial=0;trial<2048;trial++){
  for(unsigned i=0;i<8;i++)guarded.before[i]=guarded.after[i]=0xdeadbeefu;
  atlas.count=random_value()%65;unsigned n=random_value()%65;
  for(unsigned i=0;i<atlas.count;i++)atlas.pieces[i]=(ActorPiece){.screen_x=(uint16_t)(random_value()%350),.screen_y=(uint16_t)(random_value()%250),.width=(uint16_t)(1+random_value()%200),.height=(uint16_t)(1+random_value()%160),.order=(uint16_t)(random_value()%9==0?255:random_value()%32)};
  for(unsigned i=0;i<n;i++)draws[i]=(NativeDraw){.x=(int16_t)((int)(random_value()%500)-140),.y=(int16_t)((int)(random_value()%400)-100),.w=(uint16_t)(1+random_value()%200),.h=(uint16_t)(1+random_value()%160),.order=(uint16_t)(random_value()%9==0?255:random_value()%32)};
  assert(!native_occlusion_regions(guarded.regions,31,32,&atlas,draws,n));
  assert(native_occlusion_regions(guarded.regions,256,32,&atlas,draws,n));
  ActorRegion all=native_region_empty();
  for(unsigned order=0;order<32;order++){
   ActorRegion expected=native_region_empty();
   for(unsigned j=0;j<atlas.count+n;j++){
    int l,t,r,b;unsigned rank;
    if(j<atlas.count){ActorPiece *p=atlas.pieces+j;l=p->screen_x;t=p->screen_y;r=l+p->width;b=t+p->height;rank=p->order;}
    else{NativeDraw *p=draws+(j-atlas.count);l=p->x;t=p->y;r=l+p->w;b=t+p->h;rank=p->order;}
    if(l<0)l=0;if(t<0)t=0;if(r>256)r=256;if(b>192)b=192;
    if(l>=r||t>=b)continue;
    ActorRegion rect={l,t,r,b,rank};if(rank<order)native_region_merge(&expected,rect);
    if(order==0)native_region_merge(&all,rect);
   }
   ActorRegion got=guarded.regions[order];assert(got.left==expected.left&&got.top==expected.top&&got.right==expected.right&&got.bottom==expected.bottom&&got.first_order==expected.first_order);
  }
  for(unsigned i=0;i<64;i++){
   int dx=(int)(random_value()%128),dy=(int)(random_value()%96);
   DepthRect q={(uint16_t)(random_value()%300),(uint16_t)(random_value()%240),0,0,(uint16_t)(random_value()%32)};q.right=(uint16_t)(q.left+1+random_value()%200);q.bottom=(uint16_t)(q.top+1+random_value()%160);
   int old[4],now[4];bool previous=actor_occlusion_clip(&q,dx,dy,all,old,old+1,old+2,old+3),current=actor_occlusion_clip(&q,dx,dy,guarded.regions[q.order],now,now+1,now+2,now+3);
   if(previous)old_area+=(unsigned)(old[2]-old[0])*(unsigned)(old[3]-old[1]);
   if(current){assert(previous&&now[0]>=old[0]&&now[1]>=old[1]&&now[2]<=old[2]&&now[3]<=old[3]);new_area+=(unsigned)(now[2]-now[0])*(unsigned)(now[3]-now[1]);}
   for(unsigned j=0;j<atlas.count+n;j++){
    int l,t,r,b;unsigned rank;
    if(j<atlas.count){ActorPiece *p=atlas.pieces+j;l=p->screen_x;t=p->screen_y;r=l+p->width;b=t+p->height;rank=p->order;}
    else{NativeDraw *p=draws+(j-atlas.count);l=p->x;t=p->y;r=l+p->w;b=t+p->h;rank=p->order;}
    if(rank>=q.order)continue;
    if(l<0)l=0;if(t<0)t=0;if(r>256)r=256;if(b>192)b=192;
    if(l<(int)q.left-dx)l=(int)q.left-dx;if(t<(int)q.top-dy)t=(int)q.top-dy;
    if(r>(int)q.right-dx)r=(int)q.right-dx;if(b>(int)q.bottom-dy)b=(int)q.bottom-dy;
    if(l>=r||t>=b)continue;
    assert(current&&now[0]<=l&&now[1]<=t&&now[2]>=r&&now[3]>=b);intersections++;
   }
   queries++;
  }
  for(unsigned i=0;i<8;i++)assert(guarded.before[i]==0xdeadbeefu&&guarded.after[i]==0xdeadbeefu);
 }
 atlas.count=ACTOR_ATLAS_PIECES+1;assert(!native_occlusion_regions(guarded.regions,256,32,&atlas,draws,0));atlas.count=0;assert(!native_occlusion_regions(guarded.regions,256,32,&atlas,draws,NATIVE_DRAW_LIMIT+1));
 draws[0]=(NativeDraw){.w=1,.h=1,.order=256};assert(!native_occlusion_regions(guarded.regions,256,32,&atlas,draws,1));
 assert(intersections&&new_area<old_area);printf("{\"queries\":%u,\"potential_occlusions_preserved\":%u,\"old_area\":%llu,\"new_area\":%llu}\n",queries,intersections,old_area,new_area);
}
'''.replace('if(l<0)l=0;if(t<0)t=0;if(r>256)r=256;if(b>192)b=192;','if(l<0)l=0;\n    if(t<0)t=0;\n    if(r>256)r=256;\n    if(b>192)b=192;').replace('if(l<(int)q.left-dx)l=(int)q.left-dx;if(t<(int)q.top-dy)t=(int)q.top-dy;','if(l<(int)q.left-dx)l=(int)q.left-dx;\n    if(t<(int)q.top-dy)t=(int)q.top-dy;').replace('if(r>(int)q.right-dx)r=(int)q.right-dx;if(b>(int)q.bottom-dy)b=(int)q.bottom-dy;','if(r>(int)q.right-dx)r=(int)q.right-dx;\n    if(b>(int)q.bottom-dy)b=(int)q.bottom-dy;')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();header=R/'research/rendering/native-scene-prototype/native_occlusion.h'
 with tempfile.TemporaryDirectory(prefix='kinder-native-occlusion-')as td:
  d=Path(td);source=d/'test.c';source.write_text(C);exe=d/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(header.parent),'-I'+str(R/'ds/source'),str(source),'-o',str(exe)],check=True);r=subprocess.run([str(exe)],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
  report=json.loads(r.stdout)
 report.update(scope=__doc__,source_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),sanitizers=['address','undefined'],limits=['Geometric coverage proof and bounds guards; actual GPU raster and game timing need separate tests.','Area reduction in random fixtures is not a measured game speedup.']);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
