"""Production60Hz accumulator and bounded catch-up vs integer timing model.
DS scheduling adaptation; not an original executable or hardware FPS proof.
"""
from pathlib import Path
import ctypes as C,json,random,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
class Clock(C.Structure):_fields_=[('last',C.c_uint64),('accumulated',C.c_uint64)]
with tempfile.TemporaryDirectory(prefix='kinder-clock-')as tmp:
 so=Path(tmp)/'clock.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/game_clock.c'),'-o',str(so)],check=True);c=C.CDLL(str(so));c.game_clock_reset.argtypes=[C.POINTER(Clock),C.c_uint64];c.game_clock_advance.argtypes=[C.POINTER(Clock),C.c_uint64];c.game_clock_limit_backlog.argtypes=[C.POINTER(Clock),C.c_uint32,C.c_uint32];c.game_clock_limit_backlog.restype=C.c_uint64;c.game_clock_take_tick.argtypes=[C.POINTER(Clock),C.c_uint32];c.game_clock_take_tick.restype=C.c_bool
 rng=random.Random(6008);frames=0;discarded=0
 for frequency in (1,59,60,523656,1000000,0xffffffff):
  a=Clock();c.game_clock_reset(C.byref(a),0);now=accumulated=0
  for frame in range(4096):
   elapsed=rng.choice((0,frequency//120,frequency//60,frequency//30,frequency//15,frequency//2,frequency*3));now+=elapsed;accumulated+=elapsed*60;c.game_clock_advance(C.byref(a),now)
   whole,fraction=divmod(accumulated,frequency);drop=max(0,whole-8);expected=min(whole,8)*frequency+fraction
   assert c.game_clock_limit_backlog(C.byref(a),frequency,8)==drop
   assert a.accumulated==expected
   updates=0
   while c.game_clock_take_tick(C.byref(a),frequency):updates+=1
   assert updates==min(whole,8) and a.accumulated==fraction;accumulated=fraction;discarded+=drop;frames+=1
 # Ordinary cadence preserves all time/ticks and fractional remainder.
 normal=0
 for fps in (30,60):
  frequency=523656;a=Clock();c.game_clock_reset(C.byref(a),0);ticks=0
  for frame in range(1,6001):
   now=frame*frequency//fps;c.game_clock_advance(C.byref(a),now);assert c.game_clock_limit_backlog(C.byref(a),frequency,8)==0
   while c.game_clock_take_tick(C.byref(a),frequency):ticks+=1
  assert ticks==6000*60//fps;normal+=ticks
 # Counter rollback and explicit pause reset never leave deferred updates.
 a=Clock(100,123456);c.game_clock_advance(C.byref(a),99);assert(a.last,a.accumulated)==(99,0)
 c.game_clock_reset(C.byref(a),10000);assert a.accumulated==0 and not c.game_clock_take_tick(C.byref(a),523656)
 # A long stall drains to one bounded burst, then ordinary cadence resumes.
 a=Clock();c.game_clock_reset(C.byref(a),0);frequency=523656;c.game_clock_advance(C.byref(a),frequency*10);assert c.game_clock_limit_backlog(C.byref(a),frequency,8)==592
 for i in range(8):assert c.game_clock_take_tick(C.byref(a),frequency)
 assert not c.game_clock_take_tick(C.byref(a),frequency)
 main=(R/'ds/source/main.c').read_text();assert main.count('game_clock_limit_backlog(&game_clock,BUS_CLOCK/64,MAX_CATCHUP_TICKS)')==1
 result={'scope':__doc__,'modeled_frames':frames,'normal_cadence_ticks':normal,'normal_display_frames':12000,'ten_second_stall_discarded_ticks':592,'rollback_and_pause_reset':True,'main_bound_matches_update_loop':True,'limits':['Under overload excess elapsed whole ticks are deliberately dropped; game rules remain fixed60Hz per executed tick.','Prevents persistent backlog, not proof of sufficient DS CPU throughput or stable FPS.','No emulator/hardware run.']};(R/'research/gameplay/game-clock-backlog-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
