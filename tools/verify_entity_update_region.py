"""Original active/frame/persistent/350px region gates and post-callback blink.
Frame-info/bounds services supplied from production metadata or synthetic fixtures;
original gate and blink instructions execute. No full engine/playthrough claim.
"""
from pathlib import Path
import ctypes as C,json,random,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX,UC_X86_REG_EBP,UC_X86_REG_EDI,UC_X86_REG_EDX
R=Path(__file__).resolve().parents[1]
class Entity(C.Structure):_fields_=[('raw',C.c_uint8*186)]
class Geometry(C.Structure):_fields_=[(n,C.c_int16)for n in ('id','x','y','active','width','height','align_x','align_y')]+[('solid',C.c_uint8),('top_trim',C.c_uint8),('index',C.c_int32)]
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));image=pe.get_memory_mapped_image();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,0x50000)
STACK=0x208000;OBJ=0x210000;ENGINE=0x230000;CON=0x240000;geometry=None;present=False;phase=0;result=False

def ret(pop,value=0):
 sp=u.reg_read(UC_X86_REG_ESP);pc=struct.unpack('<I',u.mem_read(sp,4))[0];u.reg_write(UC_X86_REG_ESP,sp+4+pop);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,pc)
def hook(uc,at,size,ctx):
 global result
 sp=uc.reg_read(UC_X86_REG_ESP)
 if at==0x430b90:
  _,frame,output=struct.unpack('<3I',uc.mem_read(sp+4,12));uc.mem_write(output,struct.pack('<H',2 if present else 0)+bytes(20));ret(12)
 elif at==0x431300:
  _,*outputs=struct.unpack('<5I',uc.mem_read(sp+4,20))
  for p,v in zip(outputs,(geometry.width,geometry.height,geometry.align_x,geometry.align_y)):uc.mem_write(p,struct.pack('<h',v))
  ret(20)
 elif phase==0 and at in (0x4336da,0x433868):
  result=at==0x4336da and bool(struct.unpack('<I',uc.mem_read(sp+0x18,4))[0]);uc.emu_stop()
 elif phase==1 and at in (0x4339f9,0x433a39):result=at==0x4339f9;uc.emu_stop()
u.hook_add(UC_HOOK_CODE,hook)

def native(raw,cx,cy,visual):
 global phase,result
 phase=int(visual);result=False;u.mem_write(OBJ,raw);u.mem_write(CON+2,struct.pack('<I',OBJ));u.mem_write(ENGINE+0x14d1,struct.pack('<I',CON));u.mem_write(ENGINE+0x14c5,struct.pack('<2i',800,600));u.mem_write(STACK,bytes(256));u.mem_write(STACK+(0x24 if visual else 0x28),struct.pack('<2i',cx,cy));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_EAX,CON);u.reg_write(UC_X86_REG_EDX,0)
 u.reg_write(UC_X86_REG_EDI if visual else UC_X86_REG_EBP,ENGINE);u.emu_start(0x4338fe if visual else 0x433600,0x433b00,count=10000)
 return result,bytes(u.mem_read(OBJ,186))

with tempfile.TemporaryDirectory(prefix='kinder-region-')as tmp:
 t=Path(tmp);w=t/'world.c';w.write_text('''
#include "scene.h"
static bool override_enabled,override_present;static GeometryObject override_geometry;static size_t selected_index;
static bool probe_geometry(size_t index,GeometryObject*out){if(override_enabled&&index==selected_index){if(override_present)*out=override_geometry;return override_present;}return scene_geometry_object(index,out);}
/* Preserve injected frame-info services for synthetic native fixtures; real
 * shipped-record fixtures call the production fused region predicate. */
static bool probe_region(size_t index,int cx,int cy){
 if(!override_enabled||index!=selected_index)return scene_entity_update_region(index,cx,cy);
 GeometryObject g;if(!probe_geometry(index,&g))return false;
 size_t count;GameEntity*objects=scene_entities(&count);if(objects[index].bytes[184])return true;
 int left=g.x+g.align_x,top=g.y+g.align_y;
 return left+g.width>cx-350&&left<cx+1150&&top+g.height>cy-350&&top<cy+950;
}
#define scene_entity_update_region probe_region
#define scene_geometry_object probe_geometry
#include "'''+str(R/'ds/source/world.c')+'''"
#undef scene_geometry_object
#undef scene_entity_update_region
void test_setup(unsigned index,const GameEntity*raw,int cx,int cy,bool force,bool present,const GeometryObject*g){
 size_t count;GameEntity*objects=scene_entities(&count);selected_index=index;objects[index]=*raw;override_enabled=force;override_present=present;if(g)override_geometry=*g;
 unsigned layer=entity_layer(objects+index);if(layer<8)camera.layers[layer]=(CameraLayer){cx/32,cy/32,-(cx%32),-(cy%32),2,2};
}
bool test_geometry(GeometryObject*g){return probe_geometry(selected_index,g);}
bool test_eligible(void){size_t count;GameEntity*objects=scene_entities(&count);return entity_needs_update(selected_index,objects+selected_index);}
void test_visual(void){world_entity_visual_step(selected_index);}
void test_record(GameEntity*out){size_t count;GameEntity*objects=scene_entities(&count);*out=objects[selected_index];}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),*[f'-D{k}="{v}"'for k,v in defs.items()],str(w),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.scene_open.restype=c.test_geometry.restype=c.test_eligible.restype=C.c_bool;c.test_setup.argtypes=[C.c_uint,C.POINTER(Entity),C.c_int,C.c_int,C.c_bool,C.c_bool,C.POINTER(Geometry)];c.test_record.argtypes=[C.POINTER(Entity)];c.test_geometry.argtypes=[C.POINTER(Geometry)];rng=random.Random(433662);checks=visuals=records=synthetic=0
 def compare(index,raw,cx,cy,force=False,g=None,has_geometry=True):
  global geometry,present,checks,visuals
  e=Entity.from_buffer_copy(raw);c.test_setup(index,C.byref(e),cx,cy,force,has_geometry,C.byref(g)if g else None);geometry=Geometry();present=bool(c.test_geometry(C.byref(geometry)))
  expected,_=native(raw,cx,cy,False);assert bool(c.test_eligible())==expected,(index,cx,cy,'gate',present,list(raw[184:186]));checks+=1
  _,expected_raw=native(raw,cx,cy,True);c.test_visual();actual=Entity();c.test_record(C.byref(actual));assert bytes(actual)==expected_raw,(index,cx,cy,'visual',present);visuals+=1
 for item in json.loads((R/'generated/maps/inventory.json').read_text()):
  name=item['file'];assert c.scene_open(name.encode());data=(R/'ds/nitrofs/scenes'/f'{name}.entities').read_bytes();n=struct.unpack_from('<I',data,4)[0]
  for index in range(n):
   raw=bytearray(data[8+index*186:8+(index+1)*186]);x,y=struct.unpack_from('<hh',raw,2)
   for cx,cy in ((0,0),(x+350,y+350),(x-1150,y-950),(x-400,y-300)):
    probe=bytearray(raw);probe[45]=rng.randrange(256);probe[46]=rng.randrange(256);compare(index,bytes(probe),cx,cy)
   records+=1
  c.scene_close()
 assert c.scene_open(b'Welt1.W02')
 for case in range(4096):
  raw=bytearray(rng.randbytes(186));struct.pack_into('<hhhh',raw,0,210,rng.randrange(-30000,30000),rng.randrange(-30000,30000),rng.choice((0,1,255,-1)));raw[25]=rng.randrange(8);raw[184]=rng.choice((0,0,0,1,255));g=Geometry(210,*struct.unpack_from('<hh',raw,2),struct.unpack_from('<h',raw,6)[0],rng.randrange(-200,800),rng.randrange(-200,600),rng.randrange(-200,200),rng.randrange(-200,200),1,30,0)
  cx=rng.randrange(-20000,20000);cy=rng.randrange(-20000,20000)
  # Explicit strict border cases accompany random signed coordinates.
  if case%4==0:cx=g.x+g.align_x+g.width+350
  elif case%4==1:cx=g.x+g.align_x-1150
  elif case%4==2:cy=g.y+g.align_y+g.height+350
  compare(0,bytes(raw),cx,cy,True,g,case%7!=0);synthetic+=1
 c.scene_close();result={'scope':__doc__,'shipped_records':records,'native_gate_cases':checks,'native_visual_cases':visuals,'synthetic_cases':synthetic,'all186_post_visual_bytes_equal':True,'limits':['Native layer/group selection and frame-info service availability are supplied boundaries,not full engine dispatch.','Actual current-frame geometry metadata has separate original-AOM validation.','No full gameplay/emulator/hardware timing verification.']}
 (R/'research/gameplay/entity-update-region-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
