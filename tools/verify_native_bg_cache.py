"""Stress the real cache with live-map publication, front protection and partial-write failures."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();header=R/'research/rendering/native-bg-prototype/native_bg_cache.h'
C=r'''
#include "HEADER"
#include <assert.h>
#include <stdio.h>
static NativeBGCache cache;
static uint32_t graphics[960],seed=2001;
static uint16_t map[2048];
static int front_x,front_y;
static bool visible,fail_next;
static unsigned front_checks,uploads,failures,published,aborted;
static unsigned random_u(void){seed=seed*1664525u+1013904223u;return seed;}
static uint32_t key_at(unsigned x,unsigned y){return (x+y*3)%17?y*4096+x+1:0;}
static unsigned at(unsigned x,unsigned y){return (y%32)*32+x%32+((x%64)/32)*1024;}
static void check_front(void){
 if(!visible)return;
 for(unsigned y=front_y/8;y<=(unsigned)(front_y+191)/8;y++)for(unsigned x=front_x/8;x<=(unsigned)(front_x+255)/8;x++){
  uint16_t word=map[at(x,y)];unsigned slot=word&1023;uint32_t key=key_at(x,y);
  assert(slot<960&&graphics[slot]==key&&cache.entries[slot].key==key);
  assert((word>>12)==((x+y)%16));assert(cache.entries[slot].flags&NATIVE_BG_FRONT);
  assert(native_bg_find(&cache,key)==(int)slot);
 }
 front_checks++;
}
static bool upload(void *context,uint32_t key,unsigned slot){
 (void)context;assert(slot>0&&slot<960);assert(!(cache.entries[slot].flags&(NATIVE_BG_FRONT|NATIVE_BG_NEXT)));
 check_front();graphics[slot]=key^0xabcdef;check_front();
 if(fail_next){fail_next=false;failures++;return false;}
 graphics[slot]=key;check_front();uploads++;return true;
}
static bool prepare(int x,int y){
 assert(native_bg_cache_begin(&cache));assert(!native_bg_cache_begin(&cache));
 for(unsigned yy=y/8;yy<=(unsigned)(y+191)/8;yy++)for(unsigned xx=x/8;xx<=(unsigned)(x+255)/8;xx++){
  unsigned slot;
  if(!native_bg_cache_acquire(&cache,key_at(xx,yy),upload,NULL,&slot)){
   assert(!native_bg_cache_publish(&cache));native_bg_cache_abort(&cache);check_front();aborted++;return false;
  }
  uint16_t word=(uint16_t)(slot|(((xx+yy)%16)<<12));
  if(map[at(xx,yy)]!=word){map[at(xx,yy)]=word;check_front();}
 }
 check_front();return true;
}
static void publish(int x,int y){
 front_x=x;front_y=y;visible=true;assert(native_bg_cache_publish(&cache));assert(!native_bg_cache_publish(&cache));check_front();published++;
}
int main(void){
 assert(!native_bg_cache_reset(NULL,false));assert(!native_bg_cache_begin(NULL));native_bg_cache_abort(NULL);
 assert(native_bg_cache_reset(&cache,false));graphics[0]=0;
 assert(!native_bg_cache_publish(&cache));assert(prepare(129,65));publish(129,65);
 for(unsigned frame=0;frame<6000;frame++){
  int x=front_x+(int)(random_u()%33)-16,y=front_y+(int)(random_u()%33)-16;
  if(x<64)x=64;if(x>4096)x=4096;if(y<64)y=64;if(y>2048)y=2048;
  NativeBGCache saved=cache;assert(!native_bg_cache_reset(&cache,true));assert(!memcmp(&cache,&saved,sizeof(cache)));
  if(frame%37==0)fail_next=true;
  if(!prepare(x,y)){fail_next=false;assert(prepare(x,y));}
  if(frame%53==0){native_bg_cache_abort(&cache);check_front();aborted++;assert(prepare(x,y));}
  publish(x,y);
 }
 assert(front_checks&&uploads&&failures&&aborted);
 unsigned live_uploads=uploads,live_hits=cache.hits;
 visible=false;assert(native_bg_cache_reset(&cache,false));assert(native_bg_cache_begin(&cache));
 for(unsigned i=1;i<960;i++){unsigned slot;assert(native_bg_cache_acquire(&cache,i,upload,NULL,&slot));}
 unsigned slot=123;assert(!native_bg_cache_acquire(&cache,9999,upload,NULL,&slot)&&slot==123);assert(!native_bg_cache_begin(&cache));assert(!native_bg_cache_publish(&cache));native_bg_cache_abort(&cache);
 assert(native_bg_cache_begin(&cache));assert(!native_bg_cache_acquire(&cache,0x10000000,upload,NULL,&slot));assert(!native_bg_cache_acquire(&cache,1,upload,NULL,NULL));native_bg_cache_abort(&cache);
 printf("{\"published_views\":%u,\"front_checks\":%u,\"live_uploads\":%u,\"cache_hits\":%u,\"injected_partial_failures\":%u,\"aborts\":%u,\"capacity_rejection\":true,\"cache_bytes\":%zu}\n",published,front_checks,live_uploads,live_hits,failures,aborted,sizeof(cache));
}
'''.replace('HEADER',str(header)).replace('  if(x<64)x=64;if(x>4096)x=4096;if(y<64)y=64;if(y>2048)y=2048;','  if(x<64)x=64;\n  if(x>4096)x=4096;\n  if(y<64)y=64;\n  if(y>2048)y=2048;')
with tempfile.TemporaryDirectory(prefix='kinder-bg-cache-')as td:
 d=Path(td);src=d/'test.c';src.write_text(C);exe=d/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(src),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],text=True,capture_output=True)
 if r.returncode:print(r.stderr);raise RuntimeError('native BG front/cache proof failed')
 result=json.loads(r.stdout)
result.update(scope=__doc__,header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),sanitizers=['address','undefined'],limits=['Synthetic virtual world with unique cell graphics and blanks; no actual DS GPU, storage read timings or full-game integration.','Caller must actually publish matching hardware map/scroll state before releasing front pins.','Test camera steps remain within16DS pixels/axis; larger transitions need explicit admission.'])
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
