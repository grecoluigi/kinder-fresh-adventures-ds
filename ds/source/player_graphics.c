#include "gpu_actors.h"
#include "hot_code.h"
#include "ds_projection.h"
#include "player_graphics.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __NDS__
#include <nds/system_counter.h>
#endif
#ifndef PLAYER_ROOT
#define PLAYER_ROOT "nitro:/players"
#endif
#define MAX_FRAMES 512
#define SOURCE_CACHE_BYTES (128u*1024u)
typedef struct { uint16_t w,h; int16_t x,y; } Geometry;
typedef struct { Geometry original,raster[2]; } Frame;
static Frame frames[2][MAX_FRAMES];
static unsigned counts[2];
/* Dedicated native source cache, independent of sprite decoding. */
static uint8_t *source_arena;
static uint32_t elapsed_us;
static int last_bounds[4];
static uint16_t read_le16(const uint8_t *p){return (uint16_t)(p[0]|p[1]<<8);}
static uint32_t read_le32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static Geometry geometry(const uint8_t *p){return (Geometry){read_le16(p),read_le16(p+2),(int16_t)read_le16(p+4),(int16_t)read_le16(p+6)};}
static bool valid_geometry(Geometry g){return g.w&&g.h&&(size_t)g.w*g.h<=512u*512u;}
void player_graphics_last_bounds(int bounds[4]){memcpy(bounds,last_bounds,sizeof(last_bounds));}
uint32_t player_graphics_elapsed_us(void){return elapsed_us;}
void player_graphics_close(void){
 free(source_arena);source_arena=NULL;memset(counts,0,sizeof(counts));
 elapsed_us=0;memset(last_bounds,0,sizeof(last_bounds));
}
static bool load_character(unsigned character,const char *name){
 char path[128];
 if(snprintf(path,sizeof(path),"%s/%s",PLAYER_ROOT,name)>=(int)sizeof(path))return false;
 FILE *file=fopen(path,"rb");if(!file)return false;
 uint8_t header[8];bool ok=fread(header,1,sizeof(header),file)==sizeof(header)&&!memcmp(header,"KFP4",4);
 unsigned count=ok?read_le32(header+4):0;ok=ok&&count&&count<=MAX_FRAMES;
 for(unsigned i=0;ok&&i<count;i++){
  uint8_t record[24];ok=fread(record,1,sizeof(record),file)==sizeof(record);
  if(!ok)break;
  Frame *f=&frames[character][i];f->original=geometry(record);
  f->raster[0]=geometry(record+8);f->raster[1]=geometry(record+16);
  ok=valid_geometry(f->original)&&valid_geometry(f->raster[0])&&valid_geometry(f->raster[1]);
 }
 /* Reject payload-bearing or truncated banks instead of retaining a decoder. */
 if(ok)ok=fgetc(file)==EOF&&!ferror(file);
 fclose(file);if(ok)counts[character]=count;return ok;
}
bool player_graphics_open(void){
 player_graphics_close();
 if(!load_character(0,"pinguin.frames")||!load_character(1,"milchschnitte.frames"))goto fail;
 source_arena=malloc(SOURCE_CACHE_BYTES);if(!source_arena)goto fail;
 return true;
 fail:player_graphics_close();return false;
}
KF_ITCM_CODE bool player_graphics_draw(uint16_t *pixels,int character,int index,int facing,int bx,int by,int cx,int cy){
 memset(last_bounds,0,sizeof(last_bounds));elapsed_us=0;
 if(!pixels||character<0||character>1||index<0||(unsigned)index>=counts[character])return false;
 #ifdef __NDS__
 uint32_t started=(uint32_t)systemCounterGetTicks();
 #endif
 const Geometry *f=&frames[character][index].raster[facing==0?0:1];
 int left=ds_relative_pixel(bx,cx)+f->x,top=ds_relative_pixel(by,cy)+f->y;
 bool ok=gpu_actors_native(0,((unsigned)index*2u+(unsigned)character)*2u+(facing==0?0u:1u),f->w,f->h,left,top);
 if(ok){
  int x0=left<0?0:left,y0=top<0?0:top,x1=left+f->w,y1=top+f->h;
  if(x1>256)x1=256;
  if(y1>192)y1=192;
  if(x0<x1&&y0<y1){last_bounds[0]=x0;last_bounds[1]=y0;last_bounds[2]=x1;last_bounds[3]=y1;}
 }
 #ifdef __NDS__
 elapsed_us=systemCounterTicksToUsec((uint32_t)systemCounterGetTicks()-started);
 #endif
 return ok;
}
void *player_graphics_native_cache(unsigned *bytes){*bytes=source_arena?SOURCE_CACHE_BYTES:0;return source_arena;}
