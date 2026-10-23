"""Pair RGB555 row copies vs scalar pixels: alpha patterns, alignment and exact ends."""
from pathlib import Path
import subprocess,tempfile,json
R=Path(__file__).resolve().parents[1]
import argparse,hashlib
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--header',type=Path,default=R/'research/rendering/rgb555_blit_aligned_pair_experiment.h');args=parser.parse_args();header=args.header.resolve()
with tempfile.TemporaryDirectory(prefix='kinder-pair-blit-')as td:
 t=Path(td);src=t/'check.c';src.write_text('#include "'+str(header)+'"\n'+r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static unsigned cases;static uint32_t seed=2001;
static uint16_t random_color(void){seed=seed*1664525u+1013904223u;return (uint16_t)(seed>>16);}
static void check(unsigned count,unsigned sp,unsigned dp,unsigned mode,unsigned mask,bool exact){
 unsigned prefix=16,extra=exact?0:16;
 unsigned ns=prefix+sp+count+extra,nd=prefix+dp+count+extra;
 uint16_t *s=malloc(ns*2u),*d=malloc(nd*2u),*expected=malloc(nd*2u),*before=malloc(ns*2u);assert(s&&d&&expected&&before);
 for(unsigned i=0;i<ns;i++)s[i]=0x2345;
 for(unsigned i=0;i<nd;i++)d[i]=random_color();
 uint16_t *source=s+prefix+sp,*dest=d+prefix+dp;
 for(unsigned i=0;i<count;i++){
  uint16_t color=random_color();unsigned opaque=mode==0?0:mode==1?1:mode==2?(mask>>(i&15u))&1u:(color>>15);
  source[i]=(uint16_t)((color&32767u)|(opaque<<15));
 }
 memcpy(expected,d,nd*2u);memcpy(before,s,ns*2u);
 for(unsigned i=0;i<count;i++)if(source[i]&0x8000u)expected[prefix+dp+i]=source[i];
 rgb555_blit_masked(dest,source,count);assert(!memcmp(d,expected,nd*2u)&&!memcmp(s,before,ns*2u));
 free(s);free(d);free(expected);free(before);cases++;
}
int main(void){
 rgb555_blit_masked(NULL,NULL,0);
 for(unsigned mask=0;mask<65536;mask++)for(unsigned sp=0;sp<2;sp++)for(unsigned dp=0;dp<2;dp++)check(16,sp,dp,2,mask,false);
 unsigned sizes[]={0,1,2,3,4,5,7,8,15,16,17,31,32,33,63,64,65,127,128,129,255,256,257,799,800};
 for(unsigned n=0;n<sizeof(sizes)/sizeof(*sizes);n++)for(unsigned sp=0;sp<2;sp++)for(unsigned dp=0;dp<2;dp++)for(unsigned mode=0;mode<4;mode++)check(sizes[n],sp,dp,mode,0x5555,true);
 printf("{\"row_cases\":%u,\"binary_alpha_patterns\":65536,\"pointer_phases\":4,\"source_unchanged\":true,\"exact_allocation_ends\":true,\"zero_count_null\":true}\n",cases);return 0;
}
''')
 results={}
 for name,flags in [('paired',[]),('scalar',['-DRGB555_SCALAR_BLIT'])]:
  exe=t/name;subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',*flags,str(src),'-o',str(exe)],check=True);results[name]=json.loads(subprocess.check_output([str(exe)],text=True))
 assert results['paired']==results['scalar']
 report=dict(scope=__doc__,header=str(header),header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),variants=results,sanitizers=['address','undefined'],limits=['Row copy equivalence only; original assets, production world paths and DS timings have separate checks.'])
 (R/'research/rendering/rgb555-pair-blit-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
