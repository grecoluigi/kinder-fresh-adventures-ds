#ifndef KINDER_ACTOR_ATLAS_H
#define KINDER_ACTOR_ATLAS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define ACTOR_ATLAS_WIDTH 256u
#define ACTOR_ATLAS_HEIGHT 64u
#define ACTOR_ATLAS_PIECES 128u
#define ACTOR_ATLAS_STRIP_HEIGHT 8u
typedef struct {uint16_t x,y,width,height,screen_x,screen_y,order;} ActorPiece;
typedef struct {uint16_t x,y,height;} ActorShelf;
/* Prototype only. Caller supplies 32KiB staging pixels. No retained image
 * pointers: source caches may evict immediately after append returns. */
typedef struct {
 uint16_t *pixels;
 ActorPiece pieces[ACTOR_ATLAS_PIECES];
 ActorShelf shelves[ACTOR_ATLAS_HEIGHT];
 unsigned count,shelf_count,used_height;
 bool failed;
} ActorAtlas;
static inline void actor_atlas_reset(ActorAtlas *a,uint16_t *pixels){
 memset(a,0,sizeof(*a));a->pixels=pixels;a->failed=!pixels;
 /* Only allocated rectangles are uploaded, so unused staging need not clear. */
}
/* On false discard the entire collection and rerender through the CPU path.
 * Source and atlas must not alias. Coordinates are already DS screen pixels. */
static inline bool actor_atlas_collect(ActorAtlas *a,const uint16_t *image,unsigned width,unsigned height,unsigned stride,int left,int top,unsigned order,bool layout_only){
 if(a->failed)return false;
 if((!image&&!layout_only)||!width||!height||width>4096||height>4096||stride<width||order>65535){a->failed=true;return false;}
 if(left>=256||top>=192||left<=-(int)width||top<=-(int)height)return true;
 unsigned sx=left<0?(unsigned)-left:0,sy=top<0?(unsigned)-top:0;
 unsigned w=width-sx,h=height-sy;
 if(w>(unsigned)(256-(left+(int)sx)))w=(unsigned)(256-(left+(int)sx));
 if(h>(unsigned)(192-(top+(int)sy)))h=(unsigned)(192-(top+(int)sy));
 unsigned done=0;
 while(done<h){
  unsigned rows=h-done;if(rows>ACTOR_ATLAS_STRIP_HEIGHT)rows=ACTOR_ATLAS_STRIP_HEIGHT;
  unsigned shelf=a->shelf_count;
  for(unsigned i=0;i<a->shelf_count;i++)if(a->shelves[i].height>=rows&&a->shelves[i].x+w<=256){shelf=i;break;}
  if(a->count==ACTOR_ATLAS_PIECES||(shelf==a->shelf_count&&a->used_height+rows>64)){a->failed=true;return false;}
  if(shelf==a->shelf_count){a->shelves[shelf]=(ActorShelf){0,(uint16_t)a->used_height,(uint16_t)rows};a->used_height+=rows;a->shelf_count++;}
  ActorShelf *s=&a->shelves[shelf];unsigned x=s->x,y=s->y;s->x+=(uint16_t)w;
  if(!layout_only)for(unsigned row=0;row<rows;row++)memcpy(a->pixels+(y+row)*256+x,image+(size_t)(sy+done+row)*stride+sx,w*2);
  a->pieces[a->count++]=(ActorPiece){(uint16_t)x,(uint16_t)y,(uint16_t)w,(uint16_t)rows,(uint16_t)(left+(int)sx),(uint16_t)(top+(int)sy+done),(uint16_t)order};
  done+=rows;
 }
 return true;
}
static inline bool actor_atlas_append(ActorAtlas *a,const uint16_t *p,unsigned w,unsigned h,unsigned stride,int l,int t,unsigned order){return actor_atlas_collect(a,p,w,h,stride,l,t,order,false);}
static inline bool actor_atlas_layout(ActorAtlas *a,unsigned w,unsigned h,int l,int t,unsigned order){return actor_atlas_collect(a,NULL,w,h,w,l,t,order,true);}
#endif
