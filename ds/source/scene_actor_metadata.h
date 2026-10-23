#ifndef KINDER_SCENE_ACTOR_METADATA_H
#define KINDER_SCENE_ACTOR_METADATA_H
/* Metadata-only KFE4/KFU4. Original geometry + two DS facing geometries;
 * immutable pixel pages are stored separately in the native GPU pack. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define SCENE_ACTOR_FRAME_BYTES 24u
static inline unsigned scene_actor_u16(const uint8_t *p){return p[0]|(unsigned)p[1]<<8;}
static inline uint32_t scene_actor_u32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static inline bool scene_actor_metadata_size(const uint8_t h[12],bool enemies,size_t *bytes){
 if(!h||!bytes||memcmp(h,enemies?"KFE4":"KFU4",4))return false;
 unsigned resources=scene_actor_u16(h+4),frames=scene_actor_u16(h+6);
 if(!resources||resources>(enemies?64u:11u)||(!enemies&&resources!=11u)||!frames||frames>(enemies?2048u:256u))return false;
 size_t size=12u+resources*(enemies?84u:12u)+frames*SCENE_ACTOR_FRAME_BYTES;
 if(scene_actor_u32(h+8)!=size)return false;
 *bytes=size;return true;
}
static inline bool scene_actor_metadata_valid(const uint8_t *data,size_t bytes,bool enemies){
 size_t size;
 if(!data||bytes<12||!scene_actor_metadata_size(data,enemies,&size)||size!=bytes)return false;
 unsigned resources=scene_actor_u16(data+4),frames=scene_actor_u16(data+6),stride=enemies?84u:12u;
 uint8_t seen[128]={0};
 for(unsigned i=0;i<resources;i++){
  const uint8_t *r=data+12+i*stride;
  unsigned id=scene_actor_u16(r),first=scene_actor_u16(r+2),count=scene_actor_u16(r+4);
  if(id>=1024||(seen[id/8]&(1u<<(id%8)))||!count||first>frames||count>frames-first)return false;
  seen[id/8]|=(uint8_t)(1u<<(id%8));
  if(!enemies&&(id<48||id>58||scene_actor_u16(r+6)>=count||scene_actor_u16(r+8)>=count))return false;
 }
 for(unsigned i=0;i<frames;i++){
  const uint8_t *f=data+12+resources*stride+i*SCENE_ACTOR_FRAME_BYTES;
  unsigned w=scene_actor_u16(f),h=scene_actor_u16(f+2);
  if(!w||!h||w>32767||h>32767)return false;
  for(unsigned facing=0;facing<2;facing++){
   const uint8_t *g=f+8+facing*8;
   w=scene_actor_u16(g);h=scene_actor_u16(g+2);
   int x=(int16_t)scene_actor_u16(g+4),y=(int16_t)scene_actor_u16(g+6);
   if(!w||!h||x+(int)w>32767||y+(int)h>32767||
      (enemies&&(w>256||h>192))||(!enemies&&(size_t)w*h>8192u))return false;
  }
 }
 return true;
}
#endif
