"""Production preselected enemy-shot block candidates vs prior full selection scan.
Live active/solid/frame changes and allocation fallback; not DS FPS proof.
"""
from pathlib import Path
import ast,ctypes as C,json,random,struct,subprocess,tempfile
R=Path(__file__).resolve().parents[1];source=(R/'tools/verify_world_tutorials.py').read_text();names=ast.literal_eval(next(line.strip().split('=',1)[1]for line in source.splitlines()if line.strip().startswith('names=')))
class Entity(C.Structure):_fields_=[('raw',C.c_uint8*186)]
with tempfile.TemporaryDirectory(prefix='kinder-shot-candidates-')as tmp:
 t=Path(tmp);wrapper=t/'world.c';wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
bool test_old(int x,int y){
 size_t count;GameEntity*objects=scene_entities(&count);
 for(size_t selected=selected_count;selected>0;){
  size_t i=geometry_indices[--selected];if(i>=count)continue;unsigned id=entity_id(objects+i);
  if((id!=76&&id!=78&&id!=83&&id!=86&&id!=87)||!entity_active(objects+i)||!objects[i].bytes[26])continue;
  GeometryObject o;if(scene_geometry_object(i,&o)&&enemy_shot_obstacle_test(&o,1,x,y))return true;
 }return false;
}
bool test_new(int x,int y,bool fallback){bool cached=shot_obstacle_cached;shot_obstacle_cached=!fallback&&cached;bool hit=enemy_shot_obstacle(NULL,x,y);shot_obstacle_cached=cached;return hit;}
size_t test_count(bool obstacles){return obstacles?shot_obstacle_count:selected_count;}
''');defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'};so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"'for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(so)],check=True);c=C.CDLL(str(so));c.world_open_stage.restype=c.test_old.restype=c.test_new.restype=C.c_bool;c.test_new.argtypes=[C.c_int,C.c_int,C.c_bool];c.test_count.restype=C.c_size_t;c.scene_entities.argtypes=[C.POINTER(C.c_size_t)];c.scene_entities.restype=C.POINTER(Entity);rng=random.Random(413070);checks=0;maps=[]
 for world in range(8):
  for tutorial in ((False,True)if world<4 else(False,)):
   assert c.world_open_stage(world,tutorial);n=C.c_size_t();objects=c.scene_entities(C.byref(n));selected=c.test_count(False);blocks=c.test_count(True);points=[(rng.randrange(-100,12000),rng.randrange(-100,8000))for _ in range(512)]
   targets=[]
   for i in range(n.value):
    id,x,y=struct.unpack_from('<Hhh',objects[i].raw)
    if id in (76,78,83,86,87):targets.append(i);points.extend((x+dx,y+dy)for dx in(-1,0,20,60,150,300)for dy in(-1,0,20,60,150,300))
   originals={i:bytes(objects[i])for i in targets}
   for variation in range(5):
    for i in targets:
     C.memmove(C.byref(objects[i]),originals[i],186)
     if variation==1:struct.pack_into('<h',objects[i].raw,6,0)
     if variation==2:objects[i].raw[26]=0
     if variation==3:struct.pack_into('<h',objects[i].raw,14,-1)
     if variation==4:objects[i].raw[43]^=1
    for x,y in points:
     expected=c.test_old(x,y)
     for fallback in(False,True):assert c.test_new(x,y,fallback)==expected,(world,tutorial,variation,x,y,fallback);checks+=1
   maps.append({'world':world,'tutorial':tutorial,'selected_objects':selected,'block_candidates':blocks,'candidate_heap_bytes':blocks*2});c.world_close()
 result={'scope':__doc__,'query_comparisons':checks,'maps':maps,'limits':['Index membership assumes map object IDs/layers remain fixed,as existing tick lists; runtime active/solid/frame values remain checked.','Fallback query uses prior complete list when allocation fails.','Host equality and reduced candidate counts,not hardware FPS or full combat/playthrough verification.']};(R/'research/gameplay/shot-obstacle-candidates-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='maps'}))
