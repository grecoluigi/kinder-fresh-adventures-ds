#include "boss_factory.h"
#include <string.h>
static int16_t r16(const GameEntity *e,unsigned o){int16_t v;memcpy(&v,e->bytes+o,2);return v;}
static int32_t r32(const GameEntity *e,unsigned o){int32_t v;memcpy(&v,e->bytes+o,4);return v;}
static void w16(GameEntity *e,unsigned o,int v){int16_t n=(int16_t)v;memcpy(e->bytes+o,&n,2);}
static void w32(GameEntity *e,unsigned o,int32_t v){memcpy(e->bytes+o,&v,4);}
static void range(GameEntity *e,int first,int last){w16(e,10,first);w16(e,12,last);w16(e,14,first);e->bytes[22]=1;}
static void voice(const FactoryBossEnvironment *v,unsigned key){if(v->voice_load&&v->voice_load(key,v->context)&&v->play)v->play(18,0,v->context);}
static void sound(const FactoryBossEnvironment *v,int channel,int sample,int repeat){if(v->sound)v->sound(channel,sample,repeat,v->context);}
static bool collisions(GameEntity *e,const FactoryBossEnvironment *v,bool pipe){
 int x=entity_x(e)+70,y=entity_y(e)+20;
 if(v->contact)v->contact(x,y,110,262,20,v->context);
 if(v->projectile)v->projectile(x,y,110,262,2,v->context);
 if(pipe&&v->pipe&&entity_y(v->pipe)>=entity_y(e)&&entity_y(v->pipe)<=entity_y(e)+19){
  float speed=-3;memcpy(v->pipe->bytes+160,&speed,4);w16(e,98,100);return true;
 }
 return false;
}
void boss_factory_shot_init(Projectile *p,uint32_t owner,float x,float y,float vx,float vy){
 memset(p,0,sizeof(*p));p->opaque04=owner;p->x=x;p->y=y;p->vx=vx;p->vy=vy;p->repeats=-1;p->mode=1;p->timer=p->delay=2;p->active=1;p->lifetime=240;p->callback=0x40d5c0;p->frame=p->first=p->last=188;
}
bool boss_factory_shot_tick(Projectile *p,const ProjectileEnvironment *t,bool (*contact)(int,int,int,int,int,void *),void *ctx){
 if(!p||p->callback!=0x40d5c0)return false;
 if(p->x<0||p->y<0){p->active=0;return true;}
 uint32_t n;memcpy(&n,&p->lifetime,4);--n;memcpy(&p->lifetime,&n,4);
 if(p->lifetime<=0){p->active=0;return true;}
 int x=(int)p->x+4,y=(int)p->y+4;
 if(t&&t->solid&&t->solid(t->context,x,y)>0){unsigned bits=t->property?t->property(t->context,x,y):0;if(!(bits&2)||p->vy>0){p->active=0;return true;}}
 if(contact&&contact(x,y,1,1,20,ctx)){p->active=0;return true;}
 p->x=(float)((double)p->x+p->vx);p->y=(float)((double)p->y+p->vy);return true;
}
bool boss_factory_tick(GameEntity *e,const FactoryBossEnvironment *v){
 if(!e||!v||entity_id(e)!=14)return false;
 int state=r16(e,98),f=r16(e,14),timer=r16(e,18);
 switch(state){
 case 0:
  w16(e,6,255);e->bytes[28]=0;w16(e,16,3);w16(e,18,3);range(e,v->intro_first,v->intro_last);voice(v,0x45608c);w16(e,98,50);w32(e,112,41);break;
 case 10:
  if(collisions(e,v,true))break;
  w16(e,6,255);w32(e,112,v->player_y<=288?2:v->player_y<=576?1:0);
  w32(e,116,(v->random?v->random(v->context):0)%10+20);w16(e,98,11);
  w16(e,10,88+17*r16(e,112));w16(e,14,r16(e,10));w16(e,12,97+17*r16(e,112));break;
 case 11:{
  if(collisions(e,v,true)){w16(e,18,1);break;}
  int aim=v->player_y<=288?2:v->player_y<=576?1:0,delta=0;
  if(aim==2){if(f>=88&&f<=104)delta=34;else if(f>=105&&f<=121)delta=17;}
  else if(aim==1){if(f>=88&&f<=104)delta=17;else if(f>=122&&f<=138)delta=-17;}
  else {if(f>=122&&f<=138)delta=-34;else if(f>=105&&f<=121)delta=-17;}
  w32(e,112,aim);w16(e,14,f+delta);w16(e,10,r16(e,10)+delta);w16(e,12,r16(e,12)+delta);f=r16(e,14);
  if(f==96+17*aim&&timer==0){w16(e,18,20);w16(e,14,97+17*aim);}
  if(r16(e,14)==95+17*aim&&r16(e,16)==r16(e,18)){
   w16(e,10,95+17*r16(e,112));
   Projectile *p=v->allocate?v->allocate(v->context):0;
   if(p){int dx=aim==1?-24:-12,dy=aim==0?157:aim==1?98:58;float vy=aim==0?10:aim==1?0:-8;
    boss_factory_shot_init(p,v->owner_handle,(float)(entity_x(e)+dx),(float)(entity_y(e)+dy),-20,vy);sound(v,6,v->shot_sample,0);}
   uint32_t n=(uint32_t)r32(e,116)-1;w32(e,116,(int32_t)n);
   if(r32(e,116)<=0){w16(e,98,12);w16(e,12,104+17*r16(e,112));w16(e,18,1);}
  }break;}
 case 12:
  if(collisions(e,v,true))break;
  if(f==r16(e,12)&&timer==0){w16(e,98,40);w16(e,10,f);}break;
 case 40:{
  if(collisions(e,v,true))break;
  int r=(v->random?v->random(v->context):0)%5;
  if(r>=0&&r<5){static const unsigned paths[]={0x456068,0x456044,0x456020,0x455ffc,0x455fd8};voice(v,paths[r]);w32(e,112,41);w16(e,98,r<2?50:60);}
  break;}
 case 41:
  if(collisions(e,v,true))break;
  w32(e,112,10);w16(e,98,60);voice(v,0x455fb4);break;
 case 50:
  if(collisions(e,v,true))break;
  w16(e,6,255);w16(e,10,172);w16(e,14,172);w16(e,12,181);w16(e,98,51);break;
 case 51:
 case 61:{
  if(collisions(e,v,true)){if(state==61&&v->stop)v->stop(9,v->context);break;}
  if(state==61){
   if(f==25&&timer==0){if(v->play)v->play(9,-10,v->context);sound(v,9,v->beam_sample,255);}
   if(f==32&&timer==0&&v->stop)v->stop(9,v->context);
  }
  int hold=state==51?178:26,end=state==51?187:37;
  if(f==hold)w16(e,10,hold);
  if(!(v->voice_active&&v->voice_active(v->context)))w16(e,12,end);
  if(f==end&&timer==0){w16(e,10,end);w16(e,98,r16(e,112));}break;}
 case 60:
  if(collisions(e,v,true))break;
  w16(e,10,19);w16(e,14,19);w16(e,6,255);w16(e,12,31);w16(e,98,61);break;
 case 100:
  collisions(e,v,false);if(v->stop)v->stop(18,v->context);range(e,v->freeze_first,v->freeze_last);sound(v,4,v->hit_sample,0);w16(e,98,101);break;
 case 101:
  collisions(e,v,false);
  if(f==r16(e,12)&&timer==0&&v->health){uint32_t n=(uint32_t)*v->health-1;*v->health=(int32_t)n;
   if(*v->health>=0){voice(v,0x455f90);w32(e,112,41);w16(e,98,50);}
   else {sound(v,9,v->death_loop_sample,255);if(v->defeated)*v->defeated=1;if(v->score)*v->score=(int32_t)((uint32_t)*v->score+10000);w16(e,98,110);range(e,v->death_first,v->death_last);}}
  break;
 case 110:
  if(f==56&&timer==0)sound(v,10,v->death_sample,0);
  if(f==69&&timer==0&&v->stop)v->stop(9,v->context);
  if(f==r16(e,12))w16(e,10,f);
  break;
 default:break;
 }
 return true;
}
