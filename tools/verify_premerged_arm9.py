"""Link the research ARM9 renderer and check heap bounds without packing a ROM or launching an emulator."""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,tempfile
R=Path(__file__).resolve().parents[1];O=R/'research/rendering/premerged-cached-runtime-candidate'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if shutil.disk_usage(R).free<256*1048576:raise RuntimeError('Less than256MiB free; ELF-only check deferred')
 tracked=[resolve_rom(R / 'ds'),R/'ds/build/kinder_fresh.elf',R/'ds/build/kinder_fresh.map',R/'ds/Makefile',*sorted((R/'ds/source').glob('*.[ch]'))];before={str(p.relative_to(R)):digest(p) for p in tracked};sources={p.name:digest(p) for p in O.glob('*.[ch]')};report={'scope':__doc__,'candidate_sources':sources,'rom_packed':False,'emulator_launched':False}
 with tempfile.TemporaryDirectory(prefix='kinder-premerged-link-') as td:
  t=Path(td);shutil.copytree(R/'ds/source',t/'source')
  for p in O.glob('*.[ch]'):shutil.copy2(p,t/'source'/p.name)
  shutil.copy2(R/'ds/Makefile',t/'Makefile');(t/'assets').symlink_to(R/'ds/assets');(t/'nitrofs').symlink_to(R/'ds/nitrofs')
  log=R/'research/rendering/premerged-cached-arm9-build.log'
  with log.open('w') as f:subprocess.run(['make','-C',str(t),'-j4','build/kinder_fresh.elf'],stdout=f,stderr=subprocess.STDOUT,check=True)
  report['elf_sha256']=digest(t/'build/kinder_fresh.elf')
  for gpu in (False,True):
   path=t/('gpu-heap.json' if gpu else 'cpu-heap.json')
   subprocess.run([sys.executable,str(R/'tools/verify_world_heap.py'),'--artifact-dir',str(t),'--source-overlay-dir',str(O),'--output',str(path),*(['--gpu-layout'] if gpu else [])],stdout=subprocess.DEVNULL,check=True)
   report['gpu_heap' if gpu else 'cpu_heap']=json.loads(path.read_text())
  path=t/'itcm.json';subprocess.run([sys.executable,str(R/'tools/verify_itcm_placement.py'),'--artifact-dir',str(t),'--output',str(path)],stdout=subprocess.DEVNULL,check=True);report['itcm']=json.loads(path.read_text())
 assert before=={str(p.relative_to(R)):digest(p) for p in tracked}
 assert sources=={p.name:digest(p) for p in O.glob('*.[ch]')}
 report['canonical_unchanged']=True;report['limits']=['ELF/link and host allocation proof only; actual NitroFS pack streaming and presentation need emulator/hardware timing.','SDK/stdio allocations reserved at64KiB, not measured.','No extra release ROM produced.']
 (R/'research/rendering/premerged-cached-arm9-verification.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'elf_linked':True,'rom_packed':False,'canonical_unchanged':True,'heap_bytes':report['gpu_heap']['linked_heap_bytes'],'minimum_after_runtime_reserve':min(m['remaining_after_runtime_reserve'] for m in report['gpu_heap']['maps'])}))
if __name__=='__main__':main()
