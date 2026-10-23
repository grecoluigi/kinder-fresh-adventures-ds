"""Walk into the first four Jungle NPC triggers; hold direction through the movement lock."""
from pathlib import Path
import ast,ctypes as C,json,subprocess,tempfile,struct
R=Path(__file__).resolve().parents[1];source=(R/'tools/verify_world_tutorials.py').read_text();names=ast.literal_eval(next(line.strip().split('=',1)[1]for line in source.splitlines()if line.strip().startswith('names=')))
with tempfile.TemporaryDirectory(prefix='kinder-tutorial-approach-')as td:
 t=Path(td);src=t/'probe.c';src.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
static size_t npc;
bool test_begin(unsigned kind){
 if(!world_open_stage(0,true))return false;
 size_t n;GameEntity *objects=scene_entities(&n);
 for(size_t i=0;i<n;i++)if(entity_id(objects+i)==77&&objects[i].bytes[42]==kind&&entity_x(objects+i)>=0&&entity_active(objects+i)){
  npc=i;if(kind){EntityEnvironment resource={0};if(!scene_entity_environment(i,&resource))return false;
   body.motion.x=(entity_x(objects+i)-180)*4096;body.motion.y=(entity_y(objects+i)+resource.height)*4096;
   body.motion.vx=body.motion.vy=body.motion.ax=body.motion.ay=0;player.state=0;player.fatal=0;
   const SceneMetadata *m=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};camera_init(&camera,m->width_cells,m->height_cells,body.motion.x/4096-200,body.motion.y/4096-400,f,2);
  }return true;
 }
 return false;
}
void test_state(int32_t *out){
 size_t n;GameEntity *objects=scene_entities(&n);int16_t state;memcpy(&state,objects[npc].bytes+98,2);
 out[0]=body.motion.x;out[1]=body.motion.y;out[2]=player.fatal;out[3]=player.state;out[4]=state;out[5]=(int32_t)npc_voice_key;out[6]=player.direction_latch;out[7]=entity_x(objects+npc);
}
''')
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'probe.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),*[f'-D{k}="{v}"'for k,v in defs.items()],str(src),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.test_begin.restype=c.world_tick.restype=c.sound_channel_active.restype=c.game_save_open_directory.restype=C.c_bool;c.test_state.argtypes=[C.POINTER(C.c_int32)];c.sound_events_mix.argtypes=[C.POINTER(C.c_int16),C.c_uint,C.c_uint]
 assert c.game_save_open_directory(str(t/'save').encode());state=(C.c_int32*8)();pcm=(C.c_int16*368)();proof=[];ticks=0
 def step(keys):
  global ticks
  c.sound_events_poll();assert c.world_tick(keys);n=(ticks+1)*22050//60-ticks*22050//60;c.sound_events_mix(pcm,n,127);ticks+=1;c.test_state(state)
 for kind,key in enumerate([0x456ab0,0x456a8c,0x456a68,0x456a44]):
  assert c.test_begin(kind);c.test_state(state);start_x=state[0]//4096
  for approach in range(300):
   step(8)
   if state[2]==1:break
  assert state[2]==1 and state[5]==key and c.sound_channel_active(17),(kind,list(state),'voice not triggered')
  trigger_x=state[0]//4096
  assert trigger_x<state[7],(kind,'trigger must precede NPC origin',list(state))
  for _ in range(3):step(8)
  locked_x=state[0];assert state[2]==1 and state[6]==1,(kind,list(state),'lock startup')
  for _ in range(30):
   step(8);assert state[0]==locked_x and state[2]==1 and c.sound_channel_active(17),(kind,list(state),'held direction bypassed speech')
  step(0);step(8);assert state[2]==0 and not c.sound_channel_active(17),(kind,list(state),'fresh direction did not skip')
  proof.append({'kind':kind,'voice':hex(key),'start_x':start_x,'trigger_x':trigger_x,'NPC_x':state[7],'approach_ticks':approach+1,'held_direction_lock_ticks':30,'release_repress_skips':True,'from_original_spawn':kind==0})
  c.world_close()
 raw=(R/'ds/nitrofs/scenes/enemies.frames').read_bytes();nr=struct.unpack_from('<H',raw,4)[0];resource=next(raw[12+i*84:12+(i+1)*84]for i in range(nr)if struct.unpack_from('<H',raw,12+i*84)[0]==77);first=struct.unpack_from('<H',resource,2)[0];base=12+nr*84
 result={'scope':__doc__,'cases':proof,'incorrect_legacy_stride_dimensions':list(struct.unpack_from('<hh',raw,base+first*16+8)),'correct_native_dimensions':list(struct.unpack_from('<HH',raw,base+first*40)),'limits':['First NPC approached from real spawn; later NPC approaches start180native pixels to the left at their foot height, not a complete tutorial traversal.','Host simulation/audio consumption, not DS frame timing, listening or button hardware.']};(R/'research/gameplay/tutorial-approach-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
