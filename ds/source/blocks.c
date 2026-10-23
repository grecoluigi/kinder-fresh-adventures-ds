#include "blocks.h"
#include <string.h>
static int16_t s16(const GameEntity *e,int o){int16_t v;memcpy(&v,e->bytes+o,2);return v;}
static int32_t s32(const GameEntity *e,int o){int32_t v;memcpy(&v,e->bytes+o,4);return v;}
static float fl(const GameEntity *e,int o){float v;memcpy(&v,e->bytes+o,4);return v;}
static void w16(GameEntity *e,int o,int v){uint16_t n=(uint16_t)v;memcpy(e->bytes+o,&n,2);}
static void w32(GameEntity *e,int o,int32_t v){memcpy(e->bytes+o,&v,4);}
static void wf(GameEntity *e,int o,float v){memcpy(e->bytes+o,&v,4);}
static void range(GameEntity *e,const BlockEnvironment *env){w16(e,10,env->first);w16(e,12,env->last);e->bytes[22]=1;w16(e,14,env->first);}
static bool scan(const BlockEnvironment *env,int x,int y,int length,bool vertical){
 if(!env->tile)return false;
 if(env->tile(2,x+(vertical?0:length-1),y+(vertical?length-1:0),env->context)>0)return true;
 for(int i=0;i<length/32;i++){if(env->tile(2,x,y,env->context)>0)return true;if(vertical)y+=32;else x+=32;}
 return false;
}
bool block_physical_tick(GameEntity *e,const BlockEnvironment *env){
 if(!e||!env)return false;
 unsigned id=entity_id(e);if(id!=76&&id!=78&&id!=86&&id!=87)return false;
 int state=s16(e,98);
 if(state==0){w16(e,6,255);e->bytes[28]=0;w16(e,98,1);w32(e,116,0);wf(e,148,s16(e,2));wf(e,152,s16(e,4));range(e,env);return true;}
 if(state!=1)return true;
 float old_vx=fl(e,156);
 double vx=(double)old_vx+(old_vx>0?-(double)0.2f:(double)0.2f);
 wf(e,156,(float)vx);if(old_vx>0?vx<=0:vx>0)wf(e,156,0);
 double vy=(double)fl(e,160)+2.0;wf(e,160,(float)vy);if(vy>20)wf(e,160,20);
 int y=(int)fl(e,152),end=(int)((double)fl(e,152)+fl(e,160));
 for(int p=y;p<=end;p++){
  if(scan(env,(int)fl(e,148),p+env->height,env->width-1,false)&&s32(e,116)<32){wf(e,160,0);wf(e,152,(float)p);break;}
  w32(e,116,(int32_t)((uint32_t)s32(e,116)+1));
 }
 if(s32(e,116)>1000)w16(e,6,0);
 if(fl(e,160)!=0){wf(e,156,0);wf(e,152,(float)((double)fl(e,152)+fl(e,160)));}
 int p=(int)fl(e,148);end=(int)((double)fl(e,148)+fl(e,156));
 if(fl(e,156)>0){for(;p<=end;p++)if(scan(env,p+env->width,(int)fl(e,152),env->height-1,true)){wf(e,156,0);wf(e,148,(float)p);break;}}
 else {int last=p;for(;p>=end;){--p;if(scan(env,p,(int)fl(e,152),env->height-1,true)){wf(e,156,0);wf(e,148,(float)last);break;}last=p;}}
 if(fl(e,156)!=0)wf(e,148,(float)((double)fl(e,148)+fl(e,156)));
 e->bytes[184]=(fl(e,156)!=0||fl(e,160)!=0);
 w16(e,2,(int)fl(e,148));w16(e,4,(int)fl(e,152));
 if(env->projectiles)env->projectiles(s16(e,2),s16(e,4),env->width,env->height,1,env->context);
 return true;
}
bool block_switch_tick(GameEntity *e,const BlockEnvironment *env){
 if(!e||!env||entity_id(e)!=83)return false;
 switch(s16(e,98)){
 case 0:w16(e,6,255);e->bytes[184]=1;e->bytes[28]=0;w16(e,98,1);range(e,env);w16(e,12,s16(e,10));break;
 case 1:if(fl(e,156)!=0){w16(e,98,2);range(e,env);if(env->sound)env->sound(2,env->switch_sample,0,env->context);}break;
 case 2:if(s16(e,14)==s16(e,12)){w16(e,98,3);w16(e,10,s16(e,12));if(env->switch_flags)env->switch_flags[e->bytes[42]]=1;}break;
 case 3:if(env->switch_flags&&!env->switch_flags[e->bytes[42]]){w16(e,98,0);wf(e,156,0);}break;
 }
 return true;
}
static void axis(GameEntity *e,bool vertical,bool positive,bool diagonal,void (*event)(GameEntity*,int,void*),void *context){
 int o=vertical?4:2,bound=s16(e,vertical?(positive?37:33):(positive?35:31)),pos=s16(e,o),speed=e->bytes[29];
 if(positive?pos<bound:pos>bound){pos+=positive?speed:-speed;w16(e,o,pos);if(positive?pos>bound:pos<bound)w16(e,o,bound);}
 if(positive?s16(e,o)>=bound:s16(e,o)<=bound){
  if(e->bytes[41])--e->bytes[41];else{
   e->bytes[41]=e->bytes[40];unsigned old=positive?(vertical?8:2):(vertical?4:1),next=positive?(vertical?4:1):(vertical?8:2);
   e->bytes[39]=diagonal?(e->bytes[39]&~old)|next:next;
   if(!vertical){if(e->bytes[44])e->bytes[43]^=1;if(event)event(e,positive?16:32,context);}
  }
 }
}
void block_default_movement(GameEntity *e,void (*event)(GameEntity*,int,void*),void *context){
 if(!e||!e->bytes[28])return;
 unsigned d=e->bytes[39];switch(d){
 case 1:case 2:axis(e,false,d==2,false,event,context);break;
 case 4:case 8:axis(e,true,d==8,false,event,context);break;
 case 5:case 6:case 9:case 10:axis(e,false,(d&2)!=0,true,event,context);axis(e,true,(d&8)!=0,true,event,context);break;
 }
}
