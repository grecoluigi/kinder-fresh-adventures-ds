"""Assemble generated runtime payloads into a source project's empty asset folders.

Only explicit runtime formats are embedded; conversion logs, previews, manifests,
original files and study data stay outside the ROM. Source headers are paired
with their generated payloads. Existing asset folders are never overwritten.
"""
from pathlib import Path
import argparse,hashlib,json,shutil
from player_metadata import player_metadata
from scene_actor_metadata import scene_actor_metadata

def assemble(generated,project,icon=None):
 generated=generated.resolve();project=project.resolve()
 icon=Path(icon).resolve() if icon is not None else project/'icon.png'
 manifest=json.loads((generated/'generation-manifest.json').read_text())
 assert manifest['through']=='scenery' and len(manifest['steps'])==29
 assert all(s['returncode']==0 for s in manifest['steps'])
 assert(project/'Makefile').is_file()and(project/'source').is_dir(),'Expected DS source project'
 assert not(project/'assets').exists()and not(project/'nitrofs').exists(),'Asset folders already exist'
 assert icon.is_file(),'Missing bundled ds/icon.png (or supply --icon for a custom banner)'
 files={}
 def add(source,destination):
  assert source.is_file(),str(source)
  assert destination not in files,'Duplicate destination '+destination
  files[destination]=source
 def group(source,destination,suffixes,count):
  paths=sorted(p for p in(generated/source).iterdir()if p.is_file()and p.suffix in suffixes)
  assert len(paths)==count,(source,len(paths),count)
  for path in paths:add(path,destination+'/'+path.name)
 group('menu','assets',{'.bin'},7)
 for source,suffixes,count in [('credits',{'.bin'},4),('end_titles',{'.bin'},2),
                              ('enemy_shots',{'.bin'},8),('highscores',{'.bin'},25),('native_actors',{'.gpu'},1),
                              ('native_bottom',{'.nhp','.nbh'},5),('native_scenery',{'.nsc','.ntb','.mesh'},36),
                              ('players',{'.frames'},2),('projectiles',{'.bin'},1)]:
  group(source,'nitrofs/'+source,suffixes,count)
 group('hardware_audio/audio','nitrofs/audio',{'.kfm'},6)
 group('hardware_audio/sounds','nitrofs/sounds',{'.hw'},1)
 group('scenes','nitrofs/scenes',{'.scene','.bg','.mask','.collision'},49)
 group('backgrounds','nitrofs/scenes',{'.par'},8)
 group('entities','nitrofs/scenes',{'.entities','.frames'},13)
 group('enemies','nitrofs/scenes',{'.frames'},1)
 group('geometry','nitrofs/scenes',{'.geometry'},1)
 add(generated/'score_popups/points.bin','nitrofs/enemy_shots/points.bin')
 for source,name in [('menu','menu_hitboxes.h'),('highscores','highscore_assets.h'),('sounds','sound_assets.inc')]:
  add(generated/source/name,'source/'+name)
 add(icon,'icon.png')
 rows=[]
 for destination,source in sorted(files.items()):
  target=project/destination;target.parent.mkdir(parents=True,exist_ok=True)
  if destination.startswith('nitrofs/players/'):
   target.write_bytes(player_metadata(source.read_bytes()))
  elif destination in ('nitrofs/scenes/enemies.frames','nitrofs/scenes/pickups.frames'):
   target.write_bytes(scene_actor_metadata(source.read_bytes(),destination.endswith('/enemies.frames')))
  elif source.resolve()!=target.resolve():shutil.copyfile(source,target)
  rows.append({'path':destination,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 result={'scope':__doc__,'files':rows,'runtime_files':sum(r['path'].startswith(('assets/','nitrofs/'))for r in rows),
         'runtime_payload_bytes':sum(r['bytes']for r in rows if r['path'].startswith(('assets/','nitrofs/'))),
         'disc':manifest['disc'],'complete_rom_build_verified':False}
 (project/'asset-assembly.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items()if k not in('files','disc','scope')}))
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--generated',type=Path,required=True);p.add_argument('--project',type=Path,required=True)
 p.add_argument('--icon',type=Path,help='Optional custom 32x32 indexed PNG; defaults to bundled PROJECT/icon.png')
 a=p.parse_args();assemble(a.generated,a.project,a.icon)

if __name__=='__main__':main()
