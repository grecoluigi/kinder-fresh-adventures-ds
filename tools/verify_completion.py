"""Exercise production qualification/name/view flow and selected-file persistence.
Native qualification and glyph/input oracles are separate; no DS touch/FAT proof.
"""
from pathlib import Path
import ctypes as C,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
class Table(C.Structure):_fields_=[('names',(C.c_char*30)*10),('score_text',(C.c_char*10)*10)]
class State(C.Structure):_fields_=[('scores',Table*4),('options',C.c_int32*22),('tutorials',C.c_uint8*4)]
class UI(C.Structure):_fields_=[('world',C.c_uint),('focus',C.c_int),('editing_rank',C.c_int),('held_key',C.c_int),('name',C.c_char*30),('name_length',C.c_uint),('exit_requested',C.c_bool),('commit_requested',C.c_bool),('revision',C.c_uint32)]
with tempfile.TemporaryDirectory(prefix='kinder-completion-')as tmp:
 t=Path(tmp);so=t/'completion.dylib'
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[str(R/'ds/source'/f'{n}.c')for n in ('completion','highscore_ui','game_save','persistence','persistence_store','save_archive')],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.game_save_state.restype=C.POINTER(State);c.game_save_open_directory.argtypes=[C.c_char_p];c.game_save_open_directory.restype=C.c_bool
 c.completion_begin.argtypes=[C.POINTER(UI),C.c_uint,C.c_int32];c.completion_confirm.argtypes=[C.POINTER(UI)];c.completion_confirm.restype=C.c_bool
 c.highscore_ui_text.argtypes=[C.POINTER(UI),C.c_uint8];c.highscore_ui_activate.argtypes=[C.POINTER(UI)]
 cases=[]
 for world in range(4):
  folder=t/f'world{world}';assert c.game_save_open_directory(str(folder).encode())
  state=c.game_save_state().contents
  for table in state.scores:
   for rank in range(10):table.names[rank].value=f'OLD{rank}'.encode();table.score_text[rank].value=str(1000-rank*100).encode()
  assert c.game_save_flush()==63
  before={p.name:p.read_bytes()for p in folder.iterdir()}
  ui=UI();assert c.completion_begin(C.byref(ui),world+4,950)==1
  assert ui.world==world and ui.editing_rank==1
  for character in b'LUIGI':assert c.highscore_ui_text(C.byref(ui),character)
  c.highscore_ui_activate(C.byref(ui));assert c.completion_confirm(C.byref(ui))
  assert ui.world==world and ui.editing_rank==-1 and not ui.exit_requested
  changed=[p.name for p in folder.iterdir()if p.read_bytes()!=before[p.name]]
  assert changed==[f'Highscore{world+1}.dat'],changed
  assert c.game_save_open_directory(str(folder).encode())
  table=c.game_save_state().contents.scores[world]
  assert table.names[1].value==b'LUIGI ' and table.score_text[1].value==b'950'
  assert table.names[2].value==b'OLD1'
  after={p.name:p.read_bytes()for p in folder.iterdir()}
  assert c.completion_begin(C.byref(ui),world,0)==-1 and ui.editing_rank==-1
  assert after=={p.name:p.read_bytes()for p in folder.iterdir()}
  cases.append({'world':world,'qualification_rank':1,'confirmed_name':'LUIGI ','selective_save':True,'reload':True,'nonqualifying_viewer':True})
 # Narrow spaces reach the28-character limit and preserve the native final space.
 ui=UI();c.completion_begin(C.byref(ui),0,9999999)
 for _ in range(28):assert c.highscore_ui_text(C.byref(ui),ord(' '))
 assert not c.highscore_ui_text(C.byref(ui),ord(' '))
 c.highscore_ui_activate(C.byref(ui));assert c.completion_confirm(C.byref(ui))
 assert c.game_save_state().contents.scores[0].names[0].value==b' '*29
 assert c.game_save_open_directory(str(folder).encode())
 assert c.game_save_state().contents.scores[0].names[0].value==b' '*29
 # Unavailable FAT still retains a name in RAM and reaches rankings.
 c.game_save_init();ui=UI();rank=c.completion_begin(C.byref(ui),0,9999999);assert rank>=0
 c.highscore_ui_text(C.byref(ui),ord('A'));c.highscore_ui_activate(C.byref(ui));assert not c.completion_confirm(C.byref(ui))
 assert ui.editing_rank==-1 and c.game_save_state().contents.scores[0].names[rank].value==b'A '
 result={'scope':__doc__,'worlds':cases,'unavailable_storage_keeps_RAM':True}
 (R/'research/highscores/completion-verification.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
