#!/usr/bin/env python3
"""Recover WAV references and world sound bindings; convert original PCM to22050mono16."""
from pathlib import Path
import argparse,re,json,wave,hashlib,struct,math
import pefile,numpy as np
from scipy.signal import resample_poly
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX,UC_X86_REG_EBX
def build(game,out):
 image=pefile.PE(str(game/'JR_FERRERO.exe')).get_memory_mapped_image()
 refs={0x400000+m.start():m.group()[:-1].decode('ascii') for m in re.finditer(rb'GData\\SDat\\[^\x00\r\n]+\.wav\x00',image)}
 files={str(p.relative_to(game)).lower():p for p in (game/'GData/SDat').rglob('*') if p.is_file()}
 out.mkdir(parents=True,exist_ok=False);rows=[];payload=bytearray()
 for va,path in sorted(refs.items()):
  if path.lower().split('\\')[-1] in ['start.wav','dschungel.wav','eis.wav','fabrik.wav','phantasie.wav','endgegner.wav']:continue
  source=files[path.replace('\\','/').lower()]
  with wave.open(str(source)) as w:
   ch,sw,hz,n=w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes();assert sw in [1,2] and w.getcomptype()=='NONE'
   a=np.frombuffer(w.readframes(n),dtype='<i2' if sw==2 else 'u1').astype(float)
   if sw==1:a=(a-128)*256
   a=a.reshape(-1,ch).mean(axis=1);g=math.gcd(hz,22050)
   a=np.clip(np.rint(resample_poly(a,22050//g,hz//g)), -32768,32767).astype('<i2')
  rows.append(dict(va=va,path=path,offset=len(payload),frames=len(a),source_rate=hz,source_frames=n,source_channels=ch,source_bits=sw*8,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),pcm_sha256=hashlib.sha256(a.tobytes()).hexdigest()))
  payload.extend(a.tobytes())
 # Execute actual native world sound initialization; intercept only native file loader.
 mappings=[]
 for world in range(8):
  u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image);u.mem_map(0x200000,4096)
  calls=[]
  def hook(_,at,size,data):
   if at!=0x422552:return
   sp=u.reg_read(UC_X86_REG_ESP);ret,va=struct.unpack('<II',bytes(u.mem_read(sp,8)))
   calls.append(va);u.reg_write(UC_X86_REG_EAX,len(calls));u.reg_write(UC_X86_REG_ESP,sp+8);u.reg_write(UC_X86_REG_EIP,ret)
  u.hook_add(UC_HOOK_CODE,hook);u.mem_write(0x4dabd4,struct.pack('<I',world));u.reg_write(UC_X86_REG_ESP,0x200800);u.reg_write(UC_X86_REG_EBX,0)
  u.emu_start(0x412000,0x4123ed,count=5000);assert u.reg_read(UC_X86_REG_EIP)==0x4123ed
  # Native sound globals are signed16 handles, all in these disjoint ranges.
  mapping={}
  for lo,hi in [(0x4dab58,0x4dab64),(0x4dabcc,0x4dabce),(0x4dac3c,0x4dac76),(0x4dbc68,0x4dbc70),(0x4e0a90,0x4e0ab8),(0x4e0afc,0x4e0b1a)]:
   for addr in range(lo,hi,2):
    handle=struct.unpack('<H',bytes(u.mem_read(addr,2)))[0]
    if 0<handle<=len(calls):mapping[addr]=calls[handle-1]
  mappings.append(mapping)
 from sound_pack import pack_samples
 pack,rows,stats=pack_samples(rows,bytes(payload))
 header=['/* Generated from original WAV Cstrings and native412000..4123ed. */','typedef struct { unsigned va,offset,frames,packed_offset; } SoundAsset;','static const SoundAsset sound_assets[]={']
 header += [f'{{0x{r["va"]:x},{r["offset"]}u,{r["frames"]}u,{r["packed_offset"]}u}},' for r in rows];header+=['};','typedef struct { unsigned world,address,va; } SoundBinding;','static const SoundBinding sound_bindings[]={']
 header += [f'{{{world},0x{addr:x},0x{va:x}}},' for world,m in enumerate(mappings) for addr,va in sorted(m.items())];header+=['};']
 (out/'sound_assets.inc').write_text('\n'.join(header)+'\n')
 (out/'samples.pcm').write_bytes(pack)
 result=dict(method='Original WAV Cstring VAs; bounded original x86 initialization with only422552 mocked; polyphase22050Hz mono16; independent KFS1 blocks',assets=rows,world_bindings=[{hex(a):hex(v) for a,v in m.items()} for m in mappings],pack_bytes=len(pack),pack_sha256=hashlib.sha256(pack).hexdigest(),**stats)
 (out/'effects-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(assets=len(rows),bindings=sum(map(len,mappings)),pack_bytes=len(pack),**stats)),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True,help='Extracted game directory containing JR_FERRERO.exe and GData');p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.source,a.output)
