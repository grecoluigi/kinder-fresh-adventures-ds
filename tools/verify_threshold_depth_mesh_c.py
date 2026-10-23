"""Overlapping C threshold rectangles vs exact scenery depth; bounds, guards and capacity fallback."""
from pathlib import Path
import json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-threshold-mesh-') as td:
 t=Path(td);src=t/'test.c';src.write_text('#include "'+str(R/'research/rendering/gpu-actors-prototype/threshold_depth_mesh.h')+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define CAPACITY 2304u
static uint8_t source[272*208+32],restored[272*208];
static struct {uint32_t before[8];DepthRect rectangles[CAPACITY];uint32_t after[8];} guarded;
static ThresholdMeshScratch scratch;
int main(void){
 uint32_t seed=2001;unsigned passed=0,overflow=0;
 for(unsigned test=0;test<2000;test++){
  seed=seed*1664525u+1013904223u;unsigned width=1+seed%272;
  seed=seed*1664525u+1013904223u;unsigned height=1+seed%208;
  memset(source,0x12,sizeof(source));memset(restored,0,sizeof(restored));
  for(unsigned y=0;y<height;y++)for(unsigned x=0;x<width;x++){
   seed=seed*1664525u+1013904223u;
   unsigned value=test%5==0?seed>>28:test%5==1?(x/16+y/13)%7:test%5==2?(x>width/3&&y>height/3?255:0):test%5==3?((x+y)%2?3:0):0;
   source[16+y*272+x]=(uint8_t)value;
  }
  for(unsigned i=0;i<8;i++)guarded.before[i]=guarded.after[i]=0x12345678u;
  size_t n=SIZE_MAX;bool ok=threshold_depth_mesh_build(source+16,width,height,272,guarded.rectangles,CAPACITY,&n,&scratch);
  assert(n<=CAPACITY);
  for(unsigned i=0;i<8;i++)assert(guarded.before[i]==0x12345678u&&guarded.after[i]==0x12345678u);
  for(unsigned i=0;i<16;i++)assert(source[i]==0x12&&source[272*208+16+i]==0x12);
  if(!ok){assert(n==CAPACITY);overflow++;continue;}
  for(size_t i=0;i<n;i++){
   DepthRect q=guarded.rectangles[i];assert(q.left<q.right&&q.right<=width&&q.top<q.bottom&&q.bottom<=height&&q.order);
   for(unsigned y=q.top;y<q.bottom;y++)for(unsigned x=q.left;x<q.right;x++){
    unsigned native=source[16+y*272+x];assert(!native||native>=q.order);
    if(native&&restored[y*272+x]<q.order)restored[y*272+x]=(uint8_t)q.order;
   }
  }
  for(unsigned y=0;y<height;y++)assert(!memcmp(restored+y*272,source+16+y*272,width));
  passed++;
 }
 size_t n;
 assert(!threshold_depth_mesh_build(NULL,1,1,1,guarded.rectangles,CAPACITY,&n,&scratch));
 assert(!threshold_depth_mesh_build(source,273,1,273,guarded.rectangles,CAPACITY,&n,&scratch));
 assert(!threshold_depth_mesh_build(source,1,209,1,guarded.rectangles,CAPACITY,&n,&scratch));
 assert(!threshold_depth_mesh_build(source,2,1,1,guarded.rectangles,CAPACITY,&n,&scratch));
 assert(passed&&overflow);
 printf("{\"exact_planes\":%u,\"bounded_overflow_rejections\":%u,\"invalid_dimensions\":4,\"scratch_bytes\":%zu,\"rectangle_bytes\":%zu}\n",passed,overflow,sizeof(scratch),sizeof(DepthRect));return 0;
}
''')
 exe=t/'test';subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(src),'-o',str(exe)],check=True)
 r=json.loads(subprocess.check_output([str(exe)],text=True));r.update(scope=__doc__,sanitizers=['address','undefined'],limits=['Host C ownership/depth proof only; real C/Python asset parity and GPU overlap/depth behavior require separate checks.'])
 (R/'research/rendering/threshold-depth-c-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
