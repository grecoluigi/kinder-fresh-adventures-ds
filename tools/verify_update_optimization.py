"""Compare optimized world update with the pre-optimization implementation.
This verifies unchanged gameplay state and pixels, not original-native coverage or DS speed.
Baseline source copies are temporary artifacts of this optimization, not shipped code.
"""
import ctypes as C,json,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=Path('/tmp/kinder-update-baseline')
assert (B/'world.c').exists() and (B/'scene.c').exists()
with tempfile.TemporaryDirectory(prefix='kinder-update-proof-') as tmp:
 libs=[]
 for old in [True,False]:
  out=Path(tmp)/('before' if old else 'after');out.mkdir();wrapper=out/'probe.c'
  w=B/'world.c' if old else R/'ds/source/world.c';s=B/'scene.c' if old else R/'ds/source/scene.c'
  wrapper.write_text('#include "'+str(w)+'"\n'
   'unsigned probe_state(unsigned char *p){unsigned n=0;\n'
   '#define COPY(v) memcpy(p+n,&(v),sizeof(v));n+=sizeof(v)\n'
   'COPY(player);COPY(body);COPY(camera);COPY(hud);COPY(shots);COPY(player_visible);\n'
   'memcpy(p+n,enemy_shots_slots(),sizeof(EnemyShot)*ENEMY_SHOTS_CAPACITY);n+=sizeof(EnemyShot)*ENEMY_SHOTS_CAPACITY;\n'
   'size_t count;GameEntity *e=scene_entities(&count);memcpy(p+n,e,count*sizeof(*e));n+=(unsigned)(count*sizeof(*e));return n;}\n')
  names=['player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks']
  defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots'}
  so=out/'test.dylib'
  subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),*[f'-D{k}="{v}"' for k,v in defs.items()],str(wrapper),str(s),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
  c=C.CDLL(str(so));c.world_open.restype=c.world_tick.restype=c.world_render.restype=C.c_bool;c.probe_state.restype=C.c_uint;libs.append(c)
 buffers=[(C.c_uint8*300000)() for _ in libs];pixels=[(C.c_uint16*49152)() for _ in libs];ticks=frames=0
 for world in range(4):
  for c in libs:c.native_rng_seed(12345);assert c.world_open(world)
  for tick in range(2400):
   keys=0 if tick<90 else 8 if tick<480 else 4 if tick<720 else 0
   if 180<=tick<186 or 330<=tick<335:keys|=16
   if tick==110 or tick==310:keys|=32
   for c in libs:assert c.world_tick(keys),(world,tick)
   sizes=[c.probe_state(b) for c,b in zip(libs,buffers)];assert sizes[0]==sizes[1]
   assert bytes(buffers[0][:sizes[0]])==bytes(buffers[1][:sizes[1]]),(world,tick,'state')
   ticks+=1
   if tick%12==0:
    for c,p in zip(libs,pixels):assert c.world_render(p),(world,tick,'render')
    assert bytes(pixels[0])==bytes(pixels[1]),(world,tick,'pixels');frames+=1
  for c in libs:c.world_close()
 result=dict(ticks_compared=ticks,frames_compared=frames,passed=True,scope=__doc__)
 (R/'research/rendering/update_optimization_verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
