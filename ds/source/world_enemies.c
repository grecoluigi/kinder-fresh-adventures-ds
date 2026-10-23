#include "world_enemies.h"
#include <string.h>
static int16_t r16(const GameEntity *e,unsigned o){int16_t v;memcpy(&v,e->bytes+o,2);return v;}
static void w16(GameEntity *e,unsigned o,int v){uint16_t n=(uint16_t)v;memcpy(e->bytes+o,&n,2);}
static int32_t r32(const GameEntity *e,unsigned o){int32_t v;memcpy(&v,e->bytes+o,4);return v;}
static void w32(GameEntity *e,unsigned o,uint32_t v){memcpy(e->bytes+o,&v,4);}
static float rf(const GameEntity *e,unsigned o){float v;memcpy(&v,e->bytes+o,4);return v;}
static void wf(GameEntity *e,unsigned o,float v){memcpy(e->bytes+o,&v,4);}
static void range(GameEntity *e,const EnemyEnvironment *env,unsigned n){w16(e,10,env->ranges[n][0]);w16(e,12,env->ranges[n][1]);w16(e,14,env->ranges[n][0]);e->bytes[22]=1;}
static void sound(const EnemyEnvironment *env,int channel,int id){if(env->sound)env->sound(channel,id,env->context);}
static void patrol(GameEntity *e){
 if(!e->bytes[28])return;
 double x=(double)rf(e,156)+rf(e,148),y=(double)rf(e,160)+rf(e,152);float vx=rf(e,156);
 wf(e,148,(float)x);wf(e,152,(float)y);
 if(vx>0){if(x>=(float)r16(e,35)){wf(e,148,(float)r16(e,35));wf(e,156,-vx);}}
 else if(x<=(float)r16(e,31)){wf(e,148,(float)r16(e,31));wf(e,156,-vx);}
 w16(e,2,(int)rf(e,148));w16(e,4,(int)(float)y);e->bytes[43]=rf(e,156)>0?1:0;
}
static void freeze(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env,int dx,int dy){
 uint32_t n;memcpy(&n,&g->score,4);n+=100;memcpy(&g->score,&n,4);
 if(env->popup)env->popup(entity_x(e)+dx,entity_y(e)+dy,100,env->context);
 e->bytes[28]=0;e->bytes[47]=1;range(e,env,17);w16(e,16,1);w16(e,18,1);w16(e,6,1);w16(e,98,100);sound(env,3,env->hit_sound);
}
static bool hit(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env,int x,int y,int w,int h,int dx,int dy){
 if(env->contact)env->contact(x,y,w,h,20,env->context);
 if(env->projectile&&env->projectile(x,y,w,h,1,env->context)){freeze(e,g,env,dx,dy);return true;}return false;
}
static void falling(GameEntity *e,const EnemyEnvironment *env){
 if(r16(e,98)==100){if(r16(e,14)!=r16(e,12))return;
  wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));e->bytes[184]=1;w16(e,18,1);w16(e,98,101);wf(e,156,e->bytes[43]?1:-1);wf(e,160,-12);w32(e,116,120);sound(env,4,env->fall_sound);return;
 }
 float vy=(float)((double)rf(e,160)+0.6f);wf(e,160,vy);if((double)rf(e,160)>20)wf(e,160,20);
 double x=(double)rf(e,156)+rf(e,148);float y=(float)((double)rf(e,160)+rf(e,152));wf(e,148,(float)x);wf(e,152,y);w16(e,2,(int)x);w16(e,4,(int)y);
 int32_t t=(int32_t)((uint32_t)r32(e,116)-1);w32(e,116,(uint32_t)t);if(t<=0)w16(e,98,200);if(r16(e,14)==r16(e,12))w16(e,18,1);
}
bool enemy_eagle_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=6)return false;
 int s=r16(e,98);
 if(s==0){wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));w16(e,6,255);e->bytes[28]=1;w16(e,98,1);wf(e,156,2);wf(e,160,0);w32(e,116,0);w16(e,16,1);w16(e,18,1);range(e,env,0);return true;}
 if(s==1){w16(e,12,8);patrol(e);if(r32(e,116))w32(e,116,(uint32_t)r32(e,116)-1);
  int x=entity_x(e),y=entity_y(e),px=env->player_x,py=env->player_y,d=px-x-90;if(d<0)d=-d;
  if((e->bytes[43]?px>x+90:px<x+90)&&d<180&&py>y+300&&py<y+500&&!r32(e,116)&&px>=r16(e,31)&&px<=r16(e,35)&&!(e->bytes[42]&1)){
   wf(e,160,12);w16(e,98,10);sound(env,10,env->throw_sound);range(e,env,16);
  }
  hit(e,g,env,entity_x(e),entity_y(e)+130,180,77,50,170);
 }else if(s==10){
  if(e->bytes[28]){
   float vy=(float)((double)rf(e,160)-0.3f);wf(e,160,vy);if(vy<=-12)wf(e,160,-12);
   double x=(double)rf(e,156)+rf(e,148),y=(double)rf(e,160)+rf(e,152);wf(e,148,(float)x);wf(e,152,(float)y);
   if(r16(e,14)==23){w16(e,10,23);w16(e,12,30);}
   if(y<=(float)r16(e,33)){w16(e,10,0);w16(e,12,35);w32(e,116,120);wf(e,152,(float)r16(e,33));wf(e,160,0);w16(e,98,1);}
   if(rf(e,156)>0){if(x>=(float)r16(e,35))wf(e,148,(float)r16(e,35));}
   else if(x<=(float)r16(e,31))wf(e,148,(float)r16(e,31));
   w16(e,2,(int)rf(e,148));w16(e,4,(int)rf(e,152));e->bytes[43]=rf(e,156)>0?1:0;
  }
  hit(e,g,env,entity_x(e),entity_y(e)+130,180,77,50,170);
 }else if(s==100||s==101)falling(e,env);
 return true;
}
bool enemy_small_octopus_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=17)return false;
 int s=r16(e,98);
 if(s==0){w16(e,6,255);wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));e->bytes[28]=1;w16(e,98,1);wf(e,156,3);wf(e,160,0);w32(e,116,0);w16(e,16,3);w16(e,18,3);range(e,env,0);return true;}
 if(s==1){
  if(r16(e,14)==7&&r16(e,18)==0&&e->bytes[22]==1)e->bytes[22]=2;
  if(r16(e,14)==0&&r16(e,18)==0&&e->bytes[22]==2)e->bytes[22]=1;
  patrol(e);
  if(hit(e,g,env,entity_x(e)+40,entity_y(e),70,90,35,30))return true;
  static const int rect[8][4]={{20,60,115,35},{-3,60,138,35},{-21,60,156,35},{-38,60,226,35},{-53,60,276,35},{-53,60,300,35},{-53,60,300,35},{-53,60,300,35}};
  int f=r16(e,14);/* Original only indexes the eight animation frames. */
  if(f>=0&&f<8){const int *r=rect[f];int x=entity_x(e)+(e->bytes[43]?152-r[0]-r[2]:r[0]);hit(e,g,env,x,entity_y(e)+r[1],r[2],r[3],35,30);}
 }else if(s==100||s==101)falling(e,env);
 return true;
}
bool enemy_bee_callback(GameEntity *e,EntityGlobals *g,const WorldEnemyEnvironment *world){
 if(!e||!g||!world||entity_id(e)!=16)return false;
 const EnemyEnvironment *env=&world->enemy;
 int s=r16(e,98);
 if(s<100&&world->ambient){int x=entity_x(e),y=entity_y(e),w=world->frame_width,h=world->frame_height;world->ambient(x,y,14,env->context);world->ambient(x+w,y,14,env->context);world->ambient(x,y+h,14,env->context);world->ambient(x+w,y+h,14,env->context);}
 if(s==0){wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));w16(e,6,255);e->bytes[28]=1;w16(e,98,1);wf(e,156,2);wf(e,160,0);w32(e,116,0);w16(e,16,1);w16(e,18,1);range(e,env,0);return true;}
 if(s==1){w16(e,12,8);patrol(e);if(r32(e,116))w32(e,116,(uint32_t)r32(e,116)-1);
  int x=entity_x(e),y=entity_y(e),px=env->player_x,py=env->player_y,d=px-x-44;if(d<0)d=-d;
  if((e->bytes[43]?px>x+44:px<x+44)&&d<180&&py>y+300&&py<y+500&&!r32(e,116)&&px>=r16(e,31)&&px<=r16(e,35)&&!(e->bytes[42]&1)){
   wf(e,160,12);w16(e,98,10);range(e,env,16);
  }
  hit(e,g,env,entity_x(e)+10,entity_y(e)+30,68,70,0,60);
 }else if(s==10){
  if(e->bytes[28]){
   float vy=(float)((double)rf(e,160)-0.3f);wf(e,160,vy);if(vy<=-12)wf(e,160,-12);
   double x=(double)rf(e,156)+rf(e,148),y=(double)rf(e,160)+rf(e,152);wf(e,148,(float)x);wf(e,152,(float)y);
   if(r16(e,14)==25){w16(e,10,25);w16(e,12,25);}
   if(y<=(float)r16(e,33)){w16(e,10,0);w16(e,12,32);w32(e,116,120);wf(e,152,(float)r16(e,33));wf(e,160,0);w16(e,98,1);}
   if(rf(e,156)>0){if(x>=(float)r16(e,35))wf(e,148,(float)r16(e,35));}
   else if(x<=(float)r16(e,31))wf(e,148,(float)r16(e,31));
   w16(e,2,(int)rf(e,148));w16(e,4,(int)rf(e,152));e->bytes[43]=rf(e,156)>0?1:0;
  }
  hit(e,g,env,entity_x(e)+10,entity_y(e)+30,68,70,0,60);
 }else if(s==100||s==101)falling(e,env);
 return true;
}
bool enemy_small_robot_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=11)return false;
 int s=r16(e,98);
 if(s==0){w16(e,6,255);wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));e->bytes[28]=1;w16(e,98,1);wf(e,156,3);wf(e,160,0);w32(e,116,0);w16(e,16,3);w16(e,18,3);range(e,env,0);return true;}
 if(s==1){patrol(e);if(hit(e,g,env,entity_x(e)+30,entity_y(e)+10,60,198,10,30))return true;
  int x=entity_x(e),y=entity_y(e),px=env->player_x,py=env->player_y,d=px-x-45;if(d<0)d=-d;
  if((e->bytes[43]?px>x+45:px<x+45)&&d<600&&py>y+8&&py<y+408&&px>=r16(e,31)&&px<r16(e,35)&&!(e->bytes[42]&1)){
   sound(env,10,env->throw_sound);e->bytes[184]=1;wf(e,156,rf(e,156)<0?-6:6);range(e,env,16);w16(e,10,0);w16(e,14,0);w16(e,98,10);
  }
 }else if(s==10){if(r16(e,14)==3)w16(e,10,3);
  if(e->bytes[28]){
   double x=(double)rf(e,156)+rf(e,148);float y=(float)((double)rf(e,160)+rf(e,152));wf(e,148,(float)x);wf(e,152,y);
   if(rf(e,156)>0){if(x>=r16(e,35)-100){w16(e,12,14);wf(e,156,3);}if(r16(e,35)>rf(e,148)){/* boundary remains ahead */}else {wf(e,148,(float)r16(e,35));wf(e,156,-3);}}
   else {if(x<r16(e,31)+100){w16(e,12,14);wf(e,156,-3);}if(r16(e,31)<rf(e,148)){/* boundary remains behind */}else {wf(e,148,(float)r16(e,31));wf(e,156,3);}}
   w16(e,2,(int)rf(e,148));w16(e,4,(int)y);e->bytes[43]=rf(e,156)>0?1:0;
  }
  if(hit(e,g,env,entity_x(e)+30,entity_y(e)+48,60,160,10,30))return true;
  if(r16(e,14)==14&&r16(e,18)==0){e->bytes[184]=0;range(e,env,0);w16(e,98,1);}
 }else if(s==100||s==101)falling(e,env);
 return true;
}
bool enemy_flying_robot_callback(GameEntity *e,EntityGlobals *g,const WorldEnemyEnvironment *world){
 if(!e||!g||!world||entity_id(e)!=13)return false;
 const EnemyEnvironment *env=&world->enemy;int s=r16(e,98);
 if(s<100&&world->ambient){int x=entity_x(e),y=entity_y(e),w=world->frame_width,h=world->frame_height;world->ambient(x,y,14,env->context);world->ambient(x+w,y,14,env->context);world->ambient(x,y+h,14,env->context);world->ambient(x+w,y+h,14,env->context);}
 if(s==0){w16(e,6,255);wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));e->bytes[28]=1;w16(e,98,1);wf(e,156,5);wf(e,160,0);wf(e,164,0.3f);wf(e,168,0.3f);w16(e,16,1);w16(e,18,1);range(e,env,0);return true;}
 if(s==1){
  if(e->bytes[28]){
   float vx=(float)((double)rf(e,164)+rf(e,156));double vy=(double)rf(e,168)+rf(e,160);wf(e,156,vx);wf(e,160,(float)vy);
   if(vx>5)wf(e,156,5);
   if(rf(e,156)<-5)wf(e,156,-5);
   if(vy>5)wf(e,160,5);
   if(rf(e,160)<-5)wf(e,160,-5);
   double x=(double)rf(e,148)+rf(e,156),y=(double)rf(e,160)+rf(e,152);wf(e,148,(float)x);wf(e,152,(float)y);
   if(x<r16(e,31))wf(e,164,0.3f);
   if(x>=r16(e,35))wf(e,164,-0.3f);
   if(y<r16(e,33))wf(e,168,0.3f);
   if(y>=r16(e,37))wf(e,168,-0.3f);
   w16(e,2,(int)x);w16(e,4,(int)(float)y);e->bytes[43]=rf(e,156)>0?1:0;
  }
  hit(e,g,env,entity_x(e),entity_y(e)+40,world->base_width,world->base_height-40,20,30);
 }else if(s==100||s==101)falling(e,env);
 return true;
}
static void decrement(GameEntity *e,unsigned offset){if(r32(e,offset))w32(e,offset,(uint32_t)r32(e,offset)-1);}
static int random_value(const EnemyEnvironment *env){return env->random?env->random(env->context):0;}
bool enemy_small_yeti_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=7)return false;
 int s=r16(e,98);
 if(s==0){w16(e,6,255);wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));e->bytes[28]=1;w16(e,98,1);wf(e,156,3);wf(e,160,0);w32(e,116,0);w32(e,120,0);w16(e,16,3);w16(e,18,3);range(e,env,0);return true;}
 if(s==1){decrement(e,116);if(r16(e,14)==37)w16(e,10,37);
  if(!r32(e,120)){w16(e,6,1);int n=random_value(env)%60;w16(e,98,2);w16(e,12,49);w32(e,120,n+60);}else decrement(e,120);
  patrol(e);
 }else if(s==2){decrement(e,116);
  if(r16(e,14)==r16(e,12)){w16(e,18,1);int x=entity_x(e),y=entity_y(e),px=env->player_x,py=env->player_y,d=px-x-50;if(d<0)d=-d;
   if((e->bytes[43]?px>x+50:px<x+50)&&d<600&&py>y-11&&py<y+389&&!r32(e,116)&&!(e->bytes[42]&1)){range(e,env,16);w16(e,98,10);w16(e,6,random_value(env)%10+1);return true;}
  }
  patrol(e);if(r16(e,14)==49)e->bytes[28]=0;
  if(!r32(e,120)){e->bytes[28]=1;w16(e,6,255);int n=random_value(env)%120;w16(e,98,1);w16(e,10,34);w16(e,14,34);w16(e,12,46);w32(e,120,n+120);}else decrement(e,120);
 }else if(s==10){
  if(r16(e,14)==19&&r16(e,18)==r16(e,16)&&env->allocate&&env->allocate(env->context)){
   sound(env,10,env->throw_sound);float x=(float)(entity_x(e)-52),y=(float)(entity_y(e)+56),vx=-11;
   if(e->bytes[43]){x+=240;vx=11;}if(env->spawn)env->spawn(e,x,y,vx,-3,env->context);
  }
  if(r16(e,14)==r16(e,12)&&r16(e,18)==0&&r16(e,6)==1){w32(e,116,120);w16(e,18,1);w16(e,98,2);w16(e,10,37);w16(e,12,49);w16(e,14,49);}
 }else {if(s==100||s==101)falling(e,env);return true;}
 int x=entity_x(e)+40,y=entity_y(e);
 if(env->contact)env->contact(x,y+20,40,159,20,env->context);
 if(env->projectile&&env->projectile(x,y+5,40,174,1,env->context))freeze(e,g,env,10,30);
 return true;
}
void enemy_ambient_reset(EnemyAmbientState *state,int32_t camera_offset_x,int32_t camera_offset_y){
 if(!state)return;
 state->camera_offset_x=camera_offset_x;state->camera_offset_y=camera_offset_y;
 for(unsigned i=0;i<16;i++)state->squared_distance[i]=INT32_MAX;
}
void enemy_ambient_contribute(EnemyAmbientState *state,int32_t x,int32_t y,unsigned slot){
 if(!state||slot>=16)return;
 int32_t cx=400-state->camera_offset_x,cy=300-state->camera_offset_y;
 if(x>cx-1200&&x<cx+1200&&y>cy-900&&y<cy+900){int32_t dx=cx-x,dy=cy-y,d=dx*dx+dy*dy;if(d<state->squared_distance[slot])state->squared_distance[slot]=d;}
}
int enemy_ambient_volume(const EnemyAmbientState *state,unsigned slot){
 if(!state||slot>=16)return -100;
 int32_t d=state->squared_distance[slot];
 if(d<122500)return 0;
 if(d>1130000)return -100;
 return ((122500-d)*50)/1007500;
}
uint32_t enemy_ambient_sample_global(unsigned world,unsigned channel){
 if(world==2){if(channel==8)return 0x4e0b0a;if(channel==14)return 0x4dab5a;}else if(world==3&&channel==14)return 0x4dbc6e;return 0;
}
bool enemy_snowman_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=8)return false;
 int s=r16(e,98);
 if(s==0){w16(e,6,255);wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));e->bytes[28]=1;w16(e,98,1);wf(e,156,3);wf(e,160,0);w32(e,116,0);w32(e,120,0);w16(e,16,3);w16(e,18,3);range(e,env,0);return true;}
 if(s==1){decrement(e,116);if(r16(e,14)==41)w16(e,10,41);
  if(!r32(e,120)){w16(e,6,1);int n=random_value(env)%60;w16(e,98,2);w16(e,12,53);w32(e,120,n+60);}else decrement(e,120);
  patrol(e);
 }else if(s==2){decrement(e,116);
  if(r16(e,14)==r16(e,12)){w16(e,18,1);int x=entity_x(e),y=entity_y(e),px=env->player_x,py=env->player_y,d=px-x-65;if(d<0)d=-d;
   if((e->bytes[43]?px>x+65:px<x+65)&&d<600&&py>y+18&&py<y+418&&!r32(e,116)&&!(e->bytes[42]&1)){range(e,env,16);w16(e,98,10);w16(e,6,random_value(env)%10+1);return true;}
  }
  patrol(e);if(r16(e,14)==53)e->bytes[28]=0;
  if(!r32(e,120)){e->bytes[28]=1;w16(e,6,255);int n=random_value(env)%120;w16(e,98,1);w16(e,10,38);w16(e,14,38);w16(e,12,50);w32(e,120,n+120);}else decrement(e,120);
 }else if(s==10){
  if(r16(e,14)==32&&r16(e,18)==r16(e,16)&&env->allocate&&env->allocate(env->context)){
   sound(env,10,env->throw_sound);float x=(float)(entity_x(e)-22),y=(float)(entity_y(e)+66),vx=-11;
   if(e->bytes[43]){x+=176;vx=11;}if(env->spawn)env->spawn(e,x,y,vx,-3,env->context);
  }
  if(r16(e,14)==r16(e,12)&&r16(e,18)==0&&r16(e,6)==1){w32(e,116,120);w16(e,18,1);w16(e,98,2);w16(e,10,41);w16(e,12,53);w16(e,14,53);}
 }else if(s==100){
  if(env->projectile)env->projectile(entity_x(e)+40,entity_y(e)+120,70,88,1,env->context);
  if(r16(e,14)==r16(e,12))w16(e,18,1);
  if(!r32(e,116)){range(e,env,17);e->bytes[22]=2;w16(e,14,r16(e,12));w16(e,98,101);}else decrement(e,116);return true;
 }else if(s==101){
  if(env->projectile)env->projectile(entity_x(e)+40,entity_y(e)+120,70,88,1,env->context);
  if(r16(e,14)==r16(e,10)&&r16(e,18)==0){
   e->bytes[184]=0;wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));w16(e,16,3);w16(e,18,3);w32(e,116,0);w32(e,120,0);wf(e,160,0);wf(e,156,3);w16(e,98,1);e->bytes[28]=1;w16(e,6,255);range(e,env,0);
  }return true;
 }else return true;
 int x=entity_x(e)+40,y=entity_y(e);
 if(env->contact)env->contact(x,y+20,70,188,20,env->context);
 if(env->projectile&&env->projectile(x,y+20,70,188,1,env->context)){
  e->bytes[28]=0;range(e,env,17);w16(e,16,1);w16(e,18,1);w16(e,6,1);w32(e,116,120);e->bytes[184]=1;w16(e,98,100);sound(env,3,env->hit_sound);
 }
 return true;
}
bool enemy_egg_robot_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=12)return false;
 int s=r16(e,98);
 if(s==0){w16(e,6,255);wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));e->bytes[28]=1;w16(e,98,1);wf(e,156,3);wf(e,160,0);w32(e,116,0);w32(e,120,0);w16(e,16,3);w16(e,18,3);range(e,env,0);return true;}
 if(s==1){decrement(e,116);if(r16(e,14)==35)w16(e,10,35);
  if(!r32(e,120)){w16(e,6,1);int n=random_value(env)%60;w16(e,98,2);w16(e,12,47);w32(e,120,n+60);}else decrement(e,120);
  patrol(e);
 }else if(s==2){decrement(e,116);
  if(r16(e,14)==r16(e,12)){w16(e,18,1);int x=entity_x(e),y=entity_y(e),px=env->player_x,py=env->player_y,d=px-x-56;if(d<0)d=-d;
   if((e->bytes[43]?px>x+56:px<x+56)&&d<600&&py>y-5&&py<y+395&&!r32(e,116)&&!(e->bytes[42]&1)){range(e,env,16);w16(e,98,10);w16(e,6,random_value(env)%10+1);return true;}
  }
  patrol(e);if(r16(e,14)==47)e->bytes[28]=0;
  if(!r32(e,120)){e->bytes[28]=1;w16(e,6,255);int n=random_value(env)%120;w16(e,98,1);w16(e,10,32);w16(e,14,32);w16(e,12,44);w32(e,120,n+120);}else decrement(e,120);
 }else if(s==10){
  if(r16(e,14)==13&&r16(e,18)>0)w16(e,18,0);
  if(r16(e,14)==14&&r16(e,18)==r16(e,16)&&env->allocate&&env->allocate(env->context)){
   sound(env,10,env->throw_sound);float x=(float)(entity_x(e)-17),y=(float)(entity_y(e)+53),vx=-11;
   if(e->bytes[43]){x+=145;vx=11;}if(env->spawn)env->spawn(e,x,y,vx,0,env->context);
  }
  if(r16(e,14)==r16(e,12)&&r16(e,18)==0&&r16(e,6)==1){w32(e,116,120);w16(e,18,1);w16(e,98,2);w16(e,10,35);w16(e,12,47);w16(e,14,47);}
 }else {if(s==100||s==101)falling(e,env);return true;}
 int x=entity_x(e)+20,y=entity_y(e);
 if(env->contact)env->contact(x,y+20,72,155,20,env->context);
 if(env->projectile&&env->projectile(x,y+20,72,155,1,env->context))freeze(e,g,env,15,30);
 return true;
}
bool world_enemy_shot_init(EnemyShot *p,unsigned owner_id,uint32_t owner,float x,float y,float vx,float vy){
 if(!p||(owner_id!=7&&owner_id!=8&&owner_id!=12))return false;
 memset(p,0,sizeof(*p));p->opaque04=owner;p->x=x;p->y=y;p->vx=vx;p->vy=vy;p->repeats=-1;p->mode=1;p->timer=p->delay=2;p->active=1;p->lifetime=120;
 p->frame=p->first=p->last=owner_id==7?25:owner_id==8?54:23;p->callback=owner_id==7?0x41b770:owner_id==8?0x41a910:0x40fd70;if(vx>0)p->opaque50=2;return true;
}
bool world_enemy_shot_callback(EnemyShot *p,const EnemyShotEnvironment *e){
 if(!p)return false;
 int tx,ty,dx,dy,w,h;float gravity;
 if(p->callback==0x41b770){tx=16;ty=30;dx=5;dy=5;w=22;h=20;gravity=0.3f;}
 else if(p->callback==0x41a910){tx=14;ty=28;dx=5;dy=5;w=18;h=18;gravity=0.3f;}
 else if(p->callback==0x40fd70){tx=13;ty=8;dx=5;dy=3;w=16;h=11;gravity=0.01f;}
 else return false;
 if(p->x<0||p->y<0){p->active=0;return true;}
 uint32_t ticks;memcpy(&ticks,&p->lifetime,4);--ticks;memcpy(&p->lifetime,&ticks,4);if(p->lifetime<=0){p->active=0;return true;}
 int x=(int)p->x,y=(int)p->y;
 if(e&&e->solid&&e->solid(e->context,x+tx,y+ty)>0){unsigned property=e->property?e->property(e->context,x+tx,y+ty):0;if(!(property&2)||p->vy>0){p->active=0;return true;}}
 if(e&&e->contact&&e->contact(x+dx,y+dy,w,h,20,e->context)){p->active=0;return true;}
 if(e&&e->obstacle&&e->obstacle(e->context,x+tx,y+ty)){p->active=0;return true;}
 double vy=(double)p->vy+gravity;p->vy=(float)vy;if(vy>20)p->vy=20;p->x=(float)((double)p->vx+p->x);p->y=(float)((double)p->vy+p->y);return true;
}
