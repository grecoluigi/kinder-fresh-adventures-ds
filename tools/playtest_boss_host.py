"""Bounded host boss combat through production world_tick inputs.
Starts at an original arena spawn; never injects damage, ammo, shots or positions.
This is a diagnostic controller, not proof that a failed policy indicates a bug.
"""
from pathlib import Path
import argparse,ast,ctypes as C,csv,json,subprocess,tempfile,hashlib
R=next(p for p in Path(__file__).resolve().parents if (p/'ds/source/world.c').is_file())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=int,choices=range(4),default=0);p.add_argument('--ticks',type=int,default=12000);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 source=(R/'tools/verify_world_tutorials.py').read_text();names=ast.literal_eval(next(x.strip().split('=',1)[1]for x in source.splitlines()if x.strip().startswith('names=')))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.with_suffix('.controller.py').write_bytes(Path(__file__).read_bytes())
 with tempfile.TemporaryDirectory(prefix='kinder-input-boss-')as tmp:
  t=Path(tmp);wrapper=t/'world.c';so=t/'world.dylib'
  wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+r'''
int probe_glide(void){return player.glide_hold;}
void probe_state(int32_t *v){
 v[0]=body.motion.x/4096;v[1]=body.motion.y/4096;v[2]=player.state;v[3]=player.character;
 v[4]=player.health;v[5]=player.inventory;v[6]=boss_energy;v[7]=boss_defeated;v[8]=player.game_mode;
 v[9]=v[10]=v[11]=v[12]=v[13]=v[14]=0;size_t n;GameEntity *e=scene_entities(&n);
 for(size_t i=0;i<n;i++)if(entity_id(e+i)==10||entity_id(e+i)==9||entity_id(e+i)==14||entity_id(e+i)==18){
  v[9]=entity_id(e+i);v[10]=entity_x(e+i);v[11]=entity_y(e+i);
  v[12]=(int16_t)(e[i].bytes[98]|e[i].bytes[99]<<8);v[13]=entity_frame(e+i);v[14]=entity_active(e+i);break;
 }
 v[15]=player.penguin_status;v[16]=finish_timer;v[17]=player.facing;v[18]=player.projectile_variant;v[19]=switch_flags[0];v[20]=switch_flags[1];v[21]=switch_flags[2];size_t count;GameEntity *objects=scene_entities(&count);v[22]=pipe_entity&&pipe_entity<=count?entity_y(objects+pipe_entity-1):-1;
}
bool probe_incoming(float *v){
 const EnemyShot *q=enemy_shots_slots();const EnemyShot *best=NULL;float x=body.motion.x/4096.0f;
 for(unsigned i=0;i<ENEMY_SHOTS_CAPACITY;i++)if(q[i].active&&(q[i].callback==0x40c2c0||q[i].callback==0x40cc60||q[i].callback==0x40d5c0)&&q[i].vx<0&&q[i].x+48>x-40){
  float gravity;memcpy(&gravity,&q[i].opaque1c,4);
  if((q[i].callback==0x40cc60||q[i].callback==0x40d5c0||gravity<.1f)&&(!best||q[i].x<best->x))best=q+i;
 }
 if(!best){
  size_t count;GameEntity *e=scene_entities(&count);
  for(size_t i=0;i<count;i++)if(entity_id(e+i)==265){
   int16_t state;memcpy(&state,e[i].bytes+98,2);
   EntityEnvironment resource={0};scene_entity_environment(i,&resource);
   if(state==3&&entity_x(e+i)+resource.width>x-40){v[0]=entity_x(e+i);v[1]=entity_y(e+i);v[2]=-10;v[3]=0;return true;}
  }
  return false;
 }
 v[0]=best->x;v[1]=best->y;v[2]=best->vx;v[3]=best->vy;return true;
}
''')
  defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
  subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"'for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(so)],check=True)
  c=C.CDLL(str(so));c.world_open.restype=c.world_tick.restype=c.world_render.restype=c.probe_incoming.restype=C.c_bool;c.game_save_open_directory.restype=C.c_bool
  assert c.game_save_open_directory(str(t/'save').encode());assert c.world_open(a.world+4)
  state=(C.c_int32*23)();incoming=(C.c_float*4)();pcm=(C.c_int16*368)();pixels=(C.c_uint16*49152)();rows=[];outcome='tick_limit';last_energy=9;wait_wave=False
  fields=('tick','x','y','state','character','health','ammo','boss_energy','boss_defeated','game_mode','boss_id','boss_x','boss_y','boss_state','boss_frame','boss_active','switch_state','finish_timer','facing','shot_variant','switch_lower','switch_middle','switch_upper','pipe_y','keys','incoming_x','incoming_y')
  with a.output.with_suffix('.csv').open('w')as f:
   writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
   for tick in range(a.ticks):
    c.probe_state(state);have=c.probe_incoming(incoming);keys=0
    if state[7]:
     keys=8 if state[0]<363 else 4 if state[0]>390 else 0
    elif a.world==0:
     if state[0]<70:keys=8
     elif state[0]>130:keys=4
     elif state[17]:keys=8
     elif not state[3]:keys=64 if state[2]in(0,1)and not state[15]else 0
     elif wait_wave:
      if state[12]!=10 and not have:wait_wave=False
      else:keys=2
     elif have and state[2]in(16,17)and incoming[0]-state[0]>400:keys=32;wait_wave=True
    elif a.world in (1,3):
     # Read-only arena knowledge: replenish from the native ammo object,
     # approach without contacting the boss, then shoot during vulnerability.
     target=(235 if a.world==1 else 305) if not state[5] else (330 if a.world==1 and not state[18] else (182 if a.world==1 else 300))
     if state[2]in(5,21):keys=16
     elif a.world==3 and state[2]in(7,11) and have:keys=16 if state[2]==11 or c.probe_glide()>0 else 0
     elif state[0]<target-10:keys=8
     elif state[0]>target+10:keys=4
     elif state[17]:keys=8
     elif a.world==3 and have and incoming[0]-state[0]<180 and incoming[1]<630:keys=2
     elif have and incoming[0]-state[0]<180 and state[2]in(0,1,16,17):keys=16

     elif state[2]in(0,1,16,17) and state[5] and state[12] in ((1,3)if a.world==1 else(1,)):keys=32

    elif a.world==2:
     if not state[3]:keys=64 if state[2]in(0,1)and not state[15]else 0
     elif state[2]in(16,17,18,19,24,25) and (state[12]in(11,12) or (have and incoming[0]-state[0]<500)):
      keys=4 if state[1]==256 and state[0]>190 else 8 if state[1]==736 and state[0]<180 else 2
     elif state[2]in(5,21):keys=16|4
     elif state[2]in(7,23) and (not state[20] or not state[21]):keys=4
     elif not state[20]:
      if state[2]==29 and state[1]<=544:keys=16|4
      elif state[1]>512:keys=8 if state[0]<72 else 4 if state[0]>88 else 1
      elif state[1]<512:keys=8 if state[0]<168 else 4 if state[0]>184 else 2
      else:keys=4
     elif not state[21]:
      if state[1]>288:
       keys=8 if state[0]<166 else 4 if state[0]>186 else 1
      elif state[2]==29:keys=16|4
      else:keys=4
     elif not state[19]:
      if state[1]<736:
       keys=8 if state[0]<290 else 4 if state[0]>310 else 0
      else:keys=4
     else:keys=0
    elif tick%90<1:keys=32
    if tick%10==0 or state[6]!=last_energy or state[4]<=0 or state[8]==2:
     row=dict(zip(fields,(tick,*state,keys,round(incoming[0],3)if have else None,round(incoming[1],3)if have else None)));rows.append(row);writer.writerow(row);f.flush();last_energy=state[6]
    if state[4]<=0:outcome='player_died';break
    if state[8]==2:outcome='game_result';break
    c.sound_events_poll();assert c.world_tick(keys)
    samples=(tick+1)*22050//60-tick*22050//60;c.sound_events_mix(pcm,samples,127)
    if tick%60==0:assert c.world_render(pixels)
   result={'scope':__doc__,'arena_completed':outcome=='game_result' and bool(state[7]) and state[4]>0,'world':a.world,'arena':a.world+4,'outcome':outcome,'last':rows[-1],'minimum_boss_energy':min(x['boss_energy']for x in rows),'minimum_player_health':min(x['health']for x in rows),'effect_underruns':c.sound_effect_underruns(),'sampled_frames':len(rows),'world_source_sha256':hashlib.sha256((R/'ds/source/world.c').read_bytes()).hexdigest(),'controller_sha256':hashlib.sha256(a.output.with_suffix('.controller.py').read_bytes()).hexdigest(),'controller_snapshot':str(a.output.with_suffix('.controller.py').resolve()),'production_source_sha256':{n:hashlib.sha256((R/'ds/source'/f'{n}.c').read_bytes()).hexdigest() for n in names},'limits':['Host execution, not DS/IRQ timing. Controller knowledge does not imply player skill or complete game verification. Arena selection is fixture setup; subsequent state changes are production input/update paths.']}
   a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));c.world_close()
if __name__=='__main__':main()
