#ifndef KINDER_DEPTH_MESH_H
#define KINDER_DEPTH_MESH_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define DEPTH_MESH_WIDTH 272u
#define DEPTH_MESH_HEIGHT 208u
typedef struct {uint16_t left,top,right,bottom,order;} DepthRect;
/* Explicit caller-owned scratch; no heap allocation or IRQ/shared state. */
typedef struct {
 uint16_t top[DEPTH_MESH_WIDTH],right[DEPTH_MESH_WIDTH],order[DEPTH_MESH_WIDTH];
 uint16_t seen[DEPTH_MESH_WIDTH],previous[DEPTH_MESH_WIDTH],current[DEPTH_MESH_WIDTH];
} DepthMeshScratch;
static inline bool depth_rect_emit(DepthRect *out,size_t capacity,size_t *count,
                                  unsigned left,unsigned top,unsigned right,unsigned bottom,unsigned order){
 if(*count>=capacity)return false;
 out[(*count)++]=(DepthRect){(uint16_t)left,(uint16_t)top,(uint16_t)right,(uint16_t)bottom,(uint16_t)order};return true;
}
/* Merge equal nonzero horizontal order runs over consecutive rows. Output
 * rectangles never overlap. Zero means transparent. On false, discard output;
 * bounded callers can retain the existing CPU renderer without truncation. */
static inline bool depth_mesh_build(const uint8_t *source,unsigned width,unsigned height,unsigned stride,
                             DepthRect *out,size_t capacity,size_t *count,DepthMeshScratch *s){
 if(count)*count=0;
 if(!source||!out||!count||!s||!width||!height||width>DEPTH_MESH_WIDTH||height>DEPTH_MESH_HEIGHT||stride<width)return false;
 for(unsigned x=0;x<width;x++)s->seen[x]=UINT16_MAX;
 unsigned previous_count=0;
 for(unsigned y=0;y<height;y++){
  const uint8_t *line=source+(size_t)y*stride;unsigned current_count=0;
  for(unsigned x=0;x<width;){
   unsigned left=x,order=line[x++];while(x<width&&line[x]==order)x++;
   if(!order)continue;
   bool previous=s->seen[left]!=UINT16_MAX&&s->seen[left]+1u==y;
   if(previous&&(s->right[left]!=x||s->order[left]!=order)){
    if(!depth_rect_emit(out,capacity,count,left,s->top[left],s->right[left],y,s->order[left]))return false;
    previous=false;
   }
   if(!previous){s->top[left]=(uint16_t)y;s->right[left]=(uint16_t)x;s->order[left]=(uint16_t)order;}
   s->seen[left]=(uint16_t)y;s->current[current_count++]=(uint16_t)left;
  }
  for(unsigned i=0;i<previous_count;i++){
   unsigned left=s->previous[i];
   if(s->seen[left]!=y){
    if(!depth_rect_emit(out,capacity,count,left,s->top[left],s->right[left],y,s->order[left]))return false;
    s->seen[left]=UINT16_MAX;
   }
  }
  for(unsigned i=0;i<current_count;i++)s->previous[i]=s->current[i];
  previous_count=current_count;
 }
 for(unsigned i=0;i<previous_count;i++){
  unsigned left=s->previous[i];if(!depth_rect_emit(out,capacity,count,left,s->top[left],s->right[left],height,s->order[left]))return false;
 }
 return true;
}
#endif
