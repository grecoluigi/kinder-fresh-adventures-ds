#ifndef KINDER_NATIVE_BG_CACHE_H
#define KINDER_NATIVE_BG_CACHE_H
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#define NATIVE_BG_SLOTS 960u
#define NATIVE_BG_LOOKUP 2048u
#define NATIVE_BG_VALID 1u
#define NATIVE_BG_FRONT 2u
#define NATIVE_BG_NEXT 4u
typedef struct {uint32_t key;uint8_t flags,pad[3];} NativeBGEntry;
typedef struct {
 NativeBGEntry entries[NATIVE_BG_SLOTS];uint16_t lookup[NATIVE_BG_LOOKUP];
 unsigned victim,state,hits,uploads,failures,evictions;
} NativeBGCache;
typedef bool (*NativeBGUpload)(void *,uint32_t,unsigned);
static inline unsigned native_bg_hash(uint32_t key){return (key*2654435761u)>>21;}
static inline int native_bg_find(const NativeBGCache *c,uint32_t key){
 unsigned at=native_bg_hash(key);
 for(unsigned i=0;i<NATIVE_BG_LOOKUP;i++,at=(at+1)&(NATIVE_BG_LOOKUP-1)){
  unsigned entry=c->lookup[at];if(!entry)return -1;
  if(c->entries[entry-1].key==key)return (int)(entry-1);
 }
 return -1;
}
static inline void native_bg_insert(NativeBGCache *c,unsigned slot){
 unsigned at=native_bg_hash(c->entries[slot].key);
 while(c->lookup[at])at=(at+1)&(NATIVE_BG_LOOKUP-1);
 c->lookup[at]=(uint16_t)(slot+1);
}
static inline void native_bg_erase(NativeBGCache *c,unsigned slot){
 unsigned at=native_bg_hash(c->entries[slot].key);
 while(c->lookup[at]!=(uint16_t)(slot+1))at=(at+1)&(NATIVE_BG_LOOKUP-1);
 c->lookup[at]=0;
 for(at=(at+1)&(NATIVE_BG_LOOKUP-1);c->lookup[at];at=(at+1)&(NATIVE_BG_LOOKUP-1)){
  unsigned moved=c->lookup[at]-1;c->lookup[at]=0;native_bg_insert(c,moved);
 }
}
/* Reset only after all old tilemap consumers are hidden. Caller clears graphic
 * slot0 to transparent pixels. It is permanently reserved and never uploaded. */
static inline bool native_bg_cache_reset(NativeBGCache *c,bool front_visible){
 if(!c||front_visible)return false;
 memset(c,0,sizeof(*c));c->entries[0].flags=NATIVE_BG_VALID|NATIVE_BG_FRONT;
 c->lookup[0]=1;c->victim=1;return true;
}
static inline bool native_bg_cache_begin(NativeBGCache *c){
 if(!c||c->state)return false;
 for(unsigned i=0;i<NATIVE_BG_SLOTS;i++)c->entries[i].flags&=(uint8_t)~NATIVE_BG_NEXT;
 c->entries[0].flags|=NATIVE_BG_NEXT;c->state=1;return true;
}
static inline bool native_bg_cache_acquire(NativeBGCache *c,uint32_t key,NativeBGUpload upload,void *context,unsigned *slot){
 if(!c||c->state!=1||!slot||key>=0x10000000u)return false;
 int found=native_bg_find(c,key);
 if(found>=0){c->entries[found].flags|=NATIVE_BG_NEXT;*slot=(unsigned)found;c->hits++;return true;}
 if(!upload){c->state=2;c->failures++;return false;}
 for(unsigned n=0;n<NATIVE_BG_SLOTS-1;n++){
  unsigned i=1+(c->victim-1+n)%(NATIVE_BG_SLOTS-1);NativeBGEntry *e=c->entries+i;
  if(e->flags&(NATIVE_BG_FRONT|NATIVE_BG_NEXT))continue;
  if(e->flags&NATIVE_BG_VALID){native_bg_erase(c,i);c->evictions++;}
  memset(e,0,sizeof(*e));
  /* Failed/partial writes invalidate this unreferenced slot. Never retain an
   * old lookup key whose graphics may now be damaged. */
  if(!upload(context,key,i)){c->state=2;c->failures++;return false;}
  e->key=key;e->flags=NATIVE_BG_VALID|NATIVE_BG_NEXT;native_bg_insert(c,i);
  c->victim=i==NATIVE_BG_SLOTS-1?1:i+1;c->uploads++;*slot=i;return true;
 }
 c->state=2;c->failures++;return false;
}
/* Publish only after the caller has made matching map/scroll state visible. */
static inline bool native_bg_cache_publish(NativeBGCache *c){
 if(!c||c->state!=1)return false;
 for(unsigned i=0;i<NATIVE_BG_SLOTS;i++){
  uint8_t flags=c->entries[i].flags;
  c->entries[i].flags=(uint8_t)((flags&NATIVE_BG_VALID)|((flags&NATIVE_BG_NEXT)?NATIVE_BG_FRONT:0));
 }
 c->entries[0].flags|=NATIVE_BG_FRONT;c->state=0;return true;
}
static inline void native_bg_cache_abort(NativeBGCache *c){
 if(!c)return;
 for(unsigned i=0;i<NATIVE_BG_SLOTS;i++)c->entries[i].flags&=(uint8_t)~NATIVE_BG_NEXT;
 c->state=0;
}
#endif
