#include "world_objects.h"
#include <string.h>
#include <stdlib.h>
static int16_t s16(const GameEntity *e,int o){int16_t v;memcpy(&v,e->bytes+o,2);return v;}
static int32_t s32(const GameEntity *e,int o){int32_t v;memcpy(&v,e->bytes+o,4);return v;}
static float fl(const GameEntity *e,int o){float v;memcpy(&v,e->bytes+o,4);return v;}
static void w16(GameEntity *e,int o,int v){uint16_t n=(uint16_t)v;memcpy(e->bytes+o,&n,2);}
static void w32(GameEntity *e,int o,int32_t v){memcpy(e->bytes+o,&v,4);}
static void wf(GameEntity *e,int o,float v){memcpy(e->bytes+o,&v,4);}
static int random_value(const WorldObjectEnvironment *v){return v->random?v->random(v->context):0;}
static int decrement(GameEntity *e,int offset){int32_t v=(int32_t)((uint32_t)s32(e,offset)-1);w32(e,offset,v);return v;}
static void range(GameEntity *e,const WorldObjectEnvironment *v,bool frozen){w16(e,10,frozen?v->frozen_first:v->first);w16(e,12,frozen?v->frozen_last:v->last);w16(e,14,s16(e,10));e->bytes[22]=1;}
static void init_anim(GameEntity *e,const WorldObjectEnvironment *v){w16(e,6,255);w16(e,98,1);w16(e,16,1);w16(e,18,1);range(e,v,false);}
static void damage(GameEntity *e,const WorldObjectEnvironment *v){if(v->damage)v->damage(s16(e,2)+5,s16(e,4)+5,v->width-10,v->width-10,20,v->context);}
static void fall(GameEntity *e,const WorldObjectEnvironment *v){
 double vy=(double)fl(e,160)+(double)0.6f;wf(e,160,(float)vy);if(vy>20)wf(e,160,20);
 /* x87 keeps the full addition in ST while the field stores float. */
 double x=(double)fl(e,156)+fl(e,148);wf(e,148,(float)x);
 float y=(float)((double)fl(e,160)+fl(e,152));wf(e,152,y);
 w16(e,2,(int)x);w16(e,4,(int)y);damage(e,v);
}
static bool tile_at_feet(GameEntity *e,const WorldObjectEnvironment *v){return v->tile&&v->tile(2,s16(e,2)+v->width/2,s16(e,4)+v->height,v->context)>0;}
static void falling_spike(GameEntity *e,const WorldObjectEnvironment *v,bool trigger){
 int state=s16(e,98);
 switch(state){
 case 0:w16(e,6,255);e->bytes[28]=0;w16(e,98,1);w32(e,116,s16(e,2));w32(e,120,s16(e,4));range(e,v,false);break;
 case 1:damage(e,v);if(trigger){uint32_t bit=1u<<(e->bytes[42]&31);if(v->ice_trigger_bits&&(*v->ice_trigger_bits&bit)){*v->ice_trigger_bits&=~bit;w16(e,98,2);w32(e,124,random_value(v)%60+60);}}
 else if(v->player_y>s16(e,4)+v->height+100&&v->player_y<s16(e,4)+v->height+400){int d=abs(v->player_x-v->width/2-s16(e,2));if(d>e->bytes[42]+150){w16(e,2,s16(e,116));w16(e,4,s16(e,120));}else if(d>e->bytes[42]+20){w16(e,2,s16(e,116)+random_value(v)%3);w16(e,4,s16(e,120)+random_value(v)%3);}else{e->bytes[184]=1;w16(e,98,2);wf(e,156,0);wf(e,160,0);wf(e,148,(float)s32(e,116));wf(e,152,(float)s32(e,120));}}
 break;
 case 2:if(trigger){damage(e,v);if(decrement(e,124)>0){w16(e,2,s16(e,116)+random_value(v)%3);w16(e,4,s16(e,120)+random_value(v)%3);}else{e->bytes[184]=1;w16(e,2,s16(e,116));w16(e,4,s16(e,120));wf(e,148,(float)s32(e,116));wf(e,152,(float)s32(e,120));wf(e,156,0);wf(e,160,0);w16(e,98,3);}}else{fall(e,v);if(tile_at_feet(e,v)){w16(e,98,3);e->bytes[46]=60;}}break;
 case 3:if(trigger){fall(e,v);if(tile_at_feet(e,v)){w16(e,98,4);e->bytes[46]=60;}}else if(!e->bytes[46]){e->bytes[184]=0;w16(e,6,0);}break;
 case 4:if(trigger&&!e->bytes[46]){e->bytes[184]=0;w16(e,2,s16(e,116));w16(e,4,s16(e,120));w16(e,98,1);}break;
 }
}
static void ice_block(GameEntity *e,const WorldObjectEnvironment *v){
 switch(s16(e,98)){
 case 0:w16(e,6,255);e->bytes[28]=0;w16(e,98,1);w32(e,116,s16(e,2));w32(e,120,s16(e,4));wf(e,148,(float)s16(e,2));wf(e,152,(float)s16(e,4));wf(e,156,0);wf(e,160,0);range(e,v,false);break;
 case 1:fall(e,v);if(tile_at_feet(e,v)){wf(e,156,0);wf(e,160,0);w16(e,98,2);if(v->ice_block_state)*v->ice_block_state=1;}break;
 case 2:damage(e,v);if(v->ice_block_state&&*v->ice_block_state==2)w16(e,98,3);break;
 case 3:w16(e,2,s16(e,2)-10);damage(e,v);if(s16(e,2)<-100){w16(e,98,4);if(v->ice_block_state)*v->ice_block_state=3;}break;
 case 4:if(v->ice_block_state&&!*v->ice_block_state){w16(e,2,s16(e,116));w16(e,4,s16(e,120));wf(e,148,(float)s16(e,116));wf(e,152,(float)s16(e,120));wf(e,156,0);wf(e,160,0);w16(e,98,1);*v->ice_block_state=1;}break;
 }
}
static void collapse(GameEntity *e,const WorldObjectEnvironment *v){switch(s16(e,98)){
 case 0:w16(e,6,255);e->bytes[28]=0;w16(e,98,1);wf(e,148,(float)s32(e,116));wf(e,152,(float)s32(e,120));wf(e,156,0);wf(e,160,0);range(e,v,false);break;
 case 1:w16(e,18,1);if(v->collapse_trigger&&*v->collapse_trigger)w16(e,98,2);break;
 case 2:if(s16(e,14)==s16(e,12)&&s16(e,18)==0)w16(e,18,1);break;
 }}
static void clamp(GameEntity *e,const WorldObjectEnvironment *v){switch(s16(e,98)){
 case 0:w16(e,6,255);e->bytes[184]=1;e->bytes[28]=0;w16(e,98,1);range(e,v,false);w16(e,12,s16(e,10));break;
 case 1:if(v->switch_flags&&v->switch_flags[e->bytes[42]]){w16(e,98,2);range(e,v,false);if(v->sound)v->sound(3,v->clamp_sample,0,v->context);}break;
 case 2:if(s16(e,14)==s16(e,12)){w16(e,98,3);w16(e,10,s16(e,12));}break;
 case 3:if(v->switch_flags&&!v->switch_flags[e->bytes[42]])w16(e,98,0);break;
 }}
static void pipe(GameEntity *e,const WorldObjectEnvironment *v){switch(s16(e,98)){
 case 0:w32(e,112,s16(e,2));w32(e,116,s16(e,4));wf(e,148,(float)s16(e,2));wf(e,152,(float)s16(e,4));e->bytes[184]=1;w16(e,6,255);e->bytes[28]=0;wf(e,156,0);wf(e,160,0);w16(e,98,1);range(e,v,false);w16(e,12,s16(e,10));if(v->pipe_entity)*v->pipe_entity=v->entity_handle;break;
 case 1:if(v->switch_flags&&v->switch_flags[0]&&v->switch_flags[1]&&v->switch_flags[2]){range(e,v,false);if(v->sound)v->sound(4,v->pipe_sample,0,v->context);w16(e,98,2);}break;
 case 2:{double vy=(double)fl(e,160)+(double)0.4f;wf(e,160,(float)vy);if(vy>20)wf(e,160,20);double y=(double)fl(e,152)+fl(e,160);wf(e,152,(float)y);w16(e,2,(int)fl(e,148));w16(e,4,(int)y);if(y>1000){if(v->switch_flags)memset(v->switch_flags,0,3);w16(e,2,s16(e,112));w16(e,4,s16(e,116));w16(e,98,0);}break;}
 }}
static void conveyor(GameEntity *e,const WorldObjectEnvironment *v){
 if(s16(e,98)==0){init_anim(e,v);w32(e,116,0);}
 int speed=(int)e->bytes[40]-128,sign=speed<0?-1:1;e->bytes[43]=(speed>=0);if(speed<0)speed=-speed;
 w16(e,18,1);int divisor=s16(e,12)+1;if(divisor)w16(e,14,(s16(e,14)+(speed<=4?1:2))%divisor);
 for(size_t i=0;i<v->body_count;i++){GameBody *b=v->bodies[i];int x=b->motion.x/4096,y=b->motion.y/4096;if(x<s16(e,2)||x>=s16(e,2)+v->width||y!=s16(e,4)+e->bytes[42]||b->motion.vy/4096<0)continue;b->motion.vy=0;int32_t dx=speed*sign*4096;platform_body_displace(b,dx,0,4,v->probe,v->context);x=b->motion.x/4096;if(x<s16(e,2)||x>s16(e,2)+v->width)b->motion.vx=dx;}
}
static bool pickup_contact(GameEntity *e,const WorldObjectEnvironment *v){return v->damage&&v->damage(s16(e,2)+10,s16(e,4)+10,v->width-20,v->height-20,0,v->context);}
static void prize(GameEntity *e,const WorldObjectEnvironment *v){
 if(!pickup_contact(e,v))return;
 if(v->seventh_item_state)*v->seventh_item_state=2;
 if(v->pickup_globals){v->pickup_globals->pickup_sound=1;v->pickup_globals->score=(int32_t)((uint32_t)v->pickup_globals->score+10000);}
 if(v->finish_timer)*v->finish_timer=240;
 if(v->score_popup){
  v->score_popup(s16(e,2)-25,s16(e,4)+30,10000,v->context);
 }
 w16(e,6,0);
}
static void dropped_item(GameEntity *e,const WorldObjectEnvironment *v){switch(s16(e,98)){
 case 0:w16(e,6,255);e->bytes[28]=0;w16(e,98,1);wf(e,148,(float)s16(e,2));w16(e,4,-200);wf(e,152,-200);wf(e,156,0);wf(e,160,0);w16(e,16,2);w16(e,18,2);range(e,v,false);break;
 case 1:if(v->boss_defeated)w16(e,98,2);break;
 case 2:fall(e,v);if(s16(e,4)+v->height>0&&tile_at_feet(e,v)){wf(e,156,0);wf(e,160,0);w16(e,98,3);}prize(e,v);break;
 case 3:prize(e,v);break;
 }}
static void snowballs(GameEntity *e,const WorldObjectEnvironment *v){int state=s16(e,98);if(!state){w16(e,6,255);e->bytes[28]=0;w16(e,98,1);w16(e,16,2);w16(e,18,2);range(e,v,false);return;}
 if(state==1&&pickup_contact(e,v)){if(v->pickup_globals){v->pickup_globals->pickup_sound=1;v->pickup_globals->ammo=10;}if(v->snowballs_available)*v->snowballs_available=1;e->bytes[184]=e->bytes[185]=1;w32(e,116,1200);w16(e,98,2);}
 if(state==1||state==2){if(!s32(e,116)){e->bytes[184]=e->bytes[185]=0;w16(e,98,1);}else decrement(e,116);}
}
static void talking_range(GameEntity *e,const WorldObjectEnvironment *v){w16(e,10,v->talking_first);w16(e,12,v->talking_last);w16(e,14,v->talking_first);e->bytes[22]=1;}
static void load_voice(const WorldObjectEnvironment *v,unsigned path){if(v->voice_load&&v->voice_load(path,v->context)&&v->voice_play)v->voice_play(v->context);}
static void dialogue_begin(GameEntity *e,const WorldObjectEnvironment *v,unsigned path,int state){
 load_voice(v,path);talking_range(e,v);if(v->dialogue_state)*v->dialogue_state=1;w16(e,98,state);w32(e,116,300);
}
static void dialogue_next(GameEntity *e,const WorldObjectEnvironment *v,unsigned path,int state){
 if(v->dialogue_state&&*v->dialogue_state==2){if(v->voice_stop)v->voice_stop(v->context);*v->dialogue_state=0;range(e,v,true);w16(e,98,1);return;}
 bool active=v->voice_active&&v->voice_active(v->context);if(active)return;
 if(!path){if(v->voice_stop)v->voice_stop(v->context);if(v->dialogue_state)*v->dialogue_state=0;range(e,v,true);w16(e,98,1);}
 else {load_voice(v,path);w16(e,98,state);}
}
static void paradiso(GameEntity *e,const WorldObjectEnvironment *v){
 unsigned kind=e->bytes[42];if((kind==6||kind==8)&&s32(e,120)!=v->progress_flag){w32(e,120,v->progress_flag);w32(e,116,0);}
 switch(s16(e,98)){
 case 0:e->bytes[184]=1;w16(e,6,255);e->bytes[28]=0;w16(e,98,1);w16(e,16,3);w32(e,116,0);range(e,v,kind!=10);if(kind==10)w16(e,12,s16(e,10));break;
 case 1:if(s32(e,116)){decrement(e,116);break;}
 if(v->player_x<=s16(e,2)-100||v->player_x>=s16(e,2)+v->width+100||v->player_y<=s16(e,4)+v->height-30||v->player_y>=s16(e,4)+v->height+100)break;
 switch(kind){
 case 0:dialogue_begin(e,v,0x456ab0,20);break;case 1:dialogue_begin(e,v,0x456a8c,10);break;case 2:dialogue_begin(e,v,0x456a68,22);break;case 3:dialogue_begin(e,v,0x456a44,10);break;case 4:dialogue_begin(e,v,0x456a20,10);break;case 5:dialogue_begin(e,v,0x4569fc,10);break;
 case 6:dialogue_begin(e,v,v->progress_flag?0x4569b4:0x4569d8,10);break;case 7:dialogue_begin(e,v,0x456990,100);break;case 8:dialogue_begin(e,v,v->progress_flag?0x45696c:0x456948,10);break;case 9:dialogue_begin(e,v,0x456924,10);break;
 case 10:if(s16(e,10)!=0)range(e,v,false);w16(e,98,200);break;
 }break;
 case 10:dialogue_next(e,v,0,1);break;case 20:dialogue_next(e,v,0x456900,21);break;case 21:dialogue_next(e,v,0x4568dc,10);break;case 22:dialogue_next(e,v,0x4568b8,10);break;
 case 100:if((v->dialogue_state&&*v->dialogue_state==2)||!(v->voice_active&&v->voice_active(v->context))){if(v->target_world)*v->target_world=v->world;if(v->completion_flags&&(unsigned)v->world<4)v->completion_flags[v->world]=1;if(v->game_mode)*v->game_mode=20;}break;
 case 200:if(s16(e,14)==s16(e,12)&&s16(e,18)==0){range(e,v,true);static const unsigned paths[4]={0x456894,0x456870,0x45684c,0x456828};if((unsigned)v->world<4)dialogue_begin(e,v,paths[v->world],10);}break;
 }
}
static bool on_platform(GameEntity *e,const WorldObjectEnvironment *v,GameBody *b){
 int x=(uint32_t)b->kind<=1?b->motion.x/4096:0,y=(uint32_t)b->kind<=1?b->motion.y/4096:0,vy=(uint32_t)b->kind<=1?b->motion.vy/4096:0;
 return x>=s16(e,2)&&x<s16(e,2)+v->width&&y==s16(e,4)+e->bytes[42]&&vy>=0;
}
static void crumble_path(GameEntity *e,const WorldObjectEnvironment *v,int direction){
 int current=direction<=2?s16(e,2):s16(e,4)-(int)fl(e,148);
 int bound=s16(e,direction==1?31:direction==2?35:direction==3?33:37),speed=e->bytes[29],delta=0;
 if(direction==1||direction==3){if(current>bound)delta=current-speed<bound?bound-current:-speed;}
 else if(current<bound)delta=current+speed>bound?bound-current:speed;
 if(delta)platform_transport(e,v->width,v->bodies,v->body_count,direction<=2?delta:0,direction>=3?delta:0,v->probe,v->context);
 int test=direction<=2?s16(e,2):current;
 if((direction==1||direction==3)?test<=bound:test>=bound)platform_path_end(e,direction<=2?3:12);
}
static void crumble(GameEntity *e,const WorldObjectEnvironment *v){
 switch(s16(e,98)){
 case 0:w16(e,10,0);w16(e,12,0);w16(e,14,0);w16(e,16,2);w16(e,18,2);break;
 case 1:if(decrement(e,116)<=0){e->bytes[26]=0;w16(e,98,2);range(e,v,false);if(v->sound)v->sound(6,v->crumble_sample,0,v->context);}break;
 case 2:if(s16(e,14)==s16(e,12)&&s16(e,18)==0){w16(e,10,0);w16(e,12,0);w16(e,14,0);e->bytes[185]=1;w32(e,116,120);w16(e,98,3);}break;
 case 3:if(decrement(e,116)<=0){e->bytes[26]=1;e->bytes[185]=0;w16(e,98,0);}break;
 }
 bool standing=false;for(size_t i=0;i<v->body_count;i++)if(on_platform(e,v,v->bodies[i])){standing=true;break;}
 if(standing){if(!s32(e,112)){w32(e,116,30);w32(e,112,1);w16(e,98,1);wf(e,152,3);}}
 else {w32(e,112,0);wf(e,152,0);}
 float velocity=(float)((double)fl(e,152)-(double)0.4f);if(velocity<-20)velocity=-20;wf(e,152,velocity);
 float old=fl(e,148),next=(float)((double)velocity+old);if(next<0)next=0;else if(next>=30){next=30;wf(e,152,0);}
 platform_transport(e,v->width,v->bodies,v->body_count,0,(int)next-(int)old,v->probe,v->context);wf(e,148,next);
 if(e->bytes[28])switch(e->bytes[39]){
 case 1:crumble_path(e,v,1);break;case 2:crumble_path(e,v,2);break;case 4:crumble_path(e,v,3);break;case 5:crumble_path(e,v,1);crumble_path(e,v,3);break;case 6:crumble_path(e,v,2);crumble_path(e,v,3);break;case 8:crumble_path(e,v,4);break;case 9:crumble_path(e,v,1);crumble_path(e,v,4);break;case 10:crumble_path(e,v,2);crumble_path(e,v,4);break;
 }
}
bool world_object_supported(unsigned id){switch(id){case 59:case 60:case 75:case 77:case 79:case 80:case 82:case 84:case 85:case 88:case 89:case 265:case 352:case 354:case 355:case 356:case 414:return true;default:return false;}}
bool world_object_tick(GameEntity *e,const WorldObjectEnvironment *v){if(!e||!v)return false;switch(entity_id(e)){
 case 59:dropped_item(e,v);break;case 60:snowballs(e,v);break;
 case 77:paradiso(e,v);break;
 case 414:crumble(e,v);break;
 case 75:falling_spike(e,v,false);break;case 79:falling_spike(e,v,true);break;case 265:ice_block(e,v);break;case 80:collapse(e,v);break;case 84:clamp(e,v);break;case 85:pipe(e,v);break;case 82:conveyor(e,v);break;
 case 354:if(!s16(e,98))init_anim(e,v);break;
 case 352:switch(s16(e,98)){case 0:init_anim(e,v);break;case 1:if(s16(e,14)==15&&s16(e,18)==1){w16(e,98,2);w32(e,116,random_value(v)%60+60);}break;case 2:if(decrement(e,116)<=0)w16(e,98,1);else w16(e,18,1);break;}break;
 case 88:case 89:switch(s16(e,98)){case 0:w16(e,6,255);w16(e,16,2);w16(e,18,2);w16(e,98,1);w32(e,116,random_value(v)%100+30);range(e,v,true);break;case 1:if(decrement(e,116)<=0){range(e,v,false);w16(e,98,2);}break;case 2:if(s16(e,14)==s16(e,12)&&s16(e,18)==1)w16(e,98,0);break;}break;
 case 355:case 356:if(!s16(e,98))init_anim(e,v);else if(s16(e,98)==1&&v->ambient){int x=s16(e,2),y=s16(e,4);v->ambient(x,y,8,v->context);v->ambient(x+v->width,y,8,v->context);v->ambient(x,y+v->height,8,v->context);v->ambient(x+v->width,y+v->height,8,v->context);}break;
 default:return false;
 }return true;}
