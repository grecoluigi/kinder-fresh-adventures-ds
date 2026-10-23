"""Real-world production scheduling of damage timers and mirror sync.
Host contact fixtures at original spawn positions; not a level playthrough.
"""
from pathlib import Path
import ctypes as C,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-world-tail-')as tmp:
 t=Path(tmp);w=t/'world.c';w.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
bool test_damage(void){
 const SceneMetadata*m=scene_metadata();body.motion.x=m->start_x*4096;body.motion.y=m->start_y*4096;
 player.health=100;player.character=0;player.facing=1;player.state=0;
 int x=m->start_x,y=m->start_y;
 for(unsigned part=0;part<3;part++){
  player.penguin.opaque_5c=0;
  int level=part==0?25:part==1?100:160;
  if(!player_rect_hazard(&player,&body,x-5,y-level-5,10,10,1,&player_environment))return false;
 }
 return player.hit_feet==5&&player.hit_middle==5&&player.hit_head==5&&player.health==97;
}
int test_timer(unsigned part){return part==0?player.hit_feet:part==1?player.hit_middle:player.hit_head;}
int test_mirror(void){return player.penguin.opaque_50==player.milk.opaque_50&&player.penguin.opaque_50==(player.facing?0u:2u);}
void test_no_op(void){player.state=26;}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"'for k,v in defs.items()],str(w),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=c.test_damage.restype=C.c_bool;cases=[]
 for world in range(8):
  assert c.world_open_stage(world,False);assert c.test_damage(),world
  for tick in range(5):
   assert c.world_tick(0);assert [c.test_timer(i)for i in range(3)]==[4-tick]*3,(world,tick)
   assert c.test_mirror()
  c.test_no_op();assert c.world_tick(0) and c.world_player_state()==26
  c.world_close();cases.append({'world':world,'contact_timers_drain_in_five_updates':True,'mirror_sync':True,'no_op_state_keeps_simulation_running':True})
 result={'scope':__doc__,'worlds':cases}
 (R/'research/gameplay/world-player-tail-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
