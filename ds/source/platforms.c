#include "platforms.h"
#include <string.h>
static int16_t s16(const uint8_t *p){return (int16_t)((uint16_t)p[0]|(uint16_t)p[1]<<8);}
static void put16(uint8_t *p,int v){p[0]=(uint8_t)v;p[1]=(uint8_t)((unsigned)v>>8);}
static float f32(const uint8_t *p){float v;memcpy(&v,p,4);return v;}
static void pf32(uint8_t *p,float v){memcpy(p,&v,4);}
static uint32_t u32(const uint8_t *p){uint32_t v;memcpy(&v,p,4);return v;}
static void pu32(uint8_t *p,uint32_t v){memcpy(p,&v,4);}
static int32_t add(int32_t a,int32_t b){return (int32_t)((uint32_t)a+(uint32_t)b);}
static int32_t fixed(int v){return (int32_t)((uint32_t)v<<12);}
static bool side(GameBody *b,BodyProbe probe,void *context,int x,int y,unsigned mode){
 y-=b->probe_stride*b->probe_count;
 for(int n=b->probe_count;n!=0;--n){y+=b->probe_stride;if(probe(context,b->layer,x,y,mode))return true;}
 return false;
}
void platform_body_displace(GameBody *b,int32_t dx,int32_t dy,unsigned mode,BodyProbe probe,void *context){
 if((uint32_t)b->kind>1)return;
 int32_t ox=b->motion.x,oy=b->motion.y;
 int x=ox/4096,y=oy/4096;
 b->motion.x=add(ox,dx);b->motion.y=add(oy,dy);
 int tx=b->motion.x/4096,ty=b->motion.y/4096;
 unsigned query=((unsigned)b->kind&1)|(mode&14);
 if(y>ty){
  y-=b->height;ty-=b->height;
  while(y!=ty&&!probe(context,b->layer,x,y,query))--y;
  if(y!=ty)b->contacts|=1;
  y+=b->height;ty+=b->height;
 }else if(y<ty){
  while(y!=ty&&!probe(context,b->layer,x,y,query))++y;
  if(y!=ty)b->contacts|=2;
 }
 if(y!=ty){b->motion.y=fixed(y);b->motion.vy=0;}
 if(x<tx){
  while(x!=tx&&!side(b,probe,context,x+b->half_width,y-b->probe_offset,query))++x;
  if(x!=tx)b->contacts|=8;
 }else if(x>tx){
  while(x!=tx&&!side(b,probe,context,x-b->half_width,y-b->probe_offset,query))--x;
  if(x!=tx)b->contacts|=4;
 }
 if(x!=tx){b->motion.x=fixed(x);b->motion.vx=0;}
 b->platform_dx=add(b->platform_dx,(int32_t)((uint32_t)b->motion.x-(uint32_t)ox));
 b->platform_dy=add(b->platform_dy,(int32_t)((uint32_t)b->motion.y-(uint32_t)oy));
}
static bool standing(const GameEntity *e,int width,const GameBody *b){
 int x=(uint32_t)b->kind<=1?b->motion.x/4096:0,y=(uint32_t)b->kind<=1?b->motion.y/4096:0;
 int vy=(uint32_t)b->kind<=1?b->motion.vy/4096:0;
 return x>=entity_x(e)&&x<entity_x(e)+width&&y==entity_y(e)+e->bytes[42]&&vy>=0;
}
void platform_transport(GameEntity *e,int width,GameBody **bodies,size_t count,int dx,int dy,BodyProbe probe,void *context){
 int step=dx<0?-1:1,n=dx<0?-dx:dx;
 while(n-->0){
  for(size_t i=0;i<count;i++)if(standing(e,width,bodies[i])){
   if((uint32_t)bodies[i]->kind<=1)bodies[i]->motion.vy=0;
   platform_body_displace(bodies[i],fixed(step),0,4,probe,context);
  }
  put16(e->bytes+2,entity_x(e)+step);
 }
 step=dy<0?-1:1;n=dy<0?-dy:dy;
 while(n-->0){
  for(size_t i=0;i<count;i++)if(standing(e,width,bodies[i])){
   bool contact=body_has_contact(bodies[i],probe,context);
   if(contact&&step>0)continue;
   if((uint32_t)bodies[i]->kind<=1)bodies[i]->motion.vy=0;
   platform_body_displace(bodies[i],0,fixed(step),4,probe,context);
  }
  put16(e->bytes+4,entity_y(e)+step);
 }
}
void platform_path_end(GameEntity *e,int event){
 if(e->bytes[41]){--e->bytes[41];return;}
 e->bytes[41]=e->bytes[40];e->bytes[39]^=(uint8_t)event;
 if(e->bytes[44])e->bytes[43]^=1;
}
static void path_move(GameEntity *e,const PlatformEnvironment *v,int direction){
 int current=(direction<=2)?entity_x(e):entity_y(e)-(int)f32(e->bytes+148);
 int bound=s16(e->bytes+(direction==1?31:direction==2?35:direction==3?33:37));
 int speed=e->bytes[29],delta=0;
 if(direction==1||direction==3){if(current>bound)delta=current-speed<bound?bound-current:-speed;}
 else if(current<bound)delta=current+speed>bound?bound-current:speed;
 if(delta)platform_transport(e,v->width,v->bodies,v->body_count,direction<=2?delta:0,direction>=3?delta:0,v->probe,v->context);
 /* Vertical nativehelpers compare the basecoordinate sampled before movement. */
 int test=direction<=2?entity_x(e):current;
 if((direction==1||direction==3)?test<=bound:test>=bound){
  int kind=direction<=2?3:12;
  if(v->path_event)v->path_event(e,kind,v->context);else platform_path_end(e,kind);
 }
}
bool platform_spring_tick(GameEntity *e,const PlatformEnvironment *v){
 unsigned id=entity_id(e);if(id!=2&&id!=200&&id!=201&&id!=202&&id!=210&&id!=220&&(id<230||id>233))return false;
 bool supported=false;for(size_t i=0;i<v->body_count;i++)if(standing(e,v->width,v->bodies[i])){supported=true;break;}
 if(supported){if(u32(e->bytes+112)==0){pu32(e->bytes+112,1);pf32(e->bytes+152,3.0f);}}
 else{pu32(e->bytes+112,0);pf32(e->bytes+152,0);}
 float velocity=(float)((double)f32(e->bytes+152)-0.4000000059604644775390625);
 if(velocity< -20.0f)velocity=-20.0f;
 pf32(e->bytes+152,velocity);
 float old=f32(e->bytes+148),next=(float)((double)velocity+(double)old);
 if(next<0)next=0;else if(next>=30){next=30;pf32(e->bytes+152,0);}
 platform_transport(e,v->width,v->bodies,v->body_count,0,(int)next-(int)old,v->probe,v->context);
 pf32(e->bytes+148,next);
 if(e->bytes[28]){
  switch(e->bytes[39]){
  case 1:path_move(e,v,1);break;case 2:path_move(e,v,2);break;case 4:path_move(e,v,3);break;
  case 5:path_move(e,v,1);path_move(e,v,3);break;case 6:path_move(e,v,2);path_move(e,v,3);break;
  case 8:path_move(e,v,4);break;case 9:path_move(e,v,1);path_move(e,v,4);break;case 10:path_move(e,v,2);path_move(e,v,4);break;default:break;
  }
 }
 return true;
}
