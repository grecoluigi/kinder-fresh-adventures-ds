#ifndef KINDER_NATIVE_STREAM_H
#define KINDER_NATIVE_STREAM_H
/* Bounded file reader for the KGP1/KAF1 research asset formats.
 * No pack-wide allocation. Callers own page scratch and map lookup storage. */
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include "native_source_cache.h"
#include "native_metadata_cache.h"
typedef struct {uint32_t texture,palette,texture_bytes,palette_bytes,texture_crc,palette_crc;uint16_t width,height;uint8_t bits;} NativeStreamPage;
typedef struct {FILE *file;uint32_t bytes,pages,reads,read_bytes,cache_keys[96],cache_age[96];NativeStreamPage cache[96];uint32_t valid,clock,version;NativeSourceCache *source;NativeMetadataCache *metadata;uint8_t hints[128];} NativeStream;
static inline uint32_t native_stream_u32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static inline uint16_t native_stream_u16(const uint8_t *p){return (uint16_t)(p[0]|(uint16_t)p[1]<<8);}
static inline bool native_stream_range(uint32_t total,uint32_t offset,uint32_t count){return offset<=total&&count<=total-offset;}
static inline uint32_t native_stream_crc(const uint8_t *p,size_t bytes){
 static const uint32_t table[16]={0,0x1db71064u,0x3b6e20c8u,0x26d930acu,0x76dc4190u,0x6b6b51f4u,0x4db26158u,0x5005713cu,0xedb88320u,0xf00f9344u,0xd6d6a3e8u,0xcb61b38cu,0x9b64c2b0u,0x86d3d2d4u,0xa00ae278u,0xbdbdf21cu};
 uint32_t crc=UINT32_MAX;
 while(bytes--){crc^=*p++;crc=(crc>>4)^table[crc&15u];crc=(crc>>4)^table[crc&15u];}
 return ~crc;
}
static inline void native_stream_close(NativeStream *s){if(!s)return;if(s->file)fclose(s->file);memset(s,0,sizeof(*s));}
static inline bool native_stream_read(NativeStream *s,uint32_t at,void *out,uint32_t bytes){
 if(!s||!s->file||!out||!native_stream_range(s->bytes,at,bytes)||at>INT32_MAX)return false;
 if(s->source)return native_source_read(s->source,s->file,s->bytes,at,out,bytes,&s->reads,&s->read_bytes);
 if(fseek(s->file,(long)at,SEEK_SET))return false;
 s->reads++;size_t n=fread(out,1,bytes,s->file);s->read_bytes+=(uint32_t)n;return n==bytes;
}
/* Metadata requests bypass the payload range cache. The direct reader is
 * also used during pack open, before the caller has assigned its arena. */
static inline bool native_stream_metadata_direct(void *context,uint32_t at,void *out,uint32_t bytes){
 NativeStream *s=context;
 if(!s||!s->file||!out||!native_stream_range(s->bytes,at,bytes)||at>INT32_MAX)return false;
 if(fseek(s->file,(long)at,SEEK_SET))return false;
 s->reads++;size_t n=fread(out,1,bytes,s->file);s->read_bytes+=(uint32_t)n;return n==bytes;
}
static inline bool native_stream_metadata(NativeStream *s,uint32_t at,void *out,uint32_t bytes){
 if(!s)return false;
 if(s->metadata)return native_metadata_read(s->metadata,s->bytes,at,out,bytes,native_stream_metadata_direct,s);
 return native_stream_metadata_direct(s,at,out,bytes);
}
/* Zero initialize before first open; reopening closes the previous file. */
static inline bool native_stream_open(NativeStream *s,const char *path){
 if(!s||!path)return false;
 native_stream_close(s);s->file=fopen(path,"rb");if(!s->file)return false;
 if(fseek(s->file,0,SEEK_END))goto fail;
 long size=ftell(s->file);if(size<32||(unsigned long)size>INT32_MAX)goto fail;
 s->bytes=(uint32_t)size;uint8_t h[32];if(!native_stream_read(s,0,h,32))goto fail;
 if(memcmp(h,"KGP1",4)||(native_stream_u32(h+4)!=1&&native_stream_u32(h+4)!=2)||native_stream_u32(h+12)!=32||native_stream_u32(h+16)!=32||native_stream_u32(h+20)!=s->bytes||native_stream_u32(h+24)||native_stream_u32(h+28))goto fail;
 s->version=native_stream_u32(h+4);s->pages=native_stream_u32(h+8);if(!s->pages||s->pages>(s->bytes-32)/32)goto fail;
 return true;
 fail:native_stream_close(s);return false;
}
static inline bool native_stream_record(NativeStream *s,unsigned index,NativeStreamPage *page){
 if(!s||!s->file||!page||index>=s->pages)return false;
 if(s->clock==UINT32_MAX){s->valid=0;s->clock=0;}
 unsigned bucket=index&127u,found=(unsigned)s->hints[bucket]-1u;
 if(found>=s->valid||s->cache_keys[found]!=index){found=s->valid;for(unsigned i=0;i<s->valid;i++)if(s->cache_keys[i]==index){found=i;break;}}
 if(found<s->valid){s->hints[bucket]=(uint8_t)(found+1u);s->cache_age[found]=++s->clock;*page=s->cache[found];return true;}
 uint8_t r[32];if(!native_stream_metadata(s,32+index*32u,r,32))return false;
 NativeStreamPage p={native_stream_u32(r),native_stream_u32(r+4),native_stream_u32(r+16),native_stream_u32(r+20),native_stream_u32(r+24),native_stream_u32(r+28),native_stream_u16(r+8),native_stream_u16(r+10),r[12]};
 uint32_t start=32+s->pages*32u;
 if(p.width<8||p.width>256||(p.width&(p.width-1))||p.height<8||p.height>32||(p.height&(p.height-1))||(s->version==1&&p.height!=8)||(unsigned)p.width*p.height>2048||(p.bits!=4&&p.bits!=8&&p.bits!=16)||r[13]!=(unsigned)(p.bits<16)||native_stream_u16(r+14))return false;
 if(p.texture<start||(p.texture&7u)||p.texture_bytes!=(uint32_t)p.width*p.height*p.bits/8u||!native_stream_range(s->bytes,p.texture,p.texture_bytes))return false;
 if(p.bits<16){if(p.palette<start||(p.palette&15u)||p.palette_bytes!=(2u<<p.bits)||!native_stream_range(s->bytes,p.palette,p.palette_bytes))return false;}
 else if(p.palette||p.palette_bytes||p.palette_crc)return false;
 unsigned slot=s->valid;
 if(slot<96)s->valid++;else{slot=0;for(unsigned i=1;i<96;i++)if(s->cache_age[i]<s->cache_age[slot])slot=i;}
 s->cache_keys[slot]=index;s->cache_age[slot]=++s->clock;s->cache[slot]=p;s->hints[bucket]=(uint8_t)(slot+1u);*page=p;return true;
}
static inline bool native_stream_page(NativeStream *s,unsigned index,uint8_t *texture,size_t texture_capacity,uint8_t *palette,size_t palette_capacity,NativeStreamPage *record){
 NativeStreamPage p;if(!native_stream_record(s,index,&p)||!texture||texture_capacity<p.texture_bytes||(p.palette_bytes&&(!palette||palette_capacity<p.palette_bytes)))return false;
 if(!native_stream_read(s,p.texture,texture,p.texture_bytes)||native_stream_crc(texture,p.texture_bytes)!=p.texture_crc)return false;
 if(p.palette_bytes&&(!native_stream_read(s,p.palette,palette,p.palette_bytes)||native_stream_crc(palette,p.palette_bytes)!=p.palette_crc))return false;
 if(record)*record=p;
 return true;
}
typedef struct {const uint8_t *bytes;uint32_t size,frames,refs,ref_offset;} NativeStreamIndex;
typedef struct {uint16_t width,height;uint32_t first,count;} NativeStreamFrame;
static inline bool native_stream_index(NativeStreamIndex *out,const uint8_t *data,size_t size,unsigned pages){
 if(!out)return false;
 memset(out,0,sizeof(*out));
 if(!data||size<32||size>UINT32_MAX||memcmp(data,"KAF1",4)||native_stream_u32(data+4)!=1||native_stream_u32(data+16)!=32||native_stream_u32(data+24)!=size||native_stream_u32(data+28))return false;
 uint32_t frames=native_stream_u32(data+8),refs=native_stream_u32(data+12),ref_offset=native_stream_u32(data+20);
 if(frames>(size-32)/24||ref_offset!=32+frames*24u||refs>(size-ref_offset)/12||ref_offset+refs*12u!=size)return false;
 uint32_t pk=0,pi=0;
 for(uint32_t i=0;i<frames;i++){
  const uint8_t *f=data+32+i*24u;uint32_t kind=native_stream_u32(f),id=native_stream_u32(f+4),first=native_stream_u32(f+12),count=native_stream_u32(f+16);
  unsigned w=native_stream_u16(f+8),h=native_stream_u16(f+10);
  if(kind>2||!w||!h||w>1024||h>1024||native_stream_u32(f+20)||first>refs||count>refs-first||(i&&(kind<pk||(kind==pk&&id<=pi))))return false;
  for(uint32_t j=0;j<count;j++){
   const uint8_t *r=data+ref_offset+(first+j)*12u;unsigned x=native_stream_u16(r+4),y=native_stream_u16(r+6),rw=native_stream_u16(r+8),rh=native_stream_u16(r+10);
   if(native_stream_u32(r)>=pages||!rw||rw>256||!rh||rh>32||x>w||rw>w-x||y>h||rh>h-y)return false;
  }
  pk=kind;pi=id;
 }
 *out=(NativeStreamIndex){data,(uint32_t)size,frames,refs,ref_offset};return true;
}
static inline bool native_stream_find(const NativeStreamIndex *s,unsigned kind,unsigned id,NativeStreamFrame *out){
 if(!s||!s->bytes||!out)return false;
 uint32_t lo=0,hi=s->frames;
 while(lo<hi){uint32_t mid=lo+(hi-lo)/2;const uint8_t *f=s->bytes+32+mid*24u;uint32_t k=native_stream_u32(f),n=native_stream_u32(f+4);
  if(k<kind||(k==kind&&n<id))lo=mid+1;else hi=mid;
 }
 if(lo==s->frames)return false;
 const uint8_t *f=s->bytes+32+lo*24u;if(native_stream_u32(f)!=kind||native_stream_u32(f+4)!=id)return false;
 *out=(NativeStreamFrame){native_stream_u16(f+8),native_stream_u16(f+10),native_stream_u32(f+12),native_stream_u32(f+16)};return true;
}
#endif
