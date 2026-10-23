"""Verify storage adapter defaults and six-file round trips using host stdio."""
import ctypes as C
import json
import subprocess
import tempfile
from pathlib import Path

R=Path(__file__).resolve().parents[1]
class HighscoreTable(C.Structure):
    _fields_=[('names',(C.c_char*30)*10),('score_text',(C.c_char*10)*10)]
class PersistenceState(C.Structure):
    _fields_=[('scores',HighscoreTable*4),('options',C.c_int32*22),
              ('tutorials',C.c_uint8*4)]
with tempfile.TemporaryDirectory(prefix='kinder-save-') as temporary:
    root=Path(temporary)
    library=root/'save.dylib'
    subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',
                    *[str(R/'ds/source'/f'{name}.c') for name in
                      ['game_save','persistence','persistence_store','save_archive']],
                    '-o',str(library)],check=True)
    lib=C.CDLL(str(library))
    lib.game_save_open_directory.argtypes=[C.c_char_p]
    lib.game_save_open_directory.restype=C.c_bool
    lib.game_save_flush.restype=lib.game_save_loaded_files.restype=C.c_uint
    lib.game_save_flush_tutorials.restype=C.c_bool
    lib.game_save_state.restype=C.POINTER(PersistenceState)
    lib.game_save_init()
    assert lib.game_save_flush()==0
    assert not lib.game_save_flush_tutorials()
    directory=root/'storage'
    assert lib.game_save_open_directory(str(directory).encode())
    assert lib.game_save_loaded_files()==0
    assert lib.game_save_flush()==63
    assert lib.game_save_open_directory(str(directory).encode())
    assert lib.game_save_loaded_files()==63
    assert len(list(directory.iterdir()))==6
    other_files={path.name:(path.read_bytes(),path.stat().st_mtime_ns)
                 for path in directory.iterdir() if path.name!='tut.ini'}
    state=lib.game_save_state().contents
    # Deliberately dirty unrelated RAM data: a tutorial flush must not save it.
    state.options[0]+=1
    state.scores[0].names[0].value=b'Unsaved player'
    flags=[1,0,255,2]
    state.tutorials[:]=flags
    assert lib.game_save_flush_tutorials()
    assert (directory/'tut.ini').read_bytes()==bytes(flags)
    assert other_files=={path.name:(path.read_bytes(),path.stat().st_mtime_ns)
                         for path in directory.iterdir() if path.name!='tut.ini'}
    assert lib.game_save_open_directory(str(directory).encode())
    assert list(lib.game_save_state().contents.tutorials)==flags
    assert lib.game_save_loaded_files()==63
    # If the specific destination is unwritable, propagate failure without
    # touching the five unrelated files (works even when running as root).
    (directory/'tut.ini').unlink()
    (directory/'tut.ini').mkdir()
    assert not lib.game_save_flush_tutorials()
    assert other_files=={path.name:(path.read_bytes(),path.stat().st_mtime_ns)
                         for path in directory.iterdir() if path.name!='tut.ini'}
    invalid=root/'not-a-directory';invalid.write_text('retained')
    assert not lib.game_save_open_directory(str(invalid).encode())
    assert lib.game_save_flush()==0 and invalid.read_text()=='retained'
    assert not lib.game_save_flush_tutorials()
    result={'scope':__doc__,'no_storage_uses_ram_defaults':True,
            'owned_directory_created':True,'six_files_saved_and_loaded':True,
            'tutorial_only_exact_four_bytes':True,
            'tutorial_only_preserves_other_five_contents_and_mtimes':True,
            'tutorial_flags_reloaded':True,'tutorial_write_failure_reported':True,
            'existing_regular_file_preserved':True,'DS_FAT_runtime_verified':False}
    (R/'research/persistence/storage_integration.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
