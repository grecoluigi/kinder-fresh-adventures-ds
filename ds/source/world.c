#include "native_actors.h"
#include "gpu_actors.h"
#include "world.h"
#include "scene.h"

#include "player.h"
#include "player_graphics.h"
#include "camera.h"
#include "tile_queries.h"
#include "native_rng.h"
#include "hazards.h"
#include "hud.h"
#include "effects.h"
#include "projectiles.h"
#include "geometry.h"
#include "platforms.h"
#include "enemies.h"
#include "enemy_shots.h"
#include "sound_events.h"
#include "blocks.h"
#include "world_objects.h"
#include "world_routes.h"
#include "world_enemies.h"
#include "boss_factory.h"
#include "boss_valley.h"
#include "boss_mountain_jungle.h"
#include "game_save.h"
#include "end_titles.h"
#include <string.h>
#include <stdlib.h>
#ifdef __NDS__
#include <nds/system_counter.h>
/* Opt-in debugger profiling: cumulative system ticks, never gameplay input.
 * Off by default; host/native behavior checks retain the same callbacks. */
static volatile bool world_update_profile_enabled;
static volatile uint32_t world_update_profile[6];
static uint32_t world_update_profile_start;
static volatile uint32_t world_entity_profile[7];
static uint32_t world_entity_profile_start;
static void entity_profile_begin(void){
 if(world_update_profile_enabled)world_entity_profile_start=(uint32_t)systemCounterGetTicks();
}
static void entity_profile_lap(unsigned part){
 if(world_update_profile_enabled){
  uint32_t now=(uint32_t)systemCounterGetTicks();world_entity_profile[part]+=now-world_entity_profile_start;world_entity_profile_start=now;
 }
}
static void update_profile_begin(void){
 if(world_update_profile_enabled)world_update_profile_start=(uint32_t)systemCounterGetTicks();
}
static void update_profile_lap(unsigned part){
 if(world_update_profile_enabled){
  uint32_t now=(uint32_t)systemCounterGetTicks();world_update_profile[part]+=now-world_update_profile_start;world_update_profile_start=now;
 }
}
#else
#define update_profile_begin() ((void)0)
#define update_profile_lap(part) ((void)0)
#define entity_profile_begin() ((void)0)
#define entity_profile_lap(part) ((void)0)
#endif
static Player player;
static EndTitle end_title;
static GameBody body;
static GameCamera camera;
static bool ready, graphics_ok, player_visible,player_render_visible,blink_advanced;
static PlayerBlinkView blink_view;
static HudState hud;
static HudState rendered_hud;
static bool hud_rendered;
static Projectiles shots;
static unsigned native_world,geometry_layer;
static const WorldRoute *active_route;
static int32_t transition_target;
static unsigned npc_voice_key;
static uint32_t ice_trigger_bits,pipe_entity;
static int32_t ice_block_state,collapse_trigger;
static int32_t boss_energy,boss_defeated,yeti_hit,finish_timer;
static unsigned boss_voice_key;
static int boss_volumes[19];
static int clamp_sound,pipe_sound,crumble_sound;
static EnemyAmbientState ambient;
static unsigned ambient_keys[16];
static bool ambient_started,camera_locked;
static int16_t enemy_hit_sound,enemy_fall_sound,parrot_sound,kong_throw_sound;
static int16_t eagle_sound,robot_charge_sound,egg_throw_sound;
static unsigned pickup_sound_key;
static uint8_t switch_flags[256];
static int switch_sound;
static GeometryRect nearby_geometry[100];
static int geometry_count;
static PlayerEnvironment player_environment;
static void player_audio_event(void *context,PlayerEventType type,int id,int argument){
 sound_events_event(context,type,id,argument);
 /* Native4243b1 returns the result of this load, not an unconditional success
  * or the preceding frame's result. player.c uses it before setting volume. */
 if(type==PLAYER_SOUND_LOAD)player_environment.sound_load_ok=sound_last_load_ok();
}
static uint16_t geometry_indices[1000],tick_indices[1024];
static size_t selected_count,tick_count;
static uint16_t *shot_obstacle_indices;
static size_t shot_obstacle_count;
static bool shot_obstacle_cached;
static bool spring_id(unsigned id){return id==2||id==200||id==201||id==202||id==210||id==220||(id>=230&&id<=233);}
static bool block_id(unsigned id){return id==76||id==78||id==83||id==86||id==87;}
static bool supported_id(unsigned id){return world_object_supported(id)||spring_id(id)||block_id(id)||(id>=3&&id<=18)||(id>=48&&id<=58);}
static void build_object_lists(void){
 size_t count;GameEntity *objects=scene_entities(&count);selected_count=tick_count=0;
 for(size_t i=0;i<count&&selected_count<1000;i++)
  if(!objects[i].bytes[24]&&entity_layer(&objects[i])==geometry_layer)geometry_indices[selected_count++]=(uint16_t)i;
 /* IDs/layer membership are fixed by the loaded map, as for tick_indices.
  * Active/solid/frame fields remain live and are checked at every query. */
 shot_obstacle_count=0;shot_obstacle_cached=true;
 for(size_t i=0;i<selected_count;i++)if(block_id(entity_id(objects+geometry_indices[i])))shot_obstacle_count++;
 if(shot_obstacle_count){
  shot_obstacle_indices=malloc(shot_obstacle_count*sizeof(*shot_obstacle_indices));
  if(!shot_obstacle_indices)shot_obstacle_cached=false;
  else{size_t n=0;for(size_t i=0;i<selected_count;i++)
   if(block_id(entity_id(objects+geometry_indices[i])))shot_obstacle_indices[n++]=geometry_indices[i];}
 }
 static const unsigned groups[3]={1,0,2};
 for(unsigned layer=0;layer<8;layer++)for(unsigned group=0;group<3;group++)for(size_t i=0;i<count;i++)
  if(entity_layer(&objects[i])==layer&&entity_group(&objects[i])==groups[group]&&supported_id(entity_id(&objects[i])))tick_indices[tick_count++]=(uint16_t)i;
}
static bool world_probe(void *context,int layer,int x,int y,unsigned mode){
 if(layer==body.layer&&geometry_query(nearby_geometry,geometry_count,x,y,mode))return true;
 return body_map_probe(context,layer,x,y,mode);
}
/* Native4173cd: reverse selected map indices, capacity100, player-centered box. */
static void rebuild_geometry(void){
 size_t count;GameEntity *objects=scene_entities(&count);geometry_count=0;
 int x=body.motion.x/4096,y=body.motion.y/4096;
 for(size_t selected=selected_count;selected>0&&geometry_count<100;){
  size_t i=geometry_indices[--selected];
  if(i>=count||!entity_active(&objects[i])||!objects[i].bytes[26])continue;
  GeometryObject object;
  if(!scene_geometry_object(i,&object))continue;
  geometry_count+=geometry_build(nearby_geometry+geometry_count,1,&object,1,x-200,y-400,x+200,y+200);
 }
}
static int32_t push_query(void *context,int x,int y,int mode){
 (void)context;return (int32_t)geometry_query(nearby_geometry,geometry_count,x,y,(unsigned)mode);
}
static uint32_t push_resolve(void *context,int32_t encoded){
 (void)context;uint32_t index=(uint32_t)encoded&~0x08000000u;
 if(!index||index>(uint32_t)geometry_count)return 0;
 return (uint32_t)nearby_geometry[index-1].object_index+1;
}
static void push_velocity(void *context,uint32_t handle,float velocity){
 (void)context;size_t count;GameEntity *objects=scene_entities(&count);
 if(handle&&handle<=count)memcpy(objects[handle-1].bytes+156,&velocity,sizeof(velocity));
}
static int32_t world_random(void *context){(void)context;return native_rng_next();}
static int enemy_random(void *context){(void)context;return (int)native_rng_next();}
/* Native417238..4172bc/4172fe overrides the generic animation defaults. */
static void player_animation_startup(Player *p){
 animation_init(&p->penguin,1,289,0,0);animation_init(&p->milk,2,297,0,0);
 p->penguin.frame=75;p->penguin.first=78;p->penguin.last=87;
 p->milk.first=3;p->milk.last=12;
 p->penguin.timer=p->penguin.delay=1;p->penguin.opaque_54=1;
 p->milk.timer=p->milk.delay=1;p->milk.opaque_54=1;
 p->puff_frame=13;p->state=1;
}
static void draw_player(uint16_t *pixels,unsigned layer,int cx,int cy,void *context){
 (void)context;
 {}
 if(layer!=(unsigned)body.layer)return;
 if(player_render_visible){
  Animation *a=player.character?&player.milk:&player.penguin;
  graphics_ok=player_graphics_draw(pixels,player.character,a->frame,player.facing,body.motion.x/4096,body.motion.y/4096,cx,cy)&&graphics_ok;
  int bounds[4];player_graphics_last_bounds(bounds);{}
 }
 graphics_ok=projectiles_draw(&shots,pixels,cx,cy)&&graphics_ok;
 int bounds[4];projectiles_last_bounds(bounds);{}
}
void world_close(void){gpu_native_reset(NULL);free(shot_obstacle_indices);shot_obstacle_indices=NULL;shot_obstacle_count=0;shot_obstacle_cached=false;end_title_close();memset(&end_title,0,sizeof(end_title));sound_events_stop();scene_set_layer_callback(NULL,NULL);scene_close();player_graphics_close();projectile_graphics_close();enemy_shot_graphics_close();hud_close();geometry_count=0;ready=false;active_route=NULL;}
static bool open_route(unsigned world,const WorldRoute *route){
 int32_t carried_score=ready&&route&&route->arena?hud.score:0;
 world_close();scene_enable_live_enemies(route&&route->base_world==0);
 scene_set_sprite_cache_bytes(route&&route->arena?512u*1024u:route&&route->tutorial?256u*1024u:384u*1024u);
 scene_enable_background_parallax(true);
 if(world>=8||!route||!scene_open(route->map_name)||!player_graphics_open()||!hud_open()||!hud_set_world_background(route->base_world)||!projectile_graphics_open()||!enemy_shot_graphics_open()){world_close();return false;}
 const SceneMetadata *m=scene_metadata();
 size_t reset_count;GameEntity *reset_objects=scene_entities(&reset_count);entities_reset_map(reset_objects,reset_count);
 memset(&body,0,sizeof(body));memset(&player,0,sizeof(player));
 body.kind=1;body.layer=2;body.opaque_18=-1;body.height=190;body.half_width=32;
 body.probe_offset=30;body.probe_count=21;body.probe_stride=8;body.slope_limit_fixed=0x2000;
 body.motion.x=m->start_x*4096;body.motion.y=m->start_y*4096;body.motion.gravity=0xb33;
 body.motion.friction_x=0x400;body.motion.friction_y=40;
 body.motion.max_x=0x7ffff000;body.motion.max_y=0x7ffff000;
 body.motion.min_vx=-0x5000;body.motion.max_vx=0x5000;body.motion.min_vy=-0x7ffff000;body.motion.max_vy=0xc000;
 player_animation_startup(&player);
 player.jump_debounce=-5;player.switch_available=0;
 player.inventory=10;player.health=100;player.death_timer=-1;
 sound_prepare_player(&player,world);
 enemy_hit_sound=sound_key_handle(sound_global_key(world,0x4dac42));
 enemy_fall_sound=sound_key_handle(sound_global_key(world,0x4e0aa6));
 parrot_sound=sound_key_handle(sound_global_key(world,0x4e0aa8));
 kong_throw_sound=sound_key_handle(sound_global_key(world,0x4dac6e));
 eagle_sound=sound_key_handle(sound_global_key(world,0x4e0a90));
 robot_charge_sound=sound_key_handle(sound_global_key(world,0x4dac6a));
 egg_throw_sound=sound_key_handle(sound_global_key(world,0x4dac60));
 pickup_sound_key=sound_global_key(world,0x4dbc68);
 switch_sound=(int)sound_global_key(world,0x4e0b06);memset(switch_flags,0,sizeof(switch_flags));
 ice_trigger_bits=pipe_entity=0;ice_block_state=collapse_trigger=0;
 clamp_sound=(int)sound_global_key(world,0x4e0b10);
 pipe_sound=(int)sound_global_key(world,0x4e0b18);
 crumble_sound=(int)sound_global_key(world,0x4dab60);
 for(unsigned channel=0;channel<16;channel++)
  ambient_keys[channel]=sound_global_key(world,enemy_ambient_sample_global(world,channel));
 ambient_started=false;boss_energy=9;boss_defeated=yeti_hit=finish_timer=0;boss_voice_key=0;memset(boss_volumes,0,sizeof(boss_volumes));
 memset(&hud,0,sizeof(hud));hud.world=(int32_t)world;hud.boss_energy=9;hud.score=carried_score;
 WorldArenaStartup arena={0};camera_locked=false;
 if(route->arena&&world_arena_startup(world,&arena)){hud.boss=arena.boss;camera_locked=arena.camera_locked!=0;for(unsigned i=0;i<6;i++)hud.letters[i]=1;}
 hud_rendered=false;
 player_visible=player_render_visible=true;blink_advanced=false;memset(&blink_view,0,sizeof(blink_view));
 projectiles_init(&shots);
 enemy_shots_init();
 const int16_t factors[8]={2,2,2,2,2,2,2,2};
 camera_init(&camera,m->width_cells,m->height_cells,route->arena?arena.camera_x:m->start_x-100,route->arena?arena.camera_y:m->start_y-400,factors,2);
 /* Native411915/411938: the consumed start marker chooses geometry objects,
  * independently of the player's layer2 tile probes. Jungle arena uses layer1. */
 geometry_layer=(unsigned)body.layer;
 size_t object_count;GameEntity *initial_objects=scene_entities(&object_count);
 for(size_t i=0;i<object_count;i++)if(entity_id(initial_objects+i)==1000)geometry_layer=entity_layer(initial_objects+i);
 build_object_lists();
 native_world=world;active_route=route;transition_target=-1;npc_voice_key=0;
 scene_set_layer_callback_at_layer(draw_player,NULL,2);ready=true;return true;
}
bool world_open(unsigned world){return open_route(world,world_route_select(world,game_save_state()->tutorials));}
bool world_open_stage(unsigned world,bool tutorial){
 uint8_t flags[4]={1,1,1,1};if(world<4&&tutorial)flags[world]=0;
 return open_route(world,world_route_select(world,flags));
}
const char *world_map_name(void){return ready&&active_route?active_route->map_name:NULL;}
int world_transition_target(void){return ready&&player.game_mode==20?transition_target:-1;}
int world_player_state(void){return player.state;}
bool world_finished(void){return ready&&player.game_mode==2;}
unsigned world_result_world(void){return native_world&3;}
int32_t world_result_score(void){return hud.score;}
static void shoot(void *context,int x,int y,float vx,float vy,int variant){
 (void)context;projectiles_spawn(&shots,x,y,vx,vy,variant);
}
static int shot_solid(void *context,int x,int y){return map_tile_solid(context,2,x,y);}
static unsigned shot_property(void *context,int x,int y){return map_tile_property(context,2,x,y);}
static int enemy_shot_solid(void *context,int x,int y){(void)context;return map_tile_solid(scene_collision_map(),2,x,y);}
static unsigned enemy_shot_property(void *context,int x,int y){(void)context;return map_tile_property(scene_collision_map(),2,x,y);}
static bool enemy_shot_obstacle(void *context,int x,int y){
 (void)context;size_t count;GameEntity *objects=scene_entities(&count);
 const uint16_t *indices=shot_obstacle_cached?shot_obstacle_indices:geometry_indices;
 size_t candidates=shot_obstacle_cached?shot_obstacle_count:selected_count;
 for(size_t selected=candidates;selected>0;){
  size_t i=indices[--selected];if(i>=count)continue;
  unsigned id=entity_id(&objects[i]);
  if((id!=76&&id!=78&&id!=83&&id!=86&&id!=87)||!entity_active(&objects[i])||!objects[i].bytes[26])continue;
  GeometryObject bounds;if(scene_geometry_object(i,&bounds)&&enemy_shot_obstacle_test(&bounds,1,x,y))return true;
 }
 return false;
}
static bool pickup_overlap(int x,int y,int width,int height,int mode,void *context){
 (void)mode;(void)context;PlayerEnvironment e={0};
 return player_rect_hazard(&player,&body,x,y,width,height,0,&e);
}
static bool enemy_contact(int x,int y,int width,int height,int damage,void *context){
 EntityGlobals *state=context;if(state)player.health=state->health;
 bool hit=player_rect_hazard(&player,&body,x,y,width,height,damage,&player_environment);
 if(state)state->health=player.health;
 return hit;
}
static bool enemy_projectile(int x,int y,int width,int height,int flags,void *context){
 (void)context;return projectiles_hit(&shots,x,y,width,height,(unsigned)flags)!=0;
}
static bool enemy_allocate(void *context){(void)context;return enemy_shots_allocate();}
static void enemy_sound(int channel,int sound,void *context){(void)context;sound_play((unsigned)channel,(unsigned)sound,0);}
static int block_tile(int layer,int x,int y,void *context){(void)context;return map_tile_solid(scene_collision_map(),layer,x,y);}
static void block_projectiles(int x,int y,int width,int height,unsigned mode,void *context){(void)context;projectiles_hit(&shots,x,y,width,height,mode);}
static void block_sound(int channel,int sample,int repeat,void *context){(void)context;sound_play((unsigned)channel,(unsigned)sample,(unsigned)repeat);}
static bool npc_voice_load(unsigned key,void *context){
 (void)context;npc_voice_key=key;return sound_key_handle(key)!=0;
}
static bool npc_voice_active(void *context){(void)context;return sound_channel_active(17);}
static void npc_voice_play(void *context){(void)context;sound_play(17,npc_voice_key,0);}
static void npc_voice_stop(void *context){(void)context;sound_channel_stop(17);}
static bool object_probe(void *context,int layer,int x,int y,unsigned mode){
 (void)context;return body_map_probe((void *)scene_collision_map(),layer,x,y,mode);
}
static void object_ambient(int x,int y,int channel,void *context){
 (void)context;enemy_ambient_contribute(&ambient,x,y,(unsigned)channel);
}
static void enemy_spawn(const GameEntity *owner,float x,float y,float vx,float vy,void *context){
 (void)context;size_t count;GameEntity *objects=scene_entities(&count);
 for(size_t i=0;i<count;i++)if(owner==&objects[i]){unsigned id=entity_id(owner);
  if(id==5)enemy_shots_spawn((uint32_t)i+1,x,y,vx,vy);
  else{EnemyShot shot;if(world_enemy_shot_init(&shot,id,(uint32_t)i+1,x,y,vx,vy))enemy_shots_spawn_record(&shot);}
  return;}
}
/* Native433662..4336da: viewport expanded350px, or persistent flag184. */
static bool entity_needs_update(size_t index,const GameEntity *entity){
 if(!entity_active(entity))return false;
 unsigned layer=entity_layer(entity);if(layer>=8)return false;
 int cx=camera_x(&camera,(int)layer),cy=camera_y(&camera,(int)layer);
 return scene_entity_update_region(index,cx,cy);
}
/* Native433907..4339de revalidates active/frame/region after callbacks,
 * before changing blink bytes45/46; hidden byte185 gates drawing later. */
static void world_entity_visual_step(size_t index){
 size_t count;GameEntity *objects=scene_entities(&count);
 if(index<count&&entity_needs_update(index,objects+index))scene_entity_visual_step(index);
}
static int boss_projectiles(int x,int y,int width,int height,int flags,void *context){
 (void)context;return projectiles_hit(&shots,x,y,width,height,(unsigned)flags);
}
static int factory_projectiles(int x,int y,int w,int h,unsigned flags,void *context){return boss_projectiles(x,y,w,h,(int)flags,context);}
static int16_t boss_sample(unsigned global){return sound_key_handle(sound_global_key(native_world,global));}
static EnemyShot *boss_allocate(void *context){(void)context;return enemy_shots_free_slot();}
static GameEntity *boss_object_at(unsigned index,void *context){
 (void)context;size_t count;GameEntity *objects=scene_entities(&count);return index<count?objects+index:NULL;
}
static bool boss_audio_load(unsigned key,int channel,void *context){
 (void)context;return sound_play((unsigned)channel,key,0);
}
static bool boss_audio_active(int channel,void *context){(void)context;return sound_channel_active((unsigned)channel);}
static void boss_audio_volume(int channel,int volume,void *context){
 (void)context;if((unsigned)channel<19)boss_volumes[channel]=volume;
 sound_channel_volume((unsigned)channel,volume);
}
static void boss_audio_stop(int channel,void *context){(void)context;sound_channel_stop((unsigned)channel);}
static void boss_audio_play(int channel,int sample,int repeat,void *context){
 (void)context;if(sound_play((unsigned)channel,(unsigned)sample,(unsigned)repeat)&&(unsigned)channel<19)
  sound_channel_volume((unsigned)channel,boss_volumes[channel]);
}
static bool factory_voice_load(unsigned key,void *context){(void)context;boss_voice_key=key;return sound_key_handle(key)!=0;}
static bool factory_voice_active(void *context){(void)context;return sound_channel_active(18);}
static void factory_play(int channel,int volume,void *context){
 boss_audio_volume(channel,volume,context);
 if(channel==18)boss_audio_play(channel,(int)boss_voice_key,0,context);
}
static MountainJungleBossEnvironment mountain_environment(EntityGlobals *state,uint32_t handle){
 MountainJungleBossEnvironment e={.health=&boss_energy,.score=&state->score,.defeated=&boss_defeated,
  .ice_trigger_bits=&ice_trigger_bits,.ice_block_state=&ice_block_state,.collapse_trigger=&collapse_trigger,.yeti_hit=&yeti_hit,
  .contact=enemy_contact,.projectiles=boss_projectiles,.random=enemy_random,
  .audio_load=boss_audio_load,.audio_active=boss_audio_active,.audio_volume=boss_audio_volume,
  .audio_stop=boss_audio_stop,.audio_play=boss_audio_play,.allocate_shot=boss_allocate,
  .entity_handle=handle,.object_at=boss_object_at,.context=state,
  .gorilla_walk=boss_sample(0x4dac56),.gorilla_hit=boss_sample(0x4dac46),
  .yeti_hit_sample=boss_sample(0x4dac54),.yeti_land=boss_sample(0x4e0aa4),.gorilla_reflect=boss_sample(0x4dac3c)};
 return e;
}
typedef struct {EntityGlobals *state;BossValleyShot *slot;} ValleyBridge;
static int32_t valley_service(uint32_t address,const int32_t *a,unsigned count,void *context){
 ValleyBridge *bridge=context;
 switch(address){
 case 0x41a3e0:return count==5?enemy_contact(a[0],a[1],a[2],a[3],a[4],bridge->state):0;
 case 0x41a5e0:return count==5?boss_projectiles(a[0],a[1],a[2],a[3],a[4],bridge->state):0;
 case 0x412e20:if(count==3)enemy_score_popup(a[0],a[1],a[2],NULL);return 0;
 case 0x4395b0:return enemy_random(NULL);
 case 0x410fb0:return bridge->slot!=NULL;
 case 0x422b60:if(count==3)boss_audio_play(a[0],a[1],a[2],NULL);return 0;
 case 0x422e04:if(count==1)boss_audio_stop(a[0],NULL);return 0;
 case 0x4231e5:return count==1&&boss_audio_active(a[0],NULL);
 case 0x4243b1:return count==4&&boss_audio_load((unsigned)a[0],a[1],NULL)?0:-1;
 case 0x42339e:if(count==2)boss_audio_volume(a[0],a[1],NULL);return 0;
 case 0x434180:return count==3?map_tile_solid(scene_collision_map(),a[0],a[1],a[2]):0;
 case 0x434200:return count==3?(int32_t)map_tile_property(scene_collision_map(),a[0],a[1],a[2]):0;
 case 0x412bf0:return count==2&&enemy_shot_obstacle(NULL,a[0],a[1]);
 /* The translated body performs range/reset and full slot initialization. */
 case 0x430b20:case 0x40adc0:case 0x41a8c0:return 0;
 default:return 0;
 }
}
static BossValleyEnvironment valley_environment(ValleyBridge *bridge,uint32_t handle){
 BossValleyEnvironment v={.player_x=body.motion.x/4096,.player_y=body.motion.y/4096,
  .hit_sound=enemy_hit_sound,.fall_sound=enemy_fall_sound,.bear_idle_sound=boss_sample(0x4dabcc),
  .bear_throw_sound=boss_sample(0x4dac6e),.octopus_sound=boss_sample(0x4dac6c),.octopus_throw_sound=boss_sample(0x4e0afc),
  .owner_handle=handle,.shot=bridge->slot,.service=valley_service,.context=bridge};return v;
}
static bool boss_ranges(size_t index,int16_t ranges[19][2]){
 for(unsigned range=0;range<19;range++)if(!scene_enemy_animation_range(index,range,&ranges[range][0],&ranges[range][1]))return false;
 return true;
}
static void tick_boss(size_t index,GameEntity *object,EntityGlobals *state){
 unsigned id=entity_id(object);uint32_t handle=(uint32_t)index+1;
 if(id==9||id==10){
  MountainJungleBossEnvironment v=mountain_environment(state,handle);
  if(!boss_ranges(index,v.ranges))return;
  entity_advance_animation(object,0);boss_mountain_jungle_tick(object,&v);
 }else if(id==14){
  size_t count;GameEntity *objects=scene_entities(&count);
  FactoryBossEnvironment v={.player_x=body.motion.x/4096,.player_y=body.motion.y/4096,
   .pipe=pipe_entity&&pipe_entity<=count?objects+pipe_entity-1:NULL,.health=&boss_energy,.defeated=&boss_defeated,.score=&state->score,
   .shot_sample=boss_sample(0x4dbc6a),.beam_sample=boss_sample(0x4e0afe),.hit_sample=enemy_hit_sound,
   .death_loop_sample=boss_sample(0x4dac58),.death_sample=boss_sample(0x4dac44),.owner_handle=handle,
   .contact=enemy_contact,.projectile=factory_projectiles,
   .random=enemy_random,.allocate=boss_allocate,.voice_load=factory_voice_load,.voice_active=factory_voice_active,
   .play=factory_play,.stop=boss_audio_stop,.sound=boss_audio_play,.context=state};
  if(!scene_enemy_animation_range(index,1,&v.intro_first,&v.intro_last)||
     !scene_enemy_animation_range(index,17,&v.freeze_first,&v.freeze_last)||
     !scene_enemy_animation_range(index,18,&v.death_first,&v.death_last))return;
  entity_advance_animation(object,0);boss_factory_tick(object,&v);
 }else{
  ValleyBridge bridge={state,(BossValleyShot *)enemy_shots_free_slot()};
  BossValleyEnvironment v=valley_environment(&bridge,handle);if(!boss_ranges(index,v.ranges))return;
  BossValleyGlobals globals={state->score,boss_energy,boss_defeated};
  entity_advance_animation(object,0);
  if(id==15)boss_valley_bear_tick(object,&globals,&v);else boss_valley_octopus_tick(object,&globals,&v);
  state->score=globals.score;boss_energy=globals.boss_energy;boss_defeated=globals.completed;
 }
 world_entity_visual_step(index);
}
static void world_shot_callback(EnemyShot *shot,const EnemyShotEnvironment *environment){
 if(shot->callback==0x412dd0)enemy_score_popup_tick(shot);
 else if(shot->callback==0x413b70)enemy_shot_callback(shot,environment);
 else if(shot->callback==0x40d5c0){
  ProjectileEnvironment terrain={.solid=environment->solid,.property=environment->property,.context=environment->context};
  boss_factory_shot_tick(shot,&terrain,environment->contact,environment->context);
 }else if(shot->callback==0x40c2c0){
  size_t count;GameEntity *objects=scene_entities(&count);
  if(!shot->opaque04||shot->opaque04>count){shot->active=0;return;}
  EntityGlobals state={.health=player.health};MountainJungleBossEnvironment v=mountain_environment(&state,shot->opaque04);
  boss_gorilla_shot_tick(shot,objects+shot->opaque04-1,&v,environment);
 }else if(shot->callback==0x40cc60){
  EntityGlobals state={.health=player.health};ValleyBridge bridge={&state,NULL};BossValleyEnvironment v=valley_environment(&bridge,shot->opaque04);
  boss_valley_shot_tick((BossValleyShot *)shot,&v);
 }else world_enemy_shot_callback(shot,environment);
}
static void tick_entities(void){
 size_t count;GameEntity *objects=scene_entities(&count);
 EntityGlobals state={.score=hud.score,.health=player.health,.ammo=player.inventory,.shoot_latch=player.projectile_variant};
 for(unsigned i=0;i<6;i++)state.letters[i]=(uint16_t)hud.letters[i];
 for(size_t selected=0;selected<tick_count;selected++){
  entity_profile_begin();
  size_t i=tick_indices[selected];if(i>=count)continue;
  unsigned id=entity_id(&objects[i]);
  bool eligible=entity_active(&objects[i])&&entity_needs_update(i,&objects[i]);entity_profile_lap(0);
  if(!eligible)continue;
  if(id==9||id==10||id==14||id==15||id==18){tick_boss(i,objects+i,&state);entity_profile_lap(6);continue;}
  if(id!=77&&world_object_supported(id)){
   EntityEnvironment resource={0};if(!scene_entity_environment(i,&resource))continue;
   GameBody *bodies[1]={&body};
   WorldObjectEnvironment environment={.width=resource.width,.height=resource.height,
    .first=resource.first,.last=resource.last,.player_x=body.motion.x/4096,.player_y=body.motion.y/4096,
    .switch_flags=switch_flags,.ice_trigger_bits=&ice_trigger_bits,.ice_block_state=&ice_block_state,
    .collapse_trigger=&collapse_trigger,.pipe_entity=&pipe_entity,.entity_handle=(uint32_t)i+1,
    .bodies=bodies,.body_count=1,.probe=object_probe,.tile=block_tile,.damage=enemy_contact,
    .random=enemy_random,.ambient=object_ambient,.sound=block_sound,.context=&state,
    .clamp_sample=clamp_sound,.pipe_sample=pipe_sound,.crumble_sample=crumble_sound,
    .score_popup=enemy_score_popup,.pickup_globals=&state,.snowballs_available=&state.shoot_latch,
    .boss_defeated=boss_defeated,.seventh_item_state=&player.death_actor,.finish_timer=&finish_timer};
   if(!scene_enemy_animation_range(i,17,&environment.frozen_first,&environment.frozen_last))continue;
   entity_advance_animation(&objects[i],0);world_object_tick(&objects[i],&environment);
   world_entity_visual_step(i);entity_profile_lap(1);continue;
  }
  if(id==77){
   EntityEnvironment resource={0};if(!scene_entity_environment(i,&resource))continue;
   WorldObjectEnvironment environment={.width=resource.width,.height=resource.height,
    .first=resource.first,.last=resource.last,.player_x=body.motion.x/4096,.player_y=body.motion.y/4096,
    .progress_flag=player.character,.world=(int32_t)native_world,.dialogue_state=&player.fatal,
    .voice_load=npc_voice_load,.voice_active=npc_voice_active,.voice_play=npc_voice_play,.voice_stop=npc_voice_stop,
    .completion_flags=game_save_state()->tutorials,.target_world=&transition_target,.game_mode=&player.game_mode};
   if(!scene_enemy_animation_range(i,17,&environment.frozen_first,&environment.frozen_last)||
      !scene_enemy_animation_range(i,16,&environment.talking_first,&environment.talking_last))continue;
   entity_advance_animation(&objects[i],0);world_object_tick(&objects[i],&environment);
   world_entity_visual_step(i);entity_profile_lap(1);continue;
  }
  if(block_id(id)){
   EntityEnvironment resource={0};if(!scene_entity_environment(i,&resource))continue;
   BlockEnvironment environment={.width=resource.width,.height=resource.height,.first=resource.first,.last=resource.last,
    .tile=block_tile,.projectiles=block_projectiles,.sound=block_sound,.switch_flags=switch_flags,.switch_sample=switch_sound};
   entity_advance_animation(&objects[i],0);
   if(id==83)block_switch_tick(&objects[i],&environment);else block_physical_tick(&objects[i],&environment);
   world_entity_visual_step(i);entity_profile_lap(2);continue;
  }
  if(spring_id(id)){
   GeometryObject bounds;if(!scene_geometry_object(i,&bounds))continue;
   GameBody *bodies[1]={&body};PlatformEnvironment platform={.width=bounds.width,
    .bodies=bodies,.body_count=1,.probe=body_map_probe,.context=(void *)scene_collision_map()};
   entity_advance_animation(&objects[i],0);platform_spring_tick(&objects[i],&platform);
   world_entity_visual_step(i);entity_profile_lap(3);continue;
  }
  if((id>=3&&id<=8)||(id>=11&&id<=13)||id==16||id==17){
   EnemyEnvironment environment={.contact=enemy_contact,.projectile=enemy_projectile,.popup=enemy_score_popup,
    .context=&state,.player_x=body.motion.x/4096,.player_y=body.motion.y/4096,
    .random=enemy_random,.allocate=enemy_allocate,.spawn=enemy_spawn,.sound=enemy_sound,
    .hit_sound=enemy_hit_sound,.fall_sound=enemy_fall_sound,
    .throw_sound=id==3?parrot_sound:id==6?eagle_sound:id==11?robot_charge_sound:id==12?egg_throw_sound:kong_throw_sound};
   if(!scene_enemy_environment(i,&environment))continue;
   entity_advance_animation(&objects[i],0);
   if(id==3)enemy_parrot_callback(&objects[i],&state,&environment);
   else if(id==4)enemy_snake_callback(&objects[i],&state,&environment);
   else if(id==5)enemy_kong_callback(&objects[i],&state,&environment);
   else if(id==6)enemy_eagle_callback(&objects[i],&state,&environment);
   else if(id==7)enemy_small_yeti_callback(&objects[i],&state,&environment);
   else if(id==8)enemy_snowman_callback(&objects[i],&state,&environment);
   else if(id==11)enemy_small_robot_callback(&objects[i],&state,&environment);
   else if(id==12)enemy_egg_robot_callback(&objects[i],&state,&environment);
   else if(id==17)enemy_small_octopus_callback(&objects[i],&state,&environment);
   else{
    GeometryObject current;EntityEnvironment first={0};
    if(scene_geometry_object(i,&current)&&scene_entity_environment(i,&first)){
     WorldEnemyEnvironment sized={.enemy=environment,.frame_width=current.width,.frame_height=current.height,
      .base_width=first.width,.base_height=first.height,.ambient=object_ambient};
     if(id==13)enemy_flying_robot_callback(&objects[i],&state,&sized);
     else enemy_bee_callback(&objects[i],&state,&sized);
    }
   }
   world_entity_visual_step(i);entity_profile_lap(4);continue;
  }
  if(id<48||id>58)continue;
  EntityEnvironment environment={.overlap=pickup_overlap,.popup=enemy_score_popup};
  if(!scene_entity_environment(i,&environment))continue;
  entity_advance_animation(&objects[i],0);
  entity_pickup_callback(&objects[i],&state,&environment);
  world_entity_visual_step(i);
  entity_profile_lap(5);
 }
 hud.boss_energy=boss_energy;hud.score=state.score;player.health=state.health;player.inventory=state.ammo;player.projectile_variant=state.shoot_latch;
 for(unsigned i=0;i<6;i++)hud.letters[i]=(int16_t)state.letters[i];
 if(state.pickup_sound)sound_play(2,pickup_sound_key,0);
}
static int32_t climb_probe(void *context,int query,int x,int y){
 const CollisionMap *map=context;
 switch(query){
 case PLAYER_PROBE_TILE_SOLID:return map_tile_solid(map,2,x,y);
 case PLAYER_PROBE_TILE_PROPERTY:return (int32_t)map_tile_property(map,2,x,y);
 case PLAYER_PROBE_CONTACT:return body_has_contact(&body,world_probe,context);
 case PLAYER_PROBE_LADDER:{PlayerEnvironment e={.climb_probe=climb_probe,.context=context};return player_ladder_at(&e,x,y);}
 default:return 0;
 }
}
bool world_tick(unsigned keys){
 if(!ready)return false;
 update_profile_begin();
 const CollisionMap *map=scene_collision_map();
 rebuild_geometry();
 player_death_tick(&player);
 update_profile_lap(0);
 if(player.game_mode==2||player.game_mode==20)return true;
 if(!ambient_started){
  for(unsigned channel=0;channel<16;channel++)if(ambient_keys[channel]){
   sound_play(channel,ambient_keys[channel],255);sound_channel_volume(channel,-100);
  }
  ambient_started=true;
 }
 keys=player_filter_input(&player,&body,keys,player.health!=0);
 player_environment=(PlayerEnvironment){.grounded=body_has_contact(&body,world_probe,(void *)map),
  .context=(void *)map,.climb_probe=climb_probe,.random=world_random,.particle=effects_particle,.projectile=shoot,.world_stage=(int32_t)native_world,
  .event=player_audio_event,.voice_active=sound_channel_active(17),.sound_load_ok=false};
 player_environment.push_query=push_query;player_environment.push_resolve=push_resolve;player_environment.push_velocity=push_velocity;
 player_environment.milk_obstacle=geometry_query(nearby_geometry,geometry_count,body.motion.x/4096+(player.facing?-32:32),body.motion.y/4096-100,5)!=0;
 player_environment.ladder=player_ladder_at(&player_environment,body.motion.x/4096,body.motion.y/4096);
 if(!player_dispatch(&player,&body,&keys,&player_environment))return false;
 update_profile_lap(1);
 int tx=(body.motion.x/4096)/32,ty=(body.motion.y/4096)/32;
 bool present=tx>=0&&ty>=0&&tx<map->width&&ty<map->height;
 const uint8_t *cell=present?collision_cell(map,2,(unsigned)tx,(unsigned)ty):NULL;
 player_tile_hazard(&player,&body,present,cell?cell[0]:0,cell?(uint16_t)(cell[1]|cell[2]<<8):0xffff,&player_environment);
 body.platform_dx=body.platform_dy=0;body_step(&body,world_probe,(void *)map);
 geometry_count=0; /* Native419dbb clears geometry before object callbacks. */
 player_sync_facing(&player);
 animation_tick(player.character?&player.milk:&player.penguin,NULL,NULL);
 update_profile_lap(2);
 ProjectileEnvironment shot_environment={.solid=shot_solid,.property=shot_property,.context=(void *)map};
 projectiles_tick(&shots,&shot_environment);
 player_visible=player_blink_tick(&player);blink_advanced=true;
 camera_follow(&camera,body.motion.x/4096,body.motion.y/4096,player.facing,camera_locked);
 if(!player_damage_effects_tick(&player,&body,&player_environment))return false;
 EnemyShotEnvironment enemy_shot_environment={.solid=enemy_shot_solid,.property=enemy_shot_property,
  .obstacle=enemy_shot_obstacle,.contact=enemy_contact,.context=NULL};
 enemy_shots_tick_with(&enemy_shot_environment,world_shot_callback);
 update_profile_lap(3);
 enemy_ambient_reset(&ambient,-camera_x(&camera,2),-camera_y(&camera,2));
 tick_entities();
 update_profile_lap(4);
 end_title.action=player.death_actor;end_title_tick(&end_title);player.death_actor=end_title.action;
 if(native_world<4&&player.game_mode!=20){
  int target=world_arena_target(native_world,hud.letters);
  if(target>=0){transition_target=target;player.game_mode=20;}
 }
 if(finish_timer){finish_timer=(int32_t)((uint32_t)finish_timer-1);if(!finish_timer)player.game_mode=2;}
 for(unsigned channel=0;channel<16;channel++)if(ambient_keys[channel])
  sound_channel_volume(channel,enemy_ambient_volume(&ambient,channel));
 update_profile_lap(5);
 return true;
}
bool world_render(uint16_t *pixels){
 if(!ready)return false;
 gpu_actors_reset();
 player_render_visible=player_blink_present(&blink_view,&player,player_visible,blink_advanced);blink_advanced=false;
 int cx[8],cy[8];for(int i=0;i<8;i++){cx[i]=camera_x(&camera,i);cy[i]=camera_y(&camera,i);}
 graphics_ok=true;
 if(!scene_render_layers(pixels,cx,cy)||!graphics_ok)return false;
 return enemy_shots_draw(pixels,camera_x(&camera,2),camera_y(&camera,2))&&end_title_draw(&end_title,pixels);
}
bool world_render_hud(uint16_t *pixels,bool force){
 if(!ready)return false;
 hud.health=player.health;hud.ammo=player.inventory;hud.actor=player.switch_available;
 hud.shot_variant=player.projectile_variant;
 if(!force&&hud_rendered&&!memcmp(&hud,&rendered_hud,sizeof(hud)))return false;
 hud_draw_bottom(pixels,&hud);rendered_hud=hud;hud_rendered=true;return true;
}

#include <stddef.h>
_Static_assert(offsetof(Player,death_actor)==316,"RSP banner fixture ABI");
_Static_assert(sizeof(EndTitle)==20,"RSP title fixture ABI");

/* Reference redraw advances no physics and preserves the prepared atlas. The
 * presentation blink helper already guards repeated draws of one update. */
