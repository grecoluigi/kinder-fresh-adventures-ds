"""Production first-raft landing and carry checks; host integration, not emulator timing."""
import ctypes as C,subprocess,tempfile,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as t:
 p=Path(t);w=p/'probe.c';w.write_text('#include "'+str(R/'ds/source/world.c')+'"\nvoid place(int x,int y){body.motion.x=x*4096;body.motion.y=y*4096;body.motion.vx=body.motion.vy=0;const int16_t f[8]={2,2,2,2,2,2,2,2};camera_init(&camera,300,80,x-200,y-400,f,2);}\nint value(int k){size_t n;GameEntity *o=scene_entities(&n); switch(k){case 0:return body.motion.x/4096;case 1:return body.motion.y/4096;case 2:return entity_x(o+2);case 3:return entity_y(o+2);case 4:return player.health;case 5:return geometry_count;case 6:return tick_count;case 7:return player.state;}return -1;}\n')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots'}
 so=p/'probe.dylib';subprocess.run(['cc','-dynamiclib','-O2',*[f'-D{k}="{v}"' for k,v in defs.items()],str(w),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=C.c_bool
 assert c.world_open_stage(0,False);c.place(2140,2306)
 samples=[]
 for i in range(180):
  assert c.world_tick(0)
  v=[c.value(k) for k in range(8)]
  assert v[0]-v[2]==84,(i,v)
  assert v[1]==v[3]+30,(i,v)
  assert v[4]==100,(i,v)
  if i%30==0:samples.append(v[:5])
 assert samples[-1][2]!=2056
 c.world_close();assert c.world_open_stage(0,False);c.place(2140,2230)
 landed=False
 for i in range(180):
  assert c.world_tick(0)
  v=[c.value(k) for k in range(8)]
  assert v[4]==100,(i,v)
  if v[1]==v[3]+30:landed=True
 assert landed
 c.world_close()
 out={'scope':__doc__,'map':'Welt1.W02','object_index':2,'native_id':210,'standing_carry_ticks':180,'landing_and_support_ticks':180,'health_preserved':True,'samples_player_x_y_raft_x_y_health':samples}
 (R/'research/gameplay/platform_integration.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
