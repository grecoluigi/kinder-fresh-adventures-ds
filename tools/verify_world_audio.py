"""Real-map player/pickup events reach the production PCM sound backend."""
import ctypes as C,json,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
manifest=json.loads((R/'research/audio/effects_manifest.json').read_text());assets={a['va']:a for a in manifest['assets']};pack=(R/'generated/audio-lossless/reference.pcm').read_bytes()
with tempfile.TemporaryDirectory(prefix='kinder-world-audio-') as temporary:
 p=Path(temporary);w=p/'probe.c'
 w.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'
 'void test_place(int x,int y){body.motion.x=x*4096;body.motion.y=y*4096;body.motion.vx=body.motion.vy=0;const SceneMetadata*m=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};camera_init(&camera,m->width_cells,m->height_cells,x-200,y-400,f,2);}\n'
 'void test_action(int action){test_place(2140,2306);player.state=action;if(action==1){player.penguin.frame=player.penguin.first=player.penguin.last=47;player.penguin.opaque_44=1;native_rng_seed(1);}if(action==15){player.penguin.frame=255;player.penguin.timer=0;player.penguin.last=260;}}\n'
 'int test_letter(void){size_t n;GameEntity*o=scene_entities(&n);for(size_t i=0;i<n;++i)if(entity_id(o+i)==53){EntityEnvironment e={0};scene_entity_environment(i,&e);test_place(entity_x(o+i)+e.width/2,entity_y(o+i)+e.height);return 1;}return 0;}\n')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=p/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"' for k,v in defs.items()],str(w),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=c.sound_channel_active.restype=C.c_bool
 c.sound_events_mix.argtypes=[C.POINTER(C.c_int16),C.c_uint,C.c_uint]
 def prefix(channel,key):
  assert c.sound_channel_active(channel),(channel,hex(key))
  out=(C.c_int16*367)();c.sound_events_mix(out,367,127)
  a=assets[key];assert bytes(out)==pack[a['offset']:a['offset']+734],(channel,hex(key),'PCM')
  c.sound_events_stop()
 cases=[]
 assert c.world_open_stage(0,False);c.test_action(4);assert c.world_tick(0);prefix(0,0x456610);cases.append('jump');c.world_close()
 assert c.world_open_stage(0,False);c.test_place(528,2352);assert c.world_tick(0);prefix(0,0x45664c);cases.append('water_hurt');c.world_close()
 assert c.world_open_stage(0,False);c.test_action(15);assert c.world_tick(32);prefix(0,0x4565b0);cases.append('penguin_shot');c.world_close()
 assert c.world_open_stage(0,False);assert c.test_letter();assert c.world_tick(0);assert c.world_tick(0);prefix(2,0x456598);cases.append('recipe_pickup');c.world_close()
 assert c.world_open_stage(0,False);c.test_action(1);assert c.world_tick(0);prefix(17,0x456c08);cases.append('idle_voice');c.world_close()
 result={'scope':__doc__,'events_checked':cases,'first367_PCM_frames_equal':True,'limits':['Host real-map update and simulated mixer consumption; DS timing and audible output remain unverified.']}
 (R/'research/audio/world_events_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
