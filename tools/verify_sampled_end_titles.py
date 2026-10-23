"""Sanitizer-check horizontally sampled ending storage against the original routine."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include "end_titles.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
bool reference_end_title_draw(const EndTitle *,uint16_t *);
void reference_end_title_close(void);
static size_t used,peak;
void *title_malloc(size_t n){size_t *p=malloc(n+sizeof(size_t));assert(p);*p=n;used+=n;if(used>peak)peak=used;return p+1;}
void title_free(void *p){if(!p)return;size_t *h=(size_t *)p-1;used-=*h;free(h);}
static struct {uint32_t before[4];uint16_t pixels[49152];uint32_t after[4];} original,sampled;
static unsigned cases;
static void check(const EndTitle *title){
 for(unsigned i=0;i<4;i++)original.before[i]=original.after[i]=sampled.before[i]=sampled.after[i]=0x12345678u;
 for(unsigned i=0;i<49152;i++)original.pixels[i]=sampled.pixels[i]=(uint16_t)(0x8000u|(i&32767u));
 assert(reference_end_title_draw(title,original.pixels)&&end_title_draw(title,sampled.pixels));
 assert(!memcmp(original.pixels,sampled.pixels,sizeof(original.pixels)));
 for(unsigned i=0;i<4;i++)assert(original.before[i]==0x12345678u&&original.after[i]==0x12345678u&&sampled.before[i]==0x12345678u&&sampled.after[i]==0x12345678u);
 assert(used<=135u*51u*2u);cases++;
}
int main(void){
 for(unsigned frame=0;frame<2;frame++){
  for(int x=-450;x<=900;x+=17)for(int y=-90;y<=680;y+=13){EndTitle title={100,(int)frame,x+0.375f,y+0.625f,0};check(&title);}
  end_title_close();reference_end_title_close();assert(!used);
  EndTitle title={(int)frame+1,0,0,0,0};end_title_tick(&title);
  for(unsigned tick=0;tick<500;tick++){end_title_tick(&title);check(&title);}
  end_title_close();reference_end_title_close();assert(!used);
 }
 assert(peak==135u*51u*2u);
 printf("{\"cases\":%u,\"pixels_exact\":%u,\"retained_bytes\":%zu,\"previous_retained_bytes\":%u}\n",cases,cases*49152u,peak,418u*51u*2u);return 0;
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();candidate=args.source.resolve()
 with tempfile.TemporaryDirectory(prefix='kinder-sampled-title-')as directory:
  work=Path(directory);reference=work/'reference.o';new=work/'sampled.o';test=work/'test.c';test.write_text(C);exe=work/'test'
  flags=['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'ds/source'),'-DEND_TITLE_ROOT="'+str(ROOT/'ds/nitrofs/end_titles')+'"']
  subprocess.run([*flags,'-Dend_title_draw=reference_end_title_draw','-Dend_title_tick=reference_end_title_tick','-Dend_title_close=reference_end_title_close','-c',str(ROOT/'ds/source/end_titles.c'),'-o',str(reference)],check=True)
  subprocess.run([*flags,'-Dmalloc=title_malloc','-Dfree=title_free','-c',str(candidate),'-o',str(new)],check=True)
  subprocess.run([*flags,str(test),str(reference),str(new),'-o',str(exe)],check=True)
  result=subprocess.run([str(exe)],capture_output=True,text=True)
  if result.returncode:print(result.stderr);raise RuntimeError('Sampled title verification failed')
  metrics=json.loads(result.stdout)
 report=dict(scope=__doc__,metrics=metrics,asan_ubsan=True,colors_alpha_and_clipping_exact=True,source_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),reference_sha256=hashlib.sha256((ROOT/'ds/source/end_titles.c').read_bytes()).hexdigest(),limits=['Host CPU draw and bounce checks; actual GPU transient uploads are checked in the full emulator harness.'])
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(metrics))
if __name__=='__main__':main()
