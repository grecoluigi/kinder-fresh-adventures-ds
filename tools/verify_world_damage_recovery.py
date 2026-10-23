"""Production water -> safe-ground recovery/render sampling and pause fixtures.
Forced positions/characters on the real jungle map; not a full DS playthrough.
"""
from pathlib import Path
import ctypes as C,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-world-damage-')as tmp:
 t=Path(tmp);w=t/'world.c';w.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
void test_place(int x,int y){body.motion.x=x*4096;body.motion.y=y*4096;body.motion.vx=body.motion.vy=0;}
void test_character(int c){player.character=c;player.state=c?15:0;}
int test_value(int k){switch(k){case 0:return body.motion.x/4096;case 1:return body.motion.y/4096;case 2:return player.health;case 3:return (player.character?player.milk:player.penguin).opaque_5c;case 4:return player_visible;case 5:return player_render_visible;default:return -1;}}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"'for k,v in defs.items()],str(w),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.world_open_stage.restype=c.world_tick.restype=c.world_render.restype=c.world_finished.restype=C.c_bool;pixels=(C.c_uint16*49152)();cases=[]
 for character in (0,1):
  for stride in (1,2,4,8):
   assert c.world_open_stage(0,False);c.test_character(character)
   for _ in range(120):assert c.world_tick(0)
   safe=(c.test_value(0),c.test_value(1));assert c.test_value(2)==100;assert c.world_render(pixels)
   c.test_place(528,2352);assert c.world_tick(0);assert c.test_value(2)==80 and c.test_value(3)==119
   c.test_place(*safe);shown=[];native=[];expired=None
   for tick in range(360):
    assert c.world_tick(0);assert c.test_value(2)==80,(character,stride,tick,c.test_value(2))
    if c.test_value(3)==0 and expired is None:expired=tick+1
    if (tick+1)%stride==0:
     assert c.world_render(pixels)
     if c.test_value(3)>0:shown.append(c.test_value(5));native.append(c.test_value(4))
   assert expired==119 and c.test_value(3)==0 and c.test_value(5)==1 and not c.world_finished()
   assert len(set(shown))==2
   if stride==1:assert shown==native
   else:assert all(a!=b for a,b in zip(shown,shown[1:])),(character,stride,shown)
   # Render-only pause while damaged: no time passes or visibility phase changes.
   c.test_place(528,2352);assert c.world_tick(0);c.test_place(*safe);assert c.world_render(pixels);before=[c.test_value(k)for k in (2,3,5)]
   for _ in range(12):assert c.world_render(pixels)and[c.test_value(k)for k in (2,3,5)]==before
   cases.append({'character':character,'ticks_per_display':stride,'safe_position':safe,'health_after_contact_and_recovery':80,'remaining_immunity_expires_after_ticks':expired,'display_visible_phases':sorted(set(shown)),'native_visible_phases':sorted(set(native)),'render_only_pause_frames':12});c.world_close()
 result={'scope':__doc__,'cases':cases,'limits':['Characters and water/safe positions are supplied fixtures. Not full keyboard-driven traversal or a measured hardware run.','Presentation phase on catch-up displays is a DS adaptation; native blink fields are retained.']}
 (R/'research/gameplay/world-damage-recovery-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
