#ifndef KINDER_NATIVE_BG_ASSETS_H
#define KINDER_NATIVE_BG_ASSETS_H
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "tile_codec.h"
#ifndef NATIVE_BG_SERVICE
#define NATIVE_BG_SERVICE() ((void)0)
#endif
#ifndef NATIVE_BG_READ_BYTES
#define NATIVE_BG_READ_BYTES 2048u
#endif
#ifndef NATIVE_BG_CACHE_BYTES
#define NATIVE_BG_CACHE_BYTES 131072u
#endif
#define NATIVE_BG_READ_PAGES (NATIVE_BG_CACHE_BYTES/NATIVE_BG_READ_BYTES)
_Static_assert(NATIVE_BG_CACHE_BYTES>=65536u && NATIVE_BG_CACHE_BYTES<=262144u && NATIVE_BG_CACHE_BYTES%NATIVE_BG_READ_BYTES==0,"read cache capacity");
_Static_assert(NATIVE_BG_READ_BYTES>=1024u && NATIVE_BG_READ_BYTES<=8192u && (NATIVE_BG_READ_BYTES&(NATIVE_BG_READ_BYTES-1u))==0,"read block size");
typedef struct {
 FILE *file;uint32_t width,height,tiles,pages,tile_records,page_records,payload,bytes;
 uint16_t palette[4096];
 uint8_t read_cache[NATIVE_BG_READ_PAGES][NATIVE_BG_READ_BYTES];
 uint32_t read_offsets[NATIVE_BG_READ_PAGES],read_sizes[NATIVE_BG_READ_PAGES],read_ages[NATIVE_BG_READ_PAGES];
 unsigned read_age,block_fills,block_bytes;
} NativeBGAssets;
static inline uint32_t native_bg_u32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static inline bool native_bg_read(FILE *file,uint32_t offset,void *out,size_t bytes){NATIVE_BG_SERVICE();return !fseek(file,(long)offset,SEEK_SET)&&fread(out,1,bytes,file)==bytes;}
static inline void native_bg_close(NativeBGAssets *a){if(a){if(a->file)fclose(a->file);memset(a,0,sizeof(*a));}}
/* Bounded whole-block reads keep metadata/graphics seeks out of the small
 * packet decoder. Counters count stdio block fills, not physical SD sectors. */
static inline bool native_bg_cached_read(NativeBGAssets *a,uint32_t offset,void *out,size_t bytes){
 if(!a||!a->file||!out||offset>a->bytes||bytes>a->bytes-offset)return false;
 uint8_t *target=out;
 while(bytes){
  uint32_t base=offset&~(NATIVE_BG_READ_BYTES-1u);unsigned slot=0;
  while(slot<NATIVE_BG_READ_PAGES&&(!a->read_sizes[slot]||a->read_offsets[slot]!=base))slot++;
  if(slot==NATIVE_BG_READ_PAGES){
   slot=0;
   for(unsigned i=0;i<NATIVE_BG_READ_PAGES;i++){
    if(!a->read_sizes[i]){slot=i;break;}
    if(a->read_ages[i]<a->read_ages[slot])slot=i;
   }
   unsigned count=a->bytes-base;if(count>NATIVE_BG_READ_BYTES)count=NATIVE_BG_READ_BYTES;
   a->read_sizes[slot]=0;
   NATIVE_BG_SERVICE();
   if(fseek(a->file,(long)base,SEEK_SET))return false;
   size_t got=fread(a->read_cache[slot],1,count,a->file);a->block_fills++;a->block_bytes+=(unsigned)got;
   if(got!=count)return false;
   a->read_offsets[slot]=base;a->read_sizes[slot]=count;
  }
  if(++a->read_age==0){a->read_age=1;memset(a->read_ages,0,sizeof(a->read_ages));}
  a->read_ages[slot]=a->read_age;
  unsigned local=offset-base,part=a->read_sizes[slot]-local;if(part>bytes)part=(unsigned)bytes;
  if(!part)return false;
  memcpy(target,a->read_cache[slot]+local,part);target+=part;offset+=part;bytes-=part;
 }
 return true;
}
/* Caller must close a previous image before reopening. Never executes assets. */
static inline bool native_bg_open(NativeBGAssets *a,const char *path){
 if(!a||!path)return false;
 memset(a,0,sizeof(*a));a->file=fopen(path,"rb");if(!a->file)return false;
 uint8_t h[48];long bytes;
 if(fseek(a->file,0,SEEK_END)||(bytes=ftell(a->file))<48||bytes>32*1024*1024||!native_bg_read(a->file,0,h,48))goto bad;
 if(memcmp(h,"KNTB",4)||native_bg_u32(h+4)!=1||native_bg_u32(h+44))goto bad;
 a->width=native_bg_u32(h+8);a->height=native_bg_u32(h+12);a->tiles=native_bg_u32(h+16);
 /* Header fields: version,width,height,tiles,groups,pages,palette,tiles,map,payload,flags. */
 if(native_bg_u32(h+20)!=16)goto bad;
 a->pages=native_bg_u32(h+24);a->tile_records=native_bg_u32(h+32);a->page_records=native_bg_u32(h+36);a->payload=native_bg_u32(h+40);a->bytes=(uint32_t)bytes;
 if(!a->width||!a->height||a->width>131070||a->height>131070||!a->tiles||a->tiles>0x0fffffff)goto bad;
 if(((uint64_t)(a->width+15)/16)*((a->height+15)/16)!=a->pages)goto bad;
 if(native_bg_u32(h+28)!=48||a->tile_records!=8240||
    (uint64_t)a->tile_records+(uint64_t)a->tiles*8!=a->page_records||
    (uint64_t)a->page_records+(uint64_t)a->pages*8!=a->payload||a->payload>a->bytes)goto bad;
 uint8_t raw[512];
 for(unsigned group=0;group<16;group++){
  if(!native_bg_cached_read(a,48+group*512,raw,sizeof(raw)))goto bad;
  for(unsigned i=0;i<256;i++)a->palette[group*256+i]=(uint16_t)(raw[i*2]|((unsigned)raw[i*2+1]<<8));
 }
 for(unsigned i=0;i<16;i++)if(a->palette[i*256])goto bad;
 return true;
 bad:native_bg_close(a);return false;
}
static inline bool native_bg_block(NativeBGAssets *a,uint32_t record,void *out,unsigned expected){
 if(!a||!a->file||!out||(expected!=64&&expected!=1024))return false;
 uint8_t header[8],packed[1156];
 if(record>a->payload||a->payload-record<8||!native_bg_cached_read(a,record,header,8))return false;
 uint32_t offset=native_bg_u32(header),bytes=native_bg_u32(header+4);
 if(bytes<4||bytes>sizeof(packed)||offset>a->bytes-a->payload||bytes>a->bytes-a->payload-offset)return false;
 if(!native_bg_cached_read(a,a->payload+offset,packed,bytes))return false;
 return tile_decode_lz(packed,bytes,out,expected);
}
static inline bool native_bg_tile(NativeBGAssets *a,uint32_t tile,uint8_t out[64]){
 return a&&tile<a->tiles&&native_bg_block(a,a->tile_records+tile*8,out,64);
}
static inline bool native_bg_page(NativeBGAssets *a,uint32_t page,uint32_t out[256]){
 uint8_t raw[1024];
 if(!a||page>=a->pages||!out||!native_bg_block(a,a->page_records+page*8,raw,1024))return false;
 for(unsigned i=0;i<256;i++)if((native_bg_u32(raw+i*4)&0x0fffffff)>=a->tiles)return false;
 for(unsigned i=0;i<256;i++)out[i]=native_bg_u32(raw+i*4);
 return true;
}
#endif
