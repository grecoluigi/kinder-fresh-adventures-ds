"""Integrated host smoke of original scenes and recovered player/body/camera; narrow scope."""
import ctypes,json,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-world-') as tmp:
 library=Path(tmp)/'world.dylib';names=['world','scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',f'-DSCENE_ROOT="{root}/ds/nitrofs/scenes"',f'-DPLAYER_ROOT="{root}/ds/nitrofs/players"',f'-DHUD_PATH="{root}/ds/nitrofs/hud_bottom.bin"',f'-DPROJECTILE_ROOT="{root}/ds/nitrofs/projectiles"',f'-DENEMY_SHOT_ROOT="{root}/ds/nitrofs/enemy_shots"',*[str(root/'ds/source'/f'{name}.c') for name in names],'-o',str(library)],check=True)
 c=ctypes.CDLL(str(library));c.world_open_stage.restype=c.world_tick.restype=c.world_render.restype=ctypes.c_bool
 rows=[];pixels=(ctypes.c_uint16*49152)()
 for world in range(4):
  assert c.world_open_stage(world,False)
  for tick in range(1200):
   keys=0 if tick<90 else (8 if tick<180 else 0)
   assert c.world_tick(keys),(world,tick,c.world_player_state())
   if tick%60==0:assert c.world_render(pixels)
  rows.append(dict(world=world,ticks=1200,final_state=c.world_player_state()));c.world_close()
 result=dict(worlds=rows,scope=__doc__+' No enemy behavior, DS frame timing, sound, saves or completion verification.')
 (root/'research/gameplay/world_smoke.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
