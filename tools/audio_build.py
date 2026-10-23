#!/usr/bin/env python3
"""Build DS music streams from original PCM WAV; no music is embedded in ARM9 RAM.
Requires numpy/scipy; reads only the supplied extracted WAV directory.
"""
from pathlib import Path
import argparse,hashlib,json,wave
import numpy as np
from scipy.signal import resample_poly
TRACKS=['Start','Dschungel','Eis','Fabrik','Phantasie','endgegner']
def build(source_dir,out,rate=22050,bits=16):
 out.mkdir(parents=True,exist_ok=False);rows=[]
 for name in TRACKS:
  source=source_dir/f'{name}.wav'
  raw=source.read_bytes()
  with wave.open(str(source)) as w:
   channels,width,hz,count=w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes()
   assert w.getcomptype()=='NONE' and width in (1,2)
   samples=np.frombuffer(w.readframes(count),dtype='<i2' if width==2 else 'u1').astype(np.float64)
   if width==1:samples=(samples-128)*256
   samples=samples.reshape(-1,channels).mean(axis=1)
   # Original music44100 ->22050 or11025. Polyphase FIR prevents aliasing.
   assert hz%rate==0
   samples=resample_poly(samples,1,hz//rate,padtype='constant')
   samples=np.clip(np.rint(samples),-32768,32767).astype('<i2')
   payload=samples.tobytes() if bits==16 else np.clip(np.rint(samples.astype(np.float64)/256)+128,0,255).astype('u1').tobytes()
  dest=out/f'{name}.wav'
  with wave.open(str(dest),'wb') as w:
   w.setnchannels(1);w.setsampwidth(bits//8);w.setframerate(rate);w.writeframes(payload)
  with wave.open(str(dest)) as w:assert w.getnframes()==len(samples) and w.getframerate()==rate
  rows.append(dict(track=name,source=str(source.resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),original_rate=hz,original_channels=channels,original_bits=width*8,original_frames=count,path=dest.name,rate=rate,channels=1,bits=bits,frames=len(samples),duration=len(samples)/rate,bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
 (out/'manifest.json').write_text(json.dumps(dict(method='Channel mean; scipy.signal.resample_poly FIR; nearest integer with clipping',tracks=rows),indent=2)+'\n')
 print(json.dumps(rows,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--rate',type=int,choices=[11025,22050],default=22050);p.add_argument('--bits',type=int,choices=[8,16],default=16);a=p.parse_args();build(a.source,a.output,a.rate,a.bits)
