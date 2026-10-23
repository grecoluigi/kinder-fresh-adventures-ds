"""Sanitized two-bank proof of restoring immutable scenery beneath CPU foreground."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1];H=R/'research/rendering/resident-actors-prototype/texture_foreground.h'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--header',type=Path,default=H);parser.add_argument('--output',type=Path,default=R/'research/rendering/texture-foreground-verification.json');args=parser.parse_args();H=args.header.resolve()
with tempfile.TemporaryDirectory(prefix='kinder-texture-foreground-') as td:
 t=Path(td);src=t/'test.c'
 src.write_text('#include "'+str(H)+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
static TextureWindow windows[2];static TextureForeground foreground[2];
static uint16_t textures[2][65536],base[272*208],overlay[272*208],source[49154],expected[49152];
static uint32_t seed=2001;
static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static uint16_t world(unsigned x,unsigned y){return (x+y)%11?(uint16_t)((x*137u+y*3571u)|32768u):(uint16_t)(x&32767u);}
static uint16_t front(unsigned x,unsigned y){return (x*3u+y)%5?(uint16_t)(x&32767u):(uint16_t)((x*2347u+y*739u)|32768u);}
static bool fail_write(int x,int y,unsigned w,unsigned h,void *context){(void)x;(void)y;(void)w;(void)h;(void)context;return false;}
int main(void){
 unsigned long long restored=0,uploaded=0,written=0;unsigned cpu_frames=0;
 for(unsigned frame=0;frame<2400;frame++){
  unsigned bank=frame&1u;int x=(int)(frame<512?frame/2u:rnd()%2000),y=(int)(frame<512?frame/2u:rnd()%2000);
  if(frame%5==0){x=windows[bank].x;y=windows[bank].y;}
  if(frame%31==0){memset(textures[bank],0xd7,sizeof(textures[bank]));windows[bank].valid=false;foreground[bank].valid=false;}
  for(unsigned yy=(unsigned)y;yy<(unsigned)y+208;yy++)for(unsigned xx=(unsigned)x;xx<(unsigned)x+272;xx++){
   unsigned at=(yy%208u)*272u+xx%272u;base[at]=world(xx,yy);overlay[at]=front(xx,yy);
  }
  TextureWindowCopy copy={textures[bank],base,0,0,frame%2?overlay:NULL};
  /* A scenery-layer change invalidates the window just as production does. */
  if(frame%17==0){windows[bank].valid=false;foreground[bank].valid=false;}
  assert(texture_window_update(windows+bank,x,y,texture_window_copy,&copy));uploaded+=copy.pixels;
  unsigned before=copy.pixels;
  assert(texture_fg_restore(foreground+bank,x,y,texture_window_copy,&copy));restored+=copy.pixels-before;
  uint16_t *pixels=source+(frame%2);memset(source,0,sizeof(source));bool cpu=frame%7!=0;
  if(cpu){
   for(unsigned n=0;n<1+frame%12;n++){
    unsigned sx=rnd()%256,sy=rnd()%192,w=1+rnd()%50,h=1+rnd()%50;
    for(unsigned yy=sy;yy<sy+h&&yy<192;yy++)for(unsigned xx=sx;xx<sx+w&&xx<256;xx++)pixels[yy*256+xx]=(uint16_t)(rnd()>>16);
   }
  }
  for(unsigned yy=0;yy<192;yy++)for(unsigned xx=0;xx<256;xx++){
   uint16_t b=world((unsigned)x+xx,(unsigned)y+yy),o=copy.overlay?front((unsigned)x+xx,(unsigned)y+yy):0,f=pixels[yy*256+xx];
   expected[yy*256+xx]=(f&32768u)?f:(o&32768u)?o:b;
  }
  if(cpu){unsigned count;assert(texture_fg_apply(foreground+bank,x,y,textures[bank],pixels,&count));written+=count;cpu_frames++;}
  /* Evicted/overwritten CPU sources must have no effect on retained VRAM. */
  memset(source,0x83,sizeof(source));
  for(unsigned yy=0;yy<192;yy++)for(unsigned xx=0;xx<256;xx++)assert(textures[bank][(((unsigned)y+yy)&255u)*256u+(((unsigned)x+xx)&255u)]==expected[yy*256+xx]);
  /* GPU actor staging lives in the unused rows; subsequent scrolling must
   * restore these when they enter the visible window. */
  if(!cpu)for(unsigned yy=192;yy<256;yy++)memset(textures[bank]+(((unsigned)y+yy)&255u)*256u,0xe5,512);
 }
 TextureForeground state={0};state.valid=true;
#ifdef KINDER_TEXTURE_FOREGROUND_TILES
 state.rows[0]=1;
#else
 state.bottom=192;
#endif
 assert(!texture_fg_restore(&state,0,0,fail_write,NULL)&&!state.valid);
 assert(!texture_fg_apply(&state,-1,0,textures[0],source,NULL));
 assert(!texture_fg_apply(&state,INT_MAX,0,textures[0],source,NULL));
 assert(!texture_fg_apply(&state,0,0,NULL,source,NULL));
 printf("{\"frames\":2400,\"cpu_frames\":%u,\"static_upload_pixels\":%llu,\"restored_pixels\":%llu,\"foreground_pixels\":%llu}\n",cpu_frames,uploaded,restored,written);
}
''')
 exe=t/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),'-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),'-o',str(exe)],check=True)
 report=json.loads(subprocess.check_output([str(exe)],text=True));report.update(scope=__doc__,asan_ubsan=True,prototype_sha256=hashlib.sha256(H.read_bytes()).hexdigest(),limits=['Synthetic VRAM ownership proof only; production scenery caches, DS rasterization and timing are not exercised.'])
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
