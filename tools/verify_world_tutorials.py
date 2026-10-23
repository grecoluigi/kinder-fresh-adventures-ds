"""Original-map NPC dialogue, movement lock, tutorial completion and save/reload.
Host teleport fixtures select NPC boundaries; this is not a full DS playthrough.
"""
import ctypes as C,json,os,struct,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
STAGE=Path(os.environ.get('KF_SCENE_OUTPUT_ROOT',str(R/'ds/nitrofs/scenes')))
manifest=json.loads((R/'research/audio/effects_manifest.json').read_text())
assets={a['va']:a for a in manifest['assets']}
pack=(R/'generated/audio-lossless/reference.pcm').read_bytes()
with tempfile.TemporaryDirectory(prefix='kinder-tutorial-integration-') as temporary:
 t=Path(temporary);wrapper=t/'probe.c'
 wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
static size_t test_npc_index;
int test_select_npc(unsigned kind){
 size_t n;GameEntity *e=scene_entities(&n);
 for(size_t i=0;i<n;i++)if(entity_id(e+i)==77&&e[i].bytes[42]==kind&&entity_x(e+i)>=0&&entity_active(e+i)){
  EntityEnvironment resource={0};if(!scene_entity_environment(i,&resource))return 0;
  test_npc_index=i;int x=entity_x(e+i)+resource.width/2,y=entity_y(e+i)+resource.height;
  body.motion.x=x*4096;body.motion.y=y*4096;body.motion.vx=body.motion.vy=body.motion.ax=body.motion.ay=0;
  player.state=0;player.fatal=0;player.knockback_timer=0;player.health=100;
  const SceneMetadata*m=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};
  camera_init(&camera,m->width_cells,m->height_cells,x-200,y-400,f,2);return 1;
 }
 return 0;
}
int test_npc_state(void){size_t n;GameEntity*e=scene_entities(&n);int16_t state;memcpy(&state,e[test_npc_index].bytes+98,2);return state;}
int test_dialogue(void){return player.fatal;}
int test_x(void){return body.motion.x;}
int test_start_x(void){return scene_metadata()->start_x;}
void test_flags(unsigned world,unsigned flag){game_save_state()->tutorials[world]=(uint8_t)flag;}
int test_flag(unsigned world){return game_save_state()->tutorials[world];}
void test_character(int actor){player.character=actor;player.state=actor?16:0;}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':STAGE,'PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"' for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_map_name.restype=C.c_char_p
 for name in ('world_open','world_tick','world_render','sound_channel_active','game_save_open_directory','game_save_flush_tutorials'):getattr(c,name).restype=C.c_bool
 c.sound_events_mix.argtypes=[C.POINTER(C.c_int16),C.c_uint,C.c_uint]
 pixels=(C.c_uint16*49152)();voice_events=[];routes=[]
 def begin(kind,actor=0):
  assert c.test_select_npc(kind)
  c.test_character(actor)
  for _ in range(4):
   assert c.world_tick(0)
   if c.test_dialogue()==1:break
  assert c.test_dialogue()==1 and c.sound_channel_active(17),(kind,c.test_npc_state())
  assert c.world_render(pixels)
 def voice(key):
  for channel in list(range(16))+[18]:c.sound_channel_stop(channel)
  out=(C.c_int16*367)();c.sound_events_mix(out,367,127)
  a=assets[key];assert bytes(out)==pack[a['offset']:a['offset']+734],hex(key)
  voice_events.append(hex(key));c.sound_events_poll()
  while c.sound_channel_active(17):
   out=(C.c_int16*1024)();c.sound_events_mix(out,1024,127);c.sound_events_poll()
 storage=t/'save';assert c.game_save_open_directory(str(storage).encode())
 tutorial=['Welt1t.W02','Welt2T.W02','welt3t.W02','welt4t.W02']
 normal=['Welt1.W02','Welt2.W02','welt3.W02','welt4.W02']
 starts=[64,48,43,44]
 for world in range(4):
  assert c.world_open(world) and c.world_map_name().decode()==tutorial[world]
  assert c.test_start_x()==starts[world]
  for _ in range(3):assert c.world_tick(0)
  assert c.world_render(pixels)
  begin(0);voice(0x456ab0);assert c.world_tick(0) and c.test_npc_state()==21
  voice(0x456900);assert c.world_tick(0) and c.test_npc_state()==10
  voice(0x4568dc);assert c.world_tick(0) and c.test_dialogue()==0
  for kind,actor,keys in [(1,0,[0x456a8c]),(2,0,[0x456a68,0x4568b8]),
    (3,0,[0x456a44]),(4,0,[0x456a20]),(5,0,[0x4569fc]),
    (6,0,[0x4569d8]),(6,1,[0x4569b4]),(8,0,[0x456948]),(8,1,[0x45696c])]:
   assert c.world_open(world);begin(kind,actor)
   for key in keys:voice(key);assert c.world_tick(0)
   assert c.test_dialogue()==0 and not c.sound_channel_active(17)
  if world in (0,2):
   assert c.world_open(world);begin(9);voice(0x456924)
   assert c.world_tick(0) and c.test_dialogue()==0
  # Reopen for an independent direction-key skip boundary.
  assert c.world_open(world);begin(1)
  for _ in range(5):assert c.world_tick(0)
  assert c.world_player_state() in (39,41),c.world_player_state()
  x=c.test_x();assert c.world_tick(1) and c.test_x()==x
  assert c.world_tick(8) and c.test_dialogue()==0 and not c.sound_channel_active(17)
  assert c.world_open(world);begin(1,1)
  for _ in range(5):assert c.world_tick(0)
  assert c.world_player_state()==41,c.world_player_state()
  assert c.world_tick(4) and c.test_dialogue()==0 and not c.sound_channel_active(17)
  assert c.world_open(world)
  begin(7);voice(0x456990);assert c.world_tick(0)
  assert c.world_transition_target()==world and c.test_flag(world)==1
  assert c.game_save_flush_tutorials()
  c.world_close();assert c.game_save_open_directory(str(storage).encode())
  assert c.world_open(world) and c.world_map_name().decode()==normal[world]
  assert c.world_render(pixels)
  routes.append({'world':world,'tutorial':tutorial[world],'main':normal[world],'start_x':starts[world],'completion_saved':True})
  c.world_close()
 assert [p.name for p in storage.iterdir()]==['tut.ini']
 assert (storage/'tut.ini').read_bytes()==b'\1\1\1\1'
 result={'scope':__doc__,'asset_root':str(STAGE),'worlds':routes,'voice_PCM_prefixes':voice_events,'movement_lock_and_direction_skip':True,'only_tutorial_file_written':True,'limits':['Teleport fixtures exercise NPC boundaries; full tutorial navigation, audible DS playback, FAT writes and frame timing remain unverified.']}
 (R/'research/gameplay/tutorial_integration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
