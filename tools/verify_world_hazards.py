"""Real-map object-stage bindings: conveyor, crumbling platform, switches/pipe and ammo.
Host fixtures place the player/set switch flags; this is not an arena playthrough.
"""
import ctypes as C,json,os,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];out=Path(os.environ.get('KF_SCENE_OUTPUT_ROOT',str(R/'ds/nitrofs/scenes')))
with tempfile.TemporaryDirectory(prefix='kinder-hazard-bindings-') as temporary:
 t=Path(temporary);wrapper=t/'world.c'
 wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
static size_t target_object;
int test_arena(unsigned base){return open_route(base+4,world_route_select(base+4,NULL));}
int test_select(unsigned id){
 size_t n;GameEntity*e=scene_entities(&n);
 for(size_t i=0;i<n;i++)if(entity_id(e+i)==id&&entity_active(e+i)&&entity_x(e+i)>=0){
  EntityEnvironment r={0};if(!scene_entity_environment(i,&r))return 0;target_object=i;
  int x=entity_x(e+i)+r.width/2,y=entity_y(e+i)+e[i].bytes[42];
  body.motion.x=x*4096;body.motion.y=y*4096;body.motion.vx=body.motion.vy=0;
  player.health=100;player.penguin.opaque_5c=0;
  const SceneMetadata*m=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};
  camera_init(&camera,m->width_cells,m->height_cells,x-400,y-300,f,2);return 1;
 }
 return 0;
}
int test_word(unsigned offset){size_t n;GameEntity*e=scene_entities(&n);int16_t v;memcpy(&v,e[target_object].bytes+offset,2);return v;}
int test_byte(unsigned offset){size_t n;GameEntity*e=scene_entities(&n);return e[target_object].bytes[offset];}
int test_body_x(void){return body.motion.x;}int test_ammo(void){return player.inventory;}
int test_variant(void){return player.projectile_variant;}
void test_empty_ammo(void){player.inventory=0;}
void test_flags(int value){switch_flags[0]=switch_flags[1]=switch_flags[2]=(uint8_t)value;}
int test_flag_sum(void){return switch_flags[0]+switch_flags[1]+switch_flags[2];}
void test_tick(void){tick_entities();}
void test_leave(void){body.motion.x+=4000*4096;}
void test_ammo_position(void){size_t n;GameEntity*e=scene_entities(&n);EntityEnvironment r={0};scene_entity_environment(target_object,&r);body.motion.y=(entity_y(e+target_object)+r.height)*4096;}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':out,'PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"' for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=C.c_bool;cases=[]
 assert c.world_open_stage(2,False) and c.test_select(82)
 x=c.test_body_x();speed=c.test_byte(40)-128;c.test_tick()
 assert speed and c.test_body_x()!=x,('conveyor',speed,c.test_body_x()-x)
 cases.append({'conveyor_speed':speed,'body_displacement_fixed':c.test_body_x()-x});c.world_close()
 assert c.world_open_stage(3,False) and c.test_select(414)
 c.test_tick();assert c.test_word(98)==1
 for _ in range(30):c.test_tick()
 assert c.test_byte(26)==0 and c.test_word(98)==2
 c.test_leave()
 for _ in range(180):c.test_tick()
 assert c.test_byte(26)==1 and c.test_word(98)==0
 cases.append({'crumbling_platform_collapses_and_respawns':True});c.world_close()
 assert c.test_arena(2) and c.test_select(85)
 c.test_tick();c.test_flags(1);c.test_tick();assert c.test_word(98)==2
 for _ in range(100):c.test_tick()
 assert c.test_flag_sum()==0 and c.test_word(98)==1
 cases.append({'pipe_shared_switch_trigger_and_reset':True});c.world_close()
 assert c.test_arena(1) and c.test_select(60)
 c.test_empty_ammo();c.test_ammo_position();c.test_tick();c.test_tick()
 assert c.test_ammo()==10 and c.test_variant()==1 and c.test_word(98)==2
 cases.append({'ammo_and_snowball_flag_connected':True});c.world_close()
 result={'scope':__doc__,'asset_root':str(out),'cases':cases,'limits':['Fixtures invoke the production object stage on original maps; world scheduling and full keyboard-driven traversal are separate checks.','Arena fixtures use the production arena context; complete boss gameplay has separate coverage.']}
 (R/'research/gameplay/world_hazard_integration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
