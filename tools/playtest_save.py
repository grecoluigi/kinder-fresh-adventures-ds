"""Two-boot save integration test on a private256MiB DLDI card image.

Name bytes and result state are supplied in debugger RAM. The production UI
confirmation writes the save. A second process must reload every payload byte.
The test never opens the user's card image or save files.
"""
from rom_artifact import rom_path
import argparse,hashlib,json,os,shutil,struct,subprocess,sys,time,zlib
from pathlib import Path
from emulator_output import BoundedOutput
from playtest import ROOT,CONFIG,EMU,processes,section_option,write_config
from test_fat_image import create,files,root_names

def only_save_files(image):
 # Release builds must keep everything in the raw .sav: no legacy folder or files.
 names=root_names(image);extra=[n for n in names if not n.lower().endswith(('.sav','.nds'))]
 assert not extra,('Unexpected card root entries',names)
 return names
def archive(image):
 only_save_files(image)
 entries=files(image);matching=[(name,data)for name,data in entries.items()if name.lower().endswith('.sav')]
 assert len(matching)==1,('Expected one save file',list(entries))
 name,data=matching[0];assert len(data)==8192,('Save file length',name,len(data))
 valid=[]
 for slot in range(2):
  block=data[slot*4096:(slot+1)*4096];magic=block[:8]
  sequence,size,crc=struct.unpack_from('<III',block,8)
  if magic!=b'KFDSAV\x01\0' or size!=1692:continue
  payload=block[20:20+size]
  if crc!=(zlib.crc32(block[8:16])^zlib.crc32(payload)):continue
  valid.append((sequence,payload,slot))
 assert valid,'No valid checksummed save records'
 # Test creates only a few records; wraparound ordering is covered by host tests.
 sequence,payload,slot=max(valid)
 return {'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'valid_slots':[{'slot':i,'sequence':n}for n,_,i in valid],'latest_sequence':sequence},payload

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifact-dir',type=Path,default=ROOT/'ds');p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--empty-save',action='store_true',help='Seed a zero-byte loader placeholder before boot');a=p.parse_args()
 if processes():raise RuntimeError('melonDS already running; will not interrupt it')
 if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('Less than1GiB free')
 artifact=a.artifact_dir.resolve();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
 image=out/'test-card.img';create(image,empty_save=a.empty_save);original=CONFIG.read_text();rom_sha=hashlib.sha256((rom_path(artifact)).read_bytes()).hexdigest()
 report={'scope':__doc__,'rom_sha256':rom_sha,'physical_DSpico_verified':False,'boots':[],'seeded_empty_save':a.empty_save}
 def boot(name,script,args):
  assert hashlib.sha256((rom_path(artifact)).read_bytes()).hexdigest()==rom_sha
  config=section_option(original,'Instance0.Gdb','Enabled','true')
  for key,value in {'Enable':'true','ReadOnly':'false','FolderSync':'false','FolderPath':'""','ImageSize':'0','ImagePath':json.dumps(str(image))}.items():config=section_option(config,'DLDI',key,value)
  write_config(config)
  with BoundedOutput([str(EMU),'-b','always',str(rom_path(artifact))])as native:
   proc=native.process
   try:
    deadline=time.monotonic()+20
    while str(proc.pid)not in subprocess.run(['lsof','-nP','-iTCP:3333','-sTCP:LISTEN'],capture_output=True,text=True).stdout:
     if proc.poll()is not None or time.monotonic()>deadline:raise RuntimeError('Save-test debugger listener failed')
     time.sleep(.2)
    with(out/(name+'.runner.log')).open('w')as log:
     subprocess.run([sys.executable,str(ROOT/'tools'/script),*args],stdout=log,stderr=subprocess.STDOUT,timeout=150,check=True,env={**os.environ,'KF_DS_ARTIFACT_DIR':str(artifact)})
   finally:
    if proc.poll()is None:proc.terminate()
    try:proc.wait(timeout=20)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=10)
    native.save(out/(name+'.emulator-tail.log'))
  assert not processes(),'Emulator remained running'
  report['boots'].append(name)
 try:
  boot('write','emulator_bottom_surfaces.py',['--output',str(out/'write-ui.json')])
  first,payload=archive(image);assert payload[:30].startswith(b'DS TEST'),'Confirmed score absent on card'
  (out/'expected-state.bin').write_bytes(payload);report['first_boot_save']=first
  boot('reload','emulator_save_reload.py',['--expected',str(out/'expected-state.bin'),'--output',str(out/'reload.json')])
  second,restored=archive(image);assert restored==payload and second['latest_sequence']>first['latest_sequence']
  report['second_boot_save']=second;report['reload']=json.loads((out/'reload.json').read_text());report['success']=True
 finally:
  write_config(section_option(original,'Instance0.Gdb','Enabled','false'));report['emulator_closed']=not processes();report['private_card_image_removed']=False
  if report['emulator_closed']and report.get('success'):
   image.unlink(missing_ok=True);report['private_card_image_removed']=True
  (out/'run.json').write_text(json.dumps(report,indent=2)+'\n')
  if not report['emulator_closed']:raise RuntimeError('Save-test emulator remains running')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
