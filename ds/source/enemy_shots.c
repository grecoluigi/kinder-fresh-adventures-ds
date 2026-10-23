#include "gpu_actors.h"
#include "enemy_shots.h"
#include "animation.h"
#include <stddef.h>
#include <stdio.h>
#include <string.h>
_Static_assert(sizeof(EnemyShot)==100,"Native general animation record size");
_Static_assert(offsetof(EnemyShot,active)==0x40,"Native activity field");
static EnemyShot slots[ENEMY_SHOTS_CAPACITY];
bool enemy_shot_obstacle_test(const GeometryObject *objects,int count,int x,int y){
 for(int i=count-1;i>=0;i--){
  const GeometryObject *o=&objects[i];if(!o->active||!o->solid)continue;
  if(o->id!=76&&o->id!=78&&o->id!=83&&o->id!=86&&o->id!=87)continue;
  int left=o->x+o->align_x,top=o->y+o->align_y;
  if(x>=left&&x<left+o->width&&y>=top&&y<top+o->height)return true;
 }
 return false;
}
void enemy_shots_init(void){memset(slots,0,sizeof(slots));}
bool enemy_shots_allocate(void){for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(!slots[i].active)return true;return false;}
EnemyShot *enemy_shots_free_slot(void){for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(!slots[i].active)return &slots[i];return NULL;}
const EnemyShot *enemy_shots_slots(void){return slots;}
bool enemy_shots_spawn(uint32_t owner,float x,float y,float vx,float vy){
 for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(!slots[i].active){
  EnemyShot *p=&slots[i];memset(p,0,sizeof(*p));p->opaque04=owner;p->x=x;p->y=y;p->vx=vx;p->vy=vy;p->repeats=-1;p->mode=1;p->timer=p->delay=2;p->active=1;p->lifetime=120;p->frame=p->first=p->last=16;p->callback=0x413b70;if(vx>0)p->opaque50=2;return true;
 }
 return false;
}
/* Native412e20/412dd0 share the general 200-slot pool with enemy shots. */
void enemy_score_popup(int x,int y,int score,void *context){
 (void)context;int frame=score==100?0:score==1000?1:score==10000?2:-1;
 if(frame<0)return;
 EnemyShot *p=enemy_shots_free_slot();if(!p)return;
 Animation a;animation_init(&a,1,3,x,y);memcpy(p,&a,sizeof(a));
 p->x=(float)x;p->y=(float)y;p->active=1;p->lifetime=20;p->vx=0;p->vy=-12;
 p->callback=0x412dd0;p->frame=p->first=p->last=frame;p->opaque50=0;
}
void enemy_score_popup_tick(EnemyShot *p){
 uint32_t ticks;memcpy(&ticks,&p->lifetime,4);--ticks;memcpy(&p->lifetime,&ticks,4);
 if(p->lifetime<=0){p->active=0;return;}
 double vy=(double)p->vy+1.0;p->vy=(float)vy;if(vy>20)p->vy=20;
 p->x=(float)((double)p->x+p->vx);p->y=(float)((double)p->y+p->vy);
}
void enemy_shot_callback(EnemyShot *p,const EnemyShotEnvironment *e){
 if(p->x<0||p->y<0){p->active=0;return;}
 uint32_t ticks;memcpy(&ticks,&p->lifetime,4);--ticks;memcpy(&p->lifetime,&ticks,4);
 if(p->lifetime<=0){p->active=0;return;}
 int x=(int)p->x,y=(int)p->y;
 if(e&&e->solid&&e->solid(e->context,x+10,y+50)>0){
  unsigned property=e->property?e->property(e->context,x+10,y+50):0;
  if(!(property&2)||p->vy>0){p->active=0;return;}
 }
 if(e&&e->contact&&e->contact(x+5,y+10,10,30,20,e->context)){p->active=0;return;}
 if(e&&e->obstacle&&e->obstacle(e->context,x+10,y+50)){p->active=0;return;}
 double vy=(double)p->vy+0.3f;p->vy=(float)vy;if(vy>20)p->vy=20;
 p->x=(float)((double)p->x+p->vx);p->y=(float)((double)p->y+p->vy);
}
bool enemy_shots_spawn_record(const EnemyShot *record){
 if(!record||!record->active)return false;
 for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(!slots[i].active){slots[i]=*record;return true;}
 return false;
}
void enemy_shots_tick_with(const EnemyShotEnvironment *e,EnemyShotCallback callback){
 for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(slots[i].active){
  if(callback)callback(&slots[i],e);else enemy_shot_callback(&slots[i],e);
  Animation copy;memcpy(&copy,&slots[i],100);animation_tick(&copy,NULL,NULL);memcpy(&slots[i],&copy,100);
 }
}
void enemy_shots_tick(const EnemyShotEnvironment *e){enemy_shots_tick_with(e,NULL);}
#ifndef ENEMY_SHOT_ROOT
#define ENEMY_SHOT_ROOT "nitro:/enemy_shots"
#endif
typedef struct {const char *file;uint32_t callback;int frame;unsigned width,height,offset;} ShotImage;
/* Original colors remain resident; points share exact4x4 tiles. Total27,638
 * bytes, no attack-frame file I/O or allocation. */
static uint16_t shot_pixels[6882],point_pixels[371*16],point_indices[1001];
static ShotImage images[11]={
 {"bear.bin",0x413b70,53,42,42,0},{"kong.bin",0x413b70,-1,20,51,1764},
 {"yeti.bin",0x41b770,-1,32,30,2784},{"snowman.bin",0x41a910,-1,28,28,3744},
 {"egg.bin",0x40fd70,-1,18,12,4528},{"gorilla.bin",0x40c2c0,-1,42,47,4744},
 {"factory.bin",0x40d5c0,-1,10,10,6718},{"octopus.bin",0x40cc60,-1,8,8,6818},
 {"points.bin",0x412dd0,0,90,41,0},{"points.bin",0x412dd0,1,120,41,253},
 {"points.bin",0x412dd0,2,152,41,583}
};
static bool loaded;
static uint16_t le16(const unsigned char *p){return (uint16_t)(p[0]|p[1]<<8);}
static ShotImage *shot_image(const EnemyShot *p){
 for(unsigned i=0;i<11;i++)if(p->callback==images[i].callback&&(images[i].frame<0||p->frame==images[i].frame))return &images[i];
 return NULL;
}
/* Bounded boot-time reads avoid the former12KiB automatic pixel buffer. */
static bool read_words(FILE *f,uint16_t *dest,size_t words){
 unsigned char raw[256];
 while(words){size_t n=words<128?words:128;if(fread(raw,2,n,f)!=n)return false;
  for(size_t j=0;j<n;j++)dest[j]=le16(raw+2*j);
  dest+=n;words-=n;
 }return true;
}
bool enemy_shot_graphics_open(void){
 loaded=false;
 for(unsigned i=0;i<8;i++){
  ShotImage *image=&images[i];char path[512];
  int n=snprintf(path,sizeof(path),"%s/%s",ENEMY_SHOT_ROOT,image->file);
  if(n<0||(size_t)n>=sizeof(path))return false;
  FILE *f=fopen(path,"rb");if(!f)return false;
  unsigned char header[8];size_t words=image->width*image->height;
  bool ok=fread(header,1,8,f)==8&&!memcmp(header,"KFE1",4)&&le16(header+4)==image->width&&le16(header+6)==image->height;
  if(ok)ok=read_words(f,shot_pixels+image->offset,words)&&fgetc(f)==EOF;
  fclose(f);if(!ok)return false;
 }
 char path[512];int n=snprintf(path,sizeof(path),"%s/points.bin",ENEMY_SHOT_ROOT);
 if(n<0||(size_t)n>=sizeof(path))return false;
 FILE *f=fopen(path,"rb");if(!f)return false;unsigned char header[12];
 bool ok=fread(header,1,12,f)==12&&!memcmp(header,"KFP2",4)&&le16(header+4)==4&&le16(header+6)==3&&le16(header+8)==371&&le16(header+10)==1001;
 for(unsigned i=8;ok&&i<11;i++){
  unsigned char frame[8];ok=fread(frame,1,8,f)==8&&le16(frame)==images[i].width&&le16(frame+2)==images[i].height&&le16(frame+4)==images[i].offset&&le16(frame+6)==0;
 }
 if(ok)ok=read_words(f,point_indices,1001)&&read_words(f,point_pixels,371*16)&&fgetc(f)==EOF;
 fclose(f);if(!ok)return false;
 for(unsigned i=0;i<1001;i++)if(point_indices[i]>=371)return false;
 loaded=true;return true;
}
void enemy_shot_graphics_close(void){loaded=false;}
bool enemy_shot_draw_command(const EnemyShot *p,int cx,int cy,int *left,int *top,bool *mirror){
 if(!p->active)return false;
 ShotImage *image=shot_image(p);if(!image)return false;
 *mirror=p->opaque50==2;*left=(int)p->x-(*mirror?(int)image->width:0)-cx;*top=(int)p->y-cy;return true;
}
static int first_sample(int camera,int target,int count){
 int lo=0,hi=count;while(lo<hi){int mid=(lo+hi)/2;if(camera+((2*mid+1)*25)/16<target)lo=mid+1;else hi=mid;}return lo;
}
static bool enemy_shots_draw_cpu(uint16_t *dest,int cx,int cy){
 if(!loaded||!dest)return false;
 for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++){
  int left,top;bool mirror;if(!enemy_shot_draw_command(&slots[i],0,0,&left,&top,&mirror))continue;
  ShotImage *image=shot_image(&slots[i]);int width=(int)image->width,height=(int)image->height;
  if(left+width<=cx||left>=cx+800||top+height<=cy||top>=cy+600)continue;
  int xmin=first_sample(cx,left,256),xmax=first_sample(cx,left+width,256),ymin=first_sample(cy,top,192),ymax=first_sample(cy,top+height,192);
  for(int y=ymin;y<ymax;y++){
   int sy=cy+((2*y+1)*25)/16-top;if(sy<0||sy>=height)continue;
   for(int x=xmin;x<xmax;x++){
    int sx=cx+((2*x+1)*25)/16-left;if(sx<0||sx>=width)continue;if(mirror)sx=width-1-sx;
    uint16_t pixel;
    if(slots[i].callback==0x412dd0){
     unsigned tile=point_indices[image->offset+(unsigned)(sy/4)*((image->width+3)/4)+(unsigned)(sx/4)];
     pixel=point_pixels[tile*16+(unsigned)(sy%4)*4+(unsigned)(sx%4)];
    }else pixel=shot_pixels[image->offset+sy*width+sx];if(pixel&0x8000)dest[y*256+x]=pixel;
   }
  }
 }
 return true;
}

bool enemy_shots_draw(uint16_t *dest,int cx,int cy){
 if(!gpu_actors_collect_only())return enemy_shots_draw_cpu(dest,cx,cy);
 const bool cpu_draw=!gpu_actors_collect_only();
 if(!loaded||!dest)return false;
 gpu_actors_ordinal(255);
 for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++){
  int left,top;bool mirror;if(!enemy_shot_draw_command(&slots[i],0,0,&left,&top,&mirror))continue;
  ShotImage *image=shot_image(&slots[i]);int width=(int)image->width,height=(int)image->height;
  if(left+width<=cx||left>=cx+800||top+height<=cy||top>=cy+600)continue;
  int xmin=first_sample(cx,left,256),xmax=first_sample(cx,left+width,256),ymin=first_sample(cy,top,192),ymax=first_sample(cy,top+height,192);
  if(xmin>=xmax||ymin>=ymax)continue;
  /* Source columns depend only on the shot and camera; sample them once per
   * shot instead of once per pixel row. -1 marks a column outside the image. */
  int16_t columns[256];
  for(int x=xmin;x<xmax;x++){
   int sx=cx+((2*x+1)*25)/16-left;if(sx<0||sx>=width)sx=-1;else if(mirror)sx=width-1-sx;
   columns[x-xmin]=(int16_t)sx;
  }
  bool points=slots[i].callback==0x412dd0;unsigned tiles_wide=(image->width+3)/4;
  for(int strip=ymin;strip<ymax;strip+=8){
   int end=strip+8;if(end>ymax)end=ymax;unsigned sw=(unsigned)(xmax-xmin);
   uint16_t *temporary=gpu_actors_scratch();memset(temporary,0,sw*(unsigned)(end-strip)*2);
   for(int y=strip;y<end;y++){
   int sy=cy+((2*y+1)*25)/16-top;if(sy<0||sy>=height)continue;
   uint16_t *out=temporary+(y-strip)*sw;
   for(unsigned x=0;x<sw;x++){
    int sx=columns[x];if(sx<0)continue;
    uint16_t pixel;
    if(points){
     unsigned tile=point_indices[image->offset+(unsigned)(sy/4)*tiles_wide+(unsigned)(sx/4)];
     pixel=point_pixels[tile*16+(unsigned)(sy%4)*4+(unsigned)(sx%4)];
    }else pixel=shot_pixels[image->offset+sy*width+sx];if(cpu_draw&&(pixel&0x8000))dest[y*256+xmin+(int)x]=pixel;out[x]=pixel;
   }
  }
   gpu_actors_sprite(temporary,sw,(unsigned)(end-strip),sw,xmin,strip,4);
  }
 }
 return true;
}
