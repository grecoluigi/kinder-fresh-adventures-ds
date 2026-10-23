"""Production save replacement under injected stdio/rename failures.
Host filesystem fault fixtures; not DS FAT/power-loss durability proof.
"""
from pathlib import Path
import ctypes as C,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
class Table(C.Structure):_fields_=[('names',(C.c_char*30)*10),('scores',(C.c_char*10)*10)]
class State(C.Structure):_fields_=[('scores',Table*4),('options',C.c_int32*22),('tutorials',C.c_uint8*4)]
with tempfile.TemporaryDirectory(prefix='kinder-save-fault-')as tmp:
 t=Path(tmp);wrapper=t/'store.c';wrapper.write_text('''
#include <stdio.h>
#include <string.h>
#include <errno.h>
static int fault;static FILE *target;
void test_fault(int value){fault=value;target=NULL;}
static FILE *fault_open(const char*p,const char*m){
 if(strstr(p,".tmp")&&!strcmp(m,"wb")){if(fault==1){errno=EIO;return NULL;}target=fopen(p,m);return target;}return fopen(p,m);
}
static size_t fault_write(const void*p,size_t s,size_t n,FILE*f){if(f==target&&fault==2)return fwrite(p,s,n/2,f);return fwrite(p,s,n,f);}
static int fault_close(FILE*f){int fail=f==target&&fault==3;int value=fclose(f);if(f==target)target=NULL;if(fail){errno=EIO;return EOF;}return value;}
static int fault_rename(const char*a,const char*b){
 int backup=strstr(b,".bak")!=NULL,publication=strstr(a,".tmp")!=NULL,rollback=strstr(a,".bak")!=NULL;
 if((fault==4&&backup)||((fault==5||fault==6)&&publication)||(fault==6&&rollback)){errno=EIO;return -1;}return rename(a,b);
}
#define fopen fault_open
#define fwrite fault_write
#define fclose fault_close
#define rename fault_rename
#include "'''+str(R/'ds/source/persistence_store.c')+'"\n');so=t/'store.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(wrapper),str(R/'ds/source/persistence.c'),'-o',str(so)],check=True);c=C.CDLL(str(so));c.persistence_defaults.argtypes=[C.POINTER(State),C.c_bool];c.persistence_save_tutorials.argtypes=[C.c_char_p,C.POINTER(State)];c.persistence_save_tutorials.restype=C.c_bool;c.persistence_load.argtypes=[C.c_char_p,C.POINTER(State)];c.persistence_load.restype=C.c_uint;state=State();c.persistence_defaults(C.byref(state),True);cases=[]
 for fault in range(7):
  folder=t/f'case{fault}';folder.mkdir();path=folder/'tut.ini';old=bytes([1,0,1,0]);new=bytes([0,1,0,1]);path.write_bytes(old);other=folder/'Highscore1.dat';other.write_bytes(b'unrelated');state.tutorials[:]=new;c.test_fault(fault);ok=c.persistence_save_tutorials(str(folder).encode(),C.byref(state));assert ok==(fault==0)
  if fault!=6:assert path.read_bytes()==(new if ok else old),fault
  else:assert not path.exists() and Path(str(path)+'.bak').read_bytes()==old
  assert other.read_bytes()==b'unrelated';assert not Path(str(path)+'.tmp').exists()
  c.test_fault(0);loaded=State();c.persistence_defaults(C.byref(loaded),True);mask=c.persistence_load(str(folder).encode(),C.byref(loaded));assert mask&32;assert bytes(loaded.tutorials)==(new if ok else old),fault;assert path.exists()
  cases.append({'fault':fault,'reported_success':ok,'previous_save_recovered':fault!=0,'unrelated_file_unchanged':True})
 # Simulated interruption after backup, and after publishing the new file.
 for publication in (False,True):
  folder=t/('published'if publication else'backedup');folder.mkdir();path=folder/'tut.ini';Path(str(path)+'.bak').write_bytes(old);Path(str(path)+'.tmp').write_bytes(new)
  if publication:path.write_bytes(new)
  loaded=State();c.persistence_defaults(C.byref(loaded),True);assert c.persistence_load(str(folder).encode(),C.byref(loaded))&32;assert bytes(loaded.tutorials)==(new if publication else old)
 result={'scope':__doc__,'failure_cases':cases,'interrupted_backup_restores_prior_save':True,'published_new_file_preferred_over_backup':True,'limits':['Injected host errors prove preservation/recovery logic, not FAT rename/fsync guarantees under actual power loss.','Formats unchanged; game still needs actual DS save/reload testing.']};(R/'research/persistence/save-failure-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
