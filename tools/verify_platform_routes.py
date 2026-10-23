"""Probe all placed spring-platform records through the production world loop.
Reports terrain/contact outcomes instead of treating every loss of support as a
port bug. Host placement fixtures are not complete DS/keyboard playthroughs.
"""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
R=Path(__file__).resolve().parents[1];IDS={2,200,201,202,210,220,230,231,232,233}
with tempfile.TemporaryDirectory(prefix='kinder-platform-routes-')as tmp:
 t=Path(tmp);w=t/'world.c'
 # Instrument the host fixture only; production world/hazard sources stay intact.
 source=(R/'ds/source/world.c').read_text().replace('unsigned id=entity_id(&objects[i]);\n  if(!entity_active', 'unsigned id=entity_id(&objects[i]);trace_actor=(int)i;trace_id=(int)id;\n  if(!entity_active')
 w.write_text('''
#include "hazards.h"
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
bool test_place(unsigned index,int drop){
 size_t n;GameEntity *e=scene_entities(&n);if(index>=n)return false;target=index;
 GeometryObject o;if(!scene_geometry_object(index,&o))return false;
 if(entity_x(e+index)<0||entity_y(e+index)<0||entity_layer(e+index)!=(unsigned)body.layer)return false;
 body.motion.x=(entity_x(e+index)+o.width/2)*4096;
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
 for world in range(4):
  for tutorial in (False,True):
   assert c.world_open_stage(world,tutorial);name=c.world_map_name().decode();objects=json.loads((R/'generated/maps'/name/'00.json').read_text())['objects'];c.world_close()
   for index,o in enumerate(objects):
    if o['obj_nr']not in IDS:continue
    for drop in (0,76):
     assert c.world_open_stage(world,tutorial)
     if not c.test_place(index,drop):c.world_close();continue
     trace=[];damage_events=[];supported=0;first_loss=None;first_contact=None
     for tick in range(120):
      c.test_clear_damage();assert c.world_tick(0),(name,index,tick)
      if c.test_damage(-1):damage_events.append({'tick':tick,'rectangle_calls':c.test_damage(-1),'last_call':[c.test_damage(k)for k in range(7)]})
      v=[c.test_value(k)for k in range(12)];contact=v[0]>=v[2] and v[0]<v[2]+v[8] and v[1]==v[3]+v[7]
      if contact:supported+=1;first_contact=tick if first_contact is None else first_contact
      if first_contact is not None and not contact and first_loss is None:first_loss=tick
      if tick<12 or tick%10==0 or v[4]<100:trace.append({'tick':tick,'values':v,'supported':contact})
      if v[6]==2:break
     cases.append({'map':name,'world':world,'tutorial':tutorial,'index':index,'id':o['obj_nr'],'drop':drop,'ticks':tick+1,'supported_ticks':supported,'first_contact':first_contact,'first_loss_after_contact':first_loss,'final_health':v[4],'damage_events':damage_events,'trace':trace});c.world_close()
 assert len(cases)==60
 for row in cases:
  assert row['first_contact'] is not None and row['first_loss_after_contact'] is None,(row['map'],row['index'],row['drop'])
  assert row['final_health']==100-20*len(row['damage_events']),row
  for event in row['damage_events']:
   assert event['rectangle_calls']==1 and event['last_call'][1] in (3,6,7) and event['last_call'][6]==20,event
 result={'support_fixtures':60,'placed_platforms':30,'world_ticks':7200,'enemy_damage_events':sum(len(c['damage_events'])for c in cases),'scope':__doc__,'cases':cases,'limits':['Player placed at each original platform center/surface; other original actors and terrain remain active.','A blocked path, scenery support, moving platform escaping a falling player or enemy contact can legitimately end support; these outcomes need native comparison, not automatic classification.']}
 (R/'research/gameplay/platform-route-probes.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps([{k:v for k,v in row.items()if k!='trace'}for row in cases],indent=2))
