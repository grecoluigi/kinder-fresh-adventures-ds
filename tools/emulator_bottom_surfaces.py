"""Observe real DS UI transfer destinations and SDK keyboard display state via RSP.

Forced result scores/game-mode and RAM-only input pulses exercise presentation,
not gameplay completion or physical touch typing. All patched code is restored.
"""
from pathlib import Path
from rom_artifact import rom_path
import argparse,json,struct,hashlib,time
from emulator_counters import RSP,symbols,ROOT,ARTIFACT_DIR

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--world',type=int,choices=range(4),default=0);parser.add_argument('--output',type=Path,default=ROOT/'research/gameplay/emulator-bottom-surfaces.json');args=parser.parse_args()
 sym=symbols();rsp=RSP(3333);patches={};active=None;stopped=True;proof=[];storage_diagnostics=None;audio_stream=None
 def patch_input(name,value):
  address=sym[name]
  if address not in patches:
   old=rsp.read(address,8);assert old[:4]==bytes.fromhex('014b1888') and old[4:6]==bytes.fromhex('7047'),(name,'unexpected Thumb input accessor');patches[address]=old
  assert 0<=value<=65535
  # A four-byte MOVS/BX stub can only return eight-bit masks. Compose both
  # bytes so X/Y/touch input cannot silently become a different instruction.
  rsp.write(address,struct.pack('<4H',0x2000|(value>>8),0x0200,0x3000|(value&255),0x4770))
 def stop_at(name,kind,changes=None):
  nonlocal active,stopped
  bp=f'0,{sym[name]:x},{kind}';assert rsp.command('Z'+bp)=='OK';active=bp
  if changes:changes()
  if stopped:rsp.resume();stopped=False
  assert rsp.receive().startswith(('S','T')),'missing breakpoint stop';stopped=True
  raw=bytes.fromhex(rsp.command('g'));regs=struct.unpack('<'+'I'*(len(raw)//4),raw)
  assert rsp.command('z'+bp)=='OK';active=None
  return regs
 def step():
  nonlocal stopped
  assert stopped and rsp.command('s').startswith(('S','T')),'single-step failed'
 def finish_call(regs):
  nonlocal active,stopped
  address=regs[14]&~1;kind=2 if regs[14]&1 else 4
  bp=f'0,{address:x},{kind}';assert rsp.command('Z'+bp)=='OK';active=bp
  rsp.resume();stopped=False;assert rsp.receive().startswith(('S','T'));stopped=True
  assert rsp.command('z'+bp)=='OK';active=None
 def observe_transfer(label,changes=None):
  if label in('world_start','world_restart')and 'publish_hud'in sym:
   regs=stop_at('publish_hud',2,changes);step();frame()
   from emulator_hud_check import check as check_hud
   row={'event':label,'destination':'0x6200000','source':hex(regs[0]),'indexed_hud':check_hud(rsp,sym)};assert row['indexed_hud']['world']==args.world,'menu selected a different world';proof.append(row);return row
  wrapped='transfer_surface'in sym and label!='restored_game_frame'
  regs=stop_at('transfer_surface'if wrapped else 'frame_transfer',2 if wrapped else 4,changes);row={'event':label,'destination':hex(regs[0]),'source':hex(regs[1]),'main_display':hex(struct.unpack('<I',rsp.read(0x04000000,4))[0]),'sub_display':hex(struct.unpack('<I',rsp.read(0x04001000,4))[0]),'BG2_control':struct.unpack('<H',rsp.read(0x0400000c,2))[0]}
  if label.endswith('return_menu'):
   src,dest,control=struct.unpack('<3I',rsp.read(0x040000d4,12));fill=struct.unpack('<I',rsp.read(0x040000ec,4))[0]
   assert src==0x040000ec and dest in (0x06000000,0x06020000)and fill==0x8000,'root menu must clear top bitmap'
   assert control&0x1fffff==49152 and control&(1<<24)and not control&(1<<26),'opaque halfword fill covers192rows'
   row['top_clear_DMA']={'source':hex(src),'destination':hex(dest),'control':hex(control),'fill':hex(fill)}
  from emulator_palette_check import check as check_palette
  lease=check_palette(rsp,sym)
  if lease is not None:row['palette_lease']=lease
  if wrapped:
   finish_call(regs)
   row['sub_display']=hex(struct.unpack('<I',rsp.read(0x04001000,4))[0]);row['transfer_finished']=True
  else:step()
  proof.append(row);return row
 def frame():
  stop_at('performance_frame',2);step()
 def selection(value):rsp.write(sym['selection'],bytes([value]))
 def viewer_entry(label,score):
  def finish():rsp.write(sym['hud'],struct.pack('<i',score));rsp.write(sym['player']+312,struct.pack('<i',2))
  regs=stop_at('highscore_ui_draw',2,finish);ui=regs[2];data=rsp.read(ui,60);rank=struct.unpack_from('<i',data,8)[0]
  proof.append({'event':label,'editing_rank':rank,'sub_display':hex(struct.unpack('<I',rsp.read(0x04001000,4))[0]),'ui':hex(ui)})
  step();row=observe_transfer(label+'_transfer');return ui,rank,row
 try:
  patch_input('keysHeld',0);patch_input('keysDown',0);rsp.resume();stopped=False
  deadline=time.monotonic()+30
  while struct.unpack('<I',rsp.read(sym['fps'],4))[0]==0:
   assert time.monotonic()<deadline,'startup timeout';time.sleep(.25)
  frame()
  row=observe_transfer('main_menu_highscores',lambda:selection(4));assert row['destination']=='0x6200000'
  frame();row=observe_transfer('highscore_return_menu',lambda:patch_input('keysDown',2));assert row['destination']=='0x6200000';patch_input('keysDown',0)
  frame();row=observe_transfer('credits_page0',lambda:selection(5));assert row['destination']=='0x6200000'
  for page in range(1,4):
   frame();row=observe_transfer(f'credits_page{page}',lambda:patch_input('keysDown',1));assert row['destination']=='0x6200000';patch_input('keysDown',0)
  frame();row=observe_transfer('credits_return_menu',lambda:patch_input('keysDown',1));assert row['destination']=='0x6200000';patch_input('keysDown',0)
  frame();observe_transfer('world_start',lambda:selection((0,2,3,1)[args.world]));frame()
  _,rank,row=viewer_entry('nonqualifying_result',-1);assert rank==-1 and row['destination']=='0x6200000'
  frame();observe_transfer('result_return_menu',lambda:patch_input('keysDown',2));patch_input('keysDown',0)
  frame();observe_transfer('world_restart',lambda:selection((0,2,3,1)[args.world]));frame()
  # Validate native hardware state after returning from results/menu.
  if 'native_scene_render' in sym:
   from emulator_native_scene_check import check as check_native_scene
   from emulator_counters import module_bss_symbol
   cache=check_native_scene(rsp)
   failures=struct.unpack('<I',rsp.read(module_bss_symbol('native_scene','native_scene_failures'),4))[0]
   assert failures==0 and bool(rsp.read(sym['gpu_native_bg_visible'],1)[0])
   proof.append({'event':'world_restart_native_state','cache':cache,'failures':failures,
                 'pixel_parity_verified':False})

  ui,rank,row=viewer_entry('qualifying_name_entry',999999);assert rank>=0 and row['destination']in ('0x6000000','0x6020000')
  gpu=bool(rsp.read(sym['gpu_mode'],1)[0])if 'gpu_mode'in sym else False
  oldbase=(int(row['destination'],16)-0x06000000)//16384;restorebase=0 if gpu else 0 if oldbase else 8
  sub=int(row['sub_display'],16);assert sub&(1<<8),'SDK keyboard must enable BG0'
  if 'keyboard_backdrop_ready'in sym:
   assert rsp.read(sym['keyboard_backdrop_ready'],1)==b'\1','level backdrop must survive world_close'
   assert sub&(1<<11),'level backdrop must remain visible behind keyboard'
   control=struct.unpack('<H',rsp.read(0x0400100e,2))[0]
   assert (control>>8)&31==4 and control&3==3,'backdrop must use upper64KiB bitmap behind keys'
   from tile_storage import unlz
   name=('jungle','ice','factory','fantasy')[args.world]
   blob=(ARTIFACT_DIR/'nitrofs/native_bottom'/(name+'.nbh')).read_bytes();expected=unlz(blob[524:])
   assert rsp.read(0x06210000,49152)==expected,'keyboard backdrop pixels differ from current level crop'
   palette=rsp.read(0x05000500,256)
   assert all((a&32767)==(b&32767)for(a,),(b,)in zip(struct.iter_unpack('<H',palette),struct.iter_unpack('<H',blob[268:524]))),'keyboard backdrop palette mismatch'
   keys_control=struct.unpack('<H',rsp.read(0x04001008,2))[0];assert keys_control&3==0
   assert rsp.read(0x06200000+((keys_control>>2)&15)*16384,32)==bytes(32),'unused keyboard map tile must be transparent'
   keymap=rsp.read(0x06200000+((keys_control>>8)&31)*2048,4096)
   assert all(word>>12<8 for(word,)in struct.iter_unpack('<H',keymap)),'keyboard must not use backdrop palette entries'
   row['keyboard_backdrop']={'world':args.world,'pixels_byte_equal':True,'palette_equal':True,'bitmap_base':'0x06210000','separate_keyboard_storage':True,'unused_keyboard_tile_transparent':True}
  else:assert not sub&(1<<11),'legacy SDK keyboard replaces sub bitmap'
  # Supply deterministic name data; actual touch decoding is outside this probe.
  rsp.write(ui+16,b'DS TEST\0');rsp.write(ui+48,struct.pack('<I',7));revision=struct.unpack('<I',rsp.read(ui+56,4))[0];rsp.write(ui+56,struct.pack('<I',revision+1))
  frame();row=observe_transfer('restored_game_frame'if gpu else'confirmed_table',lambda:patch_input('keysDown',1));patch_input('keysDown',0)
  if gpu:
   assert row['destination']=='0x6000000'and row['source']in ('0x6800000','0x6820000'),'GPU mode must restore saved inactive-bank snapshot'
   row=observe_transfer('confirmed_table')
  assert row['destination']=='0x6200000'
  sub=int(row['sub_display'],16);assert sub&(1<<11)and not sub&(1<<8),'SDK keyboard must close and restore bottom bitmap'
  assert (row['BG2_control']>>8)&31==restorebase,'top game snapshot must be restored after name entry'
  assert struct.unpack_from('<i',rsp.read(ui,60),8)[0]==-1,'confirmed editor must return to viewer'
  assert rsp.read(ui+16,7)!=b'DS TEST','viewer should reset editor state'
  frame();row=observe_transfer('confirmed_return_menu',lambda:patch_input('keysDown',2));assert row['destination']=='0x6200000';patch_input('keysDown',0)
  if 'storage_frame_read_us' in sym and ('draw_bottom_diagnostics'in sym or 'performance_draw'in sym):
   if 'publish_hud'in sym:
    frame();observe_transfer('world_restart',lambda:selection((0,2,3,1)[args.world]));frame()
   # Exercise the real Y toggle and verify the added row in sub-screen VRAM.
   wrapped_diagnostics='draw_bottom_diagnostics'in sym
   frame();regs=stop_at('draw_bottom_diagnostics'if wrapped_diagnostics else 'performance_draw',2,lambda:patch_input('keysDown',1<<11));patch_input('keysDown',0)
   indexed=wrapped_diagnostics and struct.unpack('<I',rsp.read(sym['hud_surface'],4))[0]==2
   destination=0x06200000 if wrapped_diagnostics else regs[0];assert destination==0x06200000
   row_bytes=256 if indexed else 512
   untouched=rsp.read(destination+27*row_bytes,row_bytes);step();frame()
   if indexed:
    palette=struct.unpack('<256H',rsp.read(0x05000400,512));pixels=[32768|(palette[i]&32767)for i in rsp.read(destination,256*27)]
   else:pixels=struct.unpack('<'+str(256*27)+'H',rsp.read(destination,256*27*2))
   glyphs=((14,4,4,4,4,4,14),(14,17,17,17,17,17,14))
   for column,glyph in enumerate(glyphs):
    for y in range(7):
     for x in range(6):
      expected=0xffff if x<5 and glyph[y]&(16>>x) else 0x8000
      assert pixels[(19+y)*256+column*6+x]==expected,'storage IO label missing or corrupt'
   assert all(v==0x8000 for v in pixels[26*256:27*256]),'diagnostic row padding missing'
   assert rsp.read(destination+27*row_bytes,row_bytes)==untouched,'diagnostics overwrite the next HUD row'
   storage_diagnostics={'indexed':indexed,'third_row_IO_glyphs_exact':True,'row27_preserved':True,'destination':hex(destination)}
   patch_input('keysDown',1<<11);frame();patch_input('keysDown',0)
   if indexed:
    frame()
    from emulator_hud_check import check as check_hud
    storage_diagnostics['hud_after_hiding']=check_hud(rsp,sym)
   if 'storage_profile_enabled' in sym:
    assert struct.unpack('<I',rsp.read(sym['storage_profile_enabled'],4))[0]==0,'hiding diagnostics must disable storage timing'
    storage_diagnostics['disabled_after_Y']=True
  if 'audio_stream_updates' in sym:
   fields=('audio_stream_service_gap_peak_us','audio_stream_deadline_misses','audio_stream_callback_frames_peak','audio_stream_callback_calls','audio_stream_updates')
   audio_stream={field:struct.unpack('<I',rsp.read(sym[field],4))[0]for field in fields if field in sym}
 finally:
  if active is not None:rsp.command('z'+active)
  for address,original in patches.items():rsp.write(address,original)
  if stopped:rsp.resume()
  rsp.sock.close()
  result={'scope':__doc__,'rom_sha256':hashlib.sha256((rom_path(ARTIFACT_DIR)).read_bytes()).hexdigest(),'observations':proof,'limits':['Presentation uses forced result state and scripted RAM input, not a full death/boss playthrough.','Name bytes are supplied in RAM; physical SDK touch keyboard typing, hardware FAT persistence and pixel screenshots are not verified.']}
  if storage_diagnostics is not None:result['storage_diagnostics']=storage_diagnostics
  if audio_stream is not None:result['audio_stream']=audio_stream
  args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
