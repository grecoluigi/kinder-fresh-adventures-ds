"""Integrated original-map water damage, death timeout, climbing, letter pickup and shooting checks.
Host wrappers expose state only for these checks; no test hooks enter the ROM.
"""
import ctypes as C,json,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-interactions-') as tmp:
 p=Path(tmp);wrapper=p/'world_probe.c'
 wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'
 'void test_place(int x,int y){body.motion.x=x*4096;body.motion.y=y*4096;body.motion.vx=body.motion.vy=0;}\n'
 'int test_health(void){return player.health;}\n'
 'int test_y(void){return body.motion.y/4096;}\n'
 'int test_immunity(void){return (player.character?player.milk:player.penguin).opaque_5c;}\n'
 'int test_score(void){return hud.score;}\n'
 'int test_letter(void){return hud.letters[0];}\n'
 'int test_ammo(void){return player.inventory;}\n'
 'int test_shots(void){int n=0;for(int i=0;i<10;i++)if(shots.slots[i].active)n++;return n;}\n'
 'int test_pickup(int id){size_t n;GameEntity *o=scene_entities(&n);for(size_t i=0;i<n;i++)if(entity_id(&o[i])==id){EntityEnvironment e={0};if(!scene_entity_environment(i,&e))return -1;test_place(entity_x(&o[i])+e.width/2,entity_y(&o[i])+e.height);return (int)i;}return -1;}\n'
 'int test_popups(void){int n=0;const EnemyShot*s=enemy_shots_slots();for(int i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(s[i].active&&s[i].callback==0x412dd0&&s[i].frame==1)n++;return n;}\n'
 'int test_active(int i){size_t n;GameEntity *o=scene_entities(&n);return i>=0&&(size_t)i<n&&entity_active(&o[i]);}\n'
 'void test_clear_immunity(void){player.milk.opaque_5c=player.penguin.opaque_5c=0;}\n')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 so=p/'probe.dylib'
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DSCENE_ROOT="{R}/ds/nitrofs/scenes"',f'-DPLAYER_ROOT="{R}/ds/nitrofs/players"',f'-DHUD_PATH="{R}/ds/nitrofs/hud_bottom.bin"',f'-DPROJECTILE_ROOT="{R}/ds/nitrofs/projectiles"',f'-DENEMY_SHOT_ROOT="{R}/ds/nitrofs/enemy_shots"',str(wrapper),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=c.world_finished.restype=c.world_render_hud.restype=C.c_bool
 assert c.world_open_stage(0,False)
 pixels=(C.c_uint16*49152)()
 assert c.world_render_hud(pixels,False)
 assert not c.world_render_hud(pixels,False)
 assert c.world_render_hud(pixels,True)
 health=[]
 for hit in range(5):
  c.test_place(528,2352);c.test_clear_immunity();assert c.world_tick(0)
  health.append(c.test_health());assert health[-1]==100-20*(hit+1)
  if hit==0:
   assert c.world_render_hud(pixels,False)
   assert c.test_immunity()==119
   c.test_place(528,2352);assert c.world_tick(0);assert c.test_health()==80
 assert c.world_tick(0);assert c.world_player_state()==35
 assert not c.world_finished()
 for _ in range(240):assert c.world_tick(0)
 assert c.world_finished();c.world_close()
 assert c.world_open_stage(0,False);c.test_place(2192,560);y=c.test_y();assert c.world_tick(1)
 assert c.world_player_state() in (12,13),c.world_player_state()
 for _ in range(5):assert c.world_tick(1)
 assert c.test_y()<y;c.world_close()
 assert c.world_open_stage(0,False);assert c.world_tick(0)
 index=c.test_pickup(53);assert index>=0;assert c.world_tick(0)
 # Native state0 initializes on the first eligible update; contact starts in1.
 assert c.world_tick(0)
 assert c.test_score()>=1000 and c.test_letter()==1 and not c.test_active(index)
 assert c.test_popups()==1
 c.world_close();assert c.world_open_stage(0,False);assert c.test_ammo()==10
 for _ in range(90):assert c.world_tick(0)
 shot_seen=False
 for _ in range(80):
  assert c.world_tick(32);shot_seen=shot_seen or c.test_shots()>0
 assert c.test_ammo()==9 and shot_seen;c.world_close()
 out={'bottom_hud_redraws_on_state_change_and_menu_restore':True,'letter_collects_score_and_disappears':True,'original_1000_popup_spawns_in_production_world':True,'snowball_spawns_and_consumes_one_ammo':True,'water_cell':[16,73],'health_after_unprotected_contacts':health,'immune_contact_preserves_health':True,'death_returns_to_menu_after_240_tick_interval':True,'original_climb_cell':[68,17],'climb_up_moves_player':True,'scope':__doc__}
 (R/'research/gameplay/world_interactions.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
