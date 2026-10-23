#include "camera.h"
static int clamp(int v,int hi){return v<0?0:v>hi?hi:v;}
int camera_x(const GameCamera *c,int l){return c->layers[l].tile_x*32-c->layers[l].offset_x;}
int camera_y(const GameCamera *c,int l){return c->layers[l].tile_y*32-c->layers[l].offset_y;}
/*434ab0 rescales through last-layer coordinates for bounds, then each plane. */
static void move(GameCamera *c,int dx,int dy){
 int ref=c->reference_layer,last=CAMERA_LAYERS-1;
 int x=camera_x(c,ref)+dx,y=camera_y(c,ref)+dy;
 if(x<0)x=0;
 if(y<0)y=0;
 int rx=c->layers[ref].factor_x,ry=c->layers[ref].factor_y;
 int lx=c->layers[last].factor_x,ly=c->layers[last].factor_y;
 if(x*lx/rx>=c->max_x)x=c->max_x*rx/lx;
 if(y*ly/ry>=c->max_y)y=c->max_y*ry/ly;
 for(int l=0;l<CAMERA_LAYERS;l++){
  int px=x*c->layers[l].factor_x/rx,py=y*c->layers[l].factor_y/ry;
  c->layers[l].tile_x=(int16_t)(px/32);c->layers[l].offset_x=(int16_t)(-(px%32));
  c->layers[l].tile_y=(int16_t)(py/32);c->layers[l].offset_y=(int16_t)(-(py%32));
 }
}
void camera_init(GameCamera *c,int w,int h,int x,int y,const int16_t f[CAMERA_LAYERS],int ref){
 c->reference_layer=(int16_t)ref;c->left=130;c->top=280;c->right=670;c->bottom=480;
 c->max_x=(w-800/32-1)*32;if(c->max_x<0)c->max_x=0;
 c->max_y=(h-600/32-3)*32;if(c->max_y<0)c->max_y=0;
 /* Native initialization clamps last-plane whole tile coordinate then scales ratios. */
 int px=clamp(x/32,c->max_x/32)*32,py=clamp(y/32,c->max_y/32)*32;
 for(int l=0;l<CAMERA_LAYERS;l++){
  int sx=px*f[l]/f[CAMERA_LAYERS-1],sy=py;
  /*434787 reloads reference factor for Y; preserve native init asymmetry. */
  c->layers[l]=(CameraLayer){(int16_t)(sx/32),(int16_t)(sy/32),(int16_t)(-(sx%32)),(int16_t)(-(sy%32)),f[l],f[l]};
 }
}
void camera_follow(GameCamera *c,int px,int py,int selector,int disabled){
 if(disabled)return;
 int sx=px-camera_x(c,c->reference_layer),sy=py-camera_y(c,c->reference_layer);
 if(selector==0||selector==1){
  int target=selector==0?c->left:c->right;
  int dx=sx-target;if(dx<-10)dx=-10;if(dx>10)dx=10;
  if(dx)move(c,dx,0);
 }
 if(sy<c->top)move(c,0,sy-c->top);
 if(sy>c->bottom)move(c,0,sy-c->bottom);
}
