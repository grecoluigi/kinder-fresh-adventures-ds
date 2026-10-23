#ifndef KINDER_NATIVE_CATALOG_H
#define KINDER_NATIVE_CATALOG_H
/* Bounded KAF1 index access. The caller supplies immutable storage and owns
 * its cache/file lifetime. No catalog-sized allocation or global file state.
 * Failed operations leave their outputs unusable; callers must discard them. */
#include "native_stream.h"
#define NATIVE_CATALOG_SLOTS 16u
#define NATIVE_CATALOG_BATCH 32u
typedef bool (*NativeCatalogRead)(void *,uint32_t,void *,uint32_t);
typedef struct {uint32_t kind,id,first,count;uint16_t width,height;} NativeCatalogFrame;
typedef struct {uint32_t page;uint16_t x,y,width,height;} NativeCatalogRef;
typedef struct {
 NativeCatalogRead read;void *storage;
 uint32_t bytes,pages,frames,refs,ref_offset,valid,frame_offset;
 uint32_t kind_first[3],kind_count[3];bool mirrored_refs;
 NativeCatalogFrame cache[NATIVE_CATALOG_SLOTS];
} NativeCatalog;
static inline bool native_catalog_init(NativeCatalog *c,NativeCatalogRead read,void *storage,uint32_t bytes,uint32_t pages){
 if(!c)return false;
 memset(c,0,sizeof(*c));
 uint8_t h[32];
 if(!read||bytes<32||!pages||!read(storage,0,h,sizeof(h))||native_stream_u32(h+4)!=1||native_stream_u32(h+24)!=bytes||native_stream_u32(h+28))return false;
 bool mirrored=!memcmp(h,"KAD2",4);bool direct=mirrored||!memcmp(h,"KAD1",4);unsigned frame_offset=direct?64u:32u;
 if((!direct&&memcmp(h,"KAF1",4))||bytes<frame_offset||native_stream_u32(h+16)!=frame_offset)return false;
 uint32_t frames=native_stream_u32(h+8),refs=native_stream_u32(h+12),offset=native_stream_u32(h+20);
 if(frames>(bytes-frame_offset)/24u||offset!=frame_offset+frames*24u||refs>(bytes-offset)/12u||offset+refs*12u!=bytes)return false;
 if(direct){
  uint8_t dense[32];if(!read(storage,32,dense,32)||native_stream_u32(dense+24)!=pages||native_stream_u32(dense+28))return false;
  uint32_t next=0;
  for(unsigned kind=0;kind<3;kind++){
   unsigned first=native_stream_u32(dense+kind*4u),count=native_stream_u32(dense+12u+kind*4u);
   if(first!=next||first>frames||count>frames-first)return false;
   c->kind_first[kind]=first;c->kind_count[kind]=count;next+=count;
  }
  if(next!=frames)return false;
 }
 c->mirrored_refs=mirrored;c->read=read;c->storage=storage;c->bytes=bytes;c->pages=pages;c->frames=frames;c->refs=refs;c->ref_offset=offset;c->frame_offset=frame_offset;
 return true;
}
static inline bool native_catalog_record(NativeCatalog *c,unsigned at,NativeCatalogFrame *f){
 uint8_t r[24];
 if(!c||!c->read||!f||at>=c->frames||!c->read(c->storage,c->frame_offset+at*24u,r,sizeof(r)))return false;
 NativeCatalogFrame value={native_stream_u32(r),native_stream_u32(r+4),native_stream_u32(r+12),native_stream_u32(r+16),native_stream_u16(r+8),native_stream_u16(r+10)};
 if(value.kind>2||!value.width||value.width>1024||!value.height||value.height>1024||native_stream_u32(r+20)||value.first>c->refs||value.count>c->refs-value.first)return false;
 *f=value;return true;
}
static inline bool native_catalog_find(NativeCatalog *c,unsigned kind,unsigned id,NativeCatalogFrame *f){
 if(!c||!c->read||!f||kind>2)return false;
 unsigned slot=(id*2654435761u+kind*17u)&(NATIVE_CATALOG_SLOTS-1u);
 if((c->valid&(1u<<slot))&&c->cache[slot].kind==kind&&c->cache[slot].id==id){*f=c->cache[slot];return true;}
 if(c->frame_offset==64u){
  NativeCatalogFrame found;
  if(id>=c->kind_count[kind]||!native_catalog_record(c,c->kind_first[kind]+id,&found)||found.kind!=kind||found.id!=id)return false;
  c->cache[slot]=found;c->valid|=1u<<slot;*f=found;return true;
 }
 uint32_t low=0,high=c->frames;
 while(low<high){
  uint32_t mid=low+(high-low)/2u;NativeCatalogFrame candidate;
  if(!native_catalog_record(c,mid,&candidate))return false;
  if(candidate.kind<kind||(candidate.kind==kind&&candidate.id<id))low=mid+1u;else high=mid;
 }
 NativeCatalogFrame found;
 if(low==c->frames||!native_catalog_record(c,low,&found)||found.kind!=kind||found.id!=id)return false;
 c->cache[slot]=found;c->valid|=1u<<slot;*f=found;return true;
}
static inline bool native_catalog_refs(NativeCatalog *c,const NativeCatalogFrame *f,unsigned first,unsigned count,NativeCatalogRef *out){
 if(!c||!c->read||!f||!out||!count||count>NATIVE_CATALOG_BATCH||!f->width||!f->height||f->first>c->refs||f->count>c->refs-f->first||first>f->count||count>f->count-first)return false;
 uint8_t r[NATIVE_CATALOG_BATCH*12u];
 if(!c->read(c->storage,c->ref_offset+(f->first+first)*12u,r,count*12u))return false;
 for(unsigned i=0;i<count;i++){
  const uint8_t *p=r+i*12u;
  NativeCatalogRef value={native_stream_u32(p),native_stream_u16(p+4),native_stream_u16(p+6),native_stream_u16(p+8),native_stream_u16(p+10)};
  if((value.page&(c->mirrored_refs?0x7fffffffu:0xffffffffu))>=c->pages||!value.width||value.width>256||!value.height||value.height>32||value.x>f->width||value.width>f->width-value.x||value.y>f->height||value.height>f->height-value.y)return false;
  out[i]=value;
 }
 return true;
}
#endif
