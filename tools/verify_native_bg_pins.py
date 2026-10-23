"""Recount displayed/prepared tile references independently across long eviction routes."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
C=r'''
#include "native_bg_stream.h"
#include <assert.h>
#include <stdlib.h>
static NativeBGStream s;
static uint16_t hardware[2048],graphics[960][32];
static bool fail_tile,fail_map;static unsigned failures,aborts,checks,views;
static bool tile(void *p,unsigned slot,const uint16_t *data){
 (void)p;assert(slot&&slot<960&&!(s.cache.entries[slot].flags&NATIVE_BG_FRONT));
 if(fail_tile){fail_tile=false;failures++;memset(graphics[slot],0xa5,18);return false;}
 memcpy(graphics[slot],data,64);return true;
}
static bool map(void *p,unsigned at,uint16_t word){
 (void)p;assert(at<2048);
 if(fail_map){fail_map=false;failures++;hardware[at]=(uint16_t)(word^511);return false;}
 hardware[at]=word;return true;
}
static void counts(int x,int y,uint16_t *out){
 memset(out,0,960*2);
 for(int yy=y/8;yy<=(y+191)/8;yy++)for(int xx=x/8;xx<=(x+255)/8;xx++){
  unsigned at=native_bg_map_at((unsigned)xx,(unsigned)yy),slot=s.map[at]&1023;
  assert(slot<960&&hardware[at]==s.map[at]);out[slot]++;
 }
}
static void check(void){
 uint16_t displayed[960]={0},prepared[960]={0};
 if(s.visible)counts(s.front_x,s.front_y,displayed);
 if(s.pending)counts(s.target_x,s.target_y,prepared);else memcpy(prepared,displayed,sizeof(prepared));
 for(unsigned i=0;i<960;i++){
  assert(s.front_refs[i]==displayed[i]);assert(s.next_refs[i]==prepared[i]);
  unsigned flags=s.cache.entries[i].flags;
  assert(!!(flags&NATIVE_BG_FRONT)==!!(displayed[i]||!i));
  if(displayed[i]||prepared[i])assert((flags&NATIVE_BG_VALID)&&(flags&(NATIVE_BG_FRONT|NATIVE_BG_NEXT)));
  if(!s.pending)assert(!(flags&NATIVE_BG_NEXT));
 }
 if(!s.pending){assert(!s.changed_count&&!s.cache.state);for(unsigned i=0;i<120;i++)assert(!s.changed_bits[i]);}
 checks++;
}
int main(int argc,char **argv){
 assert(argc>1);unsigned evictions=0,pin_updates=0,reads=0,read_bytes=0;
 for(int asset=1;asset<argc;asset++){
  assert(native_bg_stream_open(&s,argv[asset],false));memset(hardware,0,sizeof(hardware));memset(graphics,0,sizeof(graphics));
  int x=0,y=0,dx=4,dy=2,maxx=(int)s.assets.width*8-256,maxy=(int)s.assets.height*8-192;
  for(unsigned frame=0;frame<2400;frame++){
   if(frame%17==0)fail_tile=true;
   if(frame%23==0)fail_map=true;
   unsigned attempts=0;
   while(native_bg_stream_prepare(&s,x,y,tile,map,NULL)!=NATIVE_BG_STREAM_READY){assert(++attempts<=2);check();aborts++;}
   check();
   if(frame%37==0){native_bg_stream_abort(&s);check();aborts++;assert(native_bg_stream_prepare(&s,x,y,tile,map,NULL)==NATIVE_BG_STREAM_READY);check();}
   assert(native_bg_stream_publish(&s));check();views++;
   x+=dx;y+=dy;
   if(x>maxx){x=maxx;dx=-4;}else if(x<0){x=0;dx=4;}
   if(y>maxy){y=maxy;dy=-2;}else if(y<0){y=0;dy=2;}
  }
  evictions+=s.cache.evictions;pin_updates+=s.pin_updates;reads+=s.assets.block_fills;read_bytes+=s.assets.block_bytes;assert(native_bg_stream_close(&s,false));
 }
 assert(views==2400u*(unsigned)(argc-1)&&evictions&&failures&&aborts);
 printf("{\"views\":%u,\"full_reference_checks\":%u,\"cache_evictions\":%u,\"partial_failures\":%u,\"aborts\":%u,\"pin_updates\":%u,\"asset_block_reads\":%u,\"asset_block_bytes\":%u,\"stream_host_bytes\":%zu}\n",views,checks,evictions,failures,aborts,pin_updates,reads,read_bytes,sizeof(s));
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prototype-dir',type=Path,default=R/'research/rendering/native-bg-integration-prototype');p.add_argument('--assets-dir',type=Path,default=R/'research/rendering/native-bg-asset-study');p.add_argument('--output',type=Path,required=True);a=p.parse_args();headers=a.prototype_dir.resolve()
 with tempfile.TemporaryDirectory(prefix='kinder-native-pins-')as td:
  d=Path(td);source=d/'test.c';source.write_text(C);exe=d/'test'
  subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(headers),'-I'+str(R/'ds/source'),str(source),'-o',str(exe)],check=True)
  result=subprocess.run([str(exe),*[str(p.resolve())for p in sorted(a.assets_dir.glob('*.ntb'))]],capture_output=True,text=True)
  if result.returncode:raise RuntimeError(result.stderr)
  report=json.loads(result.stdout)
 report.update(scope=__doc__,sanitizers=['address','undefined'],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in headers.glob('*.h')},limits=['Host hardware-map model checks full reference counts, pins, rollback and evictions; not actual GPU pixels or physical storage timings.','Separate pixel-oracle fixtures and full-game emulator tests cover those remaining renderer contracts.']);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='source_sha256'}))
if __name__=='__main__':main()
