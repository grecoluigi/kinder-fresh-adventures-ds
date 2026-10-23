#include "boss_valley.h"
#include <string.h>
static int16_t r16(const GameEntity *e,unsigned a){int16_t v;memcpy(&v,e->bytes+a,2);return v;}
static int32_t r32(const GameEntity *e,unsigned a){int32_t v;memcpy(&v,e->bytes+a,4);return v;}
static float rf(const GameEntity *e,unsigned a){float v;memcpy(&v,e->bytes+a,4);return v;}
static void w16(GameEntity *e,unsigned a,int v){uint16_t n=(uint16_t)v;memcpy(e->bytes+a,&n,2);}
static void w32(GameEntity *e,unsigned a,int32_t v){memcpy(e->bytes+a,&v,4);}
static void wf(GameEntity *e,unsigned a,float v){memcpy(e->bytes+a,&v,4);}
static int32_t add(int32_t a,int32_t b){uint32_t x=(uint32_t)a+(uint32_t)b;memcpy(&a,&x,4);return a;}
static int32_t call(const BossValleyEnvironment *v,uint32_t a,unsigned n,const int32_t *p){return v->service?v->service(a,p,n,v->context):0;}
static int32_t one(const BossValleyEnvironment *v,uint32_t a,int32_t x){return call(v,a,1,&x);}
static void sound(const BossValleyEnvironment *v,int ch,int s){int32_t a[3]={ch,s,0};call(v,0x422b60,3,a);}
static void range(GameEntity *e,const BossValleyEnvironment *v,unsigned i,unsigned mode){int32_t a[2]={(int)i,(int)mode};call(v,0x430b20,2,a);w16(e,10,v->ranges[i][0]);w16(e,12,v->ranges[i][1]);e->bytes[22]=(uint8_t)mode;w16(e,14,v->ranges[i][mode==2]);}
static void decrement(GameEntity *e,unsigned at){int32_t n=r32(e,at);if(n)w32(e,at,add(n,-1));}
static int random_value(const BossValleyEnvironment *v){return call(v,0x4395b0,0,NULL);}
static int collision(GameEntity *e,const BossValleyEnvironment *v,uint32_t a,int x,int y,int w,int h,int mode){int32_t p[5]={r16(e,2)+x,r16(e,4)+y,w,h,mode};return call(v,a,5,p);}
static void popup(GameEntity *e,BossValleyGlobals *g,const BossValleyEnvironment *v){g->score=add(g->score,100);int32_t p[3]={r16(e,2),r16(e,4)+30,100};call(v,0x412e20,3,p);}
static void bear_hit(GameEntity *e,const BossValleyEnvironment *v){e->bytes[28]=0;e->bytes[47]=1;range(e,v,17,1);w16(e,16,1);w16(e,18,1);w16(e,6,1);w16(e,98,100);sound(v,3,v->hit_sound);}
static void patrol(GameEntity *e){
 if(!e->bytes[28])return;
 double x=(double)rf(e,148)+(double)rf(e,156),y=(double)rf(e,152)+(double)rf(e,160);wf(e,148,(float)x);wf(e,152,(float)y);
 float vx=rf(e,156);int bound=r16(e,vx>0?35:31);
 if(vx>0?x>=bound:x<=bound){wf(e,148,(float)bound);wf(e,156,-vx);}
 /* Native conversion reads clamped stored x, not the x87 temporary. */
 w16(e,2,(int)rf(e,148));w16(e,4,(int)(float)y);e->bytes[43]=rf(e,156)>0;
}
static void shot_word(BossValleyShot *s,unsigned at,uint32_t value){memcpy(s->bytes+at,&value,4);}
static void shot_float(BossValleyShot *s,unsigned at,float value){memcpy(s->bytes+at,&value,4);}
static BossValleyShot *spawn(const BossValleyEnvironment *v,float x,float y){
 if(!call(v,0x410fb0,0,NULL)||!v->shot)return NULL;
 int32_t args[3]={0,0,0};memcpy(args+1,&x,4);memcpy(args+2,&y,4);call(v,0x40adc0,3,args);
 BossValleyShot *s=v->shot;memset(s,0,sizeof(*s));shot_float(s,12,x);shot_float(s,16,y);shot_word(s,36,0xffffffff);shot_word(s,40,1);shot_word(s,56,2);shot_word(s,60,2);return s;
}
bool boss_valley_bear_tick(GameEntity *e,BossValleyGlobals *g,const BossValleyEnvironment *v){
 if(!e||!g||!v||entity_id(e)!=15)return false;
 int state=r16(e,98);
 if(state==0){w16(e,6,255);wf(e,148,(float)r16(e,2));wf(e,152,(float)r16(e,4));e->bytes[28]=1;w16(e,98,1);wf(e,156,3);wf(e,160,0);w32(e,116,0);w32(e,120,0);w16(e,16,3);w16(e,18,3);range(e,v,0,1);w16(e,10,62);w16(e,12,62);w16(e,14,62);return true;}
 if(state==100){if(r16(e,14)==r16(e,12)){wf(e,148,(float)r16(e,2));wf(e,152,(float)r16(e,4));e->bytes[184]=1;w16(e,18,1);w16(e,98,101);wf(e,156,e->bytes[43]?1:-1);wf(e,160,-12);w32(e,116,120);sound(v,4,v->fall_sound);}return true;}
 if(state==101){double vy=(double)rf(e,160)+(double)0.6f;wf(e,160,(float)vy);if(vy>20)wf(e,160,20);double x=(double)rf(e,148)+rf(e,156),y=(double)rf(e,152)+rf(e,160);wf(e,148,(float)x);wf(e,152,(float)y);w16(e,2,(int)x);w16(e,4,(int)(float)y);w32(e,116,add(r32(e,116),-1));if(r32(e,116)<=0)w16(e,98,200);if(r16(e,14)==r16(e,12))w16(e,18,1);return true;}
 if(state==1){decrement(e,116);if(r16(e,14)==65)w16(e,10,65);if(!r32(e,120)){w16(e,6,1);w16(e,98,2);w16(e,12,77);w32(e,120,random_value(v)%60+60);}else decrement(e,120);patrol(e);collision(e,v,0x41a3e0,10,10,68,205,20);if(collision(e,v,0x41a5e0,10,10,68,205,1)){popup(e,g,v);bear_hit(e,v);}return true;}
 if(state==2||state==3){collision(e,v,0x41a3e0,10,10,68,205,20);if(collision(e,v,0x41a5e0,10,10,68,205,1)){if(state==3)one(v,0x422e04,9);popup(e,g,v);bear_hit(e,v);return true;}decrement(e,116);
  if(state==2){if(r16(e,14)==r16(e,12)){w16(e,18,1);call(v,0x41a8c0,0,NULL);int x=r16(e,2),y=r16(e,4),px=v->player_x,py=v->player_y,d=px-x-107;if(d<0)d=-d;
    if((e->bytes[43]?px>x+107:px<x+107)&&d<600&&py>y+19&&py<y+419&&!r32(e,116)&&!(e->bytes[42]&1)){range(e,v,16,1);w16(e,98,10);w16(e,6,random_value(v)%10+1);return true;}}
   patrol(e);if(r16(e,14)==77){e->bytes[28]=0;w16(e,6,255);range(e,v,1,1);w16(e,98,3);if(!one(v,0x4231e5,9))sound(v,9,v->bear_idle_sound);}
  }else if(r16(e,14)==r16(e,12)&&!r16(e,18)&&!one(v,0x4231e5,9)){e->bytes[28]=1;w16(e,98,1);w16(e,10,62);w16(e,14,62);w16(e,12,74);w32(e,120,random_value(v)%120+120);}return true;
 }
 if(state==10){if(r16(e,14)==47&&r16(e,18)==r16(e,16)){
   /* Original sound occurs after successfulallocation and beforeinitializer. */
   if(call(v,0x410fb0,0,NULL)&&v->shot){sound(v,10,v->bear_throw_sound);float x=(float)(r16(e,2)-72),y=(float)(r16(e,4)+76);int32_t a[3]={0,0,0};memcpy(a+1,&x,4);memcpy(a+2,&y,4);call(v,0x40adc0,3,a);BossValleyShot *s=v->shot;memset(s,0,sizeof(*s));shot_float(s,12,x);shot_float(s,16,y);shot_word(s,36,0xffffffff);shot_word(s,40,1);shot_word(s,56,2);shot_word(s,60,2);shot_word(s,64,1);shot_word(s,68,120);shot_float(s,24,-3);shot_word(s,96,0x413b70);shot_word(s,44,53);shot_word(s,48,53);shot_word(s,52,53);shot_word(s,4,v->owner_handle);if(e->bytes[43]){shot_float(s,12,x+245);shot_word(s,80,2);shot_float(s,20,11);}else shot_float(s,20,-11);}}
  if(r16(e,14)==r16(e,12)&&!r16(e,18)&&r16(e,6)==1){w32(e,116,120);w16(e,18,1);w16(e,98,2);w16(e,10,65);w16(e,12,77);w16(e,14,77);}collision(e,v,0x41a3e0,10,10,68,205,20);if(collision(e,v,0x41a5e0,10,10,68,205,1)){popup(e,g,v);bear_hit(e,v);}return true;
 }
 return true;
}
static void voice(const BossValleyEnvironment *v,uint32_t address){int32_t p[4]={(int32_t)address,18,0,0};if(call(v,0x4243b1,4,p)!=-1){int32_t a[2]={18,0};call(v,0x42339e,2,a);}}
static void octopus_attack(GameEntity *e,const BossValleyEnvironment *v){range(e,v,16,1);w16(e,98,2);w32(e,116,random_value(v)%30+50);w32(e,120,0);w32(e,124,random_value(v)%2);}
static void octopus_contacts(GameEntity *e,const BossValleyEnvironment *v,int mode){collision(e,v,0x41a3e0,30,10,170,175,20);if(collision(e,v,0x41a5e0,30,10,170,175,mode))w32(e,144,1);}
bool boss_valley_octopus_tick(GameEntity *e,BossValleyGlobals *g,const BossValleyEnvironment *v){
 if(!e||!g||!v||entity_id(e)!=18)return false;
 int state=r16(e,98);
 if(state==0){w16(e,6,255);e->bytes[28]=0;w16(e,16,3);w16(e,18,3);voice(v,0x455f6c);range(e,v,3,1);w16(e,98,50);w32(e,144,0);return true;}
 if(state==1){collision(e,v,0x41a3e0,30,10,170,175,20);
  if(collision(e,v,0x41a5e0,30,10,170,175,1)){one(v,0x422e04,9);w32(e,144,0);w16(e,98,101);range(e,v,17,1);voice(v,0x455f48);return true;}
  if(!one(v,0x4231e5,9)&&r32(e,140)){e->bytes[22]=2;if(!r16(e,14)&&!r16(e,18)){one(v,0x422e04,9);octopus_attack(e,v);return true;}}
  int frame=r16(e,14);
  if(frame==7&&!r16(e,18)&&e->bytes[22]==1){sound(v,9,v->octopus_sound);w32(e,140,1);}
  if(frame==10&&!r16(e,18))e->bytes[22]=2;
  if(frame==8&&!r16(e,18)&&one(v,0x4231e5,9))e->bytes[22]=1;
  return true;
 }
 if(state==2){octopus_contacts(e,v,2);int32_t timer=r32(e,116);
  if(timer){w32(e,116,add(timer,-1));if(r16(e,14)==40&&!r16(e,18)&&e->bytes[22]==1)sound(v,9,v->octopus_throw_sound);
   if(r16(e,14)==41){w16(e,18,1);if(!r32(e,120)){w32(e,120,1);BossValleyShot *s=spawn(v,(float)(r16(e,2)-40),(float)(r16(e,4)+60));if(!s)return true;shot_word(s,64,1);shot_word(s,68,240);shot_float(s,20,-10);if(r32(e,124)==0){shot_float(s,24,-6);shot_float(s,28,0.2f);}else if(r32(e,124)==1){shot_float(s,24,0);shot_float(s,28,0.07f);}shot_word(s,96,0x40cc60);shot_word(s,44,50);shot_word(s,48,50);shot_word(s,52,50);shot_word(s,4,v->owner_handle);}else decrement(e,120);}return true;
  }
  e->bytes[22]=2;if(r16(e,14)!=36||r16(e,18))return true;
  if(!r32(e,144)){int n=random_value(v)%2;if(n==0)voice(v,0x455f24);else if(n==1)voice(v,0x455f00);}
  else {int n=random_value(v)%3;if(n==0)voice(v,0x455eb8);else if(n==1)voice(v,0x455edc);else if(n==2)voice(v,0x455f00);}
  range(e,v,3,1);w16(e,98,50);w32(e,144,0);return true;
 }
 if(state==50){octopus_contacts(e,v,2);w16(e,6,255);w16(e,10,42);w16(e,12,49);w16(e,14,42);w16(e,98,51);return true;}
 if(state==51){octopus_contacts(e,v,2);if(r16(e,14)==46)w16(e,10,46);if(!one(v,0x4231e5,18)){w16(e,10,42);e->bytes[22]=2;w16(e,98,52);}return true;}
 if(state==52){octopus_contacts(e,v,2);if(r16(e,14)!=42||r16(e,18))return true;
  if(random_value(v)%100<50){w32(e,140,0);w16(e,98,1);w32(e,116,random_value(v)%120+120);range(e,v,0,1);}else octopus_attack(e,v);return true;
 }
 if(state==101){octopus_contacts(e,v,2);if(r16(e,14)!=r16(e,12)||r16(e,18))return true;
  g->boss_energy=add(g->boss_energy,-1);
  if(g->boss_energy>=0){w16(e,18,1);int n=random_value(v)%2;if(n==0)voice(v,0x455e70);else if(n==1)voice(v,0x455e94);w16(e,98,50);}
  else {g->completed=1;g->score=add(g->score,10000);w16(e,98,110);range(e,v,18,1);voice(v,0x455e4c);}return true;
 }
 if(state==110){if(r16(e,14)==r16(e,12))w16(e,10,r16(e,12));return true;}
 return true;
}
static uint32_t shot_u32(const BossValleyShot *s,unsigned at){uint32_t v;memcpy(&v,s->bytes+at,4);return v;}
static float shot_f32(const BossValleyShot *s,unsigned at){float v;memcpy(&v,s->bytes+at,4);return v;}
void boss_valley_shot_tick(BossValleyShot *s,const BossValleyEnvironment *v){
 uint32_t callback=shot_u32(s,96);if(callback!=0x413b70&&callback!=0x40cc60)return;
 bool bear=callback==0x413b70;float x=shot_f32(s,12),y=shot_f32(s,16);if(x<0||y<0){shot_word(s,64,0);return;}
 int32_t life=(int32_t)shot_u32(s,68);life=add(life,-1);shot_word(s,68,(uint32_t)life);if(life<=0){shot_word(s,64,0);return;}
 int32_t tile[3]={2,(int)x+(bear?10:4),(int)y+(bear?50:4)};
 if(call(v,0x434180,3,tile)>0){if(!(call(v,0x434200,3,tile)&2)||shot_f32(s,24)>0){shot_word(s,64,0);return;}}
 int32_t contact[5]={(int)x+(bear?5:2),(int)y+(bear?10:2),bear?10:4,bear?30:4,20};
 if(call(v,0x41a3e0,5,contact)){shot_word(s,64,0);return;}
 if(bear){int32_t obstacle[2]={(int)x+10,(int)y+50};if(call(v,0x412bf0,2,obstacle)){shot_word(s,64,0);return;}}
 double vy=(double)shot_f32(s,24)+(bear?(double)0.3f:(double)shot_f32(s,28));shot_float(s,24,(float)vy);if(vy>20)shot_float(s,24,20);
 shot_float(s,12,(float)((double)x+shot_f32(s,20)));shot_float(s,16,(float)((double)y+shot_f32(s,24)));
}
