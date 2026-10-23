#ifndef KINDER_NATIVE_CACHE_H
#define KINDER_NATIVE_CACHE_H
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#define NATIVE_CACHE_ENTRIES 96u
#define NATIVE_CACHE_HINTS 128u
typedef struct {uint32_t key,at;uint16_t bytes,age;} NativeCacheEntry;
typedef struct {NativeCacheEntry entries[NATIVE_CACHE_ENTRIES];unsigned count;uint16_t epoch;uint32_t allowed[2][2];unsigned ranges;uint8_t hints[128];} NativeCache;
static inline void native_cache_clear(NativeCache *c){memset(c,0,sizeof(*c));}
static inline void native_cache_remove(NativeCache *c,unsigned i){memmove(c->entries+i,c->entries+i+1,(c->count-i-1)*sizeof(*c->entries));c->count--;}
static inline void native_cache_begin(NativeCache *c,uint32_t a,uint32_t b,uint32_t d,uint32_t e){
 if(++c->epoch==0){native_cache_clear(c);c->epoch=1;}
 c->allowed[0][0]=a;c->allowed[0][1]=b;c->allowed[1][0]=d;c->allowed[1][1]=e;c->ranges=d<e?2:1;
 for(unsigned i=0;i<c->count;){NativeCacheEntry *p=c->entries+i;bool valid=false;
  for(unsigned j=0;j<c->ranges;j++)if(p->at>=c->allowed[j][0]&&p->at+p->bytes<=c->allowed[j][1])valid=true;
  if(valid)i++;else native_cache_remove(c,i);
 }
}
static inline bool native_cache_space(const NativeCache *c,unsigned bytes,uint32_t *at){
 for(unsigned r=0;r<c->ranges;r++){
  uint32_t here=(c->allowed[r][0]+15u)&~15u,end=c->allowed[r][1];
  if(here>end)continue;
  for(unsigned i=0;i<c->count;i++){const NativeCacheEntry *p=c->entries+i;
   if(p->at+p->bytes<=here||p->at>=end)continue;
   if(bytes<=end-here&&here+bytes<=p->at){*at=here;return true;}
   here=(p->at+p->bytes+15u)&~15u;if(here>end)break;
  }
  if(here<=end&&bytes<=end-here){*at=here;return true;}
 }
 return false;
}
static inline bool native_cache_get(NativeCache *c,uint32_t key,unsigned bytes,uint32_t *at,bool *hit){
 if(!c||!at||!hit||!bytes||bytes>65535||!c->epoch)return false;
 unsigned bucket=(key^(key>>7)^(key>>17))&127u,found=(unsigned)c->hints[bucket]-1u;
 if(found>=c->count||c->entries[found].key!=key){found=c->count;for(unsigned i=0;i<c->count;i++)if(c->entries[i].key==key){found=i;break;}}
 if(found<c->count){if(c->entries[found].bytes!=bytes)return false;c->entries[found].age=c->epoch;c->hints[bucket]=(uint8_t)(found+1u);*at=c->entries[found].at;*hit=true;return true;}
 for(;;){
  if(c->count<NATIVE_CACHE_ENTRIES&&native_cache_space(c,bytes,at))break;
  unsigned victim=c->count;uint16_t oldest=UINT16_MAX;
  for(unsigned i=0;i<c->count;i++)if(c->entries[i].age!=c->epoch&&c->entries[i].age<oldest){oldest=c->entries[i].age;victim=i;}
  if(victim==c->count)return false;
  native_cache_remove(c,victim);
 }
 unsigned i=0;while(i<c->count&&c->entries[i].at<*at)i++;
 memmove(c->entries+i+1,c->entries+i,(c->count-i)*sizeof(*c->entries));c->entries[i]=(NativeCacheEntry){key,*at,(uint16_t)bytes,c->epoch};c->count++;c->hints[bucket]=(uint8_t)(i+1u);*hit=false;return true;
}
#endif
