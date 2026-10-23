#ifndef KINDER_TEXTURE_WINDOW_H
#define KINDER_TEXTURE_WINDOW_H
#include <stdbool.h>
#include <stdint.h>
#include <limits.h>

/* A 256x192 viewport in a wrapping 256x256 texture. Coordinates identify
 * immutable world pixels; retained pixels stay at (world_x&255,world_y&255).
 * The upload callback must also write transparent pixels to remove old art.
 * Publication belongs at VBlank, after the source viewport has been prepared.
 */
typedef struct {int x,y;bool valid;} TextureWindow;
typedef bool (*TextureWindowWrite)(int x,int y,unsigned width,unsigned height,void *context);
static inline bool texture_window_update(TextureWindow *window,int x,int y,
                                        TextureWindowWrite write,void *context){
 if(!window||!write||x<0||y<0||x>INT_MAX-256||y>INT_MAX-192)return false;
 if(window->valid&&window->x==x&&window->y==y)return true;
 bool previous=window->valid;window->valid=false;
 int left=x,top=y,right=x+256,bottom=y+192;
 if(previous){
  if(window->x>left)left=window->x;
  if(window->y>top)top=window->y;
  if(window->x+256<right)right=window->x+256;
  if(window->y+192<bottom)bottom=window->y+192;
 }
 if(!previous||left>=right||top>=bottom){
  if(!write(x,y,256,192,context))return false;
 }else{
  /* Horizontal bands cover the corners; side bands cover only shared rows.
   * No region is uploaded twice, including diagonal or reverse movement. */
  if(top>y&&!write(x,y,256,(unsigned)(top-y),context))return false;
  if(bottom<y+192&&!write(x,bottom,256,(unsigned)(y+192-bottom),context))return false;
  if(left>x&&!write(x,top,(unsigned)(left-x),(unsigned)(bottom-top),context))return false;
  if(right<x+256&&!write(right,top,(unsigned)(x+256-right),(unsigned)(bottom-top),context))return false;
 }
 window->x=x;window->y=y;window->valid=true;return true;
}

/* Copy a requested world rectangle from the existing 272x208 RGB555 scenery
 * cache into the wrapping texture. Halfword stores are safe for DS LCDC VRAM;
 * generic memcpy may use byte stores for odd addresses and is unsuitable here.
 * Both pitches are fixed, and requests must be within the prepared viewport.
 */
typedef struct {volatile uint16_t *texture;const uint16_t *source;unsigned pixels,rectangles;const uint16_t *overlay;} TextureWindowCopy;
static inline void texture_copy_rgb555(volatile uint16_t *dest,const uint16_t *source,unsigned count){
 typedef uint32_t Word __attribute__((__may_alias__));
 /* LCDC VRAM accepts aligned word writes. Copy two pixels per access where
  * source/destination alignment agrees; odd clipped edges stay halfwords. */
 if((((uintptr_t)dest^(uintptr_t)source)&3u)==0){
  if(count&&((uintptr_t)dest&3u)){*dest++=*source++;count--;}
  volatile Word *d=(volatile Word *)dest;const Word *s=(const Word *)source;
  unsigned words=count/2u;
  for(unsigned i=0;i<words;i++)d[i]=s[i];
  dest+=words*2u;source+=words*2u;count-=words*2u;
 }
 while(count--)*dest++=*source++;
}
static inline bool texture_window_copy(int x,int y,unsigned width,unsigned height,void *context){
 TextureWindowCopy *copy=(TextureWindowCopy *)context;
 if(!copy||!copy->texture||!copy->source||x<0||y<0||!width||!height||width>256||height>192)return false;
 for(unsigned row=0;row<height;row++){
  unsigned sy=((unsigned)y+row)%208u,dy=((unsigned)y+row)&255u;
  unsigned sx=(unsigned)x%272u,dx=(unsigned)x&255u,remaining=width;
  while(remaining){
   unsigned count=272u-sx;if(count>256u-dx)count=256u-dx;if(count>remaining)count=remaining;
   const uint16_t *source=copy->source+sy*272u+sx;
   volatile uint16_t *dest=copy->texture+dy*256u+dx;
   if(copy->overlay){
    const uint16_t *overlay=copy->overlay+sy*272u+sx;
    for(unsigned i=0;i<count;i++){uint16_t color=overlay[i];dest[i]=(color&0x8000u)?color:source[i];}
   }else texture_copy_rgb555(dest,source,count);
   remaining-=count;sx+=count;dx+=count;if(sx==272u)sx=0;if(dx==256u)dx=0;
  }
 }
 copy->pixels+=width*height;copy->rectangles++;return true;
}
#endif
