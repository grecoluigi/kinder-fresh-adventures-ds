"""Measure image-cache record pressure on bounded production host routes.
Temporary instrumentation counts metadata evictions; it does not change cache policy.
"""
from pathlib import Path
import argparse,ast,ctypes as C,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--entries',type=int,choices=(32,64,96,128));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
source=(R/'tools/verify_world_tutorials.py').read_text();names=ast.literal_eval(next(x.strip().split('=',1)[1]for x in source.splitlines()if x.strip().startswith('names=')))
with tempfile.TemporaryDirectory(prefix='kinder-cache-pressure-')as tmp:
 t=Path(tmp);scene=t/'scene.c';world=t/'world.c';lib=t/'probe.dylib'
 code=(R/'ds/source/scene.c').read_text();assert code.count('if(slot<0){')==1
 code=code.replace('static const uint8_t *enemy_cached_frame', 'static unsigned probe_cache_inserts;static unsigned probe_metadata_evictions;static uint64_t probe_metadata_spare;\nstatic const uint8_t *enemy_cached_frame').replace('if(slot<0){', 'if(slot<0){probe_metadata_evictions++;probe_metadata_spare+=enemy_cache_capacity-enemy_cache_bytes;')
 code=code.replace('enemy_cache[slot]=(EnemyFrameCache)', 'probe_cache_inserts++;enemy_cache[slot]=(EnemyFrameCache)')
 scene.write_text(code+'''\nvoid probe_reset(void){probe_cache_inserts=probe_metadata_evictions=0;probe_metadata_spare=0;}
void probe_cache(uint32_t *v){unsigned n=0;for(unsigned i=0;i<ENEMY_CACHE_ENTRIES;i++)if(enemy_cache[i].data)n++;v[0]=n;v[1]=enemy_cache_bytes;v[2]=enemy_cache_capacity;v[3]=ENEMY_CACHE_ENTRIES;v[4]=probe_cache_inserts;v[5]=probe_metadata_evictions;v[6]=probe_metadata_evictions?(uint32_t)(probe_metadata_spare/probe_metadata_evictions):0;}
''')
 world.write_text('#include "'+str(R/'ds/source/world.c')+'"\nvoid probe_player(int32_t *v){v[0]=body.motion.x/4096;v[1]=body.motion.y/4096;v[2]=player.health;}\n')
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),*[f'-D{k}="{v}"'for k,v in defs.items()],*([f'-DENEMY_CACHE_ENTRIES={a.entries}u']if a.entries else[]),str(scene),str(world),*[str(R/'ds/source'/f'{n}.c')for n in names if n!='scene'],'-o',str(lib)],check=True)
 c=C.CDLL(str(lib));c.world_open_stage.restype=c.world_tick.restype=c.world_render.restype=c.game_save_open_directory.restype=C.c_bool
 assert c.game_save_open_directory(str(t/'save').encode());stats=(C.c_uint32*7)();player=(C.c_int32*3)();pcm=(C.c_int16*368)();pixels=(C.c_uint16*49152)();routes=[]
 for world in range(4):
  c.probe_reset();assert c.world_open_stage(world,False);decodes=peak_entries=peak_bytes=renders=0;minx=maxx=0;render_digest=hashlib.sha256()
  for tick in range(600):
   c.sound_events_poll();assert c.world_tick(8|(16 if tick%90<22 else 0)|(32 if tick%45==0 else 0));n=(tick+1)*22050//60-tick*22050//60;c.sound_events_mix(pcm,n,127)
   if tick%2==0:
    assert c.world_render(pixels);render_digest.update(bytes(pixels));c.probe_cache(stats);decodes=stats[4];peak_entries=max(peak_entries,stats[0]);peak_bytes=max(peak_bytes,stats[1]);renders+=1
   c.probe_player(player);minx=min(minx,player[0]);maxx=max(maxx,player[0])
   if player[2]<=0:break
  c.probe_cache(stats);routes.append({'render_sequence_sha256':render_digest.hexdigest(),'world':world,'updates':tick+1,'renders':renders,'x_max':maxx,'health':player[2],'peak_entries':peak_entries,'record_limit':stats[3],'peak_payload_bytes':peak_bytes,'arena_capacity':stats[2],'decoded_image_insertions':decodes,'metadata_evictions':stats[5],'average_spare_bytes_at_metadata_eviction':stats[6]});c.world_close()
 result={'scope':__doc__,'scene_sha256':hashlib.sha256((R/'ds/source/scene.c').read_bytes()).hexdigest(),'routes':routes,'limits':['Host deterministic input routes/render every2updates, not full levels or device timing.','Only cache counters are instrumented; gameplay positions/health/ammo are not injected.']};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
