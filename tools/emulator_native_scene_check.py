"""Read native scenery cache pins and map publication at a stopped game boundary."""
from functools import lru_cache
from pathlib import Path
import struct,subprocess,tempfile
from emulator_counters import ARTIFACT_DIR,NM,module_bss_symbol

@lru_cache(None)
def layout():
 # Ask the target compiler for field offsets; host FILE pointers/alignment differ.
 expressions={'cache':'offsetof(NativeBGStream,cache)','map':'offsetof(NativeBGStream,map)','front_x':'offsetof(NativeBGStream,front_x)','front_y':'offsetof(NativeBGStream,front_y)','pending':'offsetof(NativeBGStream,pending)'}
 expressions.update({name:'offsetof(NativeBGStream,assets)+offsetof(NativeBGAssets,'+field+')'for name,field in (('asset_block_reads','block_fills'),('asset_block_bytes','block_bytes'))})
 if 'pin_updates'in(ARTIFACT_DIR/'source/native_bg_stream.h').read_text():
  expressions.update({name:'offsetof(NativeBGStream,'+name+')'for name in ('pin_updates','pin_changes_peak')})
 expressions.update({k:'offsetof(NativeBGCache,'+k+')' for k in ('entries','state','hits','uploads','failures','evictions')})
 with tempfile.TemporaryDirectory(prefix='kinder-native-layout-') as td:
  root=Path(td);source=root/'layout.c';obj=root/'layout.o'
  source.write_text('#include "native_bg_stream.h"\n'+''.join('char layout_'+name+'[('+expression+')+1];\n' for name,expression in expressions.items()))
  subprocess.run([str(NM.with_name('arm-none-eabi-gcc')),'-mcpu=arm946e-s','-I'+str(ARTIFACT_DIR/'source'),'-c',str(source),'-o',str(obj)],check=True,capture_output=True)
  offsets={parts[3][7:]:int(parts[1],16)-1 for line in subprocess.check_output([str(NM),'-S',str(obj)],text=True).splitlines() if len(parts:=line.split())==4 and parts[3].startswith('layout_')}
 assert set(offsets)==set(expressions)
 return offsets

def check(rsp):
 offsets=layout()
 def read32(at):return struct.unpack('<I',rsp.read(at,4))[0]
 stream=read32(module_bss_symbol('native_scene','stream'));assert stream,'Native scenery workspace missing'
 cache=stream+offsets['cache'];values={k:read32(cache+offsets[k]) for k in ('state','hits','uploads','failures','evictions')}
 assert values['state']==0 and values['failures']==0,'Native tile cache not successfully published'
 assert not rsp.read(stream+offsets['pending'],1)[0],'Unpublished native view at frame boundary'
 mirror=rsp.read(stream+offsets['map'],4096);actual=rsp.read(0x0600f000,4096)
 assert mirror==actual,'Native scenery map differs from hardware'
 entries=rsp.read(cache+offsets['entries'],960*8);words=struct.unpack('<2048H',mirror)
 x=read32(stream+offsets['front_x']);y=read32(stream+offsets['front_y']);references=0
 for yy in range(y//8,(y+191)//8+1):
  for xx in range(x//8,(x+255)//8+1):
   at=(yy%32)*32+(xx%32)+((xx%64)//32)*1024;slot=words[at]&1023
   assert slot<960 and entries[slot*8+4]&3==3,'Displayed map references an invalid/unpinned tile'
   references+=1
 values.update(map_halfwords_equal=2048,displayed_references_valid=references,pinned_slots=sum(bool(entries[i*8+4]&2) for i in range(960)),front_x=x,front_y=y)
 values.update({name:read32(stream+offsets[name])for name in ('asset_block_reads','asset_block_bytes','pin_updates','pin_changes_peak')if name in offsets})
 return values
