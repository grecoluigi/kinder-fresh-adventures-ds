"""Verify host-token identity and linked ARM9 ITCM placement for the candidate."""
from pathlib import Path
import argparse,hashlib,json,subprocess
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifact-dir',type=Path,required=True);p.add_argument('--reference-dir',type=Path,default=R/'research/rendering/itcm-reference');p.add_argument('--candidate-dir',type=Path);p.add_argument('--placement-only',action='store_true');p.add_argument('--output',type=Path,default=R/'research/rendering/itcm-placement-verification.json');a=p.parse_args()
candidate=a.candidate_dir or R/'research/rendering/itcm-candidate';results=[]
for name in (() if a.placement_only else ('scene.c','player_graphics.c','sound_events.c')):
 texts=[]
 for path in (a.reference_dir/name,candidate/name):
  text=subprocess.check_output(['cc','-E','-P','-I'+str(R/'ds/source'),str(path)],text=True)
  texts.append(' '.join(text.split()))
 assert texts[0]==texts[1],name+' changes host tokens beyond placement annotations'
 results.append({'file':name,'preprocessed_host_tokens_exact':True,'tokens_sha256':hashlib.sha256(texts[0].encode()).hexdigest()})
nm=Path.home()/'.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin/arm-none-eabi-nm'
lines=subprocess.check_output([str(nm),'-S',str(a.artifact_dir/'build/kinder_fresh.elf')],text=True).splitlines();symbols={}
for line in lines:
 parts=line.split()
 if len(parts)==4:symbols[parts[3]]={'address':int(parts[0],16),'bytes':int(parts[1],16)}
 elif len(parts)==3:symbols[parts[2]]={'address':int(parts[0],16)}
start=symbols['__itcm_start']['address'];end=symbols['__itcm_end']['address'];assert start==0x01000000 and 0<end-start<=32768
functions={}
for name in ('draw_enemy_object','draw_live_object','scene_entity_update_region','player_graphics_draw','sound_events_mix'):
 matches={k:v for k,v in symbols.items() if k==name or k.startswith(name+'.')}
 assert matches,name+' absent'
 for k,v in matches.items():assert start<=v['address'] and v['address']+v['bytes']<=end,(k,v)
 functions.update(matches)
audio_buffers=('channels','mixed','sound_pool' if 'sound_pool' in symbols else 'sound_pages','sound_packet','sound_delta','sound_decoded')
for name in audio_buffers:
 assert 0x02000000<=symbols[name]['address']<symbols[name]['address']+symbols[name]['bytes']<=0x02400000,(name,symbols[name])
if 'sound_pool' in symbols:assert symbols['sound_pool']['bytes']%8192==0 and symbols['sound_pool']['bytes']>=19*8192
report={'scope':'Linked ARM9 ITCM placement; optional host token identity compares the selected source tree.','candidate_dir':str(candidate),'host_identity_checked':not a.placement_only,'host_sources':results,'itcm_start':hex(start),'itcm_used_bytes':end-start,'itcm_capacity_bytes':32768,'functions':functions,'audio_buffers_stay_in_main_ram':True,'limits':['Host token identity and linker bounds do not prove hardware speed or runtime cache behavior.','Boot and actual raster/audio checks are recorded by the separate emulator diagnostic.']}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
