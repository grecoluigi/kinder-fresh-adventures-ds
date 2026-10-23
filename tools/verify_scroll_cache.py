"""Coupled parallax/live-object scroll cache: compare two configured capacities.
Counts host decodes/reads on selected original frame loops; not DS FPS proof.
"""
from pathlib import Path
import ctypes as C,hashlib,json,struct,subprocess,tempfile,argparse
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capacity-kib',nargs=2,type=int,default=[192,272]);parser.add_argument('--hardware-background',action='store_true');parser.add_argument('--output',type=Path,default=R/'research/rendering/scroll-cache-verification.json');args=parser.parse_args()
assert all(0<n<=272 for n in args.capacity_kib)
class Entity(C.Structure):_fields_=[('bytes',C.c_uint8*186)]
class Stats(C.Structure):_fields_=[('values',C.c_uint32*13)]
with tempfile.TemporaryDirectory(prefix='kinder-scroll-cache-')as tmp:
 so=Path(tmp)/'scene.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-DSCENE_ROOT="'+str(R/'ds/nitrofs/scenes')+'"',*[str(R/'ds/source'/f'{n}.c')for n in ('scene','composite','collision')],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.scene_entities.argtypes=[C.POINTER(C.c_size_t)];c.scene_entities.restype=C.POINTER(Entity);c.scene_open.restype=c.scene_render.restype=C.c_bool;c.scene_set_decoded_row_cache.argtypes=[C.POINTER(C.c_uint16),C.c_size_t];c.scene_render_stats.restype=C.POINTER(Stats);c.scene_enable_background_parallax(True);c.scene_enemy_animation_range.argtypes=[C.c_size_t,C.c_uint,C.POINTER(C.c_int16),C.POINTER(C.c_int16)];c.scene_enemy_animation_range.restype=C.c_bool
 arena=(C.c_uint16*(272*1024//2+2))();arena[0]=0x1234;arena[-1]=0x5678;buffer=C.cast(C.byref(arena,2),C.POINTER(C.c_uint16));pixels=(C.c_uint16*49152)();cases=[]
 gpu=(C.c_uint16*(65536+2))();gpu[0]=0x1234;gpu[-1]=0x5678
 if args.hardware_background:
  c.scene_set_hardware_background.argtypes=[C.POINTER(C.c_uint16),C.c_size_t];c.scene_set_hardware_background(C.cast(C.byref(gpu,2),C.POINTER(C.c_uint16)),128*1024)
 for name,id,frames,budget in [('Welt1t.W02',77,list(range(5,16)),256),('Welt2T.W02',77,list(range(5,16)),256),('welt3t.W02',77,list(range(5,16)),256),('welt4t.W02',77,list(range(5,16)),256),('Welt1E.W02',10,list(range(33,39)),512),('Welt2E.W02',9,list(range(42,47)),512),('Welt3E.W02',14,list(range(178,182)),512),('Welt4E.W02',18,list(range(46,50)),512)]:
  hashes=[];variants=[]
  for capacity in (n*1024 for n in args.capacity_kib):
   for i in range(1,len(arena)-1):arena[i]=0x1357
   c.scene_set_decoded_row_cache(buffer,capacity);c.scene_set_sprite_cache_bytes(budget*1024);assert c.scene_open(name.encode());n=C.c_size_t();objects=c.scene_entities(C.byref(n));target=next(i for i in range(n.value)if struct.unpack_from('<H',objects[i].bytes)[0]==id);e=objects[target]
   if args.hardware_background:assert c.scene_hardware_background_active()
   if id==77:
    first=C.c_int16();last=C.c_int16();assert c.scene_enemy_animation_range(target,16,C.byref(first),C.byref(last));frames=list(range(first.value,last.value+1))
   e.bytes[45]=1;e.bytes[185]=0;struct.pack_into('<h',e.bytes,6,255)
   x,y=struct.unpack_from('<hh',e.bytes,2);metadata=json.loads((R/'generated/maps'/name/'00.json').read_text());maxx=max(0,metadata['width_cells']*32-800);maxy=max(0,metadata['height_cells']*32-600);base_x=max(0,min(x-300,maxx));base_y=max(0,min(y-200,maxy));images=[];decodes=hits=reads=0
   for step in range(100):
    phase=step%25;struct.pack_into('<h',e.bytes,14,frames[(step//2)%len(frames)]);e.bytes[43]=(step//25)%2
    assert c.scene_render(pixels,min(base_x+phase,maxx),min(base_y+phase,maxy)),(name,step)
    images.append(hashlib.sha256(bytes(pixels)).hexdigest());stats=c.scene_render_stats().contents.values
    if step>=50:decodes+=stats[11];hits+=stats[12];reads+=stats[0]
   assert all(value==0x1357 for value in arena[capacity//2+1:-1]),(name,capacity,'outside configured cache')
   hashes.append(images);variants.append({'arena_KiB':capacity//1024,'warm50_decodes':decodes,'warm50_hits':hits,'warm50_scene_reads':reads});c.scene_close()
  assert hashes[0]==hashes[1],name;assert arena[0]==0x1234 and arena[-1]==0x5678
  assert gpu[0]==0x1234 and gpu[-1]==0x5678
  cases.append({'map':name,'id':id,'frames':frames,'display_cases':100,'comparisons':variants,'pixel_equivalence':True})
 result={'scope':__doc__,'capacity_KiB':args.capacity_kib,'hardware_background':args.hardware_background,'cases':cases,**{f'total_warm_decodes_{capacity}KiB':sum(c['comparisons'][i]['warm50_decodes']for c in cases)for i,capacity in enumerate(args.capacity_kib)},'arena_canaries':True,'outside_configured_cache_untouched':True,'limits':['Selected frame loops/camera phases in host scene rendering,not complete dynamic fights/dialogue or hardware timings.','Packet-cache/file reads and decoding are distinct; more decoded-cache hits do not prove hardware FPS.']}
 args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
