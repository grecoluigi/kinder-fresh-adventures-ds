"""Check a second boot's complete save state against independently read card data."""
import argparse,hashlib,json,struct,time
from pathlib import Path
from emulator_counters import RSP,symbols,module_bss_symbol

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s=symbols();r=RSP(3333)
 try:
  r.resume();deadline=time.monotonic()+30
  while struct.unpack('<I',r.read(s['storage_status'],4))[0]!=1:
   assert time.monotonic()<deadline,'save initialization failed';time.sleep(.2)
  loaded=struct.unpack('<I',r.read(module_bss_symbol('game_save','loaded'),4))[0];assert loaded==63
  expected=a.expected.read_bytes();assert len(expected)==1692
  actual=r.read(module_bss_symbol('game_save','state'),len(expected));assert actual==expected,'Reloaded state differs from saved payload'
  assert actual[:30].startswith(b'DS TEST'),'Confirmed name was not reloaded'
  path=r.read(s['archive_path'],256).split(b'\0')[0].decode()
  report={'scope':__doc__,'loaded_mask':loaded,'state_bytes_exact':len(expected),'state_sha256':hashlib.sha256(actual).hexdigest(),'save_path':path,'top_name':actual[:30].split(b'\0')[0].decode(),'physical_DSpico_verified':False}
 finally:r.sock.close()
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
