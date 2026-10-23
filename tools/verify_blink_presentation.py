"""Damage blink at60/30/20/15/7.5 FPS sampling, without changing native immunity.
Native blink/death/hazards are separately x86 compared. No actual DS frame-rate proof.
"""
from pathlib import Path
import ctypes as C,json,subprocess,sys,tempfile
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'research/gameplay'));from verify_player import Player
class View(C.Structure):_fields_=[('remaining',C.c_uint32),('character',C.c_int32),('active',C.c_bool),('visible',C.c_bool)]
with tempfile.TemporaryDirectory(prefix='kinder-blink-view-')as tmp:
 so=Path(tmp)/'player.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/player.c'),'-o',str(so)],check=True)
 c=C.CDLL(str(so));c.player_blink_tick.argtypes=[C.POINTER(Player)];c.player_blink_tick.restype=C.c_bool;c.player_blink_present.argtypes=[C.POINTER(View),C.POINTER(Player),C.c_bool,C.c_bool];c.player_blink_present.restype=C.c_bool
 cases=[];unchanged=0
 for character in (0,1):
  for stride in (1,2,3,4,8):
   p=Player();p.controls[1]=character;p.controls[25]=80;anim=p.milk if character else p.penguin;anim[23]=120;v=View();drawn=[];native=[];ticks=0
   while anim[23]>0:
    for _ in range(min(stride,anim[23])):native_visible=c.player_blink_tick(C.byref(p));ticks+=1
    snapshot=bytes(p);shown=c.player_blink_present(C.byref(v),C.byref(p),native_visible,True);assert bytes(p)==snapshot;unchanged+=1
    if anim[23]:drawn.append(shown);native.append(native_visible)
    else:assert shown
   assert ticks==120 and anim[23]==0 and p.controls[25]==80
   if stride==1:assert drawn==native
   else:assert all(a!=b for a,b in zip(drawn,drawn[1:])),(character,stride)
   if stride%2==0:assert len(set(native))==1 and len(set(drawn))==2
   snapshot=bytes(p);assert c.player_blink_present(C.byref(v),C.byref(p),True,False);assert bytes(p)==snapshot
   cases.append({'character':character,'simulation_ticks_per_display':stride,'immunity_ticks':ticks,'native_visible_phases':sorted(set(native)),'presented_visible_phases':sorted(set(drawn)),'60FPS_phase_exact':stride==1})
 # Pause/repeated renders freeze the display phase and never drain immunity.
 p=Player();p.penguin[23]=120;v=View();visible=c.player_blink_tick(C.byref(p));visible=c.player_blink_present(C.byref(v),C.byref(p),visible,True);snapshot=bytes(p)
 for _ in range(120):assert c.player_blink_present(C.byref(v),C.byref(p),visible,False)==visible and bytes(p)==snapshot
 p.penguin[23]=0;assert c.player_blink_present(C.byref(v),C.byref(p),False,False)
 # Character change/reset restarts from the current native selected actor phase.
 p.controls[1]=1;p.milk[23]=97;p.milk[22]=0;assert not c.player_blink_present(C.byref(v),C.byref(p),False,True)
 p.milk[23]=120;p.milk[22]=1;assert c.player_blink_present(C.byref(v),C.byref(p),True,True)
 # Irregular catch-up schedules still expire after exactly120 ticks.
 for schedule in ((1,2),(2,4,8),(3,1,2,1)):
  p=Player();p.penguin[23]=120;v=View();ticks=0;values=[];frame=0
  while p.penguin[23]>0:
   stride=min(schedule[frame%len(schedule)],p.penguin[23]);frame+=1
   for _ in range(stride):native_visible=c.player_blink_tick(C.byref(p));ticks+=1
   snapshot=bytes(p);values.append(c.player_blink_present(C.byref(v),C.byref(p),native_visible,True));assert bytes(p)==snapshot
  assert ticks==120 and len(set(values[:-1]))==2 and values[-1]
 result={'scope':__doc__,'sampling_cases':cases,'player_bytes_unchanged_checks':unchanged,'paused_displays_checked':120,'character_and_new_hit_resynchronize':True,'mixed_catchup_schedules':3,'limits':['Display phase adaptation on catch-up frames is deliberate DS presentation behavior; original simulation fields/duration remain unchanged.','Not a full water recovery/rope/playthrough or measured DS FPS check.']}
 (R/'research/gameplay/blink-presentation-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
