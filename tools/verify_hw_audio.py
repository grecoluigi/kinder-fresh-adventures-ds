#!/usr/bin/env python3
"""Verify hardware-playable audio assets and the ARM9 sound slot logic on the host.

Checks the KFH1 pack against the KFS1 source PCM (PCM16 exact, ADPCM decoded
with the runtime codec and measured by SNR), exercises sound_events.c with a
deterministic host clock (one-shots, finite/infinite repeats, stop, volume,
cache eviction under a small cache, malformed packs) under ASan/UBSan, and
decodes every KFM1 music block with the runtime codec against the adapted WAV.
Hardware channel output itself is not observable here.
"""
import argparse,json,math,re,shutil,struct,subprocess,tempfile,wave
from pathlib import Path
import numpy as np
from sound_hw_build import kfs1_pcm
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "sound_events.h"
#include "adpcm_codec.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void advance(unsigned frames){static int16_t pcm[4096];while(frames){unsigned n=frames>4096?4096:frames;sound_events_mix(pcm,n,127);frames-=n;}}
int main(int argc,char **argv){
 if(argc>1&&!strcmp(argv[1],"decode")){
  /* decode <file> <offset> <bytes> <frames> <out.raw>: runtime codec, header sample first. */
  FILE *f=fopen(argv[2],"rb");long offset=atol(argv[3]);size_t bytes=(size_t)atol(argv[4]);unsigned frames=(unsigned)atol(argv[5]);
  uint8_t *data=malloc(bytes);int16_t *out=malloc(frames*2u);assert(f&&data&&out&&!fseek(f,offset,SEEK_SET)&&fread(data,1,bytes,f)==bytes);
  out[0]=(int16_t)(data[0]|data[1]<<8);assert(frames==1||adpcm_decode_block(data,bytes,frames-1,out+1));
  FILE *o=fopen(argv[6],"wb");fwrite(out,2,frames,o);fclose(o);fclose(f);return 0;
 }
 if(argc>1&&!strcmp(argv[1],"music")){
  FILE *f=fopen(argv[2],"rb");uint8_t h[16],packet[1028];int16_t block[2048];assert(f&&fread(h,1,16,f)==16&&!memcmp(h,"KFM1",4));
  unsigned frames=h[4]|h[5]<<8|h[6]<<16|(unsigned)h[7]<<24,blocks=h[12]|h[13]<<8|h[14]<<16|(unsigned)h[15]<<24;
  FILE *o=fopen(argv[3],"wb");
  for(unsigned b=0;b<blocks;b++){unsigned n=frames-b*2048u;if(n>2048)n=2048;assert(fread(packet,1,1028,f)==1028);
   block[0]=(int16_t)(packet[0]|packet[1]<<8);assert(n==1||adpcm_decode_block(packet,1028,n-1,block+1));fwrite(block,2,n,o);}
  assert(fgetc(f)==EOF);fclose(o);fclose(f);return 0;
 }
 if(argc>1&&!strcmp(argv[1],"bad")){/* A malformed pack must refuse every play. */
  assert(!sound_play(1,1,0));assert(!sound_channel_active(1));puts("{\"rejected\":true}");return 0;}
 unsigned short_key=(unsigned)atoi(argv[1]),long_key=(unsigned)atoi(argv[2]),short_frames=(unsigned)atoi(argv[3]),long_frames=(unsigned)atoi(argv[4]);
 unsigned checks=0;
 assert(sound_play(0,short_key,0)&&sound_channel_active(0));advance(short_frames-1);assert(sound_channel_active(0));advance(1);assert(!sound_channel_active(0));checks+=4;
 assert(sound_play(1,short_key,2));advance(short_frames*3-1);assert(sound_channel_active(1));advance(1);assert(!sound_channel_active(1));checks+=3;
 assert(sound_play(2,short_key,255));advance(short_frames*50);assert(sound_channel_active(2));sound_channel_volume(2,-100);sound_channel_volume(2,-3);
 sound_channel_stop(2);assert(!sound_channel_active(2));checks+=3;
 assert(!sound_play(16,short_key,0)&&!sound_play(19,short_key,0)&&!sound_play(0,99999,0));checks+=3;
 /* Small-cache build: a long sample evicts idle ones but never a playing one. */
 assert(sound_play(3,long_key,0));
 bool second=sound_play(4,long_key==1?2:1,0);(void)second;
 assert(sound_channel_active(3));advance(long_frames);assert(!sound_channel_active(3));checks+=3;
 sound_events_stop();for(unsigned i=0;i<19;i++)assert(!sound_channel_active(i));checks++;
 printf("{\"semantic_checks\":%u,\"dropped\":%u}\n",checks,(unsigned)sound_effect_underruns());return 0;
}
'''
def snr(a,b):
 n=float(np.sum((a.astype(np.float64)-b)**2));s=float(np.sum(a.astype(np.float64)**2))
 return 99.0 if n==0 else 10*math.log10(s/n)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source-dir',type=Path,default=ROOT/'ds/source');p.add_argument('--nitrofs',type=Path,default=ROOT/'ds/nitrofs')
 p.add_argument('--reference-sounds',type=Path,required=True,help='Directory with the KFS1 samples.pcm used to build the pack')
 p.add_argument('--reference-audio',type=Path,required=True,help='Directory with the adapted music WAVs');p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();src=a.source_dir;work=Path(tempfile.mkdtemp());pack=a.nitrofs/'sounds/samples.hw'
 (work/'harness.c').write_text(HARNESS)
 def build(name,pack_path,cache):
  exe=work/name
  subprocess.run(['cc','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Wall','-Wextra','-Werror','-I',str(src),f'-DSOUND_PACK="{pack_path}"',f'-DSOUND_CACHE_BYTES={cache}u',str(work/'harness.c'),str(src/'sound_events.c'),'-o',str(exe)],check=True)
  return exe
 table=[tuple(int(x.rstrip('u'),0) for x in m) for m in re.findall(r'\{(0x[0-9a-f]+),(\d+)u,(\d+)u,(\d+)u\}',(src/'sound_assets.inc').read_text())]
 blob=pack.read_bytes();count=struct.unpack_from('<I',blob,4)[0];assert blob[:4]==b'KFH1' and count==len(table)
 reference=(a.reference_sounds/'samples.pcm').read_bytes();exe=build('full',pack,384*1024);results=[]
 for i,(va,_,frames,packed) in enumerate(table):
  eva,eframes,offset,size,fmt=struct.unpack_from('<IIIIB',blob,16+20*i);assert (eva,eframes)==(va,frames)
  original=kfs1_pcm(reference,packed,frames)
  if fmt==0:
   decoded=np.frombuffer(blob[offset:offset+frames*2],'<i2');assert np.array_equal(decoded,original)
  else:
   raw=work/'d.raw';subprocess.run([str(exe),'decode',str(pack),str(offset),str(size),str(frames),str(raw)],check=True);decoded=np.fromfile(raw,'<i2')
  results.append({'va':hex(va),'format':'pcm16' if fmt==0 else 'adpcm','snr_db':round(snr(original,decoded),2)})
 shorts=[(i+1,f) for i,(va,_,f,_) in enumerate(table) if f<22050 and struct.unpack_from('<B',blob,16+20*i+16)[0]==2]
 longest=max(range(len(table)),key=lambda i:table[i][2])
 small=build('small',pack,struct.unpack_from('<I',blob,16+20*longest+12)[0]+4096)
 run=subprocess.run([str(small),str(shorts[0][0]),str(longest+1),str(shorts[0][1]),str(table[longest][2])],capture_output=True,text=True)
 if run.returncode:raise SystemExit(run.stdout+run.stderr)
 semantics=json.loads(run.stdout)
 bad_cases=[]
 for label,mutate in (('magic',lambda b:b'KFX1'+b[4:]),('count',lambda b:b[:4]+struct.pack('<I',count+1)+b[8:]),('format',lambda b:b[:16+16]+b'\x05'+b[16+17:]),('truncated',lambda b:b[:40])):
  path=work/f'bad-{label}.hw';path.write_bytes(mutate(blob));exe_bad=build('bad-'+label,path,65536)
  r=subprocess.run([str(exe_bad),'bad'],capture_output=True,text=True);assert r.returncode==0,(label,r.stderr);bad_cases.append(label)
 music=[]
 for kfm in sorted((a.nitrofs/'audio').glob('*.kfm')):
  raw=work/'m.raw';subprocess.run([str(exe),'music',str(kfm),str(raw)],check=True);decoded=np.fromfile(raw,'<i2')
  with wave.open(str(a.reference_audio/(kfm.stem+'.wav')))as w:original=np.frombuffer(w.readframes(w.getnframes()),'<i2')
  assert len(decoded)==len(original);music.append({'track':kfm.stem,'frames':len(decoded),'snr_db':round(snr(original,decoded),2)})
 adpcm=[r['snr_db'] for r in results if r['format']=='adpcm']
 report={'scope':__doc__.strip().splitlines()[0],'assets':len(results),'pcm16_exact':sum(r['format']=='pcm16' for r in results),
  'adpcm_snr_min_db':min(adpcm),'adpcm_snr_median_db':float(np.median(adpcm)),'semantics':semantics,'malformed_packs_rejected':bad_cases,
  'music':music,'sanitizers':['address','undefined'],'sounds':results,'limits':['No hardware channel output or listening test.']}
 a.output.write_text(json.dumps(report,indent=1)+'\n');shutil.rmtree(work)
 print(json.dumps({k:v for k,v in report.items() if k!='sounds'}))
if __name__=='__main__':main()
