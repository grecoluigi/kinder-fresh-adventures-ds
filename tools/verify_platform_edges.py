"""Probe original platform edge placement and side approaches in the production world loop.
Reports terrain/contact outcomes instead of treating every loss of support as a
port bug. Host placement fixtures are not complete DS/keyboard playthroughs.
"""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
R=Path(__file__).resolve().parents[1];IDS={2,200,201,202,210,220,230,231,232,233}
# Replay original body integration on the actual production point-query inputs.
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX,UC_X86_REG_ECX
pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));native=Uc(UC_ARCH_X86,UC_MODE_32);image=pe.get_memory_mapped_image()
native.mem_map(0x400000,(len(image)+4095)&~4095);native.mem_write(0x400000,image)
for address,size in ((0x200000,0x3000),(0x300000,0x1000),(0x4000,0x1000)):native.mem_map(address,size)
Probe=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_uint)
Observer=C.CFUNCTYPE(None,C.POINTER(C.c_int32),Probe,C.c_void_p);Checker=C.CFUNCTYPE(None,C.POINTER(C.c_int32));Query=C.CFUNCTYPE(None,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_bool)
native_trace=[];port_trace=[];native_expected=b'';native_cases=0;native_query_count=0;native_failures=[];current_probe=None;current_context=None
def native_hook(uc,address,size,context):
 sp=uc.reg_read(UC_X86_REG_ESP);pc,layer,x,y,mode=struct.unpack('<IiiiI',uc.mem_read(sp,20));hit=bool(current_probe(current_context,layer,x,y,mode));native_trace.append((layer,x,y,mode,hit));uc.reg_write(UC_X86_REG_EAX,int(hit));uc.reg_write(UC_X86_REG_ESP,sp+20);uc.reg_write(UC_X86_REG_EIP,pc)
native.hook_add(UC_HOOK_CODE,native_hook,begin=0x431e90,end=0x431e90)
@Observer
def before_body(body,probe,context):
 global native_expected,native_cases,native_query_count,current_probe,current_context
 try:
  current_probe=probe;current_context=context;native_trace.clear();port_trace.clear();native.mem_write(0x300000,C.string_at(body,132));native.mem_write(0x201000,struct.pack('<2I',0x4000,0x300000));native.reg_write(UC_X86_REG_ESP,0x201000);native.reg_write(UC_X86_REG_ECX,0);native.emu_start(0x432350,0x4000,count=100000)
  assert native.reg_read(UC_X86_REG_EIP)==0x4000
  native_expected=bytes(native.mem_read(0x300000,132));native_cases+=1;native_query_count+=len(native_trace)
 except Exception as error:native_failures.append(repr(error))
@Query
def port_query(layer,x,y,mode,hit):port_trace.append((layer,x,y,mode,bool(hit)))
@Checker
def after_body(body):
 if native_expected!=C.string_at(body,132)or native_trace!=port_trace:native_failures.append({'case':native_cases,'native_body':native_expected.hex(),'port_body':C.string_at(body,132).hex(),'query_order_matches':native_trace==port_trace})
with tempfile.TemporaryDirectory(prefix='kinder-platform-routes-')as tmp:
 t=Path(tmp);w=t/'world.c'
 # Instrument the host fixture only; production world/hazard sources stay intact.
 source=(R/'ds/source/world.c').read_text().replace('body_step(&body,world_probe,(void *)map);','traced_body_step(&body,world_probe,(void *)map);').replace('unsigned id=entity_id(&objects[i]);\n  if(!entity_active', 'unsigned id=entity_id(&objects[i]);trace_actor=(int)i;trace_id=(int)id;\n  if(!entity_active')
 w.write_text('''
#include "hazards.h"
#include <stddef.h>
typedef void (*BodyObserver)(GameBody*,BodyProbe,void*);
typedef void (*BodyChecker)(GameBody*);
typedef void (*QueryObserver)(int,int,int,unsigned,bool);
static BodyObserver body_observer;static BodyChecker body_checker;static QueryObserver query_observer;
static BodyProbe forwarded_probe;static void *forwarded_context;
void test_native_observers(BodyObserver before,BodyChecker after,QueryObserver query){body_observer=before;body_checker=after;query_observer=query;}
static bool traced_probe(void*ctx,int layer,int x,int y,unsigned mode){(void)ctx;bool hit=forwarded_probe(forwarded_context,layer,x,y,mode);if(query_observer)query_observer(layer,x,y,mode,hit);return hit;}
static void traced_body_step(GameBody*b,BodyProbe probe,void*ctx){forwarded_probe=probe;forwarded_context=ctx;if(body_observer)body_observer(b,probe,ctx);body_step(b,traced_probe,NULL);if(body_checker)body_checker(b);}
static int trace_actor=-1,trace_id=-1,damage_count,damage_record[7];
static bool traced_rect_hazard(Player*p,const GameBody*b,int x,int y,int width,int height,int damage,const PlayerEnvironment*env){
 int before=p->health;bool hit=player_rect_hazard(p,b,x,y,width,height,damage,env);
 if(p->health<before){damage_count++;damage_record[0]=trace_actor;damage_record[1]=trace_id;
 damage_record[2]=x;damage_record[3]=y;damage_record[4]=width;damage_record[5]=height;damage_record[6]=damage;}
 return hit;
}
#define player_rect_hazard traced_rect_hazard
'''+source+'''
#undef player_rect_hazard
int test_damage(int key){return key<0?damage_count:damage_record[key];}
void test_clear_damage(void){damage_count=0;trace_actor=trace_id=-1;}
'''+'''
static size_t target;
bool test_place(unsigned index,int drop,int offset){
 size_t n;GameEntity *e=scene_entities(&n);if(index>=n)return false;target=index;
 GeometryObject o;if(!scene_geometry_object(index,&o))return false;
 if(entity_x(e+index)<0||entity_y(e+index)<0||entity_layer(e+index)!=(unsigned)body.layer)return false;
 body.motion.x=(entity_x(e+index)+(offset==9999?o.width-1:offset==9998?o.width+48:offset))*4096;
 if(body.motion.x<0||body.motion.x/4096>=scene_metadata()->width_pixels)return false;
 body.motion.y=(entity_y(e+index)+e[index].bytes[42]-drop)*4096;
 body.motion.vx=body.motion.vy=body.motion.ax=body.motion.ay=0;
 player.state=0;player.health=100;player.facing=0;player.character=0;
 const SceneMetadata*m=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};
 camera_init(&camera,m->width_cells,m->height_cells,body.motion.x/4096-400,body.motion.y/4096-380,f,2);
 return true;
}
int test_value(int key){
 size_t n;GameEntity *e=scene_entities(&n);e+=target;
 switch(key){case 0:return body.motion.x/4096;case 1:return body.motion.y/4096;
 case 2:return entity_x(e);case 3:return entity_y(e);case 4:return player.health;
 case 5:return player.state;case 6:return player.game_mode;
 case 7:return e->bytes[42];case 8:{GeometryObject o;return scene_geometry_object(target,&o)?o.width:0;}
 case 9:return body.motion.vy;case 10:return e->bytes[39];case 11:return player.hit_feet;
 default:return -1;}
}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),*[f'-D{k}="{v}"'for k,v in defs.items()],str(w),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=c.test_place.restype=C.c_bool;c.world_map_name.restype=C.c_char_p;cases=[]
 c.test_native_observers.argtypes=[Observer,Checker,Query];c.test_native_observers(before_body,after_body,port_query)
 for world in range(4):
  for tutorial in (False,True):
   assert c.world_open_stage(world,tutorial);name=c.world_map_name().decode();objects=json.loads((R/'generated/maps'/name/'00.json').read_text())['objects'];c.world_close()
   for index,o in enumerate(objects):
    if o['obj_nr']not in IDS:continue
    for kind,drop,offset,keys in (('left-edge',0,0,0),('right-edge',0,9999,0),('left-approach',160,-48,8),('right-approach',160,9998,4)):
     assert c.world_open_stage(world,tutorial)
     if not c.test_place(index,drop,offset):c.world_close();continue
     trace=[];damage_events=[];supported=0;first_loss=None;first_contact=None
     for tick in range(120):
      c.test_clear_damage();assert c.world_tick(keys if first_contact is None else 0),(name,index,tick)
      if c.test_damage(-1):damage_events.append({'tick':tick,'rectangle_calls':c.test_damage(-1),'last_call':[c.test_damage(k)for k in range(7)]})
      v=[c.test_value(k)for k in range(12)];contact=v[0]>=v[2] and v[0]<v[2]+v[8] and v[1]==v[3]+v[7]
      if contact:supported+=1;first_contact=tick if first_contact is None else first_contact
      if first_contact is not None and not contact and first_loss is None:first_loss=tick
      if tick<30 or tick%10==0 or v[4]<100:trace.append({'tick':tick,'values':v,'supported':contact})
      if v[6]==2:break
     cases.append({'map':name,'world':world,'tutorial':tutorial,'index':index,'id':o['obj_nr'],'fixture':kind,'drop':drop,'offset':offset,'keys_until_contact':keys,'ticks':tick+1,'supported_ticks':supported,'first_contact':first_contact,'first_loss_after_contact':first_loss,'final_health':v[4],'damage_events':damage_events,'trace':trace});c.world_close()
 assert len(cases)==118
 assert not native_failures,native_failures[:1]
 assert sum(c['first_contact']is not None for c in cases)==117
 assert not any(c['first_loss_after_contact']is not None for c in cases)
 result={'native_body_steps_compared':native_cases,'native_point_queries_compared':native_query_count,'native_body_bytes_and_query_order_equal':True,'native_boundary':'Original432350 body solver/integrator executes;431e90 uses current production tile/dynamic geometry query, independently covered by native geometry/collision checks. Player state, world callbacks and full gameplay are not replayed natively here.','scope':__doc__,'fixture_count':len(cases),'contact_fixtures':sum(c['first_contact']is not None for c in cases),'support_losses':sum(c['first_loss_after_contact']is not None for c in cases),'cases':cases,'limits':['Full original actors/terrain remain active; side approaches can miss a moving target or encounter enemies.','Player is placed near original platform edges; these are scoped host fixtures, not complete keyboard/DS playthroughs.','Do not classify damage or contact loss as a port bug without native comparison.']}
 (R/'research/gameplay/platform-edge-probes.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps([{k:v for k,v in row.items()if k!='trace'}for row in cases],indent=2))
