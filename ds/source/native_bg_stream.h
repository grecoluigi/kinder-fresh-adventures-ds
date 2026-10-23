#ifndef KINDER_NATIVE_BG_STREAM_H
#define KINDER_NATIVE_BG_STREAM_H
#include "native_bg_assets.h"
#include "native_bg_cache.h"
typedef struct {uint32_t id,age,words[256];bool valid;} NativeBGPage;
typedef struct {
 NativeBGAssets assets;NativeBGCache cache;NativeBGPage pages[9];
 uint16_t map[2048],front_refs[960],next_refs[960];unsigned age,page_reads,tile_reads,map_writes;
 int front_x,front_y,target_x,target_y;bool visible,pending,repeated;
 uint16_t changed[960],changed_count;uint8_t changed_bits[120];
 unsigned pin_updates,pin_changes_peak;
} NativeBGStream;
_Static_assert(sizeof(NativeBGStream)<=NATIVE_BG_CACHE_BYTES+49152u,"native tile stream workspace budget");
typedef bool (*NativeBGTileWriter)(void *,unsigned,const uint16_t *);
typedef bool (*NativeBGMapWriter)(void *,unsigned,uint16_t);
typedef enum {NATIVE_BG_STREAM_READY,NATIVE_BG_STREAM_BAD,NATIVE_BG_STREAM_BRIDGE} NativeBGStreamResult;
/* A previous file must be closed before opening. The caller must hide all old
 * tilemap consumers, load palettes and clear graphics slot0 before prepare. */
static inline bool native_bg_stream_open(NativeBGStream *s,const char *path,bool front_visible){
 if(!s||front_visible)return false;
 memset(s,0,sizeof(*s));
 if(!native_bg_open(&s->assets,path))return false;
 uint8_t blank[64];
 if(!native_bg_tile(&s->assets,0,blank)){native_bg_close(&s->assets);return false;}
 for(unsigned i=0;i<64;i++)if(blank[i]){native_bg_close(&s->assets);return false;}
 return native_bg_cache_reset(&s->cache,false);
}
static inline bool native_bg_stream_close(NativeBGStream *s,bool front_visible){
 if(!s||front_visible)return false;
 native_bg_close(&s->assets);memset(s,0,sizeof(*s));return true;
}
static inline unsigned native_bg_map_at(unsigned x,unsigned y){return (y&31u)*32u+(x&31u)+((x&63u)>>5)*1024u;}
static inline bool native_bg_stream_word(NativeBGStream *s,unsigned x,unsigned y,uint32_t *word){
 unsigned id=(y/16)*((s->assets.width+15)/16)+x/16,slot=0;
 while(slot<9&&(!s->pages[slot].valid||s->pages[slot].id!=id))slot++;
 if(slot==9){
  slot=0;
  for(unsigned i=0;i<9;i++){
   if(!s->pages[i].valid){slot=i;break;}
   if(s->pages[i].age<s->pages[slot].age)slot=i;
  }
  NativeBGPage *p=s->pages+slot;p->valid=false;
  if(!native_bg_page(&s->assets,id,p->words))return false;
  p->id=id;p->valid=true;s->page_reads++;
 }
 if(++s->age==0){s->age=1;for(unsigned i=0;i<9;i++)s->pages[i].age=0;}
 s->pages[slot].age=s->age;*word=s->pages[slot].words[(y%16)*16+x%16];return true;
}
typedef struct {NativeBGStream *stream;NativeBGTileWriter write;void *context;} NativeBGUploadContext;
static inline bool native_bg_stream_upload(void *context,uint32_t key,unsigned slot){
 NativeBGUploadContext *u=context;uint16_t pixels[32];u->stream->tile_reads++;
 return native_bg_tile(&u->stream->assets,key,(uint8_t *)pixels)&&u->write(u->context,slot,pixels);
}
static inline bool native_bg_stream_touch(NativeBGStream *s,unsigned slot){
 if(slot>=960)return false;
 unsigned mask=1u<<(slot&7u);
 if(!(s->changed_bits[slot>>3]&mask)){
  if(s->changed_count==960)return false;
  s->changed_bits[slot>>3]|=(uint8_t)mask;s->changed[s->changed_count++]=(uint16_t)slot;
 }
 return true;
}
static inline void native_bg_stream_abort(NativeBGStream *s){if(s){
 native_bg_cache_abort(&s->cache);
 for(unsigned i=0;i<s->changed_count;i++){
  unsigned slot=s->changed[i];s->next_refs[slot]=s->front_refs[slot];
  s->changed_bits[slot>>3]&=(uint8_t)~(1u<<(slot&7u));
 }
 s->changed_count=0;s->pending=s->repeated=false;
}}
typedef struct {int l,t,r,b;} NativeBGRect;
static inline NativeBGRect native_bg_rect(int x,int y){return (NativeBGRect){x/8,y/8,(x+255)/8,(y+191)/8};}
static inline bool native_bg_rect_valid(NativeBGRect a){return a.l<=a.r&&a.t<=a.b;}
static inline int native_bg_min(int a,int b){return a<b?a:b;}
static inline int native_bg_max(int a,int b){return a>b?a:b;}
typedef bool (*NativeBGCellAction)(NativeBGStream *,unsigned,unsigned,void *);
static inline bool native_bg_rect_run(NativeBGStream *s,NativeBGRect a,NativeBGCellAction action,void *context){
 if(!native_bg_rect_valid(a))return true;
 for(int y=a.t;y<=a.b;y++)for(int x=a.l;x<=a.r;x++)if(!action(s,(unsigned)x,(unsigned)y,context))return false;
 return true;
}
/* Four disjoint strips cover A minus B. Common interior cells are never
 * enumerated; this also works for empty or disjoint rectangles. */
static inline bool native_bg_rect_difference(NativeBGStream *s,NativeBGRect a,NativeBGRect b,NativeBGCellAction action,void *context){
 if(!native_bg_rect_valid(a))return true;
 if(!native_bg_rect_valid(b))return native_bg_rect_run(s,a,action,context);
 int top=native_bg_max(a.t,b.t),bottom=native_bg_min(a.b,b.b);
 NativeBGRect strips[4]={{a.l,a.t,a.r,native_bg_min(a.b,b.t-1)},
  {a.l,native_bg_max(a.t,b.b+1),a.r,a.b},
  {a.l,top,native_bg_min(a.r,b.l-1),bottom},
  {native_bg_max(a.l,b.r+1),top,a.r,bottom}};
 for(unsigned i=0;i<4;i++)if(!native_bg_rect_run(s,strips[i],action,context))return false;
 return true;
}
static inline bool native_bg_stream_leave(NativeBGStream *s,unsigned x,unsigned y,void *context){
 (void)context;unsigned slot=s->map[native_bg_map_at(x,y)]&1023;
 if(slot>=960||!s->next_refs[slot]||!native_bg_stream_touch(s,slot))return false;
 if(--s->next_refs[slot]==0&&slot)s->cache.entries[slot].flags&=(uint8_t)~NATIVE_BG_NEXT;
 return true;
}
typedef struct {NativeBGUploadContext upload;NativeBGMapWriter map_writer;} NativeBGEdgeContext;
static inline bool native_bg_stream_enter(NativeBGStream *s,unsigned x,unsigned y,void *context){
 NativeBGEdgeContext *c=context;uint32_t source;unsigned slot;
 if(!native_bg_stream_word(s,x,y,&source)||!native_bg_cache_acquire(&s->cache,source&0x0fffffff,native_bg_stream_upload,&c->upload,&slot))return false;
 if(!native_bg_stream_touch(s,slot)||s->next_refs[slot]==65535)return false;
 unsigned at=native_bg_map_at(x,y);uint16_t word=(uint16_t)(slot|((source>>28)<<12));
 /* New cells always rewrite: a previous failed partial map write cannot
  * leave stale hardware contents hidden behind a matching CPU mirror. */
 if(!c->map_writer(c->upload.context,at,word))return false;
 s->map[at]=word;s->next_refs[slot]++;s->map_writes++;return true;
}
static inline NativeBGStreamResult native_bg_stream_prepare(NativeBGStream *s,int x,int y,NativeBGTileWriter tile_writer,NativeBGMapWriter map_writer,void *context){
 if(!s||!s->assets.file||s->pending||s->cache.state||!tile_writer||!map_writer||x<0||y<0||s->assets.width*8<256||s->assets.height*8<192||
    (unsigned)x>s->assets.width*8-256||(unsigned)y>s->assets.height*8-192)return NATIVE_BG_STREAM_BAD;
 if(s->visible&&(x<s->front_x-16||x>s->front_x+16||y<s->front_y-16||y>s->front_y+16))return NATIVE_BG_STREAM_BRIDGE;
 NativeBGRect next=native_bg_rect(x,y),old=s->visible?native_bg_rect(s->front_x,s->front_y):(NativeBGRect){1,1,0,0};
 if(s->visible&&old.l==next.l&&old.r==next.r&&old.t==next.t&&old.b==next.b){
  s->target_x=x;s->target_y=y;s->pending=s->repeated=true;return NATIVE_BG_STREAM_READY;
 }
 /* FRONT pins already protect the retained interior. NEXT is needed only
  * for entering graphics; counts differ only at changed edge slots. Every
  * successful publish/abort clears those NEXT flags before the next begin. */
 if(s->changed_count)return NATIVE_BG_STREAM_BAD;
 s->cache.state=1;s->cache.entries[0].flags|=NATIVE_BG_NEXT;
 NativeBGEdgeContext edge={{s,tile_writer,context},map_writer};
 if(!native_bg_rect_difference(s,old,next,native_bg_stream_leave,NULL)||!native_bg_rect_difference(s,next,old,native_bg_stream_enter,&edge)){
  native_bg_stream_abort(s);return NATIVE_BG_STREAM_BAD;
 }
 s->target_x=x;s->target_y=y;s->pending=true;s->repeated=false;return NATIVE_BG_STREAM_READY;
}
/* Call only after hardware has accepted matching scroll/map publication. */
static inline bool native_bg_stream_publish(NativeBGStream *s){
 if(!s||!s->pending)return false;
 if(!s->repeated){
  if(s->cache.state!=1)return false;
  if(s->changed_count>s->pin_changes_peak)s->pin_changes_peak=s->changed_count;
  s->pin_updates+=s->changed_count;
  for(unsigned i=0;i<s->changed_count;i++){
   unsigned slot=s->changed[i];s->front_refs[slot]=s->next_refs[slot];
   s->cache.entries[slot].flags=(uint8_t)((s->cache.entries[slot].flags&NATIVE_BG_VALID)|(s->next_refs[slot]?NATIVE_BG_FRONT:0));
   s->changed_bits[slot>>3]&=(uint8_t)~(1u<<(slot&7u));
  }
  s->cache.entries[0].flags=NATIVE_BG_VALID|NATIVE_BG_FRONT;s->cache.state=0;s->changed_count=0;
 }
 s->front_x=s->target_x;s->front_y=s->target_y;s->visible=true;s->pending=s->repeated=false;return true;
}
#endif
