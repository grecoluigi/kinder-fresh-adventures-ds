"""Raw RGB555 mode, tiny/large dimensions, alignment and invalid packet boundaries."""
from pathlib import Path
import subprocess,tempfile,json
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-raw-codec-')as td:
 t=Path(td);src=t/'test.c';src.write_text('#include "sprite_codec.h"\n'+r'''
#include <assert.h>
#include <stdio.h>
static uint8_t input[131084] __attribute__((aligned(4)));
static uint16_t output[65544] __attribute__((aligned(4)));
int main(void){unsigned valid=0,errors=0;
 for(unsigned n=1;n<=65536;n=n<65?n+1:n<4096?n+37:n<49152?49152:65536+!(n<65536))for(unsigned off=0;off<4;off++)for(unsigned align=0;align<2;align++){
  uint8_t *p=input+off;p[0]=16;p[1]=1;p[2]=p[3]=0;
  for(unsigned i=0;i<n*2;i++)p[4+i]=(uint8_t)(i*33u+n);
  for(unsigned i=0;i<65544;i++)output[i]=0x1234;
  uint16_t *dest=output+2+align;unsigned bytes=4+n*2;
  assert(sprite_codec_decode(p,bytes,dest,n));assert(!memcmp(dest,p+4,n*2));valid++;
  assert(!sprite_codec_decode(p,bytes-1,dest,n));errors++;
  assert(!sprite_codec_decode(p,bytes+1,dest,n));errors++;
  assert(!sprite_codec_decode(p,bytes,dest,n+1));errors++;
  assert(!sprite_codec_decode(p,bytes,dest,0));errors++;
  p[0]=8;assert(!sprite_codec_decode(p,bytes,dest,n));p[0]=16;errors++;
  p[2]=1;assert(!sprite_codec_decode(p,bytes,dest,n));p[2]=0;errors++;
  p[1]=2;assert(!sprite_codec_decode(p,bytes,dest,n));p[1]=1;errors++;
  for(unsigned i=0;i<2+align;i++)assert(output[i]==0x1234);
  for(unsigned i=2+align+n;i<65544;i++)assert(output[i]==0x1234);
 }
 assert(!sprite_codec_decode(NULL,8,output,2));assert(!sprite_codec_decode(input,8,NULL,2));
 for(unsigned bytes=0;bytes<4;bytes++)assert(!sprite_codec_decode(input,bytes,output,2));
 printf("{\"valid_cases\":%u,\"invalid_cases\":%u,\"guards_intact\":true}\n",valid,errors+6);
}
''')
 subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ds/source'),str(src),'-o',str(t/'test')],check=True)
 result=json.loads(subprocess.check_output([str(t/'test')],text=True));result['scope']=__doc__;(R/'research/rendering/raw-sprite-codec-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
