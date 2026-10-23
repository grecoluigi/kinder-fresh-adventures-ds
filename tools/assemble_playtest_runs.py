"""Assemble completed contexts from identical-ROM runs, preserving failed attempts."""
from pathlib import Path
import argparse,hashlib,json

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,action='append',required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();selected={};sources=[];failures=[];reference=None
 for folder in a.run:
  folder=folder.resolve();manifest=folder/'run.json';run=json.loads(manifest.read_text());identity=tuple(run[k]for k in ('rom_sha256','elf_sha256','rom_bytes','ticks_per_case'))
  assert run['emulator_closed']
  if reference is None:reference=identity;combined={k:v for k,v in run.items()if k!='results'}
  assert identity==reference,'Cannot combine different ROMs, symbols or update limits'
  sources.append({'path':str(manifest),'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()})
  for row in run['results']:
   if row['returncode']:
    failures.append({'case':row['case'],'source':str(manifest),'returncode':row['returncode']});continue
   case=json.loads((folder/(row['case']+'.json')).read_text());assert case['rom_sha256']==identity[0]and case['requested_ticks']==identity[3]
   selected[row['case']]=(folder,row)
 expected={world+'-'+stage for world in ('jungle','ice','factory','fantasy')for stage in ('main','tutorial','arena')};assert set(selected)==expected
 out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False);rows=[];files={}
 for name in sorted(selected):
  folder,row=selected[name];rows.append({**row,'source_run':str(folder/'run.json')})
  for source in folder.glob(name+'.*'):
   if not source.is_file():continue
   target=out/source.name;target.symlink_to(source.resolve());files[source.name]=hashlib.sha256(source.read_bytes()).hexdigest()
 combined.update(results=rows,assembled_from=sources,previous_failed_attempts=failures,artifact_sha256=files,scope=__doc__+' All inputs retain their own original reports.');(out/'run.json').write_text(json.dumps(combined,indent=2)+'\n');print(json.dumps({'contexts':len(rows),'failed_attempts_retained':len(failures),'output':str(out)}))
if __name__=='__main__':main()
