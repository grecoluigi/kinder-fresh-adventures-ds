"""Production arenas/boss bindings, shared health/pipe/ice, voices, projectiles, prize.
Fixtures complete damage-animation boundaries and inject attack frames. They are
not keyboard-driven boss fights, full gameplay, hardware timing or audible proof.
"""
import ctypes as C,json,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-boss-bindings-') as temporary:
 t=Path(temporary);wrapper=t/'world.c'
 wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
static size_t target;
static void test_set16(GameEntity*e,unsigned off,int value){int16_t n=(int16_t)value;memcpy(e->bytes+off,&n,2);}
static void test_set32(GameEntity*e,unsigned off,int32_t value){memcpy(e->bytes+off,&value,4);}
static void test_float(GameEntity*e,unsigned off,float value){memcpy(e->bytes+off,&value,4);}
static GameEntity *test_target(void){size_t n;GameEntity*e=scene_entities(&n);return e+target;}
static void test_camera(int x,int y){const SceneMetadata*m=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};camera_init(&camera,m->width_cells,m->height_cells,x-400,y-300,f,2);}
int test_select(unsigned id){size_t n;GameEntity*e=scene_entities(&n);for(size_t i=0;i<n;i++)if(entity_id(e+i)==id&&entity_active(e+i)){target=i;if(!active_route->arena)test_camera(entity_x(e+i),entity_y(e+i));body.motion.x=body.motion.y=0;return 1;}return 0;}
void test_ingredients(void){hud.score=321;for(unsigned i=0;i<6;i++)hud.letters[i]=1;}
int test_score(void){return hud.score;}int test_energy(void){return boss_energy;}
int test_defeated(void){return boss_defeated;}int test_finish_timer(void){return finish_timer;}
int test_snowballs(void){return player.projectile_variant;}int test_switch(void){return player.switch_available;}
int test_camera_locked(void){return camera_locked;}
int test_geometry_layer(void){return (int)geometry_layer;}
int test_hidden_markers(void){size_t n;GameEntity*e=scene_entities(&n);for(size_t i=0;i<n;i++)if(entity_id(e+i)==1000&&entity_active(e+i))return 0;return 1;}
void test_tick(void){tick_entities();}
int test_state(void){int16_t n;memcpy(&n,test_target()->bytes+98,2);return n;}
void test_contact(void){GameEntity*e=test_target();int x=entity_x(e),y=entity_y(e);unsigned id=entity_id(e);x+=id==9?87:id==18?115:id==15?44:125;body.motion.x=x*4096;body.motion.y=(y+180)*4096;player.health=100;player.penguin.opaque_5c=0;}
int test_health(void){return player.health;}
int test_damage_cycle(void){
 GameEntity*e=test_target();unsigned id=entity_id(e);int16_t first,last;
 scene_enemy_animation_range(target,id==9?1:17,&first,&last);
 test_set16(e,98,id==9?100:101);test_set16(e,10,first);test_set16(e,12,last);test_set16(e,14,last);test_set16(e,18,1);e->bytes[184]=1;
 if(id==9){int32_t ground;memcpy(&ground,e->bytes+128,4);test_float(e,152,(float)ground);test_float(e,160,0);}
 body.motion.x=body.motion.y=0;tick_entities();return boss_energy;
}
void test_attack(void){
 GameEntity*e=test_target();unsigned id=entity_id(e);int frame=id==10?82:id==14?129:id==15?47:41;
 test_set16(e,98,id==10||id==15?10:id==14?11:2);test_set16(e,14,frame);test_set16(e,16,3);test_set16(e,18,4);
 if(id==14){test_set16(e,10,122);test_set16(e,12,138);test_set32(e,112,2);test_set32(e,116,25);}
 if(id==18){test_set32(e,116,60);test_set32(e,120,0);test_set32(e,124,0);}
 tick_entities();
}
unsigned test_shot_callback(void){const EnemyShot*p=enemy_shots_slots();for(unsigned i=0;i<200;i++)if(p[i].active)return p[i].callback;return 0;}
int test_shot_frame(void){const EnemyShot*p=enemy_shots_slots();for(unsigned i=0;i<200;i++)if(p[i].active)return p[i].frame;return -1;}
int test_gorilla_return(void){
 EnemyShot *p=(EnemyShot *)enemy_shots_slots();GameEntity *e=test_target();
 for(unsigned i=0;i<200;i++)if(p[i].active){p[i].x=(float)(entity_x(e)+70);p[i].y=(float)(entity_y(e)+21);p[i].vx=9;EnemyShotEnvironment env={.solid=enemy_shot_solid,.property=enemy_shot_property,.obstacle=enemy_shot_obstacle,.contact=enemy_contact};world_shot_callback(p+i,&env);break;}
 return test_state();
}
int test_factory_pipe(void){
 size_t n;GameEntity*e=scene_entities(&n);test_set16(test_target(),98,10);
 for(size_t i=0;i<n;i++)if(entity_id(e+i)==85){pipe_entity=(uint32_t)i+1;test_set16(e+i,4,entity_y(test_target()));break;}
 body.motion.x=body.motion.y=0;tick_entities();return test_state();
}
int test_yeti_ice(void){
 ice_block_state=1;GameEntity*e=test_target();test_set16(e,98,3);test_set16(e,14,32);test_set16(e,18,1);
 EntityGlobals state={.health=player.health};tick_boss(target,e,&state);return ice_block_state;
}
int test_prize(void){
 if(!test_select(59))return 0;GameEntity*e=test_target();
 body.motion.x=body.motion.y=0;
 unsigned steps=0;while(entity_y(e)<100&&steps++<180)tick_entities();
 if(entity_y(e)<100)return 0;
 EntityEnvironment dimensions={0};scene_entity_environment(target,&dimensions);
 body.motion.x=(entity_x(e)+dimensions.width/2)*4096;
 body.motion.y=(entity_y(e)+dimensions.height/2+50)*4096;tick_entities();
 return !entity_active(e)&&finish_timer==240;
}
int test_finish_tick(void){const SceneMetadata*m=scene_metadata();body.motion.x=m->start_x*4096;body.motion.y=m->start_y*4096;body.motion.vx=body.motion.vy=0;player.health=100;player.penguin.opaque_5c=120;world_tick(0);return finish_timer;}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"' for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open.restype=c.world_open_stage.restype=c.world_tick.restype=c.world_finished.restype=C.c_bool;c.sound_channel_active.argtypes=[C.c_uint];c.sound_channel_active.restype=C.c_bool;c.test_shot_callback.restype=C.c_uint32;cases=[]
 for base,id in enumerate([10,9,14,18]):
  assert c.world_open_stage(base,False);c.test_ingredients();assert c.world_tick(0);target=c.world_transition_target();assert target==base+4
  assert c.world_open(target);assert c.test_score()==321 and c.test_energy()==9 and c.test_snowballs()==0 and c.test_switch()==0 and c.test_camera_locked()==(0 if target==6 else 1)
  assert c.test_geometry_layer()==(1 if target==4 else 2) and c.test_hidden_markers()
  assert c.test_select(id);c.test_tick();assert c.test_state()==50 and c.sound_channel_active(18),(id,'voice/init',c.test_state())
  c.test_contact();c.test_tick();assert c.test_health()==80,(id,'contact',c.test_health())
  for cycle in range(10):assert c.test_damage_cycle()==8-cycle,(id,'damage',cycle,c.test_energy())
  assert c.test_defeated()==1 and c.test_score()==10321,(id,'defeat',c.test_score())
  assert c.test_prize() and c.test_score()==20321,(id,'prize',c.test_score(),c.test_finish_timer())
  for expected in range(239,-1,-1):assert c.test_finish_tick()==expected,(id,'finish timer',expected,c.test_finish_timer())
  assert c.world_finished();cases.append({'arena':target,'boss':id,'contact_damage':20,'voice_channel18_started':True,'damage_cycles':10,'score_carry':321,'defeat_score':10000,'prize_score':10000,'prize_timer_ticks':240});c.world_close()
 for world,id,callback,frame in [(4,10,0x40c2c0,87),(6,14,0x40d5c0,188),(7,18,0x40cc60,50),(3,15,0x413b70,53)]:
  assert (c.world_open(world) if world>=4 else c.world_open_stage(world,False)) and c.test_select(id)
  c.test_tick();c.test_attack();assert c.test_shot_callback()==callback and c.test_shot_frame()==frame,(id,'shot',hex(c.test_shot_callback()),c.test_shot_frame())
  if id==10:assert c.test_gorilla_return()==100
  cases.append({'owner':id,'shared_pool_callback':hex(callback),'sprite_frame':frame,'returned_gorilla_shot_hits_owner':id==10});c.world_close()
 assert c.world_open(6) and c.test_select(14);c.test_tick();assert c.test_factory_pipe()==100;cases.append({'factory_pipe_triggers_hurt':True});c.world_close()
 assert c.world_open(5) and c.test_select(9);c.test_tick();assert c.test_yeti_ice()==2;cases.append({'yeti_animation_updates_shared_ice_block_state':True});c.world_close()
 result={'scope':__doc__,'cases':cases,'limits':['Damage-cycle fixtures prove shared counter/defeat bindings, not that each fight is traversable with keyboard or DS controls.','The240-tick post-prize dispatch is connected; banners and completion highscores have separate native/host proofs. Full fights/endings and DS keyboard/FAT interaction remain unverified.']}
 (R/'research/bosses/world-integration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
