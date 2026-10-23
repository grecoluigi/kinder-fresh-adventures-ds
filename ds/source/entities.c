#include "entities.h"
#include <string.h>
static uint16_t get16(const GameEntity *e,unsigned at){return (uint16_t)(e->bytes[at]|e->bytes[at+1]<<8);}
static int16_t signed16(const GameEntity *e,unsigned at){int16_t value;uint16_t raw=get16(e,at);memcpy(&value,&raw,2);return value;}
static int32_t signed32(const GameEntity *e,unsigned at){int32_t value;memcpy(&value,e->bytes+at,4);return value;}
static void set16(GameEntity *e,unsigned at,uint16_t value){e->bytes[at]=(uint8_t)value;e->bytes[at+1]=(uint8_t)(value>>8);}
static void set32(GameEntity *e,unsigned at,uint32_t value){memcpy(e->bytes+at,&value,4);}
static int32_t add32(int32_t a,uint32_t b){uint32_t raw;memcpy(&raw,&a,4);raw+=b;memcpy(&a,&raw,4);return a;}
uint16_t entity_id(const GameEntity *e){return get16(e,0);}
int16_t entity_x(const GameEntity *e){return signed16(e,2);}
int16_t entity_y(const GameEntity *e){return signed16(e,4);}
int16_t entity_frame(const GameEntity *e){return signed16(e,14);}
unsigned entity_layer(const GameEntity *e){return e->bytes[25];}
unsigned entity_group(const GameEntity *e){return e->bytes[23];}
bool entity_active(const GameEntity *e){return get16(e,6)!=0;}
bool entity_visible(const GameEntity *e){return entity_active(e)&&!e->bytes[185];}
void entities_register_callback(GameEntity *entities,size_t count,int id,uint32_t handle){
 for(size_t i=0;i<count;i++)if(signed16(&entities[i],0)==id)set32(&entities[i],94,handle?handle:0x430d90);
}
uint32_t entity_native_pickup_callback(unsigned id){
 static const uint32_t callbacks[11]={0x40edb0,0x40edb0,0x40edb0,0x40eeb0,0x40efe0,0x40f110,0x40f220,0x40f330,0x40f440,0x40f550,0x40f660};
 return id>=48&&id<=58?callbacks[id-48]:0;
}
bool entity_legacy_npc_event(GameEntity *e,unsigned event,const int16_t ranges[2][2]){
 if(e&&ranges&&entity_id(e)!=0xffff&&(event==16||event==32)){
  unsigned range=event==16?0:1;
  set16(e,10,(uint16_t)ranges[range][0]);set16(e,12,(uint16_t)ranges[range][1]);
  e->bytes[22]=1;set16(e,14,(uint16_t)ranges[range][0]);
 }
 return true;
}
size_t entities_select_geometry(const GameEntity *entities,size_t count,unsigned layer,uint16_t *indices,size_t capacity){
 size_t used=0;for(size_t i=0;i<count&&used<capacity&&used<1000;i++)
  if(!entities[i].bytes[24]&&entity_layer(&entities[i])==layer)indices[used++]=(uint16_t)i;
 return used;
}
void entity_frame_sound_step(GameEntity *e,unsigned index,const EntityFrameSoundEnvironment *env){
 if(!e||!env||!env->enabled||signed16(e,18)!=0)return;
 for(unsigned slot=0;slot<3;slot++){
  int16_t trigger=signed16(e,67+slot*2);bool request=false;
  if(trigger==signed16(e,14)&&trigger!=-1){
   if(!e->bytes[79+slot])request=true;
   else{
    unsigned channel=e->bytes[82+slot];
    if(!env->channel_owners||(int32_t)env->channel_owners[channel]!=(int32_t)index)request=true;
    else request=!env->channel_active||!env->channel_active(channel,env->context);
   }
  }else if(trigger==-2){
   if(env->request)env->request(e,slot,env->context);
   set16(e,67+slot*2,0xffff);continue;
  }else if(trigger==-3)request=!e->bytes[79+slot];
  if(request&&env->request)env->request(e,slot,env->context);
 }
}
void entity_sound_spatial(int32_t x,int32_t y,int16_t width,int16_t height,
 int32_t *attenuation,int32_t *pan){
 int half_x=width/2,half_y=height/2;
 int pan_step=half_x/10,x_step=(half_x+350)/24,y_step=(half_y+350)/24;
 if(!attenuation||!pan)return;
 /* Valid native viewports have nonzero divisors; reject corrupt dimensions. */
 if(width<20||height<=0||!pan_step||!x_step||!y_step){*attenuation=-100;*pan=0;return;}
 int64_t dx=(int64_t)x-half_x,dy=(int64_t)y-half_y;
 if(x<half_x)*pan=x>0?(int32_t)(dx/pan_step):-10;
 else *pan=dx<half_x?(int32_t)(dx/pan_step):10;
 if(dx<0)dx=-dx;
 if(dy<0)dy=-dy;
 uint16_t rx=(uint16_t)(-(dx/x_step)),ry=(uint16_t)(-(dy/y_step));
 int16_t ax,ay;memcpy(&ax,&rx,2);memcpy(&ay,&ry,2);
 *attenuation=ax<ay?ax:ay;if(*attenuation< -44)*attenuation=-100;
}
unsigned entity_sound_allocate(int16_t *current,int16_t first,int16_t count,
 bool (*active)(unsigned channel,void *context),void *context){
 if(!current)return (unsigned)(int32_t)first;
 bool found=false;
 for(int i=0;i<count;i++){
  int channel=first+i;
  if(!active||!active((unsigned)channel,context)){*current=(int16_t)channel;found=true;break;}
 }
 if(!found){
  uint16_t raw;memcpy(&raw,current,2);raw++;memcpy(current,&raw,2);
  if((int)*current>(int)first+count-1)*current=first;
 }
 if(*current<first||(int)*current>(int)first+count-1)*current=first;
 return (unsigned)(int32_t)*current;
}
void entity_sound_playback(GameEntity *objects,size_t count,int index,int slot,
 uint32_t repeat,const EntitySoundPlaybackEnvironment *env){
 if(!objects||!env||!env->enabled||index<0||(size_t)index>=count||slot<0||slot>=3)return;
 GameEntity *e=objects+index;int sample=signed16(e,73+(unsigned)slot*2);
 int available=signed16(e,61+(unsigned)slot*2);
 if(sample<0||(size_t)sample>=env->sample_count||!env->sample_handles||
    !available||available==-1||env->sample_handles[sample]==-1||!env->allocate)return;
 if(!repeat){repeat=e->bytes[88+slot];if(!repeat)repeat=1;}
 int32_t attenuation=0,pan=signed32(e,49+(unsigned)slot*4);
 if(e->bytes[91+slot]&&env->spatial){
  env->spatial(entity_x(e),entity_y(e),&attenuation,&pan,env->context);
  set32(e,49+(unsigned)slot*4,(uint32_t)pan);
 }
 unsigned channel=env->allocate(env->context)&255u;e->bytes[82+slot]=(uint8_t)channel;
 if(env->pan)env->pan(channel,pan,env->context);
 if(env->volume)env->volume(channel,add32(attenuation,e->bytes[85+slot]),env->context);
 if(env->play)env->play(channel,env->sample_handles[sample],repeat,env->context);
 if(env->owners){
  EntitySoundOwner *owner=env->owners+channel;
  if(owner->object>=0&&(size_t)owner->object<count&&owner->slot>=0&&owner->slot<3)
   objects[owner->object].bytes[79+owner->slot]=0;
  owner->object=(int16_t)index;owner->slot=(int16_t)slot;
 }
 e->bytes[79+slot]=1;
}
static int sound_half(int16_t value){return value>=0?value/2:-((-(int)value+1)/2);}
void entity_sound_maintain(GameEntity *objects,size_t count,int first,int channels,
 const EntitySoundMaintenanceEnvironment *env){
 if(!objects||!env||!env->enabled||!env->owners||!env->frame_size||!env->spatial)return;
 for(int i=0;i<channels;i++){
  int channel=first+i;if(channel<0||channel>=256)continue;
  EntitySoundOwner *owner=env->owners+channel;
  if(owner->object<0||(size_t)owner->object>=count||owner->slot<0||owner->slot>=3)continue;
  GameEntity *e=objects+owner->object;int slot=owner->slot;
  if(!e->bytes[91+slot])continue;
  int16_t width,height;if(!env->frame_size(e,&width,&height,env->context))continue;
  int32_t attenuation=0,pan=signed32(e,49+(unsigned)slot*4);
  env->spatial(entity_x(e)+sound_half(width),entity_y(e)+sound_half(height),&attenuation,&pan,env->context);
  set32(e,49+(unsigned)slot*4,(uint32_t)pan);
  unsigned actual_channel=e->bytes[82+slot];
  if(attenuation==-100){
   if(env->stop)env->stop(actual_channel,env->context);
   e->bytes[79+slot]=0;owner->object=-1;
  }else{
   if(env->pan)env->pan(actual_channel,pan,env->context);
   if(env->volume)env->volume(actual_channel,add32(attenuation,e->bytes[85+slot]),env->context);
  }
 }
}
void entity_sound_stop_all(GameEntity *objects,size_t count,int first,int channels,
 const EntitySoundMaintenanceEnvironment *env){
 if(!objects||!env||!env->owners)return;
 for(int i=0;i<channels;i++){
  int channel=first+i;if(channel<0||channel>=256)continue;
  if(env->stop)env->stop((unsigned)channel,env->context);
  EntitySoundOwner *owner=env->owners+channel;
  if(owner->object<0)continue;
  if((size_t)owner->object<count&&owner->slot>=0&&owner->slot<3)
   objects[owner->object].bytes[79+owner->slot]=0;
  owner->object=-1;
 }
}
unsigned entity_advance_animation(GameEntity *e,int16_t extra){
 int16_t timer=signed16(e,18),frame=signed16(e,14);unsigned event=4;
 if(timer>0){set16(e,18,(uint16_t)(timer-1));return event;}
 set16(e,18,(uint16_t)(get16(e,16)+(uint16_t)extra));
 bool reverse=e->bytes[22]==2;
 if(reverse?frame>signed16(e,10):frame<signed16(e,12))set16(e,14,(uint16_t)(frame+(reverse?-1:1)));
 else {
  set16(e,14,get16(e,reverse?12:10));int16_t repeats=signed16(e,6);
  if(repeats!=255&&repeats>0){set16(e,6,(uint16_t)(repeats-1));event=12;}else event=6;
 }
 return event;
}
bool entity_pickup_callback(GameEntity *e,EntityGlobals *g,const EntityEnvironment *env){
 unsigned id=entity_id(e);if(id<48||id>58||!g||!env)return false;
 int16_t state=signed16(e,98);
 if(!state){
  set16(e,6,255);e->bytes[28]=0;set16(e,98,1);set16(e,16,2);set16(e,18,2);
  set16(e,10,(uint16_t)env->first);set16(e,12,(uint16_t)env->last);e->bytes[22]=1;set16(e,14,(uint16_t)env->first);
  return true;
 }
 if(state==1){
  bool contact=env->overlap&&env->overlap(entity_x(e)+10,entity_y(e)+10,env->width-20,env->height-20,0,env->context);
  if(contact){
   g->pickup_sound=1;
   if(id<=50){
    if(env->popup)env->popup(entity_x(e)-25,entity_y(e)+30,100,env->context);
    g->score=add32(g->score,100);set16(e,6,0);
   }else if(id<=52){
    if(id==51){g->health=add32(g->health,40);if(g->health>100)g->health=100;}
    else {g->ammo=10;g->shoot_latch=0;}
    e->bytes[184]=1;e->bytes[185]=1;set32(e,116,1200);set16(e,98,2);
   }else {
    g->score=add32(g->score,1000);g->letters[id-53]=1;
    if(env->popup)env->popup(entity_x(e)-15,entity_y(e)+30,1000,env->context);
    set16(e,6,0);
   }
  }
 }
 /* Native51/52 state1 falls through to countdown, including non-contact ticks. */
 if((id==51||id==52)&&(state==1||state==2)){
  int32_t timer=signed32(e,116);
  if(!timer){e->bytes[184]=0;e->bytes[185]=0;set16(e,98,1);}
  else set32(e,116,(uint32_t)timer-1);
 }
 return true;
}

/* Native430cf0: nearest endpoint determines the initial direction on each axis.
 * -1 bounds disable an axis; horizontal ties choose right, vertical ties down. */
void entity_path_init(GameEntity *e)
{
    e->bytes[39]=0;
    if(!e->bytes[28])return;
    int left=signed16(e,31),top=signed16(e,33);
    if(left==-1&&top==-1)return;
    if(left!=-1){int x=entity_x(e),right=signed16(e,35);e->bytes[39]=(uint8_t)(x-left<=right-x?2:1);}
    if(top!=-1){int y=entity_y(e),bottom=signed16(e,37);e->bytes[39]|=(uint8_t)(y-top<=bottom-y?8:4);}
}
/* Native430ca0→430c30: only initially active records are reset. */
void entities_reset_map(GameEntity *entities,size_t count)
{
    for(size_t i=0;i<count;i++){
        GameEntity *e=entities+i;if(!entity_active(e))continue;
        set16(e,6,get16(e,8));set16(e,14,get16(e,e->bytes[22]==2?12:10));
        e->bytes[47]=0;entity_path_init(e);
    }
}
