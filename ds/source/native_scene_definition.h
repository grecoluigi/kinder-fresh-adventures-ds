#ifndef KINDER_NATIVE_SCENE_DEFINITION_H
#define KINDER_NATIVE_SCENE_DEFINITION_H
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint8_t kind, order; uint32_t argument; } NativeSceneEvent;
typedef struct {
 uint32_t native_width,native_height,width,height,static_orders,event_count;
 NativeSceneEvent *events;
} NativeSceneDefinition;
static inline uint32_t nsd_u32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static inline void native_scene_definition_close(NativeSceneDefinition *d){
 if(d){free(d->events);memset(d,0,sizeof(*d));}
}
/* Zero-initialize before first use. A failed load retains the old definition.
 * No renderer, tile cache, VRAM mapping or legacy composite dependency. */
static inline bool native_scene_definition_open(NativeSceneDefinition *d,const char *path){
 if(!d||!path)return false;
 FILE *f=fopen(path,"rb");if(!f)return false;
 NativeSceneDefinition next={0};uint8_t h[32],e[8];bool ok=false;
 if(fread(h,1,32,f)!=32||memcmp(h,"KNS1",4)||nsd_u32(h+28))goto done;
 next.native_width=nsd_u32(h+4);next.native_height=nsd_u32(h+8);
 next.width=nsd_u32(h+12);next.height=nsd_u32(h+16);
 next.static_orders=nsd_u32(h+20);next.event_count=nsd_u32(h+24);
 if(next.native_width<800||next.native_height<600||next.native_width>65535u*32u||next.native_height>65535u*32u||
    next.width<256||next.height<192||next.width>65535||next.height>65535||
    !next.static_orders||next.static_orders>255||next.event_count>4096)goto done;
 if(next.event_count){next.events=malloc(next.event_count*sizeof(*next.events));if(!next.events)goto done;}
 unsigned previous=0;
 for(unsigned i=0;i<next.event_count;i++){
  if(fread(e,1,8,f)!=8||e[0]<1||e[0]>2||e[1]<previous||e[1]>next.static_orders||e[2]||e[3])goto done;
  next.events[i]=(NativeSceneEvent){e[0],e[1],nsd_u32(e+4)};previous=e[1];
 }
 if(fgetc(f)!=EOF||ferror(f))goto done;
 ok=true;
done:
 fclose(f);
 if(ok){native_scene_definition_close(d);*d=next;}else native_scene_definition_close(&next);
 return ok;
}
#endif
