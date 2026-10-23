"""Integrated real-map milk push, block movement/friction and geometry update."""
import ctypes as C,json,subprocess,tempfile,os
from pathlib import Path
R=Path(__file__).resolve().parents[1];SCENES=Path(os.environ.get('KF_SCENE_OUTPUT_ROOT',str(R/'ds/nitrofs/scenes')))
with tempfile.TemporaryDirectory(prefix='kinder-world-blocks-') as temporary:
 p=Path(temporary);w=p/'probe.c';w.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'
 'static int selected_block,selected_facing;\n'
 'int prepare_block(void){size_t count;GameEntity*o=scene_entities(&count);for(size_t i=0;i<count;i++)if(entity_id(o+i)==76){EntityEnvironment r={0};if(!scene_entity_environment(i,&r))return 0;int y=entity_y(o+i)+r.height;for(int side=0;side<2;side++){int x=entity_x(o+i)+(side?r.width+31:-31);const CollisionMap*m=scene_collision_map();for(int yy=entity_y(o+i)+130;yy<=y+90;yy++)if(body_map_probe((void*)m,2,x,yy,3)){body.motion.x=x*4096;body.motion.y=yy*4096;body.motion.vx=body.motion.vy=0;const SceneMetadata*s=scene_metadata();const int16_t f[8]={2,2,2,2,2,2,2,2};camera_init(&camera,s->width_cells,s->height_cells,x-200,yy-400,f,2);selected_block=(int)i;selected_facing=side;return 1;}}}return 0;}\n'
 'void milk_push(void){player.character=1;player.state=33;player.facing=selected_facing;player.milk.frame=176;player.milk.first=172;player.milk.last=190;player.milk.timer=0;}\n'
 'int block_x(void){size_t n;GameEntity*e=scene_entities(&n);return entity_x(e+selected_block);}\n'
 'float block_vx(void){size_t n;GameEntity*e=scene_entities(&n);float v;memcpy(&v,e[selected_block].bytes+156,4);return v;}\n'
 'int block_grounded(void){return body_has_contact(&body,body_map_probe,(void*)scene_collision_map());}\n')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':SCENES,'PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots'}
 so=p/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"' for k,v in defs.items()],str(w),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=C.c_bool;c.block_vx.restype=C.c_float
 assert c.world_open_stage(0,False);assert c.prepare_block();assert c.world_tick(0);assert c.block_grounded()
 before=c.block_x();c.milk_push();assert c.world_tick(0)
 after=c.block_x();velocity=c.block_vx();assert abs(after-before)>0,(before,after,c.world_player_state(),velocity)
 assert 0<abs(velocity)<7,velocity
 for _ in range(40):assert c.world_tick(0)
 assert c.block_vx()==0
 final=c.block_x();assert (final-after)*velocity>=0
 c.world_close();result={'scope':__doc__,'map':'Welt1.W02','object_selection':'first jungle block with adjacent real terrain support','x_before':before,'x_after_milk_push':after,'vx_after_push':velocity,'x_after40_friction_ticks':final,'horizontal_velocity_stops':True,'limits':['Forced native push animation boundary on a real map; not a full keyboard-driven or DS playthrough.']}
 (R/'research/gameplay/block_integration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
