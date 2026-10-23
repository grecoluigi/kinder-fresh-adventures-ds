#ifndef KINDER_NATIVE_OCCLUSION_H
#define KINDER_NATIVE_OCCLUSION_H
#include "actor_occlusion.h"
#include "native_actors.h"
static inline ActorRegion native_region_empty(void){return (ActorRegion){256,192,0,0,65535};}
static inline void native_region_merge(ActorRegion *out,ActorRegion in){
 if(in.left>=in.right||in.top>=in.bottom)return;
 if(in.left<out->left)out->left=in.left;
 if(in.top<out->top)out->top=in.top;
 if(in.right>out->right)out->right=in.right;
 if(in.bottom>out->bottom)out->bottom=in.bottom;
 if(in.first_order<out->first_order)out->first_order=in.first_order;
}
static inline bool native_region_add(ActorRegion *regions,int left,int top,unsigned width,unsigned height,unsigned order){
 if(order>255||width>4096||height>4096)return false;
 int right=left+(int)width,bottom=top+(int)height;
 if(left<0)left=0;
 if(top<0)top=0;
 if(right>256)right=256;
 if(bottom>192)bottom=192;
 native_region_merge(regions+order,(ActorRegion){left,top,right,bottom,order});return true;
}
/* Entry N bounds only actors drawn before static ordinal N. Later actors do
 * not enlarge its restoration quad; the hardware base already supplies the
 * scenery everywhere without an earlier actor underneath. */
static inline bool native_occlusion_regions(ActorRegion *regions,unsigned capacity,unsigned orders,const ActorAtlas *atlas,const NativeDraw *draws,unsigned count){
 if(!regions||!orders||orders>256||capacity<orders||!atlas||atlas->count>ACTOR_ATLAS_PIECES||count>NATIVE_DRAW_LIMIT||(!draws&&count))return false;
 for(unsigned i=0;i<orders;i++)regions[i]=native_region_empty();
 for(unsigned i=0;i<atlas->count;i++){
  const ActorPiece *p=atlas->pieces+i;
  if(p->order>255)return false;
  if(p->order<orders&&!native_region_add(regions,p->screen_x,p->screen_y,p->width,p->height,p->order))return false;
 }
 for(unsigned i=0;i<count;i++){
  const NativeDraw *p=draws+i;
  if(p->order>255)return false;
  if(p->order<orders&&!native_region_add(regions,p->x,p->y,p->w,p->h,p->order))return false;
 }
 ActorRegion before=native_region_empty();
 for(unsigned i=0;i<orders;i++){ActorRegion at=regions[i];regions[i]=before;native_region_merge(&before,at);}
 return true;
}
#endif
