#ifndef KINDER_NATIVE_SCENERY_CACHE_H
#define KINDER_NATIVE_SCENERY_CACHE_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
/* Foreground occluder texels, sampled on demand. Each texture bank is a
 * 256x256 ring addressed by world coordinates; a 32x32 table tags which world
 * 8x8 cell each ring cell currently holds, plus a 64-bit mask of its valid
 * pixels (cells cut by the screen edge are partly sampled). Only pixels under
 * the clipped occluder quads of a frame are fetched, and only when missing.
 * Scrolling never forces a refill. Actor uploads use the 64 ring rows below
 * the view and invalidate just the cell rows they touch. */
#define NATIVE_CELL_EMPTY UINT32_MAX
typedef struct {uint32_t tag[32*32];uint64_t valid[32*32];} NativeOccluderCells;
/* Sample world cell (wx,wy); screen rectangle [l,r)x[t,b) is the visible part. */
typedef bool (*NativeCellSample)(int wx,int wy,int l,int t,int r,int b,void *context);
static inline void native_scenery_cache_invalidate(NativeOccluderCells *c){if(c)memset(c->tag,0xff,sizeof(c->tag));}
static inline void native_scenery_cache_overwrite(NativeOccluderCells *c,int y){
 if(!c||y<0)return;
 unsigned first=(((unsigned)y+192u)&255u)/8u,last=(((unsigned)y+255u)&255u)/8u;
 for(unsigned row=first;;row=(row+1u)&31u){
  memset(c->tag+row*32u,0xff,32u*sizeof(*c->tag));
  if(row==last)break;
 }
}
static inline uint64_t native_cell_mask(int x0,int y0,int x1,int y1){
 uint64_t row=(uint64_t)(((1u<<(x1-x0))-1u)<<x0),mask=0;
 for(int y=y0;y<y1;y++)mask|=row<<(y*8);
 return mask;
}
typedef struct {int16_t l,t,r,b;uint16_t order;} ClippedOccluder;
/* Make the screen rectangles of view (x,y) resident. The union of all
 * rectangles is marked in per-row cell bitmasks first, so overlapping
 * rectangles cost nothing extra and each needed cell is checked once. */
static inline bool native_scenery_cache_need(NativeOccluderCells *c,int x,int y,const ClippedOccluder *rects,unsigned count,NativeCellSample sample,void *context,unsigned *sampled){
 if(!c||!sample||(count&&!rects)||x<0||y<0||x>65535*8-256||y>65535*8-192)return false;
 uint64_t rows[25]={0};int base_x=x>>3,base_y=y>>3;bool any=false;
 for(unsigned i=0;i<count;i++){
  int l=rects[i].l<0?0:rects[i].l,t=rects[i].t<0?0:rects[i].t,r=rects[i].r>256?256:rects[i].r,b=rects[i].b>192?192:rects[i].b;
  if(l>=r||t>=b)continue;
  int c0=((x+l)>>3)-base_x,c1=((x+r-1)>>3)-base_x;
  uint64_t bits=(c1-c0+1>=64?UINT64_MAX:((uint64_t)1<<(c1-c0+1))-1u)<<c0;
  for(int row=((y+t)>>3)-base_y;row<=((y+b-1)>>3)-base_y;row++)rows[row]|=bits;
  any=true;
 }
 if(!any)return true;
 for(int row=0;row<25;row++)for(uint64_t bits=rows[row];bits;bits&=bits-1u){
  /* Columns span at most 33 bits; use 32-bit count-trailing-zeros (CLZ based). */
  uint32_t low=(uint32_t)bits;int bit=low?__builtin_ctz(low):32+__builtin_ctz((uint32_t)(bits>>32));
  int cx=base_x+bit,cy=base_y+row;
  unsigned at=(unsigned)(cy&31)*32u+(unsigned)(cx&31);
  uint32_t tag=(uint32_t)cy<<16|(uint32_t)cx;
  int wl=cx*8,wt=cy*8,sl=wl-x,st=wt-y,sr=sl+8,sb=st+8;
  if(sl<0)sl=0;
  if(st<0)st=0;
  if(sr>256)sr=256;
  if(sb>192)sb=192;
  /* Visible pixels of this cell, in cell-local coordinates. */
  uint64_t visible=(sl==wl-x&&st==wt-y&&sr==sl+8&&sb==st+8)?UINT64_MAX:native_cell_mask(sl+x-wl,st+y-wt,sr+x-wl,sb+y-wt);
  if(c->tag[at]==tag&&(c->valid[at]&visible)==visible)continue;
  if(c->tag[at]!=tag)c->valid[at]=0;
  c->tag[at]=NATIVE_CELL_EMPTY;
  if(!sample(wl,wt,sl,st,sr,sb,context))return false;
  c->tag[at]=tag;c->valid[at]|=visible;
  if(sampled)(*sampled)++;
 }
 return true;
}
#endif
