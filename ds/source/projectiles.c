#include "gpu_actors.h"
#include "projectiles.h"
#include <string.h>
#include <stddef.h>
#include <math.h>
#include <stdio.h>
_Static_assert(sizeof(Projectile)==100,"Native projectile size");
_Static_assert(offsetof(Projectile,active)==0x40,"Native active offset");
void projectiles_init(Projectiles *pool){
 memset(pool,0,sizeof(*pool));
 for(unsigned i=0;i<10;i++){
  Projectile *p=&pool->slots[i];p->resource=1;p->repeats=-1;p->mode=1;
  p->last=288;p->delay=p->timer=2;
 }
}
bool projectiles_spawn(Projectiles *pool,int x,int y,float vx,float vy,int variant){
 /* Native callers generate finite velocities +/-9 or +/-16. Avoid native
  * divide-by-zero outside that domain rather than invoking undefined C. */
 if(!isfinite(vx)||!isfinite(vy)||fabsf(vx)<1||fabsf(vx)>2147483520.0f)return false;
 for(unsigned i=0;i<10;i++)if(!pool->slots[i].active){
  Projectile *p=&pool->slots[i];int speed=(int)vx;if(speed<0)speed=-speed;
  p->active=1;p->x=(float)x;p->y=(float)y;p->vx=vx;p->vy=vy;
  p->lifetime=800/speed;
  if(variant==0||variant==1)p->frame=p->first=p->last=variant?232:261;
  return true;
 }
 return false;
}
void projectiles_tick(Projectiles *pool,const ProjectileEnvironment *e){
 for(unsigned i=0;i<10;i++){
  Projectile *p=&pool->slots[i];if(!p->active)continue;
  if(p->x<0||p->y<0||--p->lifetime<=0){p->active=0;continue;}
  int x=(int)p->x,y=(int)p->y;
  if(e&&e->solid&&e->solid(e->context,x,y)>0){
   unsigned property=e->property?e->property(e->context,x,y):0;
   if(!(property&2)||p->vy>0){p->active=0;continue;}
  }
  p->x+=p->vx;p->y+=p->vy;p->vy+=1.0f;if(p->vy>20)p->vy=20;
 }
}
int projectiles_hit(Projectiles *pool,int x,int y,int w,int h,unsigned flags){
 int result=0;
 for(unsigned i=0;i<10;i++){
  Projectile *p=&pool->slots[i];if(p->active!=1)continue;
  if((float)x>p->x||(float)(x+w)<p->x||(float)y>p->y||(float)(y+h)<p->y)continue;
  result=p->first==261?1:2;
  if(flags&1)p->active=0;
  if(flags&2){p->vx=-p->vx;p->active=2;}
 }
 return result;
}
#ifndef PROJECTILE_ROOT
#define PROJECTILE_ROOT "nitro:/projectiles"
#endif
typedef struct {uint16_t width,height;int16_t x,y;uint16_t pixels[22*29];} ShotImage;
static ShotImage images[2];static bool loaded;
static uint16_t le16(const unsigned char *p){return (uint16_t)(p[0]|p[1]<<8);}
bool projectile_graphics_open(void){
 loaded=false;FILE *f=fopen(PROJECTILE_ROOT "/shots.bin","rb");if(!f)return false;
 unsigned char header[4];if(fread(header,1,4,f)!=4||memcmp(header,"KFS1",4)){fclose(f);return false;}
 for(unsigned i=0;i<2;i++){
  unsigned char meta[8],raw[22*29*2];
  if(fread(meta,1,8,f)!=8){fclose(f);return false;}
  ShotImage *s=&images[i];s->width=le16(meta);s->height=le16(meta+2);s->x=(int16_t)le16(meta+4);s->y=(int16_t)le16(meta+6);
  unsigned count=s->width*s->height;
  if(count>22*29||fread(raw,2,count,f)!=count){fclose(f);return false;}
  for(unsigned j=0;j<count;j++)s->pixels[j]=le16(raw+2*j);
 }
 fclose(f);loaded=true;return true;
}
void projectile_graphics_close(void){loaded=false;}
static int first_sample(int camera,int target,int count){
 int lo=0,hi=count;while(lo<hi){int mid=(lo+hi)/2;if(camera+((2*mid+1)*25)/16<target)lo=mid+1;else hi=mid;}return lo;
}
static int last_bounds[4];
void projectiles_last_bounds(int bounds[4]){memcpy(bounds,last_bounds,sizeof(last_bounds));}
static bool projectiles_draw_cpu(const Projectiles *pool,uint16_t *dest,int cx,int cy){
 memset(last_bounds,0,sizeof(last_bounds));
 if(!loaded||!dest)return false;
 for(unsigned i=0;i<10;i++){
  const Projectile *p=&pool->slots[i];if(!p->active)continue;
  const ShotImage *s=&images[p->frame==261?0:1];
  int left=(int)p->x+s->x,top=(int)p->y+s->y;
  int xmin=first_sample(cx,left,256),xmax=first_sample(cx,left+s->width,256);
  int ymin=first_sample(cy,top,192),ymax=first_sample(cy,top+s->height,192);
  if(xmin<xmax&&ymin<ymax){
   if(last_bounds[0]>=last_bounds[2]||last_bounds[1]>=last_bounds[3]){last_bounds[0]=xmin;last_bounds[1]=ymin;last_bounds[2]=xmax;last_bounds[3]=ymax;}
   else{
    if(xmin<last_bounds[0])last_bounds[0]=xmin;
    if(ymin<last_bounds[1])last_bounds[1]=ymin;
    if(xmax>last_bounds[2])last_bounds[2]=xmax;
    if(ymax>last_bounds[3])last_bounds[3]=ymax;
   }
  }
  for(int y=ymin;y<ymax;y++){
   int sy=cy+((2*y+1)*25)/16-top;if(sy<0||sy>=s->height)continue;
   for(int x=xmin;x<xmax;x++){
    int sx=cx+((2*x+1)*25)/16-left;if(sx<0||sx>=s->width)continue;
    uint16_t pixel=s->pixels[sy*s->width+sx];if(pixel&0x8000)dest[y*256+x]=pixel;
   }
  }
 }
 return true;
}

bool projectiles_draw(const Projectiles *pool,uint16_t *dest,int cx,int cy){
 if(!gpu_actors_collect_only())return projectiles_draw_cpu(pool,dest,cx,cy);
 const bool cpu_draw=!gpu_actors_collect_only();
 memset(last_bounds,0,sizeof(last_bounds));
 if(!loaded||!dest)return false;
 for(unsigned i=0;i<10;i++){
  const Projectile *p=&pool->slots[i];if(!p->active)continue;
  const ShotImage *s=&images[p->frame==261?0:1];
  int left=(int)p->x+s->x,top=(int)p->y+s->y;
  int xmin=first_sample(cx,left,256),xmax=first_sample(cx,left+s->width,256);
  int ymin=first_sample(cy,top,192),ymax=first_sample(cy,top+s->height,192);
  if(xmin<xmax&&ymin<ymax){
   if(last_bounds[0]>=last_bounds[2]||last_bounds[1]>=last_bounds[3]){last_bounds[0]=xmin;last_bounds[1]=ymin;last_bounds[2]=xmax;last_bounds[3]=ymax;}
   else{
    if(xmin<last_bounds[0])last_bounds[0]=xmin;
    if(ymin<last_bounds[1])last_bounds[1]=ymin;
    if(xmax>last_bounds[2])last_bounds[2]=xmax;
    if(ymax>last_bounds[3])last_bounds[3]=ymax;
   }
  }
  if(xmin>=xmax||ymin>=ymax)continue;
  for(int strip=ymin;strip<ymax;strip+=8){
   int end=strip+8;if(end>ymax)end=ymax;unsigned sw=(unsigned)(xmax-xmin);
   uint16_t *temporary=gpu_actors_scratch();memset(temporary,0,sw*(unsigned)(end-strip)*2);
   for(int y=strip;y<end;y++){
   int sy=cy+((2*y+1)*25)/16-top;if(sy<0||sy>=s->height)continue;
   for(int x=xmin;x<xmax;x++){
    int sx=cx+((2*x+1)*25)/16-left;if(sx<0||sx>=s->width)continue;
    uint16_t pixel=s->pixels[sy*s->width+sx];if(cpu_draw&&(pixel&0x8000))dest[y*256+x]=pixel;temporary[(y-strip)*sw+(unsigned)(x-xmin)]=pixel;
   }
  }
   gpu_actors_sprite(temporary,sw,(unsigned)(end-strip),sw,xmin,strip,3);
  }
 }
 return true;
}
