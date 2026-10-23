"""Compare DS projection to its original64-bit definition over signed32-bit inputs."""
from pathlib import Path
import json,re,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-projection-') as td:
 t=Path(td);src=t/'check.c';exe=t/'check'
 src.write_text(r'''
#include "ds_projection.h"
#include "texture_window.h"
#include <assert.h>
#include <stdio.h>
#include <limits.h>
#include <string.h>
static int reference(int n){int64_t q=(int64_t)n*8+12;return (int)(q>=0?q/25:-((-q+24)/25));}
int main(void){
 unsigned cases=0;uint32_t random=2001;
 for(int n=-1000000;n<=1000000;n++){assert(ds_world_pixel(n)==reference(n));cases++;}
 for(unsigned i=0;i<2000000;i++){random=random*1664525u+1013904223u;int n=(int32_t)random;assert(ds_world_pixel(n)==reference(n));cases++;}
 for(int i=0;i<1000;i++){assert(ds_world_pixel(INT_MIN+i)==reference(INT_MIN+i));assert(ds_world_pixel(INT_MAX-i)==reference(INT_MAX-i));cases+=2;}
 uint16_t source[1028],dest[1028],expected[1028];unsigned copies=0;
 for(unsigned i=0;i<1028;i++)source[i]=(uint16_t)(i*1531);
 for(unsigned sa=0;sa<2;sa++)for(unsigned da=0;da<2;da++)for(unsigned n=0;n<=1024;n++){
  memset(dest,0x12,sizeof(dest));memcpy(expected,dest,sizeof(dest));memcpy(expected+da,source+sa,n*2);
  texture_copy_rgb555(dest+da,source+sa,n);assert(!memcmp(dest,expected,sizeof(dest)));copies++;
 }
 printf("{\"projection_cases\":%u,\"copy_alignment_and_length_cases\":%u,\"exact\":true}\n",cases,copies);
}
''')
 subprocess.run(['cc','-O2','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ds/source'),str(src),'-o',str(exe)],check=True)
 result=json.loads(subprocess.check_output([str(exe)],text=True));result['scope']=__doc__
 # Check the shipped ARM946E-S compiler, rather than assuming that equivalent
 # source arithmetic reduces instructions on this architecture. GCC16 already
 # inlines the old division: it is a longer sequence, not a runtime-helper call.
 arm=Path.home()/'.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin/arm-none-eabi-gcc'
 assembly={}
 for name,body in [('previous','int64_t q=(int64_t)n*8+12;return (int)(q>=0?q/25:-((-q+24)/25));'),('current','return ds_world_pixel(n);')]:
  unit=t/(name+'.c');out=t/(name+'.s')
  unit.write_text('#include "ds_projection.h"\nint project(int n){'+body+'}\n')
  subprocess.run([str(arm),'-mcpu=arm946e-s','-marm','-O2','-S','-I'+str(R/'ds/source'),str(unit),'-o',str(out)],check=True)
  assembly[name]=out.read_text()
 counts={name:len(re.findall(r'^\t[a-z][a-z0-9]*\t',code,re.M))for name,code in assembly.items()}
 assert counts['current']<counts['previous']
 assert '__aeabi_ldivmod' not in assembly['current']
 result['ARM946ES_emitted_instruction_counts']=counts
 (R/'research/rendering/projection-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
