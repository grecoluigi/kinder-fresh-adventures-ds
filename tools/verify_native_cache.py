"""Sanitize retained native texture cache ownership, eviction and current-frame pinning."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1];H=R/'research/rendering/resident-actors-prototype/native_cache.h'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=R/'research/rendering/native-cache-verification.json');args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='kinder-native-cache-')as td:
 t=Path(td);src=t/'test.c';src.write_text('#include "'+str(H)+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
static NativeCache caches[2];static uint8_t memory[2][131072];
static uint32_t seed=2001;static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static uint8_t value(unsigned key,unsigned i){return(uint8_t)(key*137u+i*41u);}
int main(void){unsigned hits=0,misses=0,failed=0;
 for(unsigned frame=0;frame<5000;frame++){
 #ifdef NATIVE_CACHE_HINTS
  if(frame%47==0)for(unsigned bank=0;bank<2;bank++)memset(caches[bank].hints,255,sizeof(caches[bank].hints));
 #endif
  unsigned bank=frame&1u,start=(frame<512?frame/2:rnd()%256);NativeCache *c=caches+bank;
  /* Every byte outside today's unused rows belongs to scenery, never actors. */
  for(unsigned row=0;row<256;row++)if(((row+256-start)&255u)>=64)memset(memory[bank]+row*512u,0xab,512);
  if(frame%83==0){native_cache_clear(c);memset(memory[bank],0xcd,sizeof(memory[bank]));}
  if(frame==4095)c->epoch=65535;
  if(start<=192)native_cache_begin(c,start*512u,(start+64)*512u,0,0);else native_cache_begin(c,0,(start-192)*512u,start*512u,131072);
  unsigned keys[100],offsets[100],sizes[100],count=0;bool ok=true;
  unsigned draw_count=frame%29?1+rnd()%80:100;
  for(unsigned i=0;i<draw_count;i++){
   unsigned key=frame%29?(rnd()%160):i,bytes=frame%29?32u<<((key>>2)%5):4096u;uint32_t at;bool hit;
   if(!native_cache_get(c,key,bytes,&at,&hit)){ok=false;failed++;break;}
   assert(!(at&15u)&&at+bytes<=131072);
   bool allowed=false;for(unsigned j=0;j<c->ranges;j++)if(at>=c->allowed[j][0]&&at+bytes<=c->allowed[j][1])allowed=true;assert(allowed);
   if(hit){hits++;for(unsigned n=0;n<bytes;n++)assert(memory[bank][at+n]==value(key,n));}
   else{misses++;for(unsigned n=0;n<bytes;n++)memory[bank][at+n]=value(key,n);}
   keys[count]=key;offsets[count]=at;sizes[count++]=bytes;
  }
  if(ok){for(unsigned i=0;i<count;i++)for(unsigned n=0;n<sizes[i];n++)assert(memory[bank][offsets[i]+n]==value(keys[i],n));}
  else native_cache_clear(c);
 }
 printf("{\"frames\":5000,\"hits\":%u,\"misses\":%u,\"capacity_rejections\":%u,\"cache_metadata_bytes\":%zu}\n",hits,misses,failed,sizeof(NativeCache));
}
''');exe=t/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),'-o',str(exe)],check=True)
 report=json.loads(subprocess.check_output([str(exe)],text=True));report.update(scope=__doc__,asan_ubsan=True,source_sha256=hashlib.sha256(H.read_bytes()).hexdigest(),limits=['Synthetic byte ownership only; deliberate oversized frames exercise rejection. Actual gameplay working sets are checked separately.'])
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
