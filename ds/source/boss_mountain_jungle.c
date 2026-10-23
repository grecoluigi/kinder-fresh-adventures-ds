#include "boss_mountain_jungle.h"
#include <string.h>
static int16_t w(const GameEntity *e,int o){int16_t v;memcpy(&v,e->bytes+o,2);return v;}
static int32_t d(const GameEntity *e,int o){int32_t v;memcpy(&v,e->bytes+o,4);return v;}
static float f(const GameEntity *e,int o){float v;memcpy(&v,e->bytes+o,4);return v;}
static void sw(GameEntity *e,int o,int v){int16_t q=(int16_t)v;memcpy(e->bytes+o,&q,2);}
static void sd(GameEntity *e,int o,int32_t v){memcpy(e->bytes+o,&v,4);}
static void sf(GameEntity *e,int o,float v){memcpy(e->bytes+o,&v,4);}
static int rnd(const MountainJungleBossEnvironment *v){return v->random?v->random(v->context):0;}
static void range(GameEntity *e,const MountainJungleBossEnvironment *v,int r,int mode){sw(e,10,v->ranges[r][0]);sw(e,12,v->ranges[r][1]);sw(e,14,v->ranges[r][0]);e->bytes[22]=(uint8_t)mode;}
static bool active(const MountainJungleBossEnvironment *v){return v->audio_active&&v->audio_active(18,v->context);}
static void stop(const MountainJungleBossEnvironment *v,int ch){if(v->audio_stop)v->audio_stop(ch,v->context);}
static void play(const MountainJungleBossEnvironment *v,int ch,int sample,int repeat){if(v->audio_play)v->audio_play(ch,sample,repeat,v->context);}
static void voice(const MountainJungleBossEnvironment *v,unsigned path){if(v->audio_load&&v->audio_load(path,18,v->context)&&v->audio_volume)v->audio_volume(18,0,v->context);}
static int contacts(GameEntity *e,const MountainJungleBossEnvironment *v,int width,int flag,bool float_damage,bool float_shots){int x=w(e,2),y=w(e,4);if(float_damage){x=(int)f(e,148);y=(int)f(e,152);}if(v->contact)v->contact(x+(width==110?70:20),y+20,width,262,20,v->context);x=w(e,2);y=w(e,4);if(float_shots){x=(int)f(e,148);y=(int)f(e,152);}return v->projectiles?v->projectiles(x+(width==110?70:20),y+20,width,262,flag,v->context):0;}
static void gorilla_restart(GameEntity *e,const MountainJungleBossEnvironment *v){sw(e,98,1);sd(e,116,rnd(v)%120+60);range(e,v,1,1);play(v,4,v->gorilla_walk,255);sw(e,12,38);}
static void gorilla(GameEntity *e,const MountainJungleBossEnvironment *v){
 int s=w(e,98);
 switch(s){
 case 0:sw(e,6,255);e->bytes[28]=0;sd(e,116,0);sd(e,124,rnd(v)%180+40);sw(e,16,3);sw(e,18,3);voice(v,0x455e28);sw(e,98,50);break;
 case 1:
  contacts(e,v,110,2,false,false);if(w(e,14)==33)sw(e,10,33);
  if(d(e,124)==0){if(!active(v)){stop(v,4);sw(e,98,3);sw(e,12,47);sd(e,124,rnd(v)%200+300);int n=rnd(v)%2;if(n==0)voice(v,0x455e28);else if(n==1)voice(v,0x455e04);break;}}else sd(e,124,d(e,124)-1);
  if(!d(e,116)){sw(e,98,2);sw(e,12,47);}else sd(e,116,d(e,116)-1);break;
 case 2:
  contacts(e,v,110,2,false,false);if(w(e,14)==w(e,12)-4&&!w(e,18))stop(v,4);
  if(w(e,14)==w(e,12)&&!w(e,18)){sw(e,6,rnd(v)%4+3);range(e,v,16,1);sw(e,98,10);}break;
 case 3:contacts(e,v,110,2,false,false);if(w(e,14)==w(e,12)&&w(e,18)==1)sw(e,98,50);break;
 case 10:{
  contacts(e,v,110,2,false,false);
  if(w(e,14)==82&&w(e,18)==w(e,16)&&v->allocate_shot){EnemyShot *q=v->allocate_shot(v->context);if(q){memset(q,0,sizeof(*q));
   uint8_t *b=(uint8_t *)q;uint32_t n;float z;
#define QD(o,val) do{n=(uint32_t)(val);memcpy(b+(o),&n,4);}while(0)
#define QF(o,val) do{z=(float)(val);memcpy(b+(o),&z,4);}while(0)
   QD(0,0);QD(4,v->entity_handle);QD(36,-1);QF(12,w(e,2)-126);QF(16,w(e,4)+60);QD(40,1);QD(44,87);QD(48,87);QD(52,87);QD(56,2);QD(60,2);QD(64,1);QD(68,240);QD(96,0x40c2c0);
   if(rnd(v)%1000>500){QF(20,-6);QF(24,0);QF(28,.03f);}else{QF(20,-6);QF(24,-6);QF(28,.3f);}
#undef QD
#undef QF
  }}
  if(w(e,6)==1&&w(e,14)==w(e,12)&&!w(e,18)){sw(e,6,255);gorilla_restart(e,v);}break;
 }
 case 50:contacts(e,v,110,2,false,false);sw(e,10,47);sw(e,14,47);sw(e,6,255);sw(e,12,51);sw(e,98,51);break;
 case 51:contacts(e,v,110,2,false,false);if(!active(v))gorilla_restart(e,v);break;
 case 100:play(v,10,v->gorilla_hit,0);stop(v,18);stop(v,4);contacts(e,v,110,2,false,false);sw(e,6,255);range(e,v,17,1);sw(e,98,101);break;
 case 101:
  contacts(e,v,110,2,false,false);
  if(w(e,14)==w(e,12)&&!w(e,18)){*v->health=(int32_t)((uint32_t)*v->health-1);if(*v->health<0){*v->defeated=1;*v->score=(int32_t)((uint32_t)*v->score+10000);sw(e,98,110);range(e,v,18,1);}else{sw(e,18,1);int n=rnd(v)%4;static const unsigned paths[4]={0x455de0,0x455dbc,0x455d98,0x455d74};if(n>=0&&n<4)voice(v,paths[n]);sw(e,98,50);}}break;
 case 110:if(w(e,14)==w(e,12))sw(e,10,w(e,12));break;
 default:break;
 }
}
static void yeti_restart(GameEntity *e,const MountainJungleBossEnvironment *v,int modulus){sd(e,116,rnd(v)%modulus+(modulus==60?60:0));sw(e,98,1);range(e,v,0,1);sw(e,12,w(e,10));}
static void yeti_defeat(GameEntity *e,const MountainJungleBossEnvironment *v){*v->collapse_trigger=1;sd(e,116,120);range(e,v,18,1);sw(e,98,110);*v->score=(int32_t)((uint32_t)*v->score+10000);*v->defeated=1;}
static void yeti_lose_health(GameEntity *e,const MountainJungleBossEnvironment *v){*v->health=(int32_t)((uint32_t)*v->health-1);if(*v->health<0){yeti_defeat(e,v);return;}sw(e,18,1);int n=rnd(v)%5;static const unsigned paths[5]={0x456164,0x456140,0x45611c,0x4560f8,0x4560d4};if(n>=0&&n<5)voice(v,paths[n]);sw(e,98,50);}
static void yeti_gravity(GameEntity *e){double q=(double)f(e,160)+.6000000238418579;sf(e,160,(float)q);if(q>20)sf(e,160,20);}
static void yeti_jump(GameEntity *e,const MountainJungleBossEnvironment *v,bool hurt){
 if(hurt&&w(e,14)==69&&!w(e,18))play(v,10,v->yeti_hit_sample,0);
 if(w(e,14)==88&&!w(e,18))sf(e,160,-12);
 yeti_gravity(e);
 double pos=(double)f(e,152)+f(e,160);sf(e,152,(float)pos);
 if(pos>=d(e,128)){
  if(f(e,160)>10){play(v,9,v->yeti_land,0);if(!*v->ice_trigger_bits){static const uint32_t masks[9]={7,56,21,47,31,55,59,61,62};int n=rnd(v)%9;if(n>=0&&n<9)*v->ice_trigger_bits=masks[n];}if(*v->ice_block_state==3)*v->ice_block_state=0;}
  sf(e,160,0);sf(e,152,(float)d(e,128));
 }
 contacts(e,v,134,2,true,true);
 if(w(e,14)==90&&f(e,160)<0)sw(e,18,1);
 if(w(e,14)==91&&d(e,128)>f(e,152))sw(e,18,1);
 if(w(e,14)==w(e,12)&&!w(e,18)){if(hurt||*v->yeti_hit)yeti_lose_health(e,v);else yeti_restart(e,v,60);}
}
static void yeti(GameEntity *e,const MountainJungleBossEnvironment *v){
 switch(w(e,98)){
 case 0:
  sw(e,6,255);e->bytes[28]=0;sd(e,116,0);sf(e,148,w(e,2));sf(e,152,w(e,4));sd(e,124,rnd(v)%180+40);sw(e,16,3);sw(e,18,3);sd(e,128,w(e,4));voice(v,0x4561d0);sw(e,98,50);*v->ice_trigger_bits=0;break;
 case 1:
  if(contacts(e,v,134,1,false,false)==2){stop(v,18);e->bytes[46]=0;range(e,v,1,1);sw(e,98,100);break;}
  if(!d(e,124)){if(!active(v)){sw(e,98,50);sd(e,124,rnd(v)%200+600);int n=rnd(v)%2;if(n==0)voice(v,0x456188);else if(n==1)voice(v,0x4561ac);break;}}else sd(e,124,d(e,124)-1);
  if(!d(e,116)){stop(v,4);sd(e,116,rnd(v)%60+60);if(*v->ice_block_state==1){range(e,v,16,1);sw(e,98,3);}else{sw(e,12,95);sw(e,10,83);sw(e,14,83);*v->yeti_hit=0;sw(e,98,5);}}else sd(e,116,d(e,116)-1);break;
 case 3:
  if(contacts(e,v,134,1,false,false)==2){stop(v,18);e->bytes[46]=0;range(e,v,1,1);sw(e,98,100);break;}
  if(w(e,14)==32&&!w(e,18)&&*v->ice_block_state==1)*v->ice_block_state=2;
  if(w(e,14)==w(e,12)&&!w(e,18))yeti_restart(e,v,60);
  break;
 case 5:yeti_jump(e,v,false);break;
 case 50:contacts(e,v,134,2,false,true);sw(e,6,255);sw(e,10,38);sw(e,14,38);sw(e,12,46);sw(e,98,51);break;
 case 51:contacts(e,v,134,2,false,true);if(w(e,14)==42)sw(e,10,42);if(!active(v)){sw(e,12,52);sw(e,98,52);}break;
 case 52:contacts(e,v,134,2,false,true);if(w(e,14)==w(e,12)&&!w(e,18))yeti_restart(e,v,30);break;
 case 100:yeti_jump(e,v,true);break;
 case 110:{GameEntity *other=v->object_at?v->object_at(13,v->context):NULL;if(other)other->bytes[26]=0;yeti_gravity(e);sf(e,152,(float)((double)f(e,152)+f(e,160)));if(w(e,14)==w(e,12))sw(e,18,1);sd(e,116,(int32_t)((uint32_t)d(e,116)-1));if(d(e,116)<=0)sw(e,6,0);break;}
 default:break;
 }
 sw(e,2,(int)f(e,148));sw(e,4,(int)f(e,152));
}
bool boss_mountain_jungle_tick(GameEntity *e,const MountainJungleBossEnvironment *v){
 if(!e||!v||!v->health||!v->score||!v->defeated)return false;
 if(entity_id(e)==10){gorilla(e,v);return true;}
 if(entity_id(e)==9&&v->ice_trigger_bits&&v->ice_block_state&&v->collapse_trigger&&v->yeti_hit){yeti(e,v);return true;}
 return false;
}
bool boss_gorilla_shot_tick(EnemyShot *q,GameEntity *owner,const MountainJungleBossEnvironment *v,const EnemyShotEnvironment *s){
 if(!q||!owner||!v||!s)return false;
 int x=(int)q->x,y=(int)q->y;
 if(v->projectiles&&v->projectiles(x,y,48,48,2,v->context)&&q->vx<0){
  play(v,3,v->gorilla_reflect,0);q->vx=9;
  float gravity;memcpy(&gravity,&q->opaque1c,4);q->vy=gravity>.1?-9:-.5f;
 }
 if(q->x>=w(owner,2)+70&&q->x<w(owner,2)+180&&q->y>=w(owner,4)+20&&q->y<w(owner,4)+282){
  play(v,3,v->gorilla_reflect,0);q->active=0;if(w(owner,98)<100)sw(owner,98,100);return true;
 }
 if(q->x<0||q->y<0){q->active=0;return true;}
 q->lifetime=(int32_t)((uint32_t)q->lifetime-1);
 if(q->lifetime<=0){q->active=0;return true;}
 x=(int)q->x;y=(int)q->y;
 if(s->solid&&s->solid(s->context,x+16,y+30)>0){
  unsigned prop=s->property?s->property(s->context,x+16,y+30):0;
  if(!(prop&2)||q->vy>0){q->active=0;return true;}
 }
 if(s->contact&&s->contact(x+5,y+5,22,20,20,s->context)){q->active=0;return true;}
 float gravity;memcpy(&gravity,&q->opaque1c,4);double vy=(double)q->vy+gravity;q->vy=(float)vy;if(vy>20)q->vy=20;
 q->x=(float)((double)q->x+q->vx);q->y=(float)((double)q->y+q->vy);return true;
}
