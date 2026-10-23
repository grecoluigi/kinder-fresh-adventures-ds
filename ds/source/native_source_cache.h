#ifndef KINDER_NATIVE_SOURCE_CACHE_H
#define KINDER_NATIVE_SOURCE_CACHE_H
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define NATIVE_SOURCE_BYTES 32768u
#define NATIVE_SOURCE_SLOTS 256u
#define NATIVE_SOURCE_HINTS 128u
typedef struct {uint32_t offset,at,age;uint16_t bytes;} NativeSourceEntry;
typedef bool (*NativeSourceRead)(void *,uint32_t,void *,uint32_t,uint32_t *,uint32_t *);
typedef struct {uint8_t *memory,*extra,*other;unsigned extra_bytes,other_bytes;void (*before_write)(void *,size_t);NativeSourceEntry entries[NATIVE_SOURCE_SLOTS];uint32_t clock;unsigned count;uint16_t hints[128];} NativeSourceCache;
static inline void native_source_forget(NativeSourceCache *c){if(c){c->count=0;c->clock=0;}}
static inline void native_source_pools(NativeSourceCache *c,void *extra,unsigned extra_bytes,void *other,unsigned other_bytes,void (*before_write)(void *,size_t)){
 if(!c)return;
 if(c->extra!=extra||c->extra_bytes!=extra_bytes||c->other!=other||c->other_bytes!=other_bytes)native_source_forget(c);
 c->extra=extra;c->extra_bytes=extra?extra_bytes:0;c->other=other;c->other_bytes=other?other_bytes:0;c->before_write=before_write;
}
static inline void native_source_extra(NativeSourceCache *c,void *extra){native_source_pools(c,extra,extra?65536u:0,NULL,0,NULL);}
static inline uint8_t *native_source_pointer(NativeSourceCache *c,unsigned at){
 if(at<NATIVE_SOURCE_BYTES)return c->memory+at;
 at-=NATIVE_SOURCE_BYTES;if(at<c->extra_bytes)return c->extra+at;
 return c->other+at-c->extra_bytes;
}
static inline bool native_source_assign(NativeSourceCache *c,void *memory,size_t bytes){
 if(!c||!memory||bytes<NATIVE_SOURCE_BYTES)return false;
 if(c->memory!=memory){native_source_forget(c);c->memory=memory;}
 return true;
}
static inline void native_source_remove(NativeSourceCache *c,unsigned i){memmove(c->entries+i,c->entries+i+1,(c->count-i-1)*sizeof(*c->entries));c->count--;}
static inline void native_source_written(NativeSourceCache *c,const void *memory,size_t bytes){
 if(!c||!memory||!bytes)return;
 uintptr_t a=(uintptr_t)memory,b=a+bytes;
 for(unsigned i=0;i<c->count;){uintptr_t x=(uintptr_t)native_source_pointer(c,c->entries[i].at),y=x+c->entries[i].bytes;
  if(a<y&&x<b)native_source_remove(c,i);else i++;
 }
}
static inline bool native_source_space(const NativeSourceCache *c,unsigned bytes,unsigned *at){
 unsigned ends[4]={0,NATIVE_SOURCE_BYTES,NATIVE_SOURCE_BYTES+c->extra_bytes,NATIVE_SOURCE_BYTES+c->extra_bytes+c->other_bytes};
 for(unsigned range=0;range<3;range++){
  unsigned here=ends[range],end=ends[range+1];if(here==end)continue;
  for(unsigned i=0;i<c->count;i++){
   if(c->entries[i].at>=end||c->entries[i].at+c->entries[i].bytes<=here)continue;
   if(here+bytes<=c->entries[i].at){*at=here;return true;}
   here=(c->entries[i].at+c->entries[i].bytes+7u)&~7u;
  }
  if(here+bytes<=end){*at=here;return true;}
 }
 return false;
}
/* The caller owns the whole arena and forgets it before every other writer.
 * Output buffers do not overlap the arena. Cache exact immutable file ranges;
 * requests spanning the source arena are read directly without allocation. */
static inline bool native_source_read_from(NativeSourceCache *c,FILE *file,uint32_t total,uint32_t offset,void *out,uint32_t bytes,uint32_t *reads,uint32_t *read_bytes,NativeSourceRead reader,void *context){
 if(!c||!c->memory||!file||!out||offset>total||bytes>total-offset)return false;
 if(!bytes)return true;
 if(bytes>NATIVE_SOURCE_BYTES){
  if(reader)return reader(context,offset,out,bytes,reads,read_bytes);
  if(fseek(file,(long)offset,SEEK_SET))return false;
  (*reads)++;size_t n=fread(out,1,bytes,file);*read_bytes+=(uint32_t)n;return n==bytes;
 }
 if(c->clock==UINT32_MAX)native_source_forget(c);
 /* Hints may become stale when sorted entries move. Validate the complete
  * current range before using one; a hint never owns cache storage. */
 unsigned bucket=((offset>>10)^(offset>>17))&127u,found=(unsigned)c->hints[bucket]-1u;
 bool covered=found<c->count&&offset>=c->entries[found].offset&&offset-c->entries[found].offset<=c->entries[found].bytes&&bytes<=c->entries[found].bytes-(offset-c->entries[found].offset);
 if(!covered){
  found=c->count;
  for(unsigned i=0;i<c->count;i++)if(offset>=c->entries[i].offset&&offset-c->entries[i].offset<=c->entries[i].bytes&&bytes<=c->entries[i].bytes-(offset-c->entries[i].offset)){found=i;break;}
 }
 if(found<c->count){
  c->hints[bucket]=(uint16_t)(found+1u);c->entries[found].age=++c->clock;
  memcpy(out,native_source_pointer(c,c->entries[found].at)+offset-c->entries[found].offset,bytes);return true;
 }
 uint32_t base=offset&~1023u,count=((offset-base+bytes+1023u)/1024u)*1024u;
 if(count>NATIVE_SOURCE_BYTES){base=offset;count=bytes;}
 if(count>total-base)count=total-base;
 unsigned at=0;
 if(bytes<=NATIVE_SOURCE_BYTES){
  while(c->count==NATIVE_SOURCE_SLOTS||!native_source_space(c,count,&at)){
   unsigned oldest=0;for(unsigned i=1;i<c->count;i++)if(c->entries[i].age<c->entries[oldest].age)oldest=i;
   native_source_remove(c,oldest);
  }
 }
 uint8_t *dest=bytes<=NATIVE_SOURCE_BYTES?native_source_pointer(c,at):out;
 if(c->before_write)c->before_write(dest,count);
 if(reader){if(!reader(context,base,dest,count,reads,read_bytes))return false;}
 else{
  if(fseek(file,(long)base,SEEK_SET))return false;
  (*reads)++;size_t n=fread(dest,1,count,file);*read_bytes+=(uint32_t)n;
  if(n!=count)return false;
 }
 if(bytes<=NATIVE_SOURCE_BYTES){
  unsigned i=0;while(i<c->count&&c->entries[i].at<at)i++;
  memmove(c->entries+i+1,c->entries+i,(c->count-i)*sizeof(*c->entries));
  c->entries[i]=(NativeSourceEntry){base,at,++c->clock,(uint16_t)count};c->count++;c->hints[bucket]=(uint16_t)(i+1u);
  memcpy(out,dest+offset-base,bytes);
 }
 return true;
}
static inline bool native_source_read(NativeSourceCache *c,FILE *file,uint32_t total,uint32_t offset,void *out,uint32_t bytes,uint32_t *reads,uint32_t *read_bytes){return native_source_read_from(c,file,total,offset,out,bytes,reads,read_bytes,NULL,NULL);}
#endif
