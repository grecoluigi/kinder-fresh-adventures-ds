#!/usr/bin/env python3
"""Build, launch, connect, drive, log and close melonDS in one command."""
from rom_artifact import rom_path
import argparse,datetime,hashlib,json,os,re,shutil,subprocess,sys,time,tomllib
from pathlib import Path
from emulator_output import BoundedOutput
ROOT=Path(__file__).resolve().parents[1]
CONFIG=Path.home()/'Library/Preferences/melonDS/melonDS.toml'
EMU=Path('/Applications/melonDS.app/Contents/MacOS/melonDS')
WORLDS=('jungle','ice','factory','fantasy')
def write_config(text,path=CONFIG):
 # A failed write must not truncate the user's original preferences file.
 tomllib.loads(text);temporary=path.with_suffix('.toml.codex-tmp')
 try:
  temporary.write_text(text);temporary.replace(path)
 finally:temporary.unlink(missing_ok=True)
def processes():
 lines=subprocess.check_output(['ps','-axo','pid,command'],text=True).splitlines()[1:]
 return [line for line in lines if len(line.split(None,1))==2 and line.split(None,1)[1].startswith(str(EMU))]
def section_option(text,section,key,value):
 pattern=r'(\['+re.escape(section)+r'\]\n)(.*?)(?=\n\[|\Z)';match=re.search(pattern,text,re.S)
 if not match:raise RuntimeError('Missing configuration section '+section)
 content=match[2];line=r'(?m)^'+re.escape(key)+r'\s*=.*$'
 if not re.search(line,content):raise RuntimeError('Missing configuration option '+section+'.'+key)
 content=re.sub(line,key+' = '+value,content)
 return text[:match.start(2)]+content+text[match.end(2):]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--no-build',action='store_true');p.add_argument('--artifact-dir',type=Path,default=ROOT/'ds',help='Directory containing the ROM and matching build ELF/map');p.add_argument('--world',choices=(*WORLDS,'all'),default='jungle');p.add_argument('--stage',choices=['main','tutorial','arena','both'],default='main');p.add_argument('--include-arenas',action='store_true');p.add_argument('--ticks',type=int,default=1800);p.add_argument('--timeout',type=int,default=120);p.add_argument('--cache-occupancy',action='store_true',help='Log native source-cache occupancy; separate from timing comparisons');p.add_argument('--profile-update',action='store_true');p.add_argument('--check-hud',action='store_true');p.add_argument('--profile-scenery',action='store_true');p.add_argument('--profile-render',action='store_true');p.add_argument('--continuous-smoke',type=float,default=0,help='Uninterrupted seconds per phase, 0 to 5');p.add_argument('--pc-samples',action='store_true',help='Statistical PC sampling for profiling; separate from timing runs');p.add_argument('--output-dir',type=Path);args=p.parse_args()
 if not 0<=args.continuous_smoke<=5:p.error('continuous-smoke must be between 0 and 5 seconds')
 if args.ticks<=0 or args.timeout<=0:p.error('ticks and timeout must be positive')
 if processes():raise RuntimeError('melonDS is already running; this runner will not interrupt that session')
 artifact_dir=args.artifact_dir.resolve()
 if not args.no_build:subprocess.run(['make','-C',str(artifact_dir),'-j4'],check=True)
 rom=rom_path(artifact_dir);elf=artifact_dir/'build/kinder_fresh.elf';sha=hashlib.sha256(rom.read_bytes()).hexdigest();elf_sha=hashlib.sha256(elf.read_bytes()).hexdigest();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=args.output_dir.resolve() if args.output_dir else ROOT/'research/playtests'/(stamp+'-'+sha[:10]);out.mkdir(parents=True,exist_ok=False)
 original=CONFIG.read_text();saved_dldi=re.search(r'\[DLDI\]\n(.*?)(?=\n\[|\Z)',original,re.S)[1];dldi_value=re.search(r'(?m)^Enable = (true|false)$',saved_dldi)[1]
 reports=[];run={'artifact_dir':str(artifact_dir),'rom_sha256':sha,'elf_sha256':elf_sha,'rom_bytes':rom.stat().st_size,'ticks_per_case':args.ticks,'cache_occupancy_enabled':args.cache_occupancy,'results':reports,'scope':'Automatic bounded controller through real game inputs, not complete game playthroughs or hardware timings.'}
 def unchanged_build():
  if hashlib.sha256(rom.read_bytes()).hexdigest()!=sha or hashlib.sha256(elf.read_bytes()).hexdigest()!=elf_sha:
   raise RuntimeError('ROM or debugger symbols changed during playtest; finish the run before rebuilding')
 try:
  for world in range(4)if args.world=='all'else [WORLDS.index(args.world)]:
   stages=('main','tutorial')if args.stage=='both'else(args.stage,)
   if args.include_arenas and 'arena'not in stages:stages+=('arena',)
   for stage in stages:
    if shutil.disk_usage(ROOT).free<1024*1024*1024:raise RuntimeError('Less than1GiB free; emulator tests stopped before launch')
    unchanged_build()
    case=WORLDS[world]+'-'+stage;logfile=out/(case+'.runner.log');result_path=out/(case+'.json')
    config=section_option(CONFIG.read_text(),'Instance0.Gdb','Enabled','true');config=section_option(config,'DLDI','Enable','false');write_config(config)
    with BoundedOutput([str(EMU),'-b','always',str(rom)])as native,logfile.open('w')as log:
     proc=native.process
     try:
      deadline=time.monotonic()+20
      while str(proc.pid)not in subprocess.run(['lsof','-nP','-iTCP:3333','-sTCP:LISTEN'],capture_output=True,text=True).stdout:
       if proc.poll()is not None or time.monotonic()>deadline:raise RuntimeError('Emulator debugger listener failed to start')
       time.sleep(.2)
      code=subprocess.run([sys.executable,str(ROOT/'tools/emulator_autoplay.py'),'--world',str(world),'--stage',stage,'--ticks',str(args.ticks),'--timeout',str(args.timeout),'--continuous-smoke',str(args.continuous_smoke),*(['--cache-occupancy']if args.cache_occupancy else[]),*(['--profile-update']if args.profile_update else[]),*(['--pc-samples']if args.pc_samples else[]),*(['--profile-render']if args.profile_render else[]),*(['--check-hud']if args.check_hud else[]),*(['--profile-scenery']if args.profile_scenery else[]),'--output',str(result_path)],stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout+20,env={**os.environ,'KF_DS_ARTIFACT_DIR':str(artifact_dir)}).returncode
      unchanged_build()
      record=json.loads(result_path.read_text())if result_path.exists()else {};metrics=record.get('statistics',{});issues=[]
      if metrics.get('effect_underruns',0):issues.append('effect_audio_underrun')
      if metrics.get('music_underruns',0):issues.append('music_audio_underrun')
      if metrics.get('minimum_fps')is not None and metrics['minimum_fps']<30:issues.append('sampled_fps_below_30')
      record['issues']=issues
      if result_path.exists():result_path.write_text(json.dumps(record,indent=2)+'\n')
      reports.append({'case':case,'returncode':code,'outcome':record.get('outcome'),'statistics':record.get('statistics'),'frame_statistics':record.get('frame_statistics'),'continuous_smoke':record.get('continuous_smoke'),'render_check':record.get('render_check'),'issues':issues});print(json.dumps(reports[-1]),flush=True)
      if code:raise RuntimeError(case+' failed; inspect '+str(logfile))
     finally:
      if proc.poll()is None:proc.terminate()
      try:proc.wait(timeout=20)
      except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=10)
      native.save(out/(case+'.emulator-tail.log'))
      if processes():raise RuntimeError('Emulator remains running after cleanup')
 finally:
  config=section_option(CONFIG.read_text(),'Instance0.Gdb','Enabled','false');config=section_option(config,'DLDI','Enable',dldi_value);write_config(config);run['emulator_closed']=not processes();(out/'run.json').write_text(json.dumps(run,indent=2)+'\n')
 print('Playtest logs: '+str(out),flush=True)
if __name__=='__main__':main()
