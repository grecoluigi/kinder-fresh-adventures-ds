"""Production real-map enemy stage: contact, freeze/rebuild, attacks/shared pool.
Fixtures position the player, inject a player projectile, or select an attack frame;
this proves bindings, not full traversal, DS timing, or audible playback.
"""
import ctypes as C,json,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-ordinary-bindings-') as temporary:
 t=Path(temporary);wrapper=t/'world.c'
 wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
static size_t target;
int test_select(unsigned id){
 size_t n;GameEntity *e=scene_entities(&n);
 for(size_t i=0;i<n;i++)if(entity_id(e+i)==id&&entity_active(e+i)&&entity_x(e+i)>=0){
  target=i;int x=entity_x(e+i),y=entity_y(e+i);
  body.motion.x=0;body.motion.y=0;player.health=100;player.penguin.opaque_5c=0;
  const SceneMetadata*m=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};
  camera_init(&camera,m->width_cells,m->height_cells,x-400,y-300,f,2);
  return 1;
 }
 return 0;
}
static GameEntity *test_entity(void){size_t n;GameEntity*e=scene_entities(&n);return e+target;}
int test_state(void){int16_t n;memcpy(&n,test_entity()->bytes+98,2);return n;}
int test_score(void){return hud.score;}int test_health(void){return player.health;}
void test_tick(void){tick_entities();}
void test_contact(void){
 GameEntity *e=test_entity();int x=entity_x(e),y=entity_y(e);unsigned id=entity_id(e);
 if(id==6){x+=90;y+=170;}else if(id==7){x+=60;y+=100;}else if(id==8){x+=75;y+=100;}
 else if(id==11){x+=60;y+=100;}else if(id==12){x+=56;y+=100;}else if(id==13){EntityEnvironment f={0};scene_entity_environment(target,&f);x+=f.width/2;y+=f.height/2+40;}
 else if(id==16){x+=44;y+=70;}else if(id==17){x+=75;y+=50;}
 body.motion.x=x*4096;body.motion.y=(y+50)*4096;
}
int test_hit(void){
 test_contact();int x=body.motion.x/4096,y=body.motion.y/4096-50;
 body.motion.x=body.motion.y=0;return projectiles_spawn(&shots,x,y,9,0,0);
}
int test_consumed(void){for(unsigned i=0;i<10;i++)if(shots.slots[i].active)return 0;return 1;}
void test_attack(unsigned id){
 GameEntity*e=test_entity();int16_t state=10,frame=id==7?19:id==8?32:14;
 memcpy(e->bytes+98,&state,2);memcpy(e->bytes+14,&frame,2);
 int16_t delay=3;memcpy(e->bytes+16,&delay,2);delay=4;memcpy(e->bytes+18,&delay,2);
}
unsigned test_child_callback(void){const EnemyShot*p=enemy_shots_slots();for(unsigned i=0;i<200;i++)if(p[i].active)return p[i].callback;return 0;}
int test_child_frame(void){const EnemyShot*p=enemy_shots_slots();for(unsigned i=0;i<200;i++)if(p[i].active)return p[i].frame;return -1;}
int test_child_contact(void){
 const EnemyShot*p=enemy_shots_slots();for(unsigned i=0;i<200;i++)if(p[i].active){body.motion.x=((int)p[i].x+10)*4096;body.motion.y=((int)p[i].y+30)*4096;break;}
 player.health=100;player.penguin.opaque_5c=0;
 EnemyShotEnvironment env={.contact=enemy_contact};enemy_shots_tick_with(&env,world_shot_callback);return player.health;
}
int test_child_active(void){const EnemyShot*p=enemy_shots_slots();for(unsigned i=0;i<200;i++)if(p[i].active)return 1;return 0;}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"' for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=C.c_bool;c.test_child_callback.restype=C.c_uint32;cases=[]
 for world,ids in [(1,[6,7,8]),(2,[11,12,13]),(3,[16,17])]:
  for id in ids:
   assert c.world_open_stage(world,False) and c.test_select(id),id
   c.test_tick();assert c.test_state()==1,(id,'initial',c.test_state())
   c.test_contact();c.test_tick();assert c.test_health()==80,(id,'contact',c.test_health())
   assert c.test_hit();score=c.test_score();c.test_tick()
   assert c.test_state()==100 and c.test_consumed(),(id,'freeze',c.test_state())
   assert c.test_score()-score==(0 if id==8 else 100),(id,'score')
   if id==8:
    for _ in range(300):c.test_tick()
    assert c.test_state()<100,(id,'rebuild',c.test_state())
   cases.append({'world':world,'id':id,'contact_damage':20,'hit_consumes_projectile':True,'score':c.test_score()-score,'snowman_rebuild_checked':id==8});c.world_close()
 for world,id,callback,frame in [(1,7,0x41b770,25),(1,8,0x41a910,54),(2,12,0x40fd70,23)]:
  assert c.world_open_stage(world,False) and c.test_select(id)
  c.test_tick();c.test_attack(id);c.test_tick()
  assert c.test_child_callback()==callback and c.test_child_frame()==frame,(id,hex(c.test_child_callback()),c.test_child_frame())
  assert c.test_child_contact()==80 and not c.test_child_active(),(id,'projectile_damage')
  cases.append({'owner':id,'shared_pool_callback':hex(callback),'frame':frame,'shot_contact_damage':20});c.world_close()
 result={'scope':__doc__,'cases':cases,'limits':['Attack-frame fixtures do not verify enemy approach/navigation; callback and trajectory native proofs remain separate.','Pool contact uses production dispatch with a contact-only fixture environment; tile/obstacle services have separate native/real-map coverage.']}
 (R/'research/enemies/ordinary-world-integration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
