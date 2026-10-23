#!/usr/bin/env python3
"""Own a bounded UI diagnostic emulator session and close it afterward."""
from rom_artifact import rom_path
import argparse,json,os,shutil,subprocess,sys,time
from pathlib import Path
from emulator_output import BoundedOutput
from playtest import ROOT,CONFIG,EMU,processes,section_option,write_config

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifact-dir',type=Path,default=ROOT/'ds');p.add_argument('--world',type=int,choices=range(4),default=0);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 if processes():raise RuntimeError('melonDS already running; will not interrupt it')
 if shutil.disk_usage(ROOT).free<1024*1024*1024:raise RuntimeError('Less than1GiB free; UI emulator test stopped before launch')
 artifact=args.artifact_dir.resolve();original=CONFIG.read_text();args.output.parent.mkdir(parents=True,exist_ok=True)
 proc=None
 try:
  c=section_option(original,'Instance0.Gdb','Enabled','true');c=section_option(c,'DLDI','Enable','false');write_config(c)
  with BoundedOutput([str(EMU),'-b','always',str(rom_path(artifact))]) as native:
   proc=native.process
   try:
    deadline=time.monotonic()+20
    while str(proc.pid)not in subprocess.run(['lsof','-nP','-iTCP:3333','-sTCP:LISTEN'],capture_output=True,text=True).stdout:
     if proc.poll()is not None or time.monotonic()>deadline:raise RuntimeError('UI debugger listener failed')
     time.sleep(.2)
    with args.output.with_suffix('.runner.log').open('w') as log:
     subprocess.run([sys.executable,str(ROOT/'tools/emulator_bottom_surfaces.py'),'--output',str(args.output),'--world',str(args.world)],stdout=log,stderr=subprocess.STDOUT,timeout=120,check=True,env={**os.environ,'KF_DS_ARTIFACT_DIR':str(artifact)})
   finally:
    if proc.poll()is None:proc.terminate()
    try:proc.wait(timeout=20)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=10)
    native.save(args.output.with_suffix('.emulator-tail.log'))
 finally:
  write_config(section_option(original,'Instance0.Gdb','Enabled','false'))
  closed=not processes();args.output.with_suffix('.cleanup.json').write_text(json.dumps({'emulator_closed':closed,'debugger_disabled':True})+'\n')
  if not closed:raise RuntimeError('UI emulator still running after cleanup')
 print('UI diagnostic completed; emulator closed: '+str(args.output),flush=True)
if __name__=='__main__':main()
