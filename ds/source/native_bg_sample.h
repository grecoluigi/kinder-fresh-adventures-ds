#ifndef KINDER_NATIVE_BG_SAMPLE_H
#define KINDER_NATIVE_BG_SAMPLE_H
#include "native_bg_stream.h"
/* Copy final native tile colors for 3D foreground restoration. Transparent
 * tiles return0; parallax stays a separate hardware layer. The pending view is
 * sampled before scroll publication so actor/scenery cameras remain matched.
 * Caller supplies actual mapped graphics and must retain front/next pins. */
static inline bool native_bg_sample_region_mode(const NativeBGStream *s,const volatile uint16_t *graphics,
 size_t graphics_words,uint16_t *out,size_t pixels,unsigned stride,int left,int top,int right,int bottom,bool opaque_only){
 if(!s||(!s->visible&&!s->pending)||!graphics||!out||graphics_words<960u*32u||stride<256||
    pixels<(size_t)191*stride+256)return false;
 if(left<0)left=0;
 if(top<0)top=0;
 if(right>256)right=256;
 if(bottom>192)bottom=192;
 if(left>=right||top>=bottom)return true;
 int cx=s->pending?s->target_x:s->front_x,cy=s->pending?s->target_y:s->front_y;
 unsigned first_x=(unsigned)(cx+left)/8,last_x=(unsigned)(cx+right-1)/8;
 unsigned first_y=(unsigned)(cy+top)/8,last_y=(unsigned)(cy+bottom-1)/8;
 /* Reject invalid references before modifying any requested pixels. */
 for(unsigned yy=first_y;yy<=last_y;yy++)for(unsigned xx=first_x;xx<=last_x;xx++){
  unsigned slot=s->map[native_bg_map_at(xx,yy)]&1023;
  if(slot>=960||!(s->cache.entries[slot].flags&NATIVE_BG_VALID)||
     !(s->cache.entries[slot].flags&(NATIVE_BG_FRONT|NATIVE_BG_NEXT)))return false;
 }
 for(unsigned yy=first_y;yy<=last_y;yy++){
 NATIVE_BG_SERVICE();
 for(unsigned xx=first_x;xx<=last_x;xx++){
  uint16_t word=s->map[native_bg_map_at(xx,yy)];unsigned slot=word&1023;
  const uint16_t *palette=s->assets.palette+(word>>12)*256u;
  int x=(int)xx*8-cx,y=(int)yy*8-cy;
  int l=native_bg_max(left,x),r=native_bg_min(right,x+8),t=native_bg_max(top,y),b=native_bg_min(bottom,y+8);
  for(int row=t;row<b;row++){
   unsigned offset=slot*32u+(unsigned)(row-y)*4u;
   for(int col=l;col<r;col++){
    unsigned local=(unsigned)(col-x);uint16_t pair=graphics[offset+local/2u];unsigned index=(pair>>((local&1u)*8u))&255u;
    if(index)out[(size_t)row*stride+(unsigned)col]=(uint16_t)(32768u|(palette[index]&32767u));
    else if(!opaque_only)out[(size_t)row*stride+(unsigned)col]=0;
   }
  }
 }
 }
 return true;
}
static inline bool native_bg_sample_region(const NativeBGStream *s,const volatile uint16_t *graphics,
 size_t graphics_words,uint16_t *out,size_t pixels,unsigned stride,int left,int top,int right,int bottom){
 return native_bg_sample_region_mode(s,graphics,graphics_words,out,pixels,stride,left,top,right,bottom,false);
}
/* Expand screen rectangle [left,right)x[top,bottom) of the prepared view
 * straight into a 256x256 RGB555 ring texture at world coordinates. Same
 * colors and transparency as native_bg_sample_region, without an intermediate
 * buffer: each 8-pixel tile row is read as two 32-bit VRAM words. Tile columns
 * are 8-aligned in world space, so a tile row never wraps inside the ring. */
static inline bool native_bg_expand_region(const NativeBGStream *s,const volatile uint16_t *graphics,
 size_t graphics_words,volatile uint16_t *texture,int left,int top,int right,int bottom){
 if(!s||(!s->visible&&!s->pending)||!graphics||!texture||graphics_words<960u*32u)return false;
 if(left<0)left=0;
 if(top<0)top=0;
 if(right>256)right=256;
 if(bottom>192)bottom=192;
 if(left>=right||top>=bottom)return true;
 int cx=s->pending?s->target_x:s->front_x,cy=s->pending?s->target_y:s->front_y;
 unsigned first_x=(unsigned)(cx+left)/8,last_x=(unsigned)(cx+right-1)/8;
 unsigned first_y=(unsigned)(cy+top)/8,last_y=(unsigned)(cy+bottom-1)/8;
 for(unsigned yy=first_y;yy<=last_y;yy++)for(unsigned xx=first_x;xx<=last_x;xx++){
  unsigned slot=s->map[native_bg_map_at(xx,yy)]&1023;
  if(slot>=960||!(s->cache.entries[slot].flags&NATIVE_BG_VALID)||
     !(s->cache.entries[slot].flags&(NATIVE_BG_FRONT|NATIVE_BG_NEXT)))return false;
 }
 for(unsigned yy=first_y;yy<=last_y;yy++)for(unsigned xx=first_x;xx<=last_x;xx++){
  uint16_t word=s->map[native_bg_map_at(xx,yy)];unsigned slot=word&1023;
  const uint16_t *palette=s->assets.palette+(word>>12)*256u;
  int x=(int)xx*8-cx,y=(int)yy*8-cy;
  int l=native_bg_max(left,x)-x,r=native_bg_min(right,x+8)-x,t=native_bg_max(top,y)-y,b=native_bg_min(bottom,y+8)-y;
  const volatile uint32_t *rows=(const volatile uint32_t *)(graphics+slot*32u);
  for(int row=t;row<b;row++){
   uint32_t low=rows[row*2],high=rows[row*2+1];
   uint8_t index[8]={(uint8_t)low,(uint8_t)(low>>8),(uint8_t)(low>>16),(uint8_t)(low>>24),
                     (uint8_t)high,(uint8_t)(high>>8),(uint8_t)(high>>16),(uint8_t)(high>>24)};
   volatile uint16_t *out=texture+(((unsigned)yy*8u+(unsigned)row)&255u)*256u+(((unsigned)xx*8u)&255u);
   for(int col=l;col<r;col++){unsigned i=index[col];out[col]=i?(uint16_t)(32768u|(palette[i]&32767u)):0;}
  }
 }
 return true;
}
/* Threshold depth rectangles can span transparent holes. Restoring a later
 * static ordinal must leave actors visible through those holes. */
static inline bool native_bg_merge_region(const NativeBGStream *s,const volatile uint16_t *graphics,
 size_t graphics_words,uint16_t *out,size_t pixels,unsigned stride,int left,int top,int right,int bottom){
 return native_bg_sample_region_mode(s,graphics,graphics_words,out,pixels,stride,left,top,right,bottom,true);
}
#endif
