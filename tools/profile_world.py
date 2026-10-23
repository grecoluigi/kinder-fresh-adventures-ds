"""Host diagnostic of production world update/render and scene IO (not DS timing)."""
import ctypes as C,json,subprocess,tempfile,time,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-profile-') as tmp:
 so=Path(tmp)/'world.dylib'
 names=['world','scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={ 'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots'}
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"' for k,v in defs.items()],*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=c.world_render.restype=C.c_bool
 class Stats(C.Structure):_fields_=[(n,C.c_uint32) for n in ['reads','bytes','tiles','sprites','sprite_bytes','setup','tile_us','object_us','callback_us','samples','sample_bytes']]
 c.scene_render_stats.restype=C.POINTER(Stats)
 pixels=(C.c_uint16*49152)();cases=[]
 for world in range(4):
  assert c.world_open_stage(world,False);assert c.world_render(pixels)
  updates=[];renders=[];reads=[];fails=[]
  for frame in range(240):
   start=time.perf_counter()
   for tick in range(3):
    if not c.world_tick(0 if frame<60 else 8):fails.append((frame,c.world_player_state()));break
   updates.append((time.perf_counter()-start)*1000)
   start=time.perf_counter();assert c.world_render(pixels),(world,frame)
   renders.append((time.perf_counter()-start)*1000);reads.append(c.scene_render_stats().contents.reads)
  def summary(v):return dict(median=round(statistics.median(v),3),maximum=round(max(v),3))
  cases.append(dict(world=world,update3_ms=summary(updates),render_ms=summary(renders),reads_first60=sum(reads[:60]),reads_motion=sum(reads[60:]),max_reads=max(reads),failed_ticks=fails[:3],last60_reads=reads[-60:]));c.world_close()
 out=dict(scope=__doc__,worlds=cases);print(json.dumps(out,indent=2));(R/'research/rendering/world_profile.json').write_text(json.dumps(out,indent=2))
