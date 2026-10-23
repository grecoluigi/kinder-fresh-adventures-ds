#!/usr/bin/env python3
"""Build hardware-playable sound assets from the adapted 22,050 Hz PCM.

samples.hw (KFH1): every effect/voice as one DS sample for ARM7 hardware
channels. Search-encoded IMA-ADPCM by default; a sound up to --pcm-seconds long
stays lossless PCM16 when its ADPCM SNR falls below --min-snr.
<track>.kfm (KFM1): music as independently decodable 2,048-frame ADPCM blocks,
decoded on the ARM9 into the existing PCM stream.

Inputs are the KFS1 pack with its sound_assets.inc table and the adapted WAVs.
"""
import argparse,ctypes as C,hashlib,json,math,re,struct,subprocess,tempfile,wave
from pathlib import Path
import numpy as np
from tile_storage import unlz
ROOT=Path(__file__).resolve().parents[1]
ENCODER=r'''
#include "adpcm_codec.h"
#include <stdlib.h>
#include <string.h>
typedef struct {int value,index;int64_t error;int parent;uint8_t nibble;} Node;
static int64_t sq(int x){return (int64_t)x*x;}
static unsigned greedy(int target,int value,int index){
 int difference=target-value,step=adpcm_steps[index];unsigned nibble=0;
 if(difference<0){nibble=8;difference=-difference;}
 if(difference>=step){nibble|=4;difference-=step;}
 if(difference>=(step>>1)){nibble|=2;difference-=step>>1;}
 if(difference>=(step>>2))nibble|=1;
 return nibble;
}
/* Beam search over nibble choices around the greedy choice. Exact hardware
 * predictor; returns encoded bytes (header + nibbles, padded to a word). */
size_t encode(const int16_t *input,unsigned n,uint8_t *out,size_t capacity,unsigned beam){
 size_t bytes=(4u+(n+1u)/2u+3u)&~3u;
 if(!input||!out||!n||capacity<bytes||!beam||beam>64)return 0;
 int initial=input[0]<-32767?-32767:input[0],best_index=0;int64_t best=INT64_MAX;
 for(int candidate=0;candidate<89;candidate++){
  int value=initial,index=candidate;int64_t error=0;
  for(unsigned i=1;i<n&&i<64;i++){adpcm_advance(greedy(input[i],value,index),&value,&index);error+=sq(value-input[i]);}
  if(error<best){best=error;best_index=candidate;}
 }
 Node *history=malloc(sizeof(Node)*(size_t)n*beam);Node current[64],next[64*8];unsigned count=1;
 if(!history)return 0;
 current[0]=(Node){initial,best_index,0,-1,0};
 /* Sample 0 is the header value; nibble i encodes sample i+1. */
 memset(out,0,bytes);
 for(unsigned i=1;i<n;i++){
  unsigned candidates=0;
  for(unsigned b=0;b<count;b++){
   unsigned g=greedy(input[i],current[b].value,current[b].index);
   unsigned options[8]={g,g^1u,(g&8u)|((g&7u)<7u?(g&7u)+1u:7u),(g&8u)|((g&7u)?(g&7u)-1u:0u),g^8u,(g&8u)|((g&7u)<6u?(g&7u)+2u:7u),(g&8u)|((g&7u)>1u?(g&7u)-2u:0u),g^2u};
   for(unsigned k=0;k<8;k++){
    int value=current[b].value,index=current[b].index;adpcm_advance(options[k],&value,&index);
    Node node={value,index,current[b].error+sq(value-input[i]),(int)b,(uint8_t)options[k]};
    bool merged=false;
    for(unsigned c=0;c<candidates;c++)if(next[c].value==value&&next[c].index==index){if(node.error<next[c].error)next[c]=node;merged=true;break;}
    if(!merged)next[candidates++]=node;
   }
  }
  /* Keep the lowest-error states. */
  for(unsigned a=0;a<candidates&&a<beam;a++){unsigned m=a;for(unsigned c=a+1;c<candidates;c++)if(next[c].error<next[m].error)m=c;Node t=next[a];next[a]=next[m];next[m]=t;}
  count=candidates<beam?candidates:beam;
  for(unsigned b=0;b<count;b++){history[(size_t)i*beam+b]=next[b];current[b]=next[b];current[b].parent=(int)b;}
 }
 /* Walk back the best path. */
 unsigned at=0;for(unsigned b=1;b<count;b++)if(current[b].error<current[at].error)at=b;
 for(unsigned i=n-1;i>=1;i--){Node node=history[(size_t)i*beam+at];unsigned slot=i-1u;out[4+slot/2]|=(uint8_t)(node.nibble<<((slot&1u)*4u));at=(unsigned)node.parent;}
 out[0]=(uint8_t)initial;out[1]=(uint8_t)((uint16_t)initial>>8);out[2]=(uint8_t)best_index;out[3]=0;
 free(history);return bytes;
}
/* Hardware decode: header sample followed by n-1 nibbles. */
int decode(const uint8_t *packet,size_t bytes,unsigned n,int16_t *out){
 if(!n||bytes<4u+n/2u)return 0;
 out[0]=(int16_t)((unsigned)packet[0]|(unsigned)packet[1]<<8);
 return n==1||adpcm_decode_block(packet,bytes,n-1,out+1);
}
'''
def kfs1_pcm(pack,offset,frames):
 at,left,result=offset,frames,bytearray()
 while left:
  n,flags=struct.unpack_from('<HH',pack,at);size=flags&32767;payload=pack[at+4:at+4+size]
  assert 0<n<=min(left,2048)
  if flags&32768:block=payload
  else:
   planes=unlz(payload);delta=np.frombuffer(planes[:n],'u1').astype(np.uint16)|(np.frombuffer(planes[n:2*n],'u1').astype(np.uint16)<<8)
   block=(np.cumsum(delta,dtype=np.uint64)&65535).astype('<u2').tobytes()
  result.extend(block);left-=n;at=(at+4+size+3)&~3
 return np.frombuffer(bytes(result),'<i2')
def snr(reference,decoded):
 noise=float(np.sum((reference.astype(np.float64)-decoded)**2));signal=float(np.sum(reference.astype(np.float64)**2))
 return 99.0 if noise==0 else (10*math.log10(signal/noise) if signal else -99.0)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--sounds-dir',type=Path,required=True,help='Directory with samples.pcm')
 p.add_argument('--table',type=Path,required=True,help='Matching sound_assets.inc')
 p.add_argument('--audio-dir',type=Path,required=True,help='Directory with adapted music WAVs')
 p.add_argument('--output',type=Path,required=True,help='New directory receiving sounds/ and audio/')
 p.add_argument('--beam',type=int,default=24);p.add_argument('--min-snr',type=float,default=20.0);p.add_argument('--pcm-seconds',type=float,default=4.0)
 p.add_argument('--codec-dir',type=Path,default=ROOT/'ds/source',help='Directory with the runtime adpcm_codec.h')
 a=p.parse_args()
 if a.output.exists():p.error('output directory must not exist')
 work=Path(tempfile.mkdtemp());(work/'encoder.c').write_text(ENCODER);lib=work/'encoder.dylib'
 subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I',str(a.codec_dir),str(work/'encoder.c'),'-o',str(lib)],check=True)
 codec=C.CDLL(str(lib));codec.encode.restype=C.c_size_t;codec.encode.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_size_t,C.c_uint];codec.decode.argtypes=[C.c_void_p,C.c_size_t,C.c_uint,C.c_void_p]
 def adpcm(samples):
  samples=np.ascontiguousarray(samples,dtype='<i2');n=len(samples);cap=(4+(n+1)//2+3)&~3;out=(C.c_uint8*cap)()
  size=codec.encode(samples.ctypes.data,n,out,cap,a.beam);assert size==cap
  decoded=np.zeros(n,'<i2');assert codec.decode(out,size,n,decoded.ctypes.data)
  return bytes(out),decoded
 pack=(a.sounds_dir/'samples.pcm').read_bytes();assert pack[:4]==b'KFS1'
 table=[tuple(int(x.rstrip('u'),0) for x in m) for m in re.findall(r'\{(0x[0-9a-f]+),(\d+)u,(\d+)u,(\d+)u\}',a.table.read_text())]
 entries=[];payload=bytearray();report={'scope':__doc__.strip().splitlines()[0],'beam':a.beam,'min_snr_db':a.min_snr,'pcm_seconds':a.pcm_seconds,'sounds':[],'music':[]}
 for va,_,frames,packed in table:
  pcm=kfs1_pcm(pack,packed,frames);assert len(pcm)==frames
  data,decoded=adpcm(pcm);quality=snr(pcm,decoded);fmt=2
  if quality<a.min_snr and frames<=a.pcm_seconds*22050:
   data=pcm.astype('<i2').tobytes()+(b'\0\0' if frames&1 else b'');fmt=0;quality=99.0
  payload.extend(bytes((-len(payload))%4));entries.append((va,frames,len(payload),len(data),fmt));payload.extend(data)
  report['sounds'].append({'va':hex(va),'seconds':round(frames/22050,3),'format':'pcm16' if fmt==0 else 'adpcm','bytes':len(data),'snr_db':round(quality,2)})
 head=16+20*len(entries)
 blob=bytearray(b'KFH1'+struct.pack('<III',len(entries),head,head+len(payload)))
 for va,frames,offset,size,fmt in entries:blob+=struct.pack('<IIIIB3x',va,frames,head+offset,size,fmt)
 blob+=payload;(a.output/'sounds').mkdir(parents=True);(a.output/'sounds/samples.hw').write_bytes(blob)
 (a.output/'audio').mkdir()
 for wav in sorted(a.audio_dir.glob('*.wav')):
  with wave.open(str(wav))as w:
   assert w.getnchannels()==1 and w.getsampwidth()==2 and w.getframerate()==22050
   pcm=np.frombuffer(w.readframes(w.getnframes()),'<i2')
  blocks=bytearray();decoded_all=[]
  for start in range(0,len(pcm),2048):
   block=pcm[start:start+2048];data,decoded=adpcm(block)
   data=data+bytes(1028-len(data));blocks+=data;decoded_all.append(decoded)
  out=b'KFM1'+struct.pack('<III',len(pcm),22050,(len(pcm)+2047)//2048)+bytes(blocks)
  (a.output/'audio'/(wav.stem+'.kfm')).write_bytes(out)
  report['music'].append({'track':wav.stem,'seconds':round(len(pcm)/22050,2),'bytes':len(out),'wav_bytes':wav.stat().st_size,'snr_db':round(snr(pcm,np.concatenate(decoded_all)),2)})
 report['samples_hw_bytes']=len(blob);report['samples_hw_sha256']=hashlib.sha256(blob).hexdigest()
 counts={f:sum(s['format']==f for s in report['sounds']) for f in ('pcm16','adpcm')};report['format_counts']=counts
 (a.output/'sound-hw-report.json').write_text(json.dumps(report,indent=1)+'\n')
 low=sorted(report['sounds'],key=lambda s:s['snr_db'])[:5]
 print(json.dumps({'samples_hw_bytes':len(blob),'formats':counts,'lowest_snr':low,'music':report['music']},indent=1))
if __name__=='__main__':main()
