#ifndef KINDER_NATIVE_METADATA_CACHE_H
#define KINDER_NATIVE_METADATA_CACHE_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
/* Metadata owns a fixed partition of the existing source arena. It never
 * consumes texture-range records or evicts resident texture/palette bytes. */
#define NATIVE_METADATA_BLOCK_BYTES 1024u
#define NATIVE_METADATA_BLOCKS 32u
#define NATIVE_METADATA_BYTES (NATIVE_METADATA_BLOCK_BYTES*NATIVE_METADATA_BLOCKS)
typedef bool (*NativeMetadataRead)(void *,uint32_t,void *,uint32_t);
typedef struct {
 uint8_t *memory;
 uint32_t offsets[NATIVE_METADATA_BLOCKS],ages[NATIVE_METADATA_BLOCKS];
 uint32_t valid,clock,hits,misses;
} NativeMetadataCache;
static inline void native_metadata_forget(NativeMetadataCache *c){
 if(c){c->valid=0;c->clock=0;}
}
static inline void native_metadata_assign(NativeMetadataCache *c,void *memory){
 if(c->memory!=memory){native_metadata_forget(c);c->memory=memory;}
}
static inline bool native_metadata_read(NativeMetadataCache *c,uint32_t total,
 uint32_t at,void *out,uint32_t bytes,NativeMetadataRead read,void *context){
 if(!c||!c->memory||!out||!read||at>total||bytes>total-at)return false;
 uint8_t *dest=out;
 while(bytes){
  if(c->clock==UINT32_MAX)native_metadata_forget(c);
  uint32_t base=at&~(NATIVE_METADATA_BLOCK_BYTES-1u);
  unsigned slot=NATIVE_METADATA_BLOCKS;
  for(unsigned i=0;i<NATIVE_METADATA_BLOCKS;i++)
   if((c->valid&(1u<<i))&&c->offsets[i]==base){slot=i;break;}
  if(slot<NATIVE_METADATA_BLOCKS)c->hits++;
  else{
   c->misses++;slot=0;
   for(unsigned i=0;i<NATIVE_METADATA_BLOCKS;i++){
    if(!(c->valid&(1u<<i))){slot=i;break;}
    if(c->ages[i]<c->ages[slot])slot=i;
   }
   c->valid&=~(1u<<slot);
   uint32_t count=total-base;
   if(count>NATIVE_METADATA_BLOCK_BYTES)count=NATIVE_METADATA_BLOCK_BYTES;
   if(!read(context,base,c->memory+slot*NATIVE_METADATA_BLOCK_BYTES,count))return false;
   c->offsets[slot]=base;c->valid|=1u<<slot;
  }
  c->ages[slot]=++c->clock;
  uint32_t local=at-base,count=NATIVE_METADATA_BLOCK_BYTES-local;
  if(count>bytes)count=bytes;
  memcpy(dest,c->memory+slot*NATIVE_METADATA_BLOCK_BYTES+local,count);
  at+=count;dest+=count;bytes-=count;
 }
 return true;
}
#endif
