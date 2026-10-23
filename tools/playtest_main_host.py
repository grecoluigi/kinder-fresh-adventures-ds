"""Input-only main-map waypoint playthrough. Controller failures are not port defects."""
import argparse, ctypes as C, csv, hashlib, json, subprocess, tempfile
from pathlib import Path
from host_gameplay import compile_logic, source_fingerprint
R=next(p for p in Path(__file__).resolve().parents if (p/'ds/source/world.c').is_file())
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--world',type=int,choices=range(4),required=True)
p.add_argument('--route',type=Path,required=True)
p.add_argument('--ticks',type=int,default=30000)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--finish-boss',action='store_true',help='Follow a naturally requested Jungle/Ice arena transition and play the boss')
p.add_argument('--boss-ticks',type=int,default=12000)
a=p.parse_args();route=json.loads(a.route.read_text())
assert route['world']==a.world
assert not a.finish_boss or a.world in(0,1), 'Continuous boss policy currently covers Jungle and Ice'
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.with_suffix('.controller.py').write_bytes(Path(__file__).read_bytes())
a.output.with_suffix('.route.json').write_text(json.dumps(route,indent=2)+'\n')
with tempfile.TemporaryDirectory(prefix='kinder-main-walk-')as tmp:
 t=Path(tmp);wrapper=t/'probe.c';lib=t/'world.dylib'
 wrapper.write_text('#include "'+str(R/'ds/source/hazards.h')+'"\n'+r'''
static int32_t last_hit[7],hit_history[256][10],probe_tick;
static unsigned hit_count;
static bool trace_rect(Player*p,const GameBody*b,int x,int y,int w,int h,int damage,const PlayerEnvironment*env){
 int before=p->health;bool result=player_rect_hazard(p,b,x,y,w,h,damage,env);
 if(p->health<before){last_hit[0]=x;last_hit[1]=y;last_hit[2]=w;last_hit[3]=h;last_hit[4]=damage;last_hit[5]=before;last_hit[6]=p->health;
  if(hit_count<256){int32_t*v=hit_history[hit_count++];v[0]=probe_tick;for(unsigned i=0;i<7;i++)v[1+i]=last_hit[i];v[8]=b->motion.x/4096;v[9]=b->motion.y/4096;}
 }
 return result;
}
'''+'#define player_rect_hazard trace_rect\n#include "'+str(R/'ds/source/world.c')+'"\n#undef player_rect_hazard\n'+r'''
void probe_last_hit(int32_t*v){memcpy(v,last_hit,sizeof(last_hit));}
void probe_begin_tick(int tick){probe_tick=tick;}
int probe_hit_history(int32_t*out){memcpy(out,hit_history,hit_count*sizeof(hit_history[0]));return hit_count;}
int probe_hazards(int32_t*out){
 size_t count;GameEntity*e=scene_entities(&count);int n=0;
 for(size_t i=0;i<count&&n<64;i++){
  unsigned id=entity_id(e+i);if(!entity_active(e+i)||(id!=59&&id!=75&&id!=79&&id!=80&&id!=265))continue;
  EntityEnvironment resource={0};scene_entity_environment(i,&resource);int16_t state;memcpy(&state,e[i].bytes+98,2);
  int32_t*v=out+n*8;v[0]=i;v[1]=id;v[2]=entity_x(e+i);v[3]=entity_y(e+i);v[4]=resource.width;v[5]=resource.height;v[6]=state;v[7]=e[i].bytes[26];++n;
 }
 return n;
}
static bool sense(const GeometryRect*r,int n,int x,int y,unsigned mode){return body_map_probe((void*)scene_collision_map(),body.layer,x,y,mode)||geometry_query(r,n,x,y,mode)!=0;}
void probe_floor_row(int y,int32_t*out){
 GeometryRect rects[100];int n=0;size_t count;GameEntity*e=scene_entities(&count);
 for(size_t j=selected_count;j&&n<100;){unsigned i=geometry_indices[--j];if(i>=count||!entity_active(e+i)||!e[i].bytes[26])continue;GeometryObject o;if(scene_geometry_object(i,&o))n+=geometry_build(rects+n,1,&o,1,0,0,800,800);}
 for(unsigned i=0;i<50;i++)out[i]=sense(rects,n,(int)i*16,y,3);
}
int probe_facing(void){return player.facing;}
int probe_glide(void){return player.glide_hold;}
int probe_flat_shot(void){
 const EnemyShot*q=enemy_shots_slots();double px=body.motion.x/4096.0,py=body.motion.y/4096.0;
 for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(q[i].active&&q[i].callback==0x40fd70&&q[i].vx!=0){
  double t=(px-q[i].x)/q[i].vx;if(t<0||t>18)continue;
  double y=q[i].y+3+q[i].vy*t+0.005*t*(t+1);
  if(y<py&&y+11>py-190)return y<py-100?1:2;
 }
 return 0;
}
int probe_platform(int index,int32_t*v){
 size_t count;GameEntity*e=scene_entities(&count);
 if(index<0||(size_t)index>=count||!entity_active(e+index))return 0;
 EntityEnvironment resource={0};if(!scene_entity_environment(index,&resource))return 0;
 v[0]=entity_x(e+index);v[1]=entity_y(e+index)+e[index].bytes[42];v[2]=resource.width;
 v[3]=body.motion.x/4096>=v[0]&&body.motion.x/4096<v[0]+v[2]&&body.motion.y/4096==v[1]&&body.motion.vy>=0;
 return 1;
}
float probe_boss(int32_t*v){
 v[0]=body.motion.x/4096;v[1]=body.motion.y/4096;v[2]=player.state;v[3]=player.character;
 v[4]=player.health;v[5]=player.inventory;v[6]=boss_energy;v[7]=boss_defeated;v[8]=player.game_mode;
 v[9]=-1;v[10]=player.penguin_status;v[11]=player.facing;v[12]=finish_timer;v[13]=player.projectile_variant;
 size_t n;GameEntity*e=scene_entities(&n);
 for(size_t i=0;i<n;i++)if(entity_id(e+i)==10||entity_id(e+i)==9){int16_t state;memcpy(&state,e[i].bytes+98,2);v[9]=state;break;}
 const EnemyShot*q=enemy_shots_slots();const EnemyShot*best=NULL;
 for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(q[i].active&&(q[i].callback==0x40c2c0||q[i].callback==0x40cc60||q[i].callback==0x40d5c0)&&q[i].vx<0&&q[i].x+48>v[0]-40){
  float gravity;memcpy(&gravity,&q[i].opaque1c,4);
  if((q[i].callback==0x40cc60||q[i].callback==0x40d5c0||gravity<.1f)&&(!best||q[i].x<best->x))best=q+i;
 }
 if(best)return best->x;
 for(size_t i=0;i<n;i++)if(entity_id(e+i)==265){
  int16_t state;memcpy(&state,e[i].bytes+98,2);EntityEnvironment resource={0};scene_entity_environment(i,&resource);
  if(state==3&&entity_x(e+i)+resource.width>v[0]-40)return entity_x(e+i);
 }
 return -1;
}
void probe(int32_t*v,int direction,int lookahead,int follow_slope){
 int x=body.motion.x/4096,y=body.motion.y/4096;
 v[0]=x;v[1]=y;v[2]=body.motion.vx;v[3]=body.motion.vy;v[4]=player.state;
 v[5]=player.character;v[6]=player.health;v[7]=player.fatal;v[8]=player.glide_hold;
 v[9]=player.penguin_status;v[10]=world_transition_target();v[11]=0;
 for(unsigned i=0;i<6;i++)if(hud.letters[i])v[11]|=1<<i;
 GeometryRect rects[100];int n=0;size_t count;GameEntity*e=scene_entities(&count);
 for(size_t j=selected_count;j&&n<100;){unsigned i=geometry_indices[--j];if(i>=count||!entity_active(e+i)||!e[i].bytes[26])continue;GeometryObject o;if(scene_geometry_object(i,&o))n+=geometry_build(rects+n,1,&o,1,x-250,y-400,x+250,y+200);}
 v[12]=0;for(int yy=follow_slope?y-48:y;yy<=y+48;yy+=4)if(sense(rects,n,x+direction*lookahead,yy,3)){v[12]=1;break;}
 v[13]=sense(rects,n,x+direction*48,y-100,5)||sense(rects,n,x+direction*48,y-160,5);
 v[14]=sense(rects,n,x,y,3)||sense(rects,n,x,y+1,3);
 PlayerEnvironment env={.context=(void*)scene_collision_map(),.climb_probe=climb_probe};
 v[15]=player_ladder_at(&env,x,y);v[16]=0;v[17]=10000;v[18]=player.inventory;
 for(size_t i=0;i<count;i++)if(entity_active(e+i)){
  unsigned id=entity_id(e+i);int ex=entity_x(e+i),ey=entity_y(e+i),dx=(ex-x)*direction;
  /* Ice navigation senses cross-layer contacts. The retained Jungle route
   * uses its original same-layer threat policy; this changes bot inputs only. */
  if(id>=3&&id<=15&&(native_world!=0||entity_layer(e+i)==(unsigned)body.layer)&&dx>0&&dx<v[17]){
   int16_t state;memcpy(&state,e[i].bytes+98,2);EntityEnvironment resource={0};
   if(state<100&&scene_entity_environment(i,&resource)&&abs(ey+resource.height-y)<210)v[17]=dx;
  }
  if(id==76||id==78||id==83||id==86||id==87){
   EntityEnvironment resource={0};scene_entity_environment(i,&resource);
   int edge=direction>0?ex:ex+resource.width,near=(edge-x)*direction;
   if(near>=-20&&near<140&&ey-40<y&&ey+resource.height+40>y)v[16]=1;
  }
 }
}
''')
 compile_logic(wrapper,lib)
 c=C.CDLL(str(lib))
 for name in ('world_open','world_open_stage','world_tick','game_save_open_directory'):getattr(c,name).restype=C.c_bool
 c.probe_boss.restype=C.c_float;c.world_map_name.restype=C.c_char_p
 assert c.game_save_open_directory(str(t/'save').encode()) and c.world_open_stage(a.world,False)
 v=(C.c_int32*19)();platform=(C.c_int32*4)();pcm=(C.c_int16*368)()
 fields=('tick','x','y','vx','vy','state','character','health','dialogue','glide_hold','switch_state','target','ingredient_mask','floor_ahead','wall_ahead','grounded','ladder','block_ahead','enemy_ahead','ammo','keys','waypoint','platform_x','platform_top','platform_width','aboard')
 index=0;last_motion=0;mx=my=0;direction=1;outcome='tick_limit';events=[];last_letters=0;lastrow={};last_keys=0
 with a.output.with_suffix('.csv').open('w')as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
  for tick in range(a.ticks):
   point=route['waypoints'][min(index,len(route['waypoints'])-1)];c.probe(v,direction,point.get('edge_probe',70),bool(point.get('follow_slope')))
   if 'platform'in point:assert c.probe_platform(point['platform'],platform)
   else:platform[:]=(0,0,0,0)
   reached=abs(v[0]-point['x'])<=point.get('rx',60) and abs(v[1]-point['y'])<=point.get('ry',100) and (not point.get('grounded') or v[14])
   reached=reached and v[6]>=point.get('health_at_least',1)
   reached=reached and v[5]==point.get('character',v[5])
   if point.get('mode')=='ride':reached=reached and bool(platform[3])
   if reached and ('ingredient'not in point or v[11]&(1<<(point['ingredient']-53))):
    events.append({'tick':tick,'waypoint':index,'x':v[0],'y':v[1],'ingredient_mask':v[11]});index+=1
    if index==len(route['waypoints']):
     outcome='route_finished';lastrow=dict(zip(fields,(tick,*v,0,index,*platform)));writer.writerow(lastrow);break
    point=route['waypoints'][index]
   direction=1 if point['x']>v[0]else -1
   c.probe(v,direction,point.get('edge_probe',70),bool(point.get('follow_slope')));move=8 if direction>0 else 4;keys=0
   if abs(v[0]-mx)>5 or abs(v[1]-my)>5:mx,my=v[0],v[1];last_motion=tick
   if v[7]or v[4]in(14,15,30,31):last_motion=tick
   if v[11]!=last_letters:events.append({'tick':tick,'ingredient_mask':v[11],'x':v[0],'y':v[1]});last_letters=v[11]
   if tick<60 or v[7]:keys=0
   elif point.get('mode')=='ride':
    assert c.probe_platform(point['platform'],platform)
    center=platform[0]+point.get('anchor',platform[2]//2)
    if platform[3]:
     # Brake relative motion using keys only; transport remains production code.
     error=center-v[0]-v[2]/4096*5
     keys=8 if error>12 else 4 if error< -12 else 0
    elif v[14] and (abs(center-v[0])>point.get('board_range',350) or platform[1]<v[1]-180):keys=0
    else:
     move=8 if center>v[0]else 4
     keys=move|(16 if v[14]or v[4]in(5,21,11)or(v[4]==7 and v[3]>=0 and v[8]>0)else 0)
   elif point.get('mode')=='climb' and v[15] and abs(point['x']-v[0])<55:
    keys=1 if point['y']<v[1] else 2
    if tick-last_motion>45:keys=16|move
   elif v[4]in(13,29) and point.get('mode')!='climb':keys=16|move
   elif point.get('character',v[5])!=v[5]:keys=64 if v[4]in(0,1,16,17)and not v[9]else 0
   elif a.world==0 and point.get('combat',True)and 50<v[17]<400 and v[18]and v[14]:keys=32 if v[4]in(0,1,16,17)else 0
   elif a.world!=0 and point.get('combat',True)and v[17]<160 and v[14]and v[4]in(0,1,2,3,16,17,18,19):keys=16|move
   elif a.world!=0 and point.get('combat',True)and 160<=v[17]<650 and v[18]and v[14]:
    keys=move if c.probe_facing()!=(direction<0) else 32 if v[4]in(0,1,16,17)else 0
   elif v[16]and point.get('jump_over_blocks'):
    keys=move|(16 if v[14]or v[4]in(5,21,11)or(v[4]==7 and v[3]>=0 and v[8]>0)else 0)
   elif v[16]and not v[5]:keys=64 if v[4]in(0,1)and not v[9]else 0
   elif v[16]and v[5]:keys=move
   elif v[4]in(5,21,11):keys=16|move
   elif v[4]==7 and v[3]>=0 and v[8]>0 and not point.get('drop'):keys=16|move
   elif v[14]and not point.get('drop')and(not v[12]or v[13]or tick-last_motion>60 or point.get('jump')and v[1]>point['y']+30):keys=16|move
   else:keys=move
   if point.get('dodge_flat_shots'):
    danger=c.probe_flat_shot()
    if danger==1:
     if v[14]and v[4]in(0,1,2,3,8,9,16,17,18,19,24,25):keys=2
     elif not v[14]:keys&=~16
    elif danger==2 and v[14]and v[4]in(0,1,2,3,16,17,18,19):keys=16|move
   # The held-jump ascent preserves existing horizontal momentum. Turn on the
   # ledge before taking off toward a higher platform in the other direction.
   if a.world!=0 and v[14]and keys&16 and v[2]*direction<0:keys=(keys&~16)|move
   # Native jump debouncing requires a release after an action consumes the
   # press. Do not hold a stale jump request throughout a shooting animation.
   if v[14]and v[4]in(0,1,2,3,16,17,18,19)and keys&16 and last_keys&16:keys&=~16
   lastrow=dict(zip(fields,(tick,*v,keys,index,*platform)))
   if tick%30==0 or v[6]<=0 or v[10]>=0:writer.writerow(lastrow);f.flush()
   if v[6]<=0:outcome='player_died';break
   if v[10]>=0:outcome='arena_transition';break
   c.probe_begin_tick(tick);c.sound_events_poll();assert c.world_tick(keys)
   last_keys=keys
   c.sound_events_mix(pcm,(tick+1)*22050//60-tick*22050//60,127)
  hit=(C.c_int32*7)();c.probe_last_hit(hit)
  main_summary={'outcome':outcome,'last_sample':lastrow.copy(),'score':c.world_result_score(),'effect_underruns':c.sound_effect_underruns(),'last_damage_rect':list(hit)}
  boss_summary=None
  if a.finish_boss and outcome=='arena_transition':
   assert v[10]==a.world+4 and v[11]==63 and v[6]>0
   assert c.game_save_flush_tutorials() and c.world_open(v[10])
   arena_map=c.world_map_name().decode();assert arena_map==('Welt1E.W02','Welt2E.W02')[a.world]
   state=(C.c_int32*14)();wait_wave=False;last_energy=9;boss_rows=[]
   floor=(C.c_int32*50)();c.probe_floor_row(480,floor)
   c.probe_boss(state);entry={'health':state[4],'score':c.world_result_score(),'support_at_y480':[i*16 for i in range(50)if floor[i]]}
   assert entry['score']==main_summary['score'], 'Main-map score must carry into the arena'
   boss_fields=('tick','x','y','state','character','health','ammo','boss_energy','boss_defeated','game_mode','boss_state','switch_state','facing','finish_timer','shot_variant','keys','incoming_x')
   with a.output.with_suffix('.boss.csv').open('w')as bf:
    bw=csv.DictWriter(bf,fieldnames=boss_fields);bw.writeheader()
    outcome='boss_tick_limit'
    for btick in range(a.boss_ticks):
     incoming=c.probe_boss(state);have=incoming>=0;keys=0
     if state[7]:
      if a.world==1 and state[12]>0:
       keys=8 if state[0]<400 else 0
       if state[2]in(0,1,2,3,5,21,11)or state[2]==7 and c.probe_glide()>0:keys|=16
      else:keys=8 if state[0]<363 else 4 if state[0]>390 else 0
     elif a.world==1:
      target=235 if not state[5]else 330 if not state[13]else 182
      if state[2]in(5,21):keys=16
      elif state[0]<target-10:keys=8
      elif state[0]>target+10:keys=4
      elif state[11]:keys=8
      elif have and incoming-state[0]<180 and state[2]in(0,1,16,17):keys=16
      elif state[2]in(0,1,16,17)and state[5]and state[9]in(1,3):keys=32
     elif state[0]<70:keys=8
     elif state[0]>130:keys=4
     elif state[11]:keys=8
     elif not state[3]:keys=64 if state[2]in(0,1)and not state[10]else 0
     elif wait_wave:
      if state[9]!=10 and not have:wait_wave=False
      else:keys=2
     elif have and state[2]in(16,17)and incoming-state[0]>400:keys=32;wait_wave=True
     if btick%10==0 or state[6]!=last_energy or state[4]<=0 or state[8]==2:
      row=dict(zip(boss_fields,(btick,*state,keys,incoming if have else None)));boss_rows.append(row);bw.writerow(row);last_energy=state[6]
     if state[4]<=0:outcome='boss_player_died';break
     if state[8]==2:outcome='game_result';break
     c.probe_begin_tick(tick+btick+1);c.sound_events_poll();assert c.world_tick(keys)
     elapsed=tick+btick+1;c.sound_events_mix(pcm,(elapsed+1)*22050//60-elapsed*22050//60,127)
    c.probe_last_hit(hit);c.probe_floor_row(480,floor)
    hazards=(C.c_int32*(64*8))();hazard_count=c.probe_hazards(hazards)
    boss_summary={'map':arena_map,'completed':outcome=='game_result'and bool(state[7])and state[4]>0,'last_sample':boss_rows[-1],'last_damage_rect':list(hit),
                  'active_hazards':[dict(zip(('index','id','x','y','width','height','state','solid'),hazards[i*8:i*8+8]))for i in range(hazard_count)],
                  'entry':entry,'support_at_y480':[i*16 for i in range(50)if floor[i]],'effect_underruns':c.sound_effect_underruns(),'result_world':c.world_result_world(),'result_score':c.world_result_score()}
  history=(C.c_int32*(256*10))();history_count=c.probe_hit_history(history)
  result={'world':a.world,'outcome':outcome,'last_sample':boss_summary['last_sample']if boss_summary else lastrow,'waypoints_reached':index,'events':events,
          'damage_history':[dict(zip(('tick','x','y','width','height','damage','health_before','health_after','player_x','player_y'),history[i*10:i*10+10]))for i in range(history_count)],
          'main':main_summary,'boss':boss_summary,
          'level_and_boss_completed':bool(boss_summary and boss_summary['completed']and main_summary['last_sample']['ingredient_mask']==63),
          'effect_underruns':c.sound_effect_underruns(),'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'route_sha256':hashlib.sha256(a.output.with_suffix('.route.json').read_bytes()).hexdigest(),
          'production_source_sha256':source_fingerprint(),
          'limits':['Headless current gameplay only; no graphics, DS timing or audible playback verification.',
                    'Only normal input bits after original main-stage selection. A failed route alone does not prove a game defect.']}
  a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ('outcome','last_sample','waypoints_reached','effect_underruns')},indent=2));c.world_close()
