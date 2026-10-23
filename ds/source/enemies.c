#include "enemies.h"
#include <string.h>
static int16_t r16(const GameEntity *e,unsigned o){int16_t v;memcpy(&v,e->bytes+o,2);return v;}
static void w16(GameEntity *e,unsigned o,int v){uint16_t n=(uint16_t)v;memcpy(e->bytes+o,&n,2);}
static int32_t r32(const GameEntity *e,unsigned o){int32_t v;memcpy(&v,e->bytes+o,4);return v;}
static void w32(GameEntity *e,unsigned o,uint32_t v){memcpy(e->bytes+o,&v,4);}
static float rf(const GameEntity *e,unsigned o){float v;memcpy(&v,e->bytes+o,4);return v;}
static void wf(GameEntity *e,unsigned o,float v){memcpy(e->bytes+o,&v,4);}
static void range(GameEntity *e,const EnemyEnvironment *env,unsigned n){w16(e,10,env->ranges[n][0]);w16(e,12,env->ranges[n][1]);w16(e,14,env->ranges[n][0]);e->bytes[22]=1;}
static void turn(GameEntity *e,unsigned mask){
 if(e->bytes[41])--e->bytes[41];else {e->bytes[41]=e->bytes[40];e->bytes[39]^=mask;if(e->bytes[44])e->bytes[43]^=1;}
}
static void move_axis(GameEntity *e,unsigned pos,unsigned bound,bool positive,unsigned turn_mask){
 int p=r16(e,pos),b=r16(e,bound),speed=e->bytes[29];
 if(positive?p<b:p>b){int d=positive?speed:-speed;if(positive?p+d>b:p+d<b)d=b-p;w16(e,pos,p+d);}
 p=r16(e,pos);if(positive?p>=b:p<=b)turn(e,turn_mask);
}
static void move(GameEntity *e){
 if(!e->bytes[28])return;
 unsigned m=e->bytes[39];
 if(m==1||m==5||m==9){e->bytes[43]=0;move_axis(e,2,31,false,3);}
 if(m==2||m==6||m==10){e->bytes[43]=1;move_axis(e,2,35,true,3);}
 if(m==4||m==5||m==6)move_axis(e,4,33,false,12);
 if(m==8||m==9||m==10)move_axis(e,4,37,true,12);
}
bool enemy_snake_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=4)return false;
 int state=r16(e,98),x=entity_x(e),y=entity_y(e);
 if(state==0){w16(e,6,255);e->bytes[28]=0;w16(e,98,1);w16(e,16,1);w16(e,18,1);range(e,env,0);}
 else if(state==1){
  if(env->contact)env->contact(x+5,y+5,25,130,20,env->context);
  if(env->projectile&&env->projectile(x,y,35,140,1,env->context)){
   uint32_t score;memcpy(&score,&g->score,4);score+=100;memcpy(&g->score,&score,4);
   if(env->popup)env->popup(x-13,y+30,100,env->context);
   e->bytes[28]=0;e->bytes[47]=1;range(e,env,17);w16(e,16,1);w16(e,18,1);w16(e,6,1);w16(e,98,100);
   if(env->sound)env->sound(3,env->hit_sound,env->context);
  }
 }else if(state==100&&r16(e,14)==r16(e,12)){
  e->bytes[184]=1;wf(e,148,(float)x);wf(e,152,(float)y);w16(e,18,1);w16(e,98,101);wf(e,156,e->bytes[43]?1.0f:-1.0f);wf(e,160,-12.0f);w32(e,116,120);
  if(env->sound)env->sound(4,env->fall_sound,env->context);
 }else if(state==101){
  float vy=rf(e,160)+0.6f;if(vy>20.0f)vy=20.0f;wf(e,160,vy);
  float xx=rf(e,148)+rf(e,156),yy=rf(e,152)+vy;wf(e,148,xx);wf(e,152,yy);w16(e,2,(int)xx);w16(e,4,(int)yy);
  uint32_t timer=(uint32_t)r32(e,116)-1;w32(e,116,timer);if((int32_t)timer<=0)w16(e,98,200);
  if(r16(e,14)==r16(e,12))w16(e,18,1);
 }
 move(e);return true;
}

static void decrement_if_nonzero(GameEntity *e,unsigned o){int32_t n=r32(e,o);if(n)w32(e,o,(uint32_t)n-1);}
static int random_value(const EnemyEnvironment *env){return env->random?env->random(env->context):0;}
static void patrol(GameEntity *e){
 if(!e->bytes[28])return;
 double x=(double)rf(e,148)+rf(e,156),y=(double)rf(e,152)+rf(e,160);float vx=rf(e,156);
 wf(e,148,x);wf(e,152,y);
 if(vx>0){float limit=(float)r16(e,35);if(x>=limit){x=limit;wf(e,148,x);wf(e,156,-vx);}}
 else {float limit=(float)r16(e,31);if(x<=limit){x=limit;wf(e,148,x);wf(e,156,-vx);}}
 w16(e,2,(int)rf(e,148));w16(e,4,(int)rf(e,152));e->bytes[43]=rf(e,156)>0?1:0;
}
static void freeze_hit(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env,int popup_x){
 uint32_t score;memcpy(&score,&g->score,4);score+=100;memcpy(&g->score,&score,4);
 if(env->popup)env->popup(entity_x(e)+popup_x,entity_y(e)+30,100,env->context);
 e->bytes[28]=0;e->bytes[47]=1;range(e,env,17);w16(e,16,1);w16(e,18,1);w16(e,6,1);w16(e,98,100);
 if(env->sound)env->sound(3,env->hit_sound,env->context);
}
static void falling_begin(GameEntity *e,const EnemyEnvironment *env){
 e->bytes[184]=1;wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));w16(e,18,1);w16(e,98,101);wf(e,156,e->bytes[43]?1.0f:-1.0f);wf(e,160,-12.0f);w32(e,116,120);
 if(env->sound)env->sound(4,env->fall_sound,env->context);
}
static void falling_tick(GameEntity *e){
 float vy=rf(e,160)+0.6f;if(vy>20.0f)vy=20.0f;wf(e,160,vy);
 double x=(double)rf(e,148)+rf(e,156),y=(double)rf(e,152)+rf(e,160);wf(e,148,(float)x);wf(e,152,(float)y);w16(e,2,(int)x);w16(e,4,(int)rf(e,152));
 uint32_t n=(uint32_t)r32(e,116)-1;w32(e,116,n);if((int32_t)n<=0)w16(e,98,200);if(r16(e,14)==r16(e,12))w16(e,18,1);
}
bool enemy_kong_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=5)return false;
 int state=r16(e,98);
 if(state==0){w16(e,6,255);wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));e->bytes[28]=1;w16(e,98,1);wf(e,156,3.0f);wf(e,160,0);w32(e,116,0);w32(e,120,0);w16(e,16,3);w16(e,18,3);range(e,env,0);return true;}
 bool contact=false;
 if(state==1){
  decrement_if_nonzero(e,116);if(r16(e,14)==3)w16(e,10,3);
  if(!r32(e,120)){w16(e,6,1);int n=random_value(env)%60;w16(e,98,2);w16(e,12,15);w32(e,120,(uint32_t)(n+60));}else decrement_if_nonzero(e,120);
  patrol(e);contact=true;
 }else if(state==2){
  decrement_if_nonzero(e,116);
  if(r16(e,14)==r16(e,12)){
   w16(e,18,1);int x=entity_x(e),y=entity_y(e),px=env->player_x,py=env->player_y;
   int distance=px-x-107;if(distance<0)distance=-distance;
   if((e->bytes[43]?px>x+107:px<x+107)&&distance<600&&py>y+19&&py<y+419&&!r32(e,116)&&!(e->bytes[42]&1)){
    range(e,env,16);w16(e,98,10);w16(e,6,random_value(env)%10+1);return true;
   }
  }
  patrol(e);if(r16(e,14)==15)e->bytes[28]=0;
  if(!r32(e,120)){e->bytes[28]=1;w16(e,6,255);int n=random_value(env)%120;w16(e,98,1);w16(e,10,0);w16(e,14,0);w16(e,12,12);w32(e,120,(uint32_t)(n+120));}else decrement_if_nonzero(e,120);
  contact=true;
 }else if(state==10){
  if(r16(e,14)==26&&r16(e,18)==r16(e,16)&&env->allocate&&env->allocate(env->context)){
   if(env->sound)env->sound(10,env->throw_sound,env->context);
   float x=(float)(entity_x(e)-72),y=(float)(entity_y(e)+76),vx=-11.0f;
   if(e->bytes[43]){x+=330.0f;vx=11.0f;}
   if(env->spawn)env->spawn(e,x,y,vx,-3.0f,env->context);
  }
  if(r16(e,14)==r16(e,12)&&r16(e,18)==0&&r16(e,6)==1){w32(e,116,120);w16(e,18,1);w16(e,98,2);w16(e,10,3);w16(e,12,15);w16(e,14,15);}
  contact=true;
 }else if(state==100){if(r16(e,14)==r16(e,12))falling_begin(e,env);}
 else if(state==101)falling_tick(e);
 if(contact){int x=entity_x(e)+40,y=entity_y(e)+20;if(env->contact)env->contact(x,y,120,190,20,env->context);if(env->projectile&&env->projectile(x,y,120,190,1,env->context))freeze_hit(e,g,env,46);}
 return true;
}
bool enemy_parrot_callback(GameEntity *e,EntityGlobals *g,const EnemyEnvironment *env){
 if(!e||!g||!env||entity_id(e)!=3)return false;
 int state=r16(e,98);bool contact=false;
 if(state==0){w16(e,6,255);e->bytes[28]=1;wf(e,148,(float)entity_x(e));wf(e,152,(float)entity_y(e));w16(e,98,1);wf(e,156,2.0f);wf(e,160,0);w32(e,116,0);w16(e,16,1);w16(e,18,1);range(e,env,0);return true;}
 if(state==1){
  patrol(e);decrement_if_nonzero(e,116);
  int x=entity_x(e),y=entity_y(e),px=env->player_x,py=env->player_y,d=px-x-40;if(d<0)d=-d;
  if((e->bytes[43]?px>x+40:px<x+40)&&d<180&&py>y+300&&py<y+500&&!r32(e,116)&&px>=r16(e,31)&&px<=r16(e,35)&&!(e->bytes[42]&1)){
   wf(e,160,12.0f);w16(e,14,r16(e,14)+9);w16(e,10,r16(e,10)+9);w16(e,12,r16(e,12)+9);w16(e,98,10);
   if(env->sound)env->sound(10,env->throw_sound,env->context);
  }
  contact=true;
 }else if(state==10){
  if(e->bytes[28]){
   double vy=(double)rf(e,160)-0.3f;if(vy<=-12.0f)vy=-12.0f;wf(e,160,(float)vy);
   double x=(double)rf(e,148)+rf(e,156),y=(double)rf(e,152)+rf(e,160);wf(e,148,(float)x);wf(e,152,(float)y);
   if(y<(float)r16(e,33)){y=(float)r16(e,33);wf(e,152,y);w32(e,116,120);w16(e,14,r16(e,14)-9);w16(e,10,r16(e,10)-9);w16(e,12,r16(e,12)-9);wf(e,160,0);w16(e,98,1);}
   if(rf(e,156)>0){if(x>=(float)r16(e,35)){x=(float)r16(e,35);wf(e,148,x);}}
   else if(x<=(float)r16(e,31)){x=(float)r16(e,31);wf(e,148,x);}
   w16(e,2,(int)rf(e,148));w16(e,4,(int)rf(e,152));e->bytes[43]=rf(e,156)>0?1:0;
  }
  contact=true;
 }else if(state==100){if(r16(e,14)==r16(e,12))falling_begin(e,env);}
 else if(state==101)falling_tick(e);
 if(contact){int x=entity_x(e),y=entity_y(e);if(env->contact)env->contact(x,y,60,100,20,env->context);
  if(env->projectile&&env->projectile(x,y,60,120,1,env->context)){
   uint32_t score;memcpy(&score,&g->score,4);score+=100;memcpy(&g->score,&score,4);
   if(env->popup)env->popup(x+10,y+60,100,env->context);
   e->bytes[28]=0;e->bytes[47]=1;range(e,env,17);w16(e,16,1);w16(e,18,1);w16(e,6,1);w16(e,98,100);if(env->sound)env->sound(3,env->hit_sound,env->context);
  }
 }
 return true;
}
