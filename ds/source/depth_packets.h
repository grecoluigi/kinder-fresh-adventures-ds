#ifndef KINDER_DEPTH_PACKETS_H
#define KINDER_DEPTH_PACKETS_H
#include "depth_mesh.h"
#include <stdio.h>
#include <string.h>
#include <limits.h>
/* One hardware screen's independent-quad budget; generated packets currently
 * peak at 1194. Larger packets are rejected by conversion and loading. */
#define DEPTH_PACKET_CAPACITY 1536u
#define DEPTH_PACKET_RECORD_BYTES 6u
/* Zero-initialize before first open. Main-thread ownership only. The decoded
 * packet covers 512x384; its key changes at 256x192 camera boundaries. */
typedef struct {
 FILE *file;
 uint32_t file_size,packet_count,key,read_calls,loads;
 uint16_t width,height,columns,rows;
 unsigned count;
 bool loaded,available;
 DepthRect rectangles[DEPTH_PACKET_CAPACITY] __attribute__((aligned(4)));
 uint8_t encoded[DEPTH_PACKET_CAPACITY*DEPTH_PACKET_RECORD_BYTES] __attribute__((aligned(4)));
} DepthPackets;
static inline uint16_t depth_packet_u16(const uint8_t *p){return (uint16_t)(p[0]|p[1]<<8);}
static inline uint32_t depth_packet_u32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static inline bool depth_packet_read(DepthPackets *p,uint32_t offset,void *data,unsigned size){
 if(!p->file||offset>p->file_size||size>p->file_size-offset)return false;
 if(fseek(p->file,(long)offset,SEEK_SET))return false;
 if(!size)return true;
 p->read_calls++;return fread(data,1,size,p->file)==size;
}
/* Bounded LZ10 on main RAM. No BIOS call trusts a malformed/truncated stream. */
static inline bool depth_packet_lz(const uint8_t *source,size_t bytes,uint8_t *dest,unsigned size){
 if(bytes<4||source[0]!=0x10||((unsigned)source[1]|(unsigned)source[2]<<8|(unsigned)source[3]<<16)!=size)return false;
 size_t in=4;unsigned out=0;
 while(out<size){
  if(in>=bytes)return false;
  unsigned flags=source[in++];
  for(unsigned bit=128;bit&&out<size;bit>>=1){
   if(flags&bit){
    if(bytes-in<2)return false;
    unsigned word=source[in]*256u+source[in+1];in+=2;unsigned length=(word>>12)+3,back=(word&4095)+1;
    if(back>out||length>size-out)return false;
    while(length--){dest[out]=dest[out-back];out++;}
   }else{if(in>=bytes)return false;dest[out++]=source[in++];}
  }
 }
 return in==bytes;
}
static inline void depth_packets_close(DepthPackets *p){
 if(p->file)fclose(p->file);
 p->file=NULL;p->loaded=p->available=false;p->count=0;
}
static inline bool depth_packets_open(DepthPackets *p,const char *path,unsigned width,unsigned height){
 depth_packets_close(p);p->read_calls=p->loads=0;
 if(!path||(p->file=fopen(path,"rb"))==NULL)return false;
 if(fseek(p->file,0,SEEK_END))goto failed;
 long end=ftell(p->file);if(end<24||(unsigned long)end>INT32_MAX)goto failed;
 p->file_size=(uint32_t)end;uint8_t header[24];if(!depth_packet_read(p,0,header,24))goto failed;
 if(memcmp(header,"KDM2",4)||depth_packet_u16(header+4)!=width||depth_packet_u16(header+6)!=height||!width||!height)goto failed;
 p->width=(uint16_t)width;p->height=(uint16_t)height;p->columns=depth_packet_u16(header+8);p->rows=depth_packet_u16(header+10);
 if(p->columns!=(width+255)/256||p->rows!=(height+191)/192||depth_packet_u16(header+12)!=256||depth_packet_u16(header+14)!=192||depth_packet_u32(header+16)!=6)goto failed;
 p->packet_count=depth_packet_u32(header+20);
 if(!p->packet_count||p->packet_count>4096||p->packet_count!=(unsigned)p->columns*p->rows||24u+p->packet_count*12u>p->file_size)goto failed;
 return true;
 failed:depth_packets_close(p);return false;
}
static inline bool depth_packets_load(DepthPackets *p,int x,int y,int *dx,int *dy){
 if(!p->file||x<0||y<0||!dx||!dy)return false;
 unsigned col=(unsigned)x/256,row=(unsigned)y/192;if(col>=p->columns||row>=p->rows)return false;
 *dx=x-(int)(col*256);*dy=y-(int)(row*192);unsigned key=row*p->columns+col;
 if(p->loaded&&p->key==key)return p->available;
 p->loaded=true;p->available=false;p->count=0;p->key=key;p->loads++;
 uint8_t entry[12];if(!depth_packet_read(p,24u+key*12u,entry,12))return false;
 uint32_t offset=depth_packet_u32(entry),bytes=depth_packet_u32(entry+4);unsigned count=depth_packet_u16(entry+8),flags=depth_packet_u16(entry+10);
 if(flags==1)return false;
 if(flags&~6u||count>DEPTH_PACKET_CAPACITY||offset<24u+p->packet_count*12u||bytes>sizeof(p->encoded))return false;
 unsigned raw_bytes=count*6;
 uint8_t *raw=(uint8_t *)p->rectangles;
 if(flags&2){
  if(!count||bytes<4||bytes>=raw_bytes||!depth_packet_read(p,offset,p->encoded,bytes)||!depth_packet_lz(p->encoded,bytes,raw,raw_bytes))return false;
 }else if(bytes!=raw_bytes||!depth_packet_read(p,offset,raw,bytes))return false;
 /* Planar decompression uses the rectangle arena as scratch. Input is no
  * longer needed after LZ; borrow that buffer for safe planar expansion. */
 if(flags&4){memcpy(p->encoded,raw,raw_bytes);raw=p->encoded;}
 for(unsigned i=count;i--;){
  uint8_t b[6];for(unsigned j=0;j<6;j++)b[j]=raw[(flags&4)?j*count+i:i*6+j];
  DepthRect q={(uint16_t)(b[0]|(b[1]&1u)<<8),(uint16_t)((b[1]>>1)|(b[2]&3u)<<7),
               (uint16_t)(((b[2]>>2)|(b[3]&7u)<<6)+1u),(uint16_t)(((b[3]>>3)|(b[4]&15u)<<5)+1u),
               (uint16_t)((b[4]>>4)|(b[5]&15u)<<4)};
  if((b[5]&240u)||q.left>=q.right||q.right>512||q.top>=q.bottom||q.bottom>384||!q.order)return false;
  p->rectangles[i]=q;
 }
 p->count=count;p->available=true;return true;
}
#endif
