#ifndef KINDER_ACTOR_OCCLUSION_H
#define KINDER_ACTOR_OCCLUSION_H
#include "actor_atlas.h"
#include "depth_mesh.h"
typedef struct {int left,top,right,bottom;unsigned first_order;} ActorRegion;
static inline ActorRegion actor_occlusion_region(const ActorAtlas *a){
 ActorRegion r={256,192,0,0,65535};
 for(unsigned i=0;i<a->count;i++){
  const ActorPiece *p=a->pieces+i;int x=p->screen_x,y=p->screen_y;
  if(p->order<r.first_order)r.first_order=p->order;
  if(x<r.left)r.left=x;
  if(y<r.top)r.top=y;
  if(x+p->width>r.right)r.right=x+p->width;
  if(y+p->height>r.bottom)r.bottom=y+p->height;
 }
 return r;
}
static inline bool actor_occlusion_clip(const DepthRect *q,int dx,int dy,ActorRegion r,int *l,int *t,int *right,int *b){
 /* Native actors with ordinal N draw after static ordinal N. Layers at
  * or before the earliest actor cannot occlude any actor in this frame. */
 if(q->order<=r.first_order)return false;
 *l=(int)q->left-dx;*right=(int)q->right-dx;*t=(int)q->top-dy;*b=(int)q->bottom-dy;
 if(*l<r.left)*l=r.left;
 if(*right>r.right)*right=r.right;
 if(*t<r.top)*t=r.top;
 if(*b>r.bottom)*b=r.bottom;
 return *l<*right&&*t<*b;
}
#endif
