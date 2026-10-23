"""Host-only actor atlas clipping, ownership, capacity fallback and wrapped UV proof."""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--header',type=Path,default=R/'research/rendering/gpu-actors-prototype/actor_atlas.h');parser.add_argument('--output',type=Path);args=parser.parse_args()
rom=resolve_rom(R / 'ds');sha=hashlib.sha256(rom.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='kinder-actor-atlas-') as td:
 t=Path(td);src=t/'test.c'
 src.write_text('#include "'+str(args.header.resolve())+'"\n#include "'+str(R/'ds/source/texture_window.h')+'"\n'+r'''
#include <assert.h>
#include <limits.h>
#include <stdio.h>
static uint16_t stage[256*64],image[300*200],expected[256*192],actual[256*192],texture[256*256];
static uint8_t covered[256*64];
static ActorAtlas atlas;
static uint16_t banks[2][256*256],cache[272*208];
static uint32_t seed=2001;
static unsigned random_word(void){seed=seed*1664525u+1013904223u;return seed;}
static uint16_t world(unsigned x,unsigned y){return (x+y)%7==0?0:(uint16_t)((x*131u+y*3571u)|0x8000u);}
int main(void){
 unsigned accepted=0,rejected=0,sprites=0;
 for(unsigned test=0;test<2000;test++){
  memset(&atlas,0xa5,sizeof(atlas));actor_atlas_reset(&atlas,stage);memset(expected,0,sizeof(expected));memset(actual,0,sizeof(actual));memset(covered,0,sizeof(covered));
  unsigned camera=random_word()%256;
  for(unsigned i=0;i<256*256;i++)texture[i]=0x4567;
  bool ok=true;
  for(unsigned actor=0;actor<1+test%20;actor++){
   unsigned w=1+random_word()%300,h=1+random_word()%200;
   int left=(int)(random_word()%500)-150,top=(int)(random_word()%350)-100;
   for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++)image[y*300+x]=(random_word()%5)?(uint16_t)(random_word()|0x8000):0;
   unsigned before=atlas.count;
   ok=actor_atlas_append(&atlas,image,w,h,300,left,top,actor);
   if(!ok){rejected++;assert(atlas.failed);assert(!actor_atlas_append(&atlas,image,w,h,300,left,top,actor));break;}
   sprites++;
   for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
    int xx=left+(int)x,yy=top+(int)y;
    if(xx>=0&&xx<256&&yy>=0&&yy<192&&(image[y*300+x]&0x8000))expected[yy*256+xx]=image[y*300+x];
   }
   /* Upload just these pieces, then mutate source to model cache eviction. */
   for(unsigned i=before;i<atlas.count;i++){
    ActorPiece p=atlas.pieces[i];assert(p.x+p.width<=256&&p.y+p.height<=64&&p.screen_x+p.width<=256&&p.screen_y+p.height<=192&&p.order==actor);
    for(unsigned y=0;y<p.height;y++)for(unsigned x=0;x<p.width;x++){
     unsigned at=(p.y+y)*256+p.x+x;assert(!covered[at]);covered[at]=1;
     unsigned ty=(camera+192+p.y+y)%256;
     /* Never overwrite the displayed 192 rows, including wrapped windows. */
     assert((ty+256-camera)%256>=192);
     texture[ty*256+p.x+x]=stage[at];
    }
   }
   memset(image,0x55,sizeof(image));
  }
  if(!ok)continue;
  for(unsigned i=0;i<atlas.count;i++){
   ActorPiece p=atlas.pieces[i];
   for(unsigned y=0;y<p.height;y++)for(unsigned x=0;x<p.width;x++){
    uint16_t color=texture[((camera+192+p.y+y)%256)*256+p.x+x];
    assert(color==stage[(p.y+y)*256+p.x+x]);
    if(color&0x8000)actual[(p.screen_y+y)*256+p.screen_x+x]=color;
   }
  }
  assert(!memcmp(expected,actual,sizeof(actual)));accepted++;
 }
 /* All camera phases have disjoint visible and staging rows. */
 for(unsigned camera=0;camera<256;camera++)for(unsigned y=0;y<64;y++)assert((((camera+192+y)%256)+256-camera)%256>=192);
 actor_atlas_reset(&atlas,stage);assert(actor_atlas_append(&atlas,image,300,200,300,INT_MIN,INT_MIN,0)&&!atlas.count);
 actor_atlas_reset(&atlas,NULL);assert(!actor_atlas_append(&atlas,image,1,1,300,0,0,0));
 actor_atlas_reset(&atlas,stage);assert(!actor_atlas_append(&atlas,image,1,1,0,0,0,0));
 /* Actual production strip updater, alternating texture banks, camera reversals,
  * teleports, idle frames and invalidations. Poison every unused row, more
  * aggressively than an actor atlas. Newly visible rows must be restored. */
 TextureWindow windows[2]={{0}};int cx=500,cy=500;unsigned uploaded=0;
 for(unsigned frame=0;frame<2000;frame++){
  unsigned bank=frame%2;
  if(frame%37==0){cx=(int)(random_word()%1500);cy=(int)(random_word()%1500);}
  else if(frame%5){cx+=(int)(random_word()%17)-8;cy+=(int)(random_word()%17)-8;if(cx<0)cx=0;if(cy<0)cy=0;}
  if(frame%113==0)windows[bank].valid=false;
  for(unsigned y=0;y<208;y++)for(unsigned x=0;x<272;x++)cache[((unsigned)cy+y)%208*272+((unsigned)cx+x)%272]=world((unsigned)cx+x,(unsigned)cy+y);
  TextureWindowCopy copy={banks[bank],cache,0,0,NULL};
  assert(texture_window_update(&windows[bank],cx,cy,texture_window_copy,&copy));uploaded+=copy.pixels;
  for(unsigned y=0;y<64;y++)for(unsigned x=0;x<256;x++)banks[bank][(((unsigned)cy+192+y)%256)*256+x]=0x1234;
  for(unsigned y=0;y<192;y++)for(unsigned x=0;x<256;x++)assert(banks[bank][(((unsigned)cy+y)%256)*256+((unsigned)cx+x)%256]==world((unsigned)cx+x,(unsigned)cy+y));
 }
 assert(accepted&&rejected);
 printf("{\"accepted_frames\":%u,\"capacity_rejections\":%u,\"accepted_sprites\":%u,\"atlas_bytes\":%zu,\"metadata_bytes\":%zu,\"camera_phases\":256,\"scroll_restoration_frames\":2000,\"scenery_upload_pixels\":%u}\n",accepted,rejected,sprites,sizeof(stage),sizeof(atlas),uploaded);
 return 0;
}
''')
 exe=t/'test';subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(src),'-o',str(exe)],check=True)
 result=json.loads(subprocess.check_output([str(exe)],text=True))
 assert hashlib.sha256(rom.read_bytes()).hexdigest()==sha
 result.update(scope=__doc__,sanitizers=['address','undefined'],rom_unchanged=True,rom_sha256=sha,limits=['Synthetic actors only; real sprite packing rates and DS upload/geometry costs not measured.','Scroll restoration uses production strip-copy code with synthetic immutable world pixels; actual VRAM bank publication is not exercised.','No GPU rasterization, depth ordering or runtime integration yet.'])
 result['header_sha256']=hashlib.sha256(args.header.read_bytes()).hexdigest();result['inactive_metadata_poisoned_before_reset']=True
 (args.output or R/'research/rendering/actor-atlas-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
