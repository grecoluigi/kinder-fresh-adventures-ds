"""Production main->arena->defeat fixture->prize->banner->score/name->save/reload.
Damage-animation boundaries/player placement are supplied, not completed fights.
"""
from pathlib import Path
import ast,ctypes as C,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1];source=(R/'tools/verify_world_bosses.py').read_text();body=source.split('static size_t target;',1)[1].split("''')",1)[0];names=ast.literal_eval(next(line.strip().split('=',1)[1]for line in source.splitlines()if line.strip().startswith('names=')))
class Table(C.Structure):_fields_=[('names',(C.c_char*30)*10),('score_text',(C.c_char*10)*10)]
class State(C.Structure):_fields_=[('scores',Table*4),('options',C.c_int32*22),('tutorials',C.c_uint8*4)]
class UI(C.Structure):_fields_=[('world',C.c_uint),('focus',C.c_int),('editing_rank',C.c_int),('held_key',C.c_int),('name',C.c_char*30),('name_length',C.c_uint),('exit_requested',C.c_bool),('commit_requested',C.c_bool),('revision',C.c_uint32)]
with tempfile.TemporaryDirectory(prefix='kinder-boss-completion-chain-')as tmp:
 t=Path(tmp);wrapper=t/'world.c';wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\nstatic size_t target;'+body+'''
int test_banner_action(void){return end_title.action;}int test_banner_frame(void){return end_title.frame;}
bool test_without_banner(uint16_t*p){int32_t action=end_title.action;end_title.action=0;bool ok=world_render(p);end_title.action=action;return ok;}
''');defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'};so=t/'chain.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"'for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c')for n in names+['completion','highscore_ui']],'-o',str(so)],check=True);c=C.CDLL(str(so));c.game_save_state.restype=C.POINTER(State);c.game_save_open_directory.argtypes=[C.c_char_p];c.completion_begin.argtypes=[C.POINTER(UI),C.c_uint,C.c_int32];c.completion_confirm.argtypes=[C.POINTER(UI)];c.highscore_ui_text.argtypes=[C.POINTER(UI),C.c_uint8];c.highscore_ui_activate.argtypes=[C.POINTER(UI)];c.highscore_ui_open.argtypes=[C.c_char_p];c.highscore_ui_draw.argtypes=[C.POINTER(C.c_uint16),C.POINTER(Table),C.POINTER(UI)]
 for fn in ('game_save_open_directory','world_open_stage','world_open','world_tick','world_finished','world_render','test_without_banner','completion_confirm','highscore_ui_open','highscore_ui_draw'):getattr(c,fn).restype=C.c_bool
 pixels=(C.c_uint16*49152)();without=(C.c_uint16*49152)();cases=[]
 for base,boss in enumerate((10,9,14,18)):
  folder=t/f'world{base}';assert c.game_save_open_directory(str(folder).encode());s=c.game_save_state().contents
  for table in s.scores:
   for rank in range(10):table.names[rank].value=f'OLD{rank}'.encode();table.score_text[rank].value=str(1000-rank*100).encode()
  assert c.game_save_flush()==63;before={p.name:p.read_bytes()for p in folder.iterdir()}
  assert c.world_open_stage(base,False);c.test_ingredients();assert c.world_tick(0);target=c.world_transition_target();assert target==base+4;assert c.world_open(target);assert c.test_select(boss);c.test_tick()
  for cycle in range(10):assert c.test_damage_cycle()==8-cycle
  assert c.test_defeated()==1 and c.test_prize() and c.test_score()==20321
  banner_frames=0
  for expected in range(239,-1,-1):
   c.sound_events_poll();assert c.test_finish_tick()==expected;pcm=(C.c_int16*368)();c.sound_events_mix(pcm,368,127)
   if expected%2==0:assert c.world_render(pixels);banner_frames+=1
  assert c.world_finished() and c.test_banner_frame()==1 and c.test_banner_action()!=0
  assert c.world_render(pixels) and c.test_without_banner(without);changed=sum(a!=b for a,b in zip(pixels,without));assert changed>100,(base,'victory overlay missing',changed)
  world=c.world_result_world();score=c.world_result_score();assert(world,score)==(base,20321);c.world_close()
  assert c.highscore_ui_open(str(R/'ds/nitrofs/highscores').encode());ui=UI();rank=c.completion_begin(C.byref(ui),world,score);assert rank==0 and ui.world==base and ui.editing_rank==0
  for ch in b'DS TEST':assert c.highscore_ui_text(C.byref(ui),ch)
  c.highscore_ui_activate(C.byref(ui));assert c.completion_confirm(C.byref(ui));assert c.highscore_ui_draw(pixels,C.byref(c.game_save_state().contents.scores[base]),C.byref(ui));c.highscore_ui_close()
  changed_files=[p.name for p in folder.iterdir()if p.read_bytes()!=before[p.name]];assert changed_files==[f'Highscore{base+1}.dat'],changed_files
  assert c.game_save_open_directory(str(folder).encode());table=c.game_save_state().contents.scores[base];assert table.names[0].value==b'DS TEST 'and table.score_text[0].value==b'20321'
  cases.append({'base_world':base,'arena':target,'boss':boss,'damage_cycles':10,'score':score,'banner_render_frames':banner_frames,'victory_overlay_pixels':changed,'rank':rank,'saved_and_reloaded_name':'DS TEST ','selected_file_only':True})
 result={'scope':__doc__,'cases':cases,'limits':['Fixture forces damage-animation completion and prize/player boundaries; not a keyboard-driven complete boss fight.','Production banner,score capture,UI name confirmation and file backend run together. DS keyboard/FAT/IRQ/runtime performance remain unverified.']};(R/'research/bosses/completion-chain-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
