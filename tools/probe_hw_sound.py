#!/usr/bin/env python3
"""Observe ARM7 hardware sound channels while the menu plays feedback sounds.

Boots a build in melonDS, holds Down so menu focus moves and UI feedback
sounds are requested, and repeatedly interrupts the ARM7 debugger stub (the
ARM9 keeps running) to read the 16 channel register blocks. Reports which
channels were seen enabled, with format/volume/source, plus the ARM9 play
counters. Emulator-only evidence of channel programming; not a listening test.
"""
from rom_artifact import rom_path as resolve_rom
import argparse,json,os,shutil,struct,subprocess,sys,time
from pathlib import Path
from emulator_output import BoundedOutput
from playtest import ROOT,CONFIG,EMU,processes,section_option,write_config
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifact-dir',type=Path,default=ROOT/'ds');p.add_argument('--output',type=Path,required=True)
 p.add_argument('--samples',type=int,default=40);a=p.parse_args()
 if processes():raise RuntimeError('melonDS already running; will not interrupt it')
 artifact=a.artifact_dir.resolve();os.environ['KF_DS_ARTIFACT_DIR']=str(artifact)
 from emulator_counters import RSP,symbols
 sym=symbols();original=CONFIG.read_text();report={'artifact':str(artifact),'samples':[],'scope':__doc__.strip().splitlines()[0]}
 try:
  c=section_option(original,'Instance0.Gdb','Enabled','true');c=section_option(c,'DLDI','Enable','false');write_config(c)
  with BoundedOutput([str(EMU),'-b','always',str(resolve_rom(artifact))]) as native:
   proc=native.process
   try:
    deadline=time.monotonic()+20
    while str(proc.pid)not in subprocess.run(['lsof','-nP','-iTCP:3334','-sTCP:LISTEN'],capture_output=True,text=True).stdout:
     if proc.poll()is not None or time.monotonic()>deadline:raise RuntimeError('debugger listener failed')
     time.sleep(.2)
    arm9=RSP(3333)
    # Hold Down: Thumb stub returning a constant from keysDown/keysHeld (same patch as the playtest controller).
    for name in ('keysDown','keysHeld'):arm9.write(sym[name],struct.pack('<HHHHI',0x4801,0x4770,0x46c0,0x46c0,0x80))
    arm9.resume();time.sleep(3)
    arm7=RSP(3334);seen={}
    for i in range(a.samples):
     arm7.sock.sendall(b'\x03');arm7.receive()
     raw=arm7.read(0x04000400,256);arm7.resume()
     enabled=[]
     for ch in range(16):
      cnt,sad=struct.unpack_from('<II',raw,ch*16)
      if cnt&0x80000000:
       entry={'channel':ch,'format':(cnt>>29)&3,'repeat':(cnt>>27)&3,'volume':cnt&127,'source':hex(sad)}
       enabled.append(entry);seen.setdefault(ch,entry)
      report['samples'].append({'i':i,'enabled':[e['channel'] for e in enabled]}) if False else None
     report['samples'].append([e['channel'] for e in enabled])
     time.sleep(.05)
    arm7.sock.close()
    arm9.sock.sendall(b'\x03');arm9.receive()
    report['arm9']={n:struct.unpack('<I',arm9.read(sym[n],4))[0] for n in ('sound_plays','sound_dropped','sound_loads') if n in sym}
    report['channels_seen_enabled']=seen
    arm9.resume();arm9.sock.close()
   finally:
    if proc.poll()is None:proc.terminate()
    try:proc.wait(timeout=20)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=10)
 finally:
  write_config(section_option(original,'Instance0.Gdb','Enabled','false'))
  report['emulator_closed']=not processes()
  a.output.write_text(json.dumps(report,indent=1)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='samples'},indent=1))
if __name__=='__main__':main()
