"""Production tutorial dialogue with60Hz world updates and22050Hz PCM mixing.
NPC positions are supplied fixtures, not keyboard-driven complete tutorials.
"""
from pathlib import Path
import ast,ctypes as C,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1];source=(R/'tools/verify_world_tutorials.py').read_text();body=source.split('static size_t test_npc_index;',1)[1].split("''')",1)[0];names=ast.literal_eval(next(line.strip().split('=',1)[1]for line in source.splitlines()if line.strip().startswith('names=')))
assets={v['va']:v for v in json.loads((R/'research/audio/effects_manifest.json').read_text())['assets']}
with tempfile.TemporaryDirectory(prefix='kinder-tutorial-audio-time-')as tmp:
 t=Path(tmp);wrapper=t/'world.c';wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\nstatic size_t test_npc_index;'+body+'\nunsigned test_voice_key(void){return npc_voice_key;}\nint test_health(void){return player.health;}\n')
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'};so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"'for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(so)],check=True);c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=C.c_bool;c.sound_channel_active.restype=C.c_bool;c.test_voice_key.restype=C.c_uint;c.world_map_name.restype=C.c_char_p;c.sound_events_mix.argtypes=[C.POINTER(C.c_int16),C.c_uint,C.c_uint];c.world_render.restype=C.c_bool;pixels=(C.c_uint16*49152)();cases=[]
 for world in range(4):
  for kind,keys in ((0,[0x456ab0,0x456900,0x4568dc]),(1,[0x456a8c]),(2,[0x456a68,0x4568b8]),(7,[0x456990])):
   assert c.world_open_stage(world,True);assert c.test_select_npc(kind);events=[];mixed=0;started=False;last_key=0;lock_x=None;locked_ticks=0
   for tick in range(3000):
    c.sound_events_poll();assert c.world_tick(0),(world,kind,tick,'world stopped')
    key=c.test_voice_key()
    if c.sound_channel_active(17) and key!=last_key:events.append({'key':hex(key),'tick':tick,'mixed_frames_before':mixed});last_key=key;started=True
    if c.test_dialogue()==1:
     if lock_x is None:lock_x=c.test_x()
     assert c.test_x()==lock_x,(world,kind,tick,'horizontal movement while speaking');locked_ticks+=1
    # Rational22050/60 pacing: alternating367/368samples per update.
    samples=(tick+1)*22050//60-tick*22050//60;out=(C.c_int16*samples)();c.sound_events_mix(out,samples,127);mixed+=samples
    if tick%2==0:assert c.world_render(pixels),(world,kind,tick,'render')
    if started and ((kind==7 and c.world_transition_target()==world)or(kind!=7 and c.test_dialogue()==0)):break
   else:raise AssertionError((world,kind,'dialogue never completed'))
   assert [v['key']for v in events]==[hex(k)for k in keys],(world,kind,events)
   # Each transition must wait for the entire preceding voice, within one update.
   for i,event in enumerate(events):
    end=events[i+1]['mixed_frames_before']if i+1<len(events)else mixed
    consumed=end-event['mixed_frames_before'];assert consumed>=assets[keys[i]]['frames'],(world,kind,i,consumed,assets[keys[i]]['frames'])
   unlocked_movement=None
   if kind!=7:
    before=c.test_x()
    for step in range(24):
     c.sound_events_poll();assert c.world_tick(8) # Original RIGHT bit.
     out=(C.c_int16*368)();c.sound_events_mix(out,368,127)
    assert c.test_x()>before,(world,kind,'movement stayed locked after speech')
    unlocked_movement=[before,c.test_x()]
   assert c.test_health()>0,(world,kind,'died during speech')
   cases.append({'world':world,'kind':kind,'ticks':tick+1,'locked_ticks':locked_ticks,'voice_events':events,'health':c.test_health(),'transition':c.world_transition_target(),'unlocked_movement_fixed':unlocked_movement});c.world_close()
 result={'scope':__doc__,'cases':cases,'voice_segments':sum(len(v['voice_events'])for v in cases),'world_updates':sum(v['ticks']for v in cases),'limits':['NPC positions are supplied; movement input is released to let speech finish. Not a full tutorial traversal.','PCM mixer and poll run at modeled rates on host; DS IRQ/storage timing and audible playback unverified.']};(R/'research/gameplay/tutorial-audio-timing-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='cases'}))
