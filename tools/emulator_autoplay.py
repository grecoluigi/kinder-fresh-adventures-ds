"""Input-only, map-aware bounded playtest over melonDS ARM9 RSP.
No teleporting, invulnerability or fabricated completion. A bot death is an
outcome, not by itself a game regression. Session launcher owns emulator cleanup.
"""
from rom_artifact import rom_path
import argparse,csv,hashlib,json,random,struct,time,re,statistics
from functools import lru_cache
from pathlib import Path
from emulator_counters import RSP,symbols,module_bss_symbol,ROOT,ARTIFACT_DIR
NAMES=('jungle','ice','factory','fantasy')
AUDIO_STREAM_FIELDS=('audio_stream_service_gap_peak_us','audio_stream_deadline_misses','audio_stream_callback_frames_peak','audio_stream_callback_calls','audio_stream_updates')
class Controller:
 def __init__(self,stage):self.stage=stage;self.map=None;self.last_x=None;self.stuck_since=0;self.last_jump=-100;self.jump_until=0;self.last_switch=-300;self.switch_from=None;self.push_until=0
 def load(self,name):
  p=ROOT/'generated/maps'/name/'00.json';self.metadata=json.loads(p.read_text());self.tiles=p.with_name('00.tiles.bin').read_bytes();self.map=name
 def cell(self,x,y):
  m=self.metadata;w,h=m['width_cells'],m['height_cells'];x=int(x)//32;y=int(y)//32
  if not(0<=x<w and 0<=y<h):return 0,b'\xff\xff'
  at=((2*h+y)*w+x)*3;p=self.tiles[at:at+3];return p[0],p[1:]
 def choose(self,tick,x,y,player):
  if player[10]:return 0,'listen_to_dialogue'
  if tick<60:return 0,'initial_idle'
  if self.last_x is None or abs(x-self.last_x)>12:self.last_x=x;self.stuck_since=tick
  # Player.switch_available is the current HUD actor selector, not an unlock
  # gate: zero is also the normal Penguin state. Switching is decided by the
  # native idle routine. Release movement/jump so that routine can run.
  if self.switch_from is not None:
   if player[1]!=self.switch_from:
    self.switch_from=None;self.stuck_since=tick;self.push_until=tick+240
   elif tick-self.last_switch<360:
    return (1024 if player[0]in(0,1,16,17)and not player[17]else 0),'settle_and_switch'
   else:self.switch_from=None
  if tick<self.push_until:return 16,'walk_and_push'
  block=any(o['obj_nr']in(76,78,83,86,87)and 0<o['x_px']-x<120 and o['y_px']-40<y<o['y_px']+300 for o in self.metadata['objects'])
  if tick-self.stuck_since>120 and tick-self.last_switch>360:
   if block and player[1]:self.push_until=tick+240;return 16,'walk_and_push'
   self.switch_from=player[1];self.last_switch=tick;self.jump_until=0
   return 0,'settle_before_switch'
  if block and tick-self.stuck_since>90:return 16 if player[1]else 0,'approach_pushable_block'
  reason='move_right';keys=16
  flags,packed=self.cell(x+90,y+36);wall,_=self.cell(x+70,y-75)
  gap=packed==b'\xff\xff';danger=bool(flags&128);obstacle=bool(wall&32)
  near=any(0<o['x_px']-x<180 and abs(o['y_px']-y)<200 and o['obj_nr']!=1000 for o in self.metadata['objects']) if self.stage=='main'else False
  if tick>=self.jump_until and tick-self.last_jump>=60 and (gap or danger or obstacle or near or tick-self.stuck_since>90):
   self.last_jump=tick;self.jump_until=tick+22;reason='jump_gap_or_obstacle'
  if tick<self.jump_until:keys|=1;reason='hold_jump'
  if self.stage=='main' and tick%45<6:keys|=2;reason+=' shoot'
  return keys,reason

def run(args):
 bss_symbol=lru_cache(None)(module_bss_symbol)
 sym=symbols();rsp=RSP(3333);held=sym['keysHeld'];down=sym['keysDown'];original={};active=None;stopped=True;rows=[];frame_rows=[];last_render_sample=None;outcome='tick_limit';render_check=None;pickup_check=None;hud_check=None;continuous_check=[];start=time.monotonic();controller=Controller(args.stage)
 phase_names=('fps','updates_per_second','audio','update','render','transfer')
 phase_begin=min(sym[k]for k in phase_names);phase_end=max(sym[k]for k in phase_names)+4
 assert phase_end-phase_begin<=256,'Performance counters unexpectedly far apart'
 args.output.parent.mkdir(parents=True,exist_ok=True);trace=args.output.with_suffix('.jsonl');csvpath=args.output.with_suffix('.csv');jsonlog=trace.open('w');csvfile=csvpath.open('w',newline='');writer=None
 def read32(address):return struct.unpack('<I',rsp.read(address,4))[0]
 def next_frame():
  nonlocal active,stopped
  active=f'0,{sym["performance_frame"]:x},2';assert rsp.command('Z'+active)=='OK'
  if stopped:rsp.resume();stopped=False
  began=time.monotonic();assert rsp.receive().startswith(('S','T'));stopped=True;elapsed=time.monotonic()-began
  if not partial[0]:frame_host.append(elapsed)
  partial[0]=False
  assert rsp.command('z'+active)=='OK';active=None
 def step():assert rsp.command('s').startswith(('S','T'))
 frame_host=[];partial=[False];boundaries=[0]
 pc_log=args.output.with_suffix('.pc.jsonl').open('w') if args.pc_samples else None
 def registers():
  # Read r0..r15 and CPSR at the current halt; raw register packet order is r0..r15.
  data=bytes.fromhex(rsp.command('g'));words=struct.unpack_from('<16I',data)
  cpsr=struct.unpack_from('<I',data,len(data)-4)[0] if len(data)>=68 else None
  return words[15],words[14],words[13],cpsr
 def sample_pc(tick):
  # Statistical sampling: emulated time is frozen while halted, so the
  # interruption does not add emulated cycles. Samples land uniformly within
  # roughly one emulated frame after the current loop boundary.
  nonlocal stopped
  estimate=statistics.median(frame_host[-31:]) if frame_host else .02
  rsp.resume();stopped=False;partial[0]=True;time.sleep(random.uniform(0,estimate))
  rsp.sock.sendall(b'\x03');assert rsp.receive().startswith(('S','T'));stopped=True
  pc,lr,sp,cpsr=registers();pc_log.write(json.dumps({'tick':tick,'pc':pc,'lr':lr,'sp':sp,'cpsr':cpsr})+'\n')
 def input_keys(value):
  # Twelve-byte Thumb function including its literal. Original function is
  # exactly isolated from keysDown; no ROM, save or next-function edits.
  rsp.write(held,struct.pack('<HHHHI',0x4801,0x4770,0x46c0,0x46c0,value))
 try:
  for address in (held,down):
   assert address%4==0,'unexpected input function alignment';original[address]=rsp.read(address,12)
   assert original[address][:8]==bytes.fromhex('014b18887047c046'),'input accessor ABI changed'
  input_keys(0);rsp.write(down,struct.pack('<HHHHI',0x4801,0x4770,0x46c0,0x46c0,0))
  next_frame();step()
  profile_address=None;previous_profile=None;entity_profile_address=None;previous_entity_profile=None;scenery_profile_address=None;previous_scenery_profile=None
  if args.profile_update:
   profile_address=bss_symbol('world','world_update_profile')
   entity_profile_address=bss_symbol('world','world_entity_profile')
   previous_entity_profile=struct.unpack('<7I',rsp.read(entity_profile_address,28))
   profile_flag=bss_symbol('world','world_update_profile_enabled')
   previous_profile=struct.unpack('<6I',rsp.read(profile_address,24))
   original[profile_flag]=rsp.read(profile_flag,1);rsp.write(profile_flag,b'\1')
  if args.profile_scenery:
   scenery_profile_address=bss_symbol('composite','composite_profile_ticks')
   previous_scenery_profile=struct.unpack('<4I',rsp.read(scenery_profile_address,16))
  if args.profile_render and 'storage_profile_enabled' in sym:
   address=sym['storage_profile_enabled'];original[address]=rsp.read(address,4);rsp.write(address,struct.pack('<I',1))
  # Scenario setup: choose tutorial/main through the normal route selector.
  # RAM-only tutorial flags and RNG seed are not persisted.
  state=bss_symbol('game_save','state');rsp.write(state+1688,bytes([0 if args.stage=='tutorial'else 1]*4))
  linkmap=(ARTIFACT_DIR/'build/kinder_fresh.map').read_text();seed=re.findall(r' \.data\.state\s+(0x[0-9a-f]+)\s+0x4 build/kinder_fresh/source/native_rng\.c\.o',linkmap);assert len(seed)==1;rsp.write(int(seed[0],16),struct.pack('<I',2001))
  rsp.write(sym['selection'],bytes([(0,2,3,1)[args.world]]))
  origin=None;next_sample=0;last_updates=None;last_progress=time.monotonic();last_input=None;origin_frames=origin_renders=0;arena_requested=False
  while time.monotonic()-start<args.timeout:
   next_frame()
   ready=bool(rsp.read(bss_symbol('world','ready'),1)[0])
   if not ready:
    if origin is not None:outcome='world_closed';break
    step();continue
   if args.stage=='arena':
    if not arena_requested:
     # Setup fixture only: request the existing main->arena transition. The
     # normal loader/music path handles it; never forge position/damage/ammo.
     rsp.write(bss_symbol('world','transition_target'),struct.pack('<i',args.world+4))
     rsp.write(sym['player']+312,struct.pack('<i',20));arena_requested=True
     step();continue
    if read32(bss_symbol('world','native_world'))!=args.world+4:
     step();continue
   total=read32(sym['performance_total_updates']);frames=read32(sym['performance_total_frames']);renders=read32(sym['performance_total_renders'])
   if origin is None:origin=total;origin_frames=frames;origin_renders=renders
   tick=(total-origin)&0xffffffff
   if total!=last_updates:last_progress=time.monotonic();last_updates=total
   body=struct.unpack('<4i',rsp.read(sym['body']+36,16));x,y=body[0]/4096,body[1]/4096
   player=struct.unpack('<29i',rsp.read(sym['player']+200,116))
   route=read32(sym['active_route']);name=rsp.read(read32(route),32).split(b'\0')[0].decode()
   if name!=controller.map:controller.load(name)
   buttons,reason=controller.choose(tick,x,y,player)
   if buttons!=last_input:
    input_keys(buttons);jsonlog.write(json.dumps({'type':'input','tick':tick,'keys':buttons,'reason':reason,'x':x,'y':y})+'\n');last_input=buttons
   # A30-update sample can repeatedly land on cold column changes, making its
   # phase median unrepresentative. Capture every completed render with one
   # compact RSP read; debugger wall time is excluded by the stopped CPU.
   if renders!=last_render_sample:
    phases=rsp.read(phase_begin,phase_end-phase_begin)
    frame={'tick':tick,'rendered_frames':(renders-origin_renders)&0xffffffff,'x':round(x,3),'y':round(y,3)}
    frame.update({k:struct.unpack_from('<I',phases,sym[k]-phase_begin)[0]for k in phase_names})
    if 'gpu_bitmap_phase_us' in sym:
     frame.update(zip(('bitmap_upload_us','bitmap_bind_us','bitmap_draw_us','bitmap_flush_us'),struct.unpack('<4I',rsp.read(sym['gpu_bitmap_phase_us'],16))))
    if 'gpu_native_active' in sym:
     frame['native_actor_active']=bool(rsp.read(sym['gpu_native_active'],1)[0])
     for field in ('gpu_native_page_hits','gpu_native_texture_bytes','gpu_native_palette_bytes','gpu_native_failures'):frame[field]=read32(sym[field])
    if 'gpu_native_crc_bytes' in sym:frame['gpu_native_crc_bytes']=read32(sym['gpu_native_crc_bytes'])
    for field in ('gpu_native_decoded_cache_hits','gpu_native_decoded_bytes'):
     if field in sym:frame[field]=read32(sym[field])
    if 'gpu_native_io_reads' in sym:
     frame['gpu_native_io_reads']=read32(sym['gpu_native_io_reads']);frame['gpu_native_io_bytes']=read32(sym['gpu_native_io_bytes'])
    for field in ('storage_frame_seek_us','storage_frame_read_us','storage_frame_seek_calls','storage_frame_read_calls','storage_frame_read_bytes'):
     if field in sym:frame[field]=read32(sym[field])
    if args.profile_render:
     if 'native_scene_render' in sym:
      for name in ('frames','cold_loads','failures','bridges','prepare_us','tile_uploads','asset_reads'):
       frame['native_scene_'+name]=read32(bss_symbol('native_scene','native_scene_'+name))
     # Keep scenery/cache costs for every completed render too; periodic samples
     # can repeatedly miss or land on the newly exposed strips.
     details=('read_calls','read_bytes','tile_misses','sprite_misses','sprite_cache_bytes','setup_us','tiles_us','objects_us','callback_us','sample_misses','sample_cache_bytes','live_row_decodes','live_row_hits','background_us')
     frame.update(zip(details,struct.unpack('<14I',rsp.read(sym['render_stats'],56))))
     counters=('composite_remaining_us','composite_prefix_us','composite_overlay_mask_pixels','composite_overlay_prepare_us','composite_overlay_us','composite_static_spans_us','composite_static_fill_us')
     addresses=[sym[k]for k in counters];begin=min(addresses);end=max(addresses)+4
     assert end-begin<=128,'Composite counters unexpectedly far apart'
     values=rsp.read(begin,end-begin)
     frame.update({k:struct.unpack_from('<I',values,sym[k]-begin)[0]for k in counters})
     if 'composite_foreground_clear_pixels' in sym:frame['foreground_clear_pixels']=read32(sym['composite_foreground_clear_pixels'])
    if scenery_profile_address is not None:
     current=struct.unpack('<4I',rsp.read(scenery_profile_address,16))
     frame.update({'scenery_'+name+'_us':(((a-b)&0xffffffff)*1000000)//(33513982//64)for name,a,b in zip(('io','packet','decode','classify'),current,previous_scenery_profile)})
     previous_scenery_profile=current
    if profile_address is not None:
     current_profile=struct.unpack('<6I',rsp.read(profile_address,24))
     names=('geometry','player','body','shots','entities','tail')
     frame.update({'update_'+k+'_us':(((a-b)&0xffffffff)*1000000)//(33513982//64)for k,a,b in zip(names,current_profile,previous_profile)})
     previous_profile=current_profile
     current_entities=struct.unpack('<7I',rsp.read(entity_profile_address,28))
     entity_names=('regions','objects','blocks','platforms','enemies','pickups','bosses')
     frame.update({'entity_'+k+'_us':(((a-b)&0xffffffff)*1000000)//(33513982//64)for k,a,b in zip(entity_names,current_entities,previous_entity_profile)})
     previous_entity_profile=current_entities
    for field in ('gpu_prefix_pixels','gpu_actor_pieces','gpu_depth_mesh_quads','gpu_scenery_cells_sampled'):
     if field in sym:frame[field]=read32(sym[field])
    if 'frame_foreground_rows' in sym:frame['foreground_transfer_rows']=read32(sym['frame_foreground_rows'])
    for field in ('gpu_direct_frames','gpu_direct_tiles','gpu_direct_fallbacks','gpu_direct_palette_us','gpu_direct_palette_line','gpu_direct_late_commits','gpu_direct_palette_cold_uploads','gpu_direct_palette_warm_uploads','direct_scenery_repeats')+AUDIO_STREAM_FIELDS:
     if field in sym:frame[field]=read32(sym[field])
    frame_rows.append(frame);last_render_sample=renders
   if tick>=next_sample or tick>=args.ticks or player[25]<=0 or player[28]==2:
    row={'tick':tick,'loop_frames':(frames-origin_frames)&0xffffffff,'rendered_frames':(renders-origin_renders)&0xffffffff,'map':name,'keys':buttons,'x':round(x,3),'y':round(y,3),'health':player[25],'player_state':player[0],'character':player[1],'switch_state':player[17],'dialogue_state':player[10]}
    for key in ('fps','updates_per_second','audio','update','render','transfer'):row[key]=read32(sym[key])
    names=('read_calls','read_bytes','tile_misses','sprite_misses','sprite_cache_bytes','setup_us','tiles_us','objects_us','callback_us','sample_misses','sample_cache_bytes','live_row_decodes','live_row_hits','background_us')
    row.update(zip(names,struct.unpack('<14I',rsp.read(sym['render_stats'],56))))
    for field in ('composite_static_fill_us','composite_static_spans_us'):
     if field in sym:row[field]=read32(sym[field])
    if args.cache_occupancy:
     from emulator_native_cache import occupancy
     row.update(occupancy(rsp,bss_symbol('native_actors','source_cache'),(ARTIFACT_DIR/'build/kinder_fresh.map').read_text()))
    if 'render_audio_services' in sym:row['render_audio_services']=read32(sym['render_audio_services'])
    for field in ('gpu_direct_frames','gpu_direct_tiles','gpu_direct_fallbacks','gpu_direct_palette_us','gpu_direct_palette_line','gpu_direct_late_commits','gpu_direct_palette_cold_uploads','gpu_direct_palette_warm_uploads','direct_scenery_repeats')+AUDIO_STREAM_FIELDS:
     if field in sym:row[field]=read32(sym[field])
    if 'sound_last_underrun' in sym:row['last_effect_underrun']=list(struct.unpack('<6I',rsp.read(sym['sound_last_underrun'],24)))
    row['music_underruns']=read32(bss_symbol('audio','underruns'));row['effect_underruns']=read32(sym['sound_dropped']) if 'sound_dropped' in sym else read32(bss_symbol('sound_events','underruns'))
    row['host_elapsed_s']=round(time.monotonic()-start,3);rows.append(row)
    if writer is None:writer=csv.DictWriter(csvfile,fieldnames=list(row));writer.writeheader()
    writer.writerow(row);csvfile.flush();jsonlog.write(json.dumps({'type':'sample',**row})+'\n');jsonlog.flush();next_sample=tick+30
    if tick%120<8:print(json.dumps({'world':NAMES[args.world],'stage':args.stage,'tick':tick,'x':x,'fps':row['fps']}),flush=True)
   if player[25]<=0:outcome='player_died';break
   if player[28]==2:outcome='game_result';break
   if tick>=args.ticks:break
   if time.monotonic()-last_progress>15:outcome='simulation_stalled';break
   step()
   boundaries[0]+=1
   # Every fourth boundary stays unsampled to keep the host frame-time estimate current.
   if pc_log and boundaries[0]%4:
    sample_pc(tick)
  else:outcome='host_timeout'
  if args.check_hud:
   from emulator_hud_check import check
   hud_check=check(rsp,sym);jsonlog.write(json.dumps({'type':'hud_check',**hud_check})+'\n')
  if 'native_scene_render' in sym:
   # Native-only builds no longer carry a software renderer or in-ROM raster
   # oracle. Validate real hardware state without inventing pixel parity.
   from emulator_native_scene_check import check as check_native_scene
   native={name:read32(bss_symbol('native_scene','native_scene_'+name))for name in ('frames','cold_loads','failures','bridges','prepare_us','tile_uploads','asset_reads')}
   assert native['failures']==0,'Native scenery failed during route'
   assert bool(rsp.read(sym['gpu_native_bg_visible'],1)[0]),'Native scenery not visible'
   native['cache']=check_native_scene(rsp)
   failures=read32(sym['gpu_prepare_failures']);assert failures==0,'GPU preparation rejected a frame'
   culling={name:read32(sym[name])for name in ('scene_events_culled','scene_events_dispatched','scene_cull_mismatches')if name in sym}
   if 'scene_cull_mismatches' in culling:assert culling['scene_cull_mismatches']==0,'Culled object event changed drawing'
   scenery_verify={name:read32(sym[name])for name in ('native_scenery_verify_views','native_scenery_verify_mismatches','native_scenery_verify_failures')if name in sym}
   if scenery_verify:
    culling['scenery_window_verification']=scenery_verify
    assert scenery_verify['native_scenery_verify_mismatches']==0 and scenery_verify['native_scenery_verify_failures']==0,'Retained foreground window differs from fresh sample'
   sound={name:read32(sym[name])for name in ('sound_plays','sound_dropped','sound_loads','sound_load_bytes','sound_evictions')if name in sym}
   if sound:
    culling['hardware_sound']=sound
   render_check={'scope':'Native hardware state; no software-raster comparison.',
                 'pixel_parity_verified':False,'native_scenery':native,'object_event_culling':culling,'gpu_prepare_failures':failures}
  if 'sound_debug_event_count' in sym and 'sound_debug_events' in sym:
   count=read32(sym['sound_debug_event_count']);raw=rsp.read(sym['sound_debug_events'],64*16)
   events=[]
   for ordinal in range(max(0,count-64),count):
    stamp,slot,key,repeat=struct.unpack_from('<4I',raw,(ordinal&63)*16)
    events.append({'ordinal':ordinal,'sample_clock':stamp,'slot':slot,'key':hex(key),'repeat':repeat})
   render_check['sound_events']={'total':count,'retained':events,'scope':'Debug-only successful play requests; no waveform or listening proof.'}
  jsonlog.write(json.dumps({'type':'render_check',**render_check})+'\n');jsonlog.flush()
  if args.continuous_smoke:
   # No per-frame stops or reads during these wall-clock intervals. Break only
   # at the following game-loop boundary to check liveness and HUD contents.
   for phase,buttons in (('idle',0),('right_jump',17),('left_jump',33),('idle_after',0)):
    input_keys(buttons);before=read32(sym['performance_total_renders']);before_updates=read32(sym['performance_total_updates'])
    step();rsp.resume();stopped=False
    time.sleep(args.continuous_smoke)
    next_frame()
    rendered=(read32(sym['performance_total_renders'])-before)&0xffffffff
    updates=(read32(sym['performance_total_updates'])-before_updates)&0xffffffff
    world_ready=bool(rsp.read(bss_symbol('world','ready'),1)[0])
    smoke_player=struct.unpack('<29i',rsp.read(sym['player']+200,116))
    record={'phase':phase,'uninterrupted_host_seconds':args.continuous_smoke,'renders':rendered,'updates':updates,'world_ready':world_ready,'health':smoke_player[25],'game_mode':smoke_player[28],'hud_byte_equal':False}
    if not world_ready:
     # A completed native death/result transition frees the HUD background.
     # Do not compare freed memory with a live-play HUD or report four phases
     # as verified. Other unexpected world closure remains a hard failure.
     record['ended']='native_results' if smoke_player[28]==2 else 'unexpected_world_close'
     continuous_check.append(record);jsonlog.write(json.dumps({'type':'continuous_smoke',**record})+'\n');jsonlog.flush()
     assert smoke_player[28]==2,'world unexpectedly closed during continuous phase: '+phase
     outcome='native_results_during_smoke';break
    assert rendered>0 and updates>0,'continuous gameplay stopped progressing: '+phase
    hud_ok=False
    if args.check_hud:
     try:check(rsp,sym);hud_ok=True
     except Exception as error:
      record['error']=str(error);continuous_check.append(record);jsonlog.write(json.dumps({'type':'continuous_smoke',**record})+'\n');jsonlog.flush();raise
    record['hud_byte_equal']=hud_ok
    continuous_check.append(record);jsonlog.write(json.dumps({'type':'continuous_smoke',**record})+'\n');jsonlog.flush()
   input_keys(0)

 finally:
  try:
   if active:rsp.command('z'+active)
   for address,data in original.items():rsp.write(address,data)
   if stopped:rsp.resume()
  finally:
   rsp.sock.close();jsonlog.close();csvfile.close()
   if pc_log:pc_log.close()
  framepath=args.output.with_suffix('.frames.csv')
  with framepath.open('w',newline='')as f:
   if frame_rows:
    frame_writer=csv.DictWriter(f,fieldnames=list(frame_rows[0]));frame_writer.writeheader();frame_writer.writerows(frame_rows)
  summary={'rom_sha256':hashlib.sha256((rom_path(ARTIFACT_DIR)).read_bytes()).hexdigest(),'world':NAMES[args.world],'stage':args.stage,'rng_seed':2001,'requested_ticks':args.ticks,'arena_transition_fixture':args.stage=='arena','outcome':outcome,'samples':rows,'trace_file':str(trace),'csv_file':str(csvpath),'frame_csv_file':str(framepath),'cache_occupancy_enabled':args.cache_occupancy,'update_profile_enabled':args.profile_update,'render_profile_enabled':args.profile_render,'scenery_profile_enabled':args.profile_scenery,'scope':'Input-only bounded bot; map-cell/object heuristics are not a complete path planner. RAM stage flags, seed and requested arena transition are test setup only. Emulator timings do not prove DSpico performance.'}
  if frame_rows:
   values=[r['render']for r in frame_rows]
   contiguous=all(((b['rendered_frames']-a['rendered_frames'])&0xffffffff)==1 for a,b in zip(frame_rows,frame_rows[1:]))
   summary['frame_statistics']={'completed_renders_observed':len(frame_rows),'render_counters_contiguous':contiguous,'render_us_median':statistics.median(values),'render_us_p95':sorted(values)[min(len(values)-1,int(len(values)*.95))],'render_us_max':max(values),'scope':'All completed renders at game-loop boundaries, rather than30-update subsamples. Includes initial cold render. Does not include presentation wait/transfer in render time.'}
  if rows:
   summary['statistics']={'ticks':rows[-1]['tick'],'x_range':[min(r['x']for r in rows),max(r['x']for r in rows)],'minimum_health':min(r['health']for r in rows),'minimum_fps':min((r['fps']for r in rows if r['tick']>=60),default=None),'render_us_median':statistics.median(r['render']for r in rows),'render_us_p95':sorted(r['render']for r in rows)[min(len(rows)-1,int(len(rows)*.95))],'render_us_max':max(r['render']for r in rows),'audio_us_max':max(r['audio']for r in rows),'music_underruns':max(r['music_underruns']for r in rows),'effect_underruns':max(r['effect_underruns']for r in rows)}
  summary['continuous_smoke']=continuous_check;summary['render_check']=render_check;summary['pickup_decode_check']=pickup_check;summary['hud_check']=hud_check
  summary['hotspots']=sorted(rows,key=lambda r:r['render'],reverse=True)[:5]
  if rows and 'audio_stream_updates'in rows[-1]:summary['audio_stream']={field:rows[-1][field]for field in AUDIO_STREAM_FIELDS if field in rows[-1]}
  if rows and 'gpu_direct_frames'in rows[-1]:summary['direct_scenery']={field:rows[-1][field]for field in ('gpu_direct_frames','gpu_direct_tiles','gpu_direct_fallbacks','gpu_direct_palette_us','gpu_direct_palette_line','gpu_direct_late_commits','gpu_direct_palette_cold_uploads','gpu_direct_palette_warm_uploads','direct_scenery_repeats')if field in rows[-1]}
  args.output.write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({'result':str(args.output),'outcome':outcome,'statistics':summary.get('statistics')}),flush=True)
 if outcome in ('host_timeout','simulation_stalled'):raise RuntimeError(outcome)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=int,choices=range(4),default=0);p.add_argument('--stage',choices=['main','tutorial','arena'],default='main');p.add_argument('--ticks',type=int,default=1800);p.add_argument('--timeout',type=int,default=120);p.add_argument('--cache-occupancy',action='store_true',help='Read native source-cache occupancy every30updates; use separately from timing comparisons');p.add_argument('--profile-update',action='store_true',help='Enable DS update phase counters and log per-frame deltas');p.add_argument('--check-hud',action='store_true',help='Verify final decoded backdrop and actual sub-screen VRAM');p.add_argument('--profile-scenery',action='store_true',help='Log scenery phase deltas; requires PROFILE_COMPOSITE=1 build');p.add_argument('--profile-render',action='store_true',help='Read detailed scenery counters every render; extra debugger reads can perturb timings');p.add_argument('--continuous-smoke',type=float,default=0,help='Uninterrupted seconds per idle/movement phase (0 disables; max 5)');p.add_argument('--pc-samples',action='store_true',help='Interrupt at a random point after every other frame boundary and log PC/LR/CPSR to <output>.pc.jsonl');p.add_argument('--output',type=Path,required=True);args=p.parse_args();assert 0<=args.continuous_smoke<=5;run(args)
