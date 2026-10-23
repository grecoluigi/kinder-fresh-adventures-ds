"""Sanitizer proof of research strip ownership, cache invalidation and pinning."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
header=R/'research/rendering/resident-actors-prototype/resident_strips.h'
with tempfile.TemporaryDirectory(prefix='kinder-resident-sanitize-') as td:
 t=Path(td);src=t/'test.c'
 src.write_text('#include "'+str(header)+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
static ResidentStrips caches[2];
static uint16_t pixels[2][256*256];
static uint32_t rng=2001;
static unsigned random_word(void){rng=rng*1664525u+1013904223u;return rng;}
static uint16_t color(unsigned key,unsigned x,unsigned y){return (uint16_t)((key*7919u+x*13u+y*3571u)^0x8000u);}
static void check(ResidentStrips *c){
 uint32_t occupied[32]={0};
 for(unsigned i=0;i<RESIDENT_ENTRIES;i++){
  ResidentStrip *e=c->entries+i;if(!e->age)continue;
  assert(e->x%8==0&&e->y%8==0&&e->x+e->w<=256&&e->y+e->h<=256);
  assert(resident_row_allowed(c,e->y));
  uint32_t mask=resident_mask(e->x/8u,(e->w+7u)/8u);
  assert(!(occupied[e->y/8u]&mask));occupied[e->y/8u]|=mask;
 }
 assert(!memcmp(occupied,c->occupied,sizeof(occupied)));
}
int main(void){
 unsigned hits=0,misses=0,rejected=0;
 for(unsigned frame=0;frame<3000;frame++){
  unsigned bank=frame&1u;ResidentStrips *c=caches+bank;
  unsigned camera=frame<512?frame/2u:frame%97==0?random_word()&255u:frame/16u&255u;
  resident_begin(c,camera);
  /* Scenery overwrites every newly visible location, including old art. */
  for(unsigned y=0;y<256;y++)if(((y+256-camera)&255u)<192)memset(pixels[bank]+y*256,0x37,512);
  for(unsigned i=0;i<1+frame%40;i++){
   unsigned key=1+(i+frame/12)%61,w=1+(key*19)%256,h=1+key%8;
   unsigned sx=key%5,sy=key%17;
   bool hit;ResidentStrip *e=resident_get(c,key,sx,sy,w,h,&hit);
   if(!e){rejected++;break;}
   if(hit)hits++;else misses++;
   for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
    uint16_t *p=pixels[bank]+(e->y+y)*256+e->x+x;
    if(hit)assert(*p==color(key,sx+x,sy+y));else *p=color(key,sx+x,sy+y);
   }
   /* Every strip pinned earlier in this frame survives later allocations. */
   for(unsigned n=0;n<RESIDENT_ENTRIES;n++){
    ResidentStrip *p=c->entries+n;if(p->age!=c->epoch)continue;
    for(unsigned y=0;y<p->h;y++)for(unsigned x=0;x<p->w;x++)assert(pixels[bank][(p->y+y)*256+p->x+x]==color((unsigned)p->key,p->sx+x,p->sy+y));
   }
   check(c);
  }
  check(c);
 }
 bool hit;ResidentStrips *c=caches;
 assert(!resident_get(c,0,0,0,1,1,&hit));
 assert(!resident_get(c,1,0,0,257,1,&hit));
 assert(!resident_get(c,1,0,0,1,9,&hit));
 c->epoch=UINT32_MAX;resident_begin(c,0);assert(c->epoch==1);
 for(unsigned i=0;i<RESIDENT_ENTRIES;i++)assert(!c->entries[i].age);
 check(c);assert(hits&&misses&&rejected);
 printf("{\"frames\":3000,\"hits\":%u,\"misses\":%u,\"capacity_rejections\":%u,\"metadata_bytes\":%zu}\n",hits,misses,rejected,sizeof(caches));
}
''')
 exe=t/'test'
 subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),'-o',str(exe)],check=True)
 data=json.loads(subprocess.check_output([str(exe)],text=True))
 data.update(scope=__doc__,asan_ubsan=True,prototype_sha256=hashlib.sha256(header.read_bytes()).hexdigest())
 (R/'research/rendering/resident-actor-strip-verification.json').write_text(json.dumps(data,indent=2)+'\n')
 print(json.dumps(data))
