"""Continuous input-only tutorial traversal from original spawn, with native speech timing.
Controller reads terrain and live objects; failures alone do not establish port bugs.
"""
from pathlib import Path
import argparse,ast,ctypes as C,csv,hashlib,json,subprocess,tempfile
R=next(p for p in Path(__file__).resolve().parents if (p/'ds/source/world.c').is_file())
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=int,choices=range(4),required=True);p.add_argument('--ticks',type=int,default=24000);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
source=(R/'tools/verify_world_tutorials.py').read_text();names=ast.literal_eval(next(x.strip().split('=',1)[1]for x in source.splitlines()if x.strip().startswith('names=')))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.with_suffix('.controller.py').write_bytes(Path(__file__).read_bytes())
with tempfile.TemporaryDirectory(prefix='kinder-tutorial-walk-')as tmp:
 t=Path(tmp);wrapper=t/'world.c';lib=t/'world.dylib'
 wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+r'''
unsigned probe_expected(void){unsigned bits=0;size_t n;GameEntity*e=scene_entities(&n);for(size_t i=0;i<n;i++)if(entity_id(e+i)==77&&entity_active(e+i)&&entity_x(e+i)>=0&&e[i].bytes[42]<10)bits|=1u<<e[i].bytes[42];return bits;}
static bool sense(const GeometryRect*r,int n,int x,int y,unsigned mode){return body_map_probe((void*)scene_collision_map(),2,x,y,mode)||geometry_query(r,n,x,y,mode)!=0;}
void probe(int32_t *v){
 int x=body.motion.x/4096,y=body.motion.y/4096;v[0]=x;v[1]=y;v[2]=body.motion.vx;v[3]=body.motion.vy;v[4]=player.state;v[5]=player.character;v[6]=player.health;v[7]=player.fatal;v[8]=player.glide_hold;v[9]=player.penguin_status;v[10]=world_transition_target();v[11]=game_save_state()->tutorials[native_world];v[22]=npc_voice_key;v[23]=sound_channel_active(17);
 GeometryRect rects[100];int n=0;size_t count;GameEntity*e=scene_entities(&count);v[16]=0;v[17]=0;v[19]=10000;v[20]=0;v[21]=player.inventory;
 for(size_t j=selected_count;j&&n<100;){unsigned i=geometry_indices[--j];if(i>=count||!entity_active(e+i)||!e[i].bytes[26])continue;GeometryObject o;if(scene_geometry_object(i,&o))n+=geometry_build(rects+n,1,&o,1,x-200,y-400,x+250,y+200);}
 v[12]=0;for(int yy=y;yy<=y+48;yy+=4)if(sense(rects,n,x+70,yy,3)){v[12]=1;break;}
 v[13]=sense(rects,n,x+48,y-100,5)||sense(rects,n,x+48,y-160,5);
 v[14]=sense(rects,n,x,y,3)||sense(rects,n,x,y+1,3);
 v[15]=player_ladder_at(&player_environment,x,y);
 for(size_t i=0;i<count;i++)if(entity_active(e+i)){
  unsigned id=entity_id(e+i);int ex=entity_x(e+i),ey=entity_y(e+i);
  if(id>=3&&id<=15&&entity_layer(e+i)==2&&ex>x&&ex-x<v[19]){
   int16_t state;memcpy(&state,e[i].bytes+98,2);EntityEnvironment env={0};
   if(state<100&&scene_entity_environment(i,&env)&&abs(ey+env.height-y)<210){v[19]=ex-x;v[20]=ey+env.height-y;}
  }
  if((id==76||id==78||id==83||id==86||id==87)&&ex>=x-20&&ex-x<140&&ey-40<y&&ey+300>y)v[16]=1;
  if(id==77&&ex>=0&&e[i].bytes[42]<10){int16_t state;memcpy(&state,e[i].bytes+98,2);if(state>=10)v[17]|=1<<e[i].bytes[42];}
 }
 v[18]=0;const CollisionMap*m=scene_collision_map();int sx=(x+70)/32,sy=(y+24)/32;
 if(sx>=0&&sy>=0&&sx<m->width&&sy<m->height){const uint8_t*c=collision_cell(m,2,sx,sy);v[18]=(c[0]&128)&&!(c[1]==255&&c[2]==255);}
}
''')
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"'for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(lib)],check=True)
 c=C.CDLL(str(lib));c.world_open.restype=c.world_open_stage.restype=c.world_tick.restype=c.world_render.restype=c.game_save_open_directory.restype=C.c_bool;c.world_map_name.restype=C.c_char_p;assert c.game_save_open_directory(str(t/'save').encode());assert c.world_open_stage(a.world,True)
 v=(C.c_int32*24)();pcm=(C.c_int16*368)();pixels=(C.c_uint16*49152)();rows=[];seen=0;maxx=0;last_progress=0;outcome='tick_limit';switching=False;last_motion=0;motion_x=motion_y=0;progress_x=0;voices=[];last_voice=0;voice_start=0;expected=c.probe_expected();assets={v['va']:v for v in json.loads((R/'research/audio/effects_manifest.json').read_text())['assets']}
 fields=('tick','x','y','vx','vy','state','character','health','dialogue','glide_hold','switch_state','target','tutorial_complete_flag','floor_ahead','wall_ahead','grounded','ladder','block_ahead','active_npc_mask','danger_ahead','enemy_ahead','enemy_height_delta','ammo','npc_voice_key','voice_active','keys','seen_npc_mask')
 with a.output.with_suffix('.csv').open('w')as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
  for tick in range(a.ticks):
   c.probe(v);seen|=v[17];keys=0
   voice_key=v[22]if v[7]and v[23]else 0
   if voice_key!=last_voice:
    if last_voice:
     length=assets[last_voice]['frames']*60/22050
     voices.append({'key':hex(last_voice),'start_tick':voice_start,'end_tick':tick,'expected_duration_ticks':length,'finished':True,'duration_matches':abs(tick-voice_start-length)<=2})
    voice_start=tick;last_voice=voice_key
   maxx=max(maxx,v[0])
   if v[0]>progress_x+10:progress_x=v[0];last_progress=tick
   if abs(v[0]-motion_x)>5 or abs(v[1]-motion_y)>5:motion_x,motion_y=v[0],v[1];last_motion=tick
   if v[7]:last_motion=tick
   if tick<60:keys=0
   elif v[7]:last_progress=tick
   elif not(seen&1) and v[0]<(793,129,333,162)[a.world]+150:keys=8
   elif 50<v[19]<450 and v[21]:
    keys=32 if v[14]and v[4]in(0,1,16,17)else 0
   elif switching or (v[16]and not v[5]):
    switching=not bool(v[5]);keys=64 if switching and v[4]in(0,1)and not v[9]else 0
   elif v[16]and v[5]:keys=8
   elif v[15]and v[4]in(13,29)and tick-last_motion>45:keys=16|8
   elif v[15]and v[4]not in(5,21):keys=1|8
   elif v[4]in(5,21):keys=16|8
   elif v[4]==11:keys=16|8
   elif v[4]==7 and v[3]>=0 and v[8]>0:keys=16|8
   elif v[14] and (not v[12]or v[13]or v[18]or tick-last_progress>60):keys=16|8
   else:keys=8
   if tick%30==0 or v[6]<=0 or v[10]>=0:
    row=dict(zip(fields,(tick,*v,keys,seen)));rows.append(row);writer.writerow(row);f.flush()
   if v[6]<=0:outcome='player_died';break
   if v[10]>=0:outcome='tutorial_transition';break
   c.sound_events_poll();assert c.world_tick(keys);n=(tick+1)*22050//60-tick*22050//60;c.sound_events_mix(pcm,n,127)
   if tick%60==0:assert c.world_render(pixels)
  result={'scope':__doc__,'tutorial_completed':outcome=='tutorial_transition' and v[10]==a.world and v[11]==1 and v[6]>0 and seen&expected==expected and all(x['duration_matches']for x in voices),'expected_npc_kinds':[i for i in range(10)if expected&(1<<i)],'npc_voice_segments':voices,'world':a.world,'outcome':outcome,'last_sample':rows[-1],'furthest_x':maxx,'npc_kinds_observed':[i for i in range(10)if seen&(1<<i)],'effect_underruns':c.sound_effect_underruns(),'controller_sha256':hashlib.sha256(a.output.with_suffix('.controller.py').read_bytes()).hexdigest(),'production_source_sha256':{n:hashlib.sha256((R/'ds/source'/f'{n}.c').read_bytes()).hexdigest()for n in ['world',*names]},'limits':['Host logic/input route, not DS frame timing. Normal PCM mix models elapsed speech time.','No positions, damage, ammo, invulnerability, NPC states or progression are injected after original route selection.']}
  if result['tutorial_completed']:
   assert c.world_open(a.world) and c.world_render(pixels)
   result['following_map']=c.world_map_name().decode();assert result['following_map']==('Welt1.W02','Welt2.W02','welt3.W02','welt4.W02')[a.world]
  a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));c.world_close()
