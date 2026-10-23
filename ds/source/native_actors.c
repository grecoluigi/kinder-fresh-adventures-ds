#include "native_actors.h"
#include "player_graphics.h"
#include "scene.h"
#if defined(__NDS__) || defined(KF_HOST_NATIVE_ACTORS)
#include "native_stream.h"
#include "native_catalog.h"
#include "native_cache.h"
#include "hot_code.h"
#include "texture_window.h"
#include <stdlib.h>
#ifndef NATIVE_ACTOR_ROOT
#define NATIVE_ACTOR_ROOT "nitro:/native_actors"
#endif
static NativeStream stream;
static NativeSourceCache source_cache;
static NativeMetadataCache metadata_cache;
static const uint16_t *transient_pixels;
static bool allowed,skipped_sources;
static volatile bool gpu_native_sources_complete;
static volatile bool gpu_native_force_failure;
void gpu_native_allow(bool enabled){allowed=enabled;}
void gpu_native_source(void *memory,size_t bytes){transient_pixels=bytes>=32768?(const uint16_t *)memory:NULL;}
void gpu_native_forget_source(void){native_source_forget(&source_cache);native_metadata_forget(&metadata_cache);stream.source=NULL;stream.metadata=NULL;metadata_cache.memory=NULL;}
bool gpu_native_skipped_sources(void){return skipped_sources;}
bool gpu_native_enabled(void){return allowed;}
void gpu_native_skip_source(void){skipped_sources=true;}
static NativeCatalog index_data;
static uint32_t catalog_offset;
static bool catalog_read(void *context,uint32_t at,void *out,uint32_t bytes){return native_stream_metadata((NativeStream *)context,catalog_offset+at,out,bytes);}
static uint8_t *verified_pages;
static char map_name[64];
static bool map_loaded,failed,identity_armed;
static unsigned identity_kind,identity_frame,draw_count;
static NativeDraw draws[NATIVE_DRAW_LIMIT];
static NativeCache texture_cache[2],palette_cache[2];
static unsigned palette_epoch;
static uint8_t palette_scratch[512] __attribute__((aligned(4)));
static volatile unsigned gpu_native_crc_bytes;
static volatile unsigned gpu_native_io_reads,gpu_native_io_bytes;
static volatile unsigned gpu_native_page_hits,gpu_native_texture_bytes,gpu_native_palette_bytes,gpu_native_failures;
void gpu_native_invalidate(unsigned bank){if(bank<2){native_cache_clear(texture_cache+bank);native_cache_clear(palette_cache+bank);}}
static void native_map(const char *name){
 if(!name)name="";
 if(!strcmp(map_name,name))return;
 free(verified_pages);verified_pages=NULL;
 memset(&index_data,0,sizeof(index_data));map_loaded=false;
 gpu_native_invalidate(0);gpu_native_invalidate(1);
 if(snprintf(map_name,sizeof(map_name),"%s",name)>=(int)sizeof(map_name)){map_name[0]=0;return;}
 if(!*map_name)return;
 char path[192];
 if(!stream.file){if(snprintf(path,sizeof(path),"%s/pages.gpu",NATIVE_ACTOR_ROOT)>=(int)sizeof(path)||!native_stream_open(&stream,path)||stream.pages>65535)return;}
 uint8_t footer[32];
 if(stream.bytes<64||!native_stream_metadata(&stream,stream.bytes-32,footer,32)||memcmp(footer,"KGC1",4)||native_stream_u32(footer+4)!=1||native_stream_u32(footer+16)!=stream.pages||native_stream_u32(footer+20)!=stream.bytes||native_stream_u32(footer+24)||native_stream_u32(footer+28))return;
 uint32_t offset=native_stream_u32(footer+8),bytes=native_stream_u32(footer+12);
 if(offset<32u+stream.pages*32u||!native_stream_range(stream.bytes-32u,offset,bytes)||offset+bytes!=stream.bytes-32u)return;
 catalog_offset=offset;
 map_loaded=native_catalog_init(&index_data,catalog_read,&stream,bytes,stream.pages);
 if(map_loaded&&index_data.frames){verified_pages=calloc((stream.pages+3u)/4u,1);if(!verified_pages)map_loaded=false;}

}
void gpu_native_reset(const char *map){if(!map||!*map)gpu_native_forget_source();native_map(map);failed=!map_loaded;identity_armed=false;draw_count=0;skipped_sources=false;gpu_native_sources_complete=false;unsigned player_bytes=0,enemy_bytes=0;void *player_pool=NULL,*enemy_pool=NULL;if(map_loaded&&index_data.frames){player_pool=player_graphics_native_cache(&player_bytes);enemy_pool=scene_native_cache(&enemy_bytes);}if(player_pool&&player_bytes>=NATIVE_METADATA_BYTES+NATIVE_SOURCE_BYTES){
 native_metadata_assign(&metadata_cache,player_pool);stream.metadata=&metadata_cache;
 native_source_assign(&source_cache,(uint8_t *)player_pool+NATIVE_METADATA_BYTES,player_bytes-NATIVE_METADATA_BYTES);
 native_source_pools(&source_cache,(uint8_t *)player_pool+NATIVE_METADATA_BYTES+NATIVE_SOURCE_BYTES,player_bytes-NATIVE_METADATA_BYTES-NATIVE_SOURCE_BYTES,enemy_pool,enemy_bytes,NULL);stream.source=&source_cache;
 }else{gpu_native_forget_source();native_source_pools(&source_cache,NULL,0,NULL,0,NULL);}}
void gpu_native_identity(unsigned kind,unsigned frame){identity_kind=kind;identity_frame=frame;identity_armed=true;}
void gpu_native_sprite(unsigned width,unsigned height,int left,int top,unsigned kind,unsigned order){
 bool armed=identity_armed;identity_armed=false;
 #ifdef KF_NATIVE_FAST_REFERENCE
 failed=true;return;
 #endif
 if(!allowed){failed=true;return;}
 if(failed)return;
 if(left>=256||top>=192||left<=-(int)width||top<=-(int)height)return;
 NativeCatalogFrame f;
 if(!armed||kind>2||kind!=identity_kind||order>255||!native_catalog_find(&index_data,kind,identity_frame,&f)||f.width!=width||f.height!=height){failed=true;return;}
 NativeCatalogRef references[NATIVE_CATALOG_BATCH];
 for(unsigned i=0;i<f.count;i++){
  unsigned local=i%NATIVE_CATALOG_BATCH;
  if(!local){unsigned count=f.count-i;if(count>NATIVE_CATALOG_BATCH)count=NATIVE_CATALOG_BATCH;if(!native_catalog_refs(&index_data,&f,i,count,references)){failed=true;return;}}
  const NativeCatalogRef *r=references+local;
  unsigned sx=r->x,sy=r->y,w=r->width,h=r->height,u=0,v=0;
  int x=left+(int)sx,y=top+(int)sy;
  if(x>=256||y>=192||x<=-(int)w||y<=-(int)h)continue;
  if(x<0){u=(unsigned)-x;w-=u;x=0;}
  if(y<0){v=(unsigned)-y;h-=v;y=0;}
  if(w>(unsigned)(256-x))w=(unsigned)(256-x);
  if(h>(unsigned)(192-y))h=(unsigned)(192-y);
  if(r->page>>31)u=r->width-u-w;
  if(draw_count==NATIVE_DRAW_LIMIT){failed=true;return;}
  draws[draw_count++]=(NativeDraw){(uint16_t)r->page,(int16_t)x,(int16_t)y,(uint16_t)u,(uint16_t)v,(uint16_t)w,(uint16_t)h,(uint16_t)order,0,0,0,(uint16_t)(r->page>>31)};
 }
}
void gpu_native_transient(const ActorPiece *p){
 if(failed)return;
 if(!p||!transient_pixels||draw_count==NATIVE_DRAW_LIMIT||!p->width||p->width>256||!p->height||p->height>8||p->x+p->width>256||p->y+p->height>64){failed=true;return;}
 draws[draw_count++]=(NativeDraw){65535,(int16_t)p->screen_x,(int16_t)p->screen_y,0,0,p->width,p->height,p->order,0,0,(uint16_t)(p->y*256u+p->x),0};
}
bool gpu_native_try(unsigned kind,unsigned frame,unsigned width,unsigned height,int left,int top,unsigned order){
 if(!allowed||failed)return false;
 gpu_native_identity(kind,frame);gpu_native_sprite(width,height,left,top,kind,order);
 if(failed)return false;
 skipped_sources=true;return true;
}
bool gpu_native_available(void){gpu_native_sources_complete=!failed&&draw_count>0;return gpu_native_sources_complete;}
const NativeDraw *gpu_native_draws(unsigned *count){*count=draw_count;return draws;}
KF_ITCM_CODE bool gpu_native_prepare(unsigned bank,int camera_y,unsigned epoch,volatile uint16_t *texture,volatile uint16_t *palette,uint16_t *scratch){
 unsigned initial_reads=stream.reads,initial_bytes=stream.read_bytes;
 gpu_native_io_reads=gpu_native_io_bytes=gpu_native_crc_bytes=0;
 gpu_native_page_hits=gpu_native_texture_bytes=gpu_native_palette_bytes=0;
 if(gpu_native_force_failure){gpu_native_failures++;return false;}
 if(!gpu_native_available()||bank>=2||!texture||!palette||!scratch||camera_y<0)return false;
 if(epoch!=palette_epoch){gpu_native_invalidate(0);gpu_native_invalidate(1);palette_epoch=epoch;}
 unsigned start=((unsigned)camera_y+192u)&255u;
 if(start<=192)native_cache_begin(texture_cache+bank,start*512u,(start+64u)*512u,0,0);
 else native_cache_begin(texture_cache+bank,0,(start-192u)*512u,start*512u,131072);
 native_cache_begin(palette_cache+bank,0,16384,0,0);
 /* Transient keys describe this frame only. Keep immutable pages resident. */
 for(unsigned i=0;i<texture_cache[bank].count;){if(texture_cache[bank].entries[i].key&0x80000000u)native_cache_remove(texture_cache+bank,i);else i++;}
 for(unsigned i=0;i<draw_count;i++){
  NativeDraw *d=draws+i;
  if(d->page==65535){
   unsigned width=8,exponent=0;while(width<d->w){width*=2;exponent++;}
   uint32_t at;bool hit;
   if(!transient_pixels||!native_cache_get(texture_cache+bank,0x80000000u|i,width*16u,&at,&hit))goto fail;
   memset(scratch,0,width*16u);
   for(unsigned row=0;row<d->h;row++)memcpy(scratch+row*width,transient_pixels+d->source_at+row*256u,d->w*2u);
   texture_copy_rgb555(texture+at/2u,scratch,width*8u);gpu_native_texture_bytes+=width*16u;
   d->format=((bank*131072u+at)>>3)|(exponent<<20)|(7u<<26);d->palette=0;continue;
  }
NativeStreamPage p;uint32_t at,pal=0;bool hit,pal_hit=true;
  if(!native_stream_record(&stream,d->page,&p)||d->u+d->w>p.width||d->v+d->h>p.height||!native_cache_get(texture_cache+bank,d->page,p.texture_bytes,&at,&hit))goto fail;
  if(p.palette_bytes&&!native_cache_get(palette_cache+bank,p.palette,p.palette_bytes,&pal,&pal_hit))goto fail;
  if(!hit){
   if(!native_stream_read(&stream,p.texture,scratch,p.texture_bytes))goto fail;
   unsigned flag=1u<<((d->page&3u)*2u);
   if(!verified_pages||!(verified_pages[d->page/4u]&flag)){gpu_native_crc_bytes+=p.texture_bytes;if(native_stream_crc((const uint8_t *)scratch,p.texture_bytes)!=p.texture_crc)goto fail;if(verified_pages)verified_pages[d->page/4u]|=(uint8_t)flag;}
   texture_copy_rgb555(texture+at/2u,scratch,p.texture_bytes/2u);gpu_native_texture_bytes+=p.texture_bytes;
  }else gpu_native_page_hits++;
  if(!pal_hit){
   if(!native_stream_read(&stream,p.palette,palette_scratch,p.palette_bytes))goto fail;
   unsigned flag=2u<<((d->page&3u)*2u);
   if(!verified_pages||!(verified_pages[d->page/4u]&flag)){gpu_native_crc_bytes+=p.palette_bytes;if(native_stream_crc(palette_scratch,p.palette_bytes)!=p.palette_crc)goto fail;if(verified_pages)verified_pages[d->page/4u]|=(uint8_t)flag;}
   texture_copy_rgb555(palette+pal/2u,(const uint16_t *)palette_scratch,p.palette_bytes/2u);gpu_native_palette_bytes+=p.palette_bytes;
  }
  unsigned width=0,height=0;for(unsigned w=p.width;w>8;w>>=1)width++;for(unsigned h=p.height;h>8;h>>=1)height++;
  d->format=((bank*131072u+at)>>3)|(width<<20)|(height<<23)|((p.bits==4?3u:p.bits==8?4u:7u)<<26)|(p.bits<16?1u<<29:0);
  d->palette=(bank*16384u+pal)>>4;
 }
 gpu_native_io_reads=stream.reads-initial_reads;gpu_native_io_bytes=stream.read_bytes-initial_bytes;
 return true;
 fail:gpu_native_io_reads=stream.reads-initial_reads;gpu_native_io_bytes=stream.read_bytes-initial_bytes;gpu_native_failures++;gpu_native_invalidate(bank);return false;
}
#endif
