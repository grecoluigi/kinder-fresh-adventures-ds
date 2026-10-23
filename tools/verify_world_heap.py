"""Bound project heap allocations against the linked DS heap on all main/tutorial/arena maps.
Host stdio/SDK allocations are excluded; reserve64KiB for runtime/storage overhead.
"""
import argparse,ctypes as C,json,os,subprocess,tempfile,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--artifact-dir',type=Path,default=R/'ds');parser.add_argument('--source-overlay-dir',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--gpu-layout',action='store_true');parser.add_argument('--native-layout',action='store_true');parser.add_argument('--native-root',type=Path);args=parser.parse_args()
args.artifact_dir=args.artifact_dir.resolve()
if args.source_overlay_dir:args.source_overlay_dir=args.source_overlay_dir.resolve()
if (args.artifact_dir.resolve()!=R/'ds' or args.source_overlay_dir) and not args.output:parser.error('Use --output for an isolated artifact/overlay check')
def source(name):
 candidate=args.source_overlay_dir/name if args.source_overlay_dir else None
 return candidate if candidate and candidate.exists() else R/'ds/source'/name
scene_root=Path(os.environ.get('KF_SCENE_OUTPUT_ROOT',str(R/'ds/nitrofs/scenes')))
nm=Path.home()/'.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin/arm-none-eabi-nm'
elf=args.artifact_dir/'build/kinder_fresh.elf';elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest()
symbols=subprocess.check_output([str(nm),str(elf)],text=True)
addresses={line.split()[2]:int(line.split()[0],16) for line in symbols.splitlines() if len(line.split())==3 and line.split()[2] in ('__end__','__eheap_end')}
heap=addresses['__eheap_end']-addresses['__end__'];reserve=65536;budget=heap-reserve
with tempfile.TemporaryDirectory(prefix='kinder-heap-') as temporary:
 t=Path(temporary);tracker=t/'tracker.c'
 tracker.write_text('''
#undef malloc
#undef calloc
#undef realloc
#undef free
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef union {struct {size_t bytes;} info;max_align_t alignment;} Header;
static size_t used,peak,limit,failures;
void heap_limit(size_t n){limit=n;peak=used;failures=0;}
size_t heap_peak(void){return peak;}size_t heap_used(void){return used;}
size_t heap_failures(void){return failures;}
void *tracked_malloc(size_t bytes){
 if(bytes>SIZE_MAX-sizeof(Header)||used+bytes+sizeof(Header)>limit){failures++;return NULL;}
 Header*p=malloc(bytes+sizeof(Header));if(!p)return NULL;p->info.bytes=bytes;
 used+=bytes+sizeof(Header);if(used>peak)peak=used;return p+1;
}
void tracked_free(void *ptr){if(!ptr)return;Header*p=(Header*)ptr-1;used-=p->info.bytes+sizeof(Header);free(p);}
void *tracked_calloc(size_t count,size_t bytes){if(bytes&&count>SIZE_MAX/bytes)return NULL;void*p=tracked_malloc(count*bytes);if(p)memset(p,0,count*bytes);return p;}
void *tracked_realloc(void*ptr,size_t bytes){if(!ptr)return tracked_malloc(bytes);if(!bytes){tracked_free(ptr);return NULL;}Header*p=(Header*)ptr-1;void*q=tracked_malloc(bytes);if(q){memcpy(q,ptr,bytes<p->info.bytes?bytes:p->info.bytes);tracked_free(ptr);}return q;}
''')
 wrapper=t/'world.c';wrapper.write_text('#include "'+str(source('world.c'))+'"\n'+'''
bool test_banner(uint16_t *pixels){end_title.action=2;end_title_tick(&end_title);return end_title_draw(&end_title,pixels);}
void test_position(int cx,int cy){
 const SceneMetadata*m=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};
 body.motion.x=(cx+400)*4096;body.motion.y=(cy+450)*4096;
 camera_init(&camera,m->width_cells,m->height_cells,cx,cy,f,2);
}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 if source('gpu_actors.c').exists():names.append('gpu_actors')
 if args.native_layout:names.append('native_actors')
 embedded=args.artifact_dir/'nitrofs'
 defs={'SCENE_ROOT':scene_root,'PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','HUD_BACKGROUND_ROOT':R/'ds/nitrofs/hud_backgrounds','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 if (embedded/'composite').exists():defs['COMPOSITE_ROOT']=(embedded/'composite').resolve()
 if args.native_layout:
  roots=[args.source_overlay_dir/'nitrofs/native_actors' if args.source_overlay_dir else None,embedded/'native_actors',R/'ds/nitrofs/native_actors']
  defs['NATIVE_ACTOR_ROOT']=(args.native_root or next(p for p in roots if p and p.exists())).resolve()
 includes=['-I'+str(R/'ds/source')]
 if args.native_layout:includes+=['-DKF_HOST_GPU_ACTORS=1','-DKF_HOST_NATIVE_ACTORS=1']
 if args.source_overlay_dir:includes.insert(0,'-I'+str(args.source_overlay_dir))
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*includes,*[f'-D{k}="{v}"' for k,v in defs.items()],'-Dmalloc=tracked_malloc','-Dcalloc=tracked_calloc','-Drealloc=tracked_realloc','-Dfree=tracked_free',str(tracker),str(wrapper),*[str(source(f'{n}.c')) for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.heap_limit.argtypes=[C.c_size_t]
 for name in ('heap_peak','heap_used','heap_failures'):getattr(c,name).restype=C.c_size_t
 c.world_open_stage.restype=c.world_tick.restype=c.world_render.restype=C.c_bool
 if args.gpu_layout:
  c.scene_set_hardware_background.argtypes=[C.c_void_p,C.c_size_t];c.scene_set_decoded_row_cache.argtypes=[C.c_void_p,C.c_size_t]
  hardware_background=(C.c_uint16*65536)();decoded_rows=(C.c_uint16*24576)()
  c.scene_set_hardware_background(hardware_background,C.sizeof(hardware_background));c.scene_set_decoded_row_cache(decoded_rows,C.sizeof(decoded_rows));c.composite_enable_texture_prefix(True)
 if args.native_layout and args.gpu_layout and hasattr(c,'gpu_native_allow'):c.gpu_native_allow(True)
 c.world_map_name.restype=C.c_char_p;pixels=(C.c_uint16*49152)();cases=[]
 for world in range(8):
  for tutorial in ((False,True) if world<4 else (False,)):
   c.heap_limit(budget);assert c.world_open_stage(world,tutorial)
   name=c.world_map_name().decode();metadata=json.loads((R/'generated/maps'/name/'00.json').read_text())
   maxx=metadata['width_cells']*32-800;maxy=metadata['height_cells']*32-600
   positions=[(maxx*i//8,maxy*j//4) for i in range(9) for j in range(5)]
   for x,y in positions:
    c.test_position(x,y)
    assert c.world_tick(0) and c.world_render(pixels),(name,x,y)
   assert c.test_banner(pixels),name
   peak=c.heap_peak();assert peak>100000 and not c.heap_failures(),name
   cases.append({'map':name,'positions':len(positions),'ending_cache_included':True,'project_heap_peak':peak,'remaining_after_runtime_reserve':budget-peak})
   c.world_close();assert c.heap_used()==0,(name,c.heap_used())
 assert hashlib.sha256(elf.read_bytes()).hexdigest()==elf_sha256,'Linked ELF changed during heap verification; rerun after the build finishes'
 result={'scope':__doc__,'elf_sha256':elf_sha256,'gpu_layout':args.gpu_layout,'native_layout':args.native_layout,'asset_roots':{k:str(v)for k,v in defs.items()},'linked_heap_bytes':heap,'runtime_reserve_bytes':reserve,'project_budget_bytes':budget,'maps':cases,'limits':['Host allocation wrappers exercise45 camera positions per map; not a complete playthrough.','SDK/stdIO allocations are reserved, not measured. H diagnostic will report actual DS free heap.']}
 output=args.output or R/'research/rendering/world-heap-verification.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
