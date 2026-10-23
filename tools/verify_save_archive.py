"""Verify raw .sav creation, selective commits, recovery and loader paths."""
import ctypes as C
import json
import subprocess
import tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
class Table(C.Structure):
 _fields_=[('names',(C.c_char*30)*10),('scores',(C.c_char*10)*10)]
class State(C.Structure):
 _fields_=[('scores',Table*4),('options',C.c_int32*22),('tutorials',C.c_uint8*4)]
with tempfile.TemporaryDirectory(prefix='kinder-sav-') as temp:
 t=Path(temp);so=t/'save.dylib'
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[str(R/'ds/source'/f'{n}.c') for n in ('game_save','persistence','persistence_store','save_archive')],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.game_save_open_archive.argtypes=[C.c_char_p,C.c_char_p];c.game_save_open_archive.restype=C.c_bool
 c.game_save_state.restype=C.POINTER(State);c.game_save_flush.restype=C.c_uint;c.game_save_status.restype=C.c_uint
 c.save_archive_load.argtypes=[C.c_char_p,C.POINTER(State),C.POINTER(C.c_uint32)];c.save_archive_load.restype=C.c_bool
 # A loader placeholder or failed first write may leave an empty archive.
 empty=t/'empty.sav'
 for initial in (b'',bytes(8192),b'\xff'*8192):
  empty.write_bytes(initial)
  assert c.game_save_open_archive(str(empty).encode(),None),'Blank save cannot initialize'
  assert empty.stat().st_size==8192 and c.game_save_status()==1
  loaded=State();seq=C.c_uint32()
  assert c.save_archive_load(str(empty).encode(),C.byref(loaded),C.byref(seq)) and seq.value==1
  empty.unlink()
 path=t/'kinder_fresh.sav';pb=str(path).encode()
 assert c.game_save_open_archive(pb,None) and c.game_save_status()==1
 assert path.stat().st_size==8192 and list(t.glob('*.sav'))==[path]
 baseline=path.read_bytes();state=c.game_save_state().contents
 state.options[0]=123;state.scores[0].names[0].value=b'UNSAVED';state.tutorials[:]=[1,0,1,0]
 assert c.game_save_flush_tutorials()
 loaded=State();seq=C.c_uint32();assert c.save_archive_load(pb,C.byref(loaded),C.byref(seq))
 assert list(loaded.tutorials)==[1,0,1,0] and loaded.options[0]!=123 and loaded.scores[0].names[0].value!=b'UNSAVED'
 state.scores[2].names[0].value=b'PLAYER';assert c.game_save_flush_highscores(2)
 assert c.save_archive_load(pb,C.byref(loaded),C.byref(seq)) and loaded.scores[2].names[0].value==b'PLAYER'
 assert loaded.scores[0].names[0].value!=b'UNSAVED'
 original=path.read_bytes();latest=seq.value&1
 # Every byte in the protected latest record is checked, including serial.
 for index in (0,8,12,16,20,319,1600,1711):
  data=bytearray(original);data[latest*4096+index]^=1;path.write_bytes(data)
  assert c.save_archive_load(pb,C.byref(loaded),C.byref(seq))
  assert loaded.scores[2].names[0].value!=b'PLAYER' and list(loaded.tutorials)==[1,0,1,0]
 # A torn final record falls back to complete first record when it exists.
 path.write_bytes(baseline[:6000]);assert not c.save_archive_load(pb,C.byref(loaded),C.byref(seq))
 damaged=bytearray(original);damaged[0:8]=b'DAMAGED!';damaged[4096:4104]=b'DAMAGED!';path.write_bytes(damaged)
 assert not c.game_save_open_archive(pb,None) and path.read_bytes()==damaged
 path.write_bytes(original)
 assert c.game_save_open_archive(pb,None) and c.game_save_loaded_files()==63
 assert c.game_save_flush()==63
 assert c.save_archive_load(pb,C.byref(loaded),C.byref(seq))
 # Inaccessible write destination propagates status while retaining RAM.
 path.unlink();path.mkdir();assert not c.game_save_flush_tutorials() and c.game_save_status()==2
 assert list(c.game_save_state().contents.tutorials)==[1,0,1,0]
 path.rmdir();assert c.game_save_flush_tutorials() and c.game_save_status()==1
 # Protect unsupported sizes and nonregular destinations.
 other=t/'foreign.sav';other.write_bytes(b'foreign');assert not c.game_save_open_archive(str(other).encode(),None)
 assert other.read_bytes()==b'foreign'
 # Native legacy data is migrated once into the raw archive.
 legacy=t/'legacy';c.game_save_open_directory(str(legacy).encode());c.game_save_state().contents.tutorials[:]=[0,1,0,1];assert c.game_save_flush()==63
 migrated=t/'migrated.sav';assert c.game_save_open_archive(str(migrated).encode(),str(legacy).encode());assert list(c.game_save_state().contents.tutorials)==[0,1,0,1]
 c.save_archive_path.argtypes=[C.c_char_p,C.c_size_t,C.c_char_p,C.c_char_p];c.save_archive_path.restype=C.c_bool
 paths=[(b'fat:/games/Kinder Fresh.nds',b'fat:/',b'fat:/games/Kinder Fresh.sav'),(b'sd:/DS/game.NDS',b'sd:/',b'sd:/DS/game.sav'),(None,b'fat:/',b'fat:/kinder_fresh.sav'),(b'nitro:/game.nds',b'fat:/',b'fat:/kinder_fresh.sav')]
 for rom,drive,expected in paths:
  out=C.create_string_buffer(256);assert c.save_archive_path(out,256,rom,drive) and out.value==expected
 out=C.create_string_buffer(3);assert not c.save_archive_path(out,3,b'fat:/game.nds',b'fat:/')
 result={'save_size_bytes':8192,'startup_creation':True,'empty_file_recovery':True,'blank_placeholder_cases':3,'selective_commits':True,'checksum_recovery_cases':8,'legacy_migration':True,'storage_error_and_retry':True,'loader_path_cases':4,'physical_DSpico_verified':False}
 (R/'research/persistence/sav-archive-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
