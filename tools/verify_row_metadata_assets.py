"""Independently check staged KFC5 records against the production pixel decoder.
The runtime also accepts legacy KFC4 as a fallback.
"""
from pathlib import Path
import json,struct,subprocess,tempfile
R=Path(__file__).resolve().parents[1];old=R/'generated/ds-raw/composite';new=R/'generated/ds-row-metadata/composite';paths=sorted(new.glob('*.atlas'));tiles=0
for p in paths:
 a=(old/p.name).read_bytes();b=p.read_bytes();assert a[:4]==b'KFC4' and b[:4]==b'KFC5'
 assert b==(R/'ds/nitrofs/composite'/p.name).read_bytes()
 n=struct.unpack_from('<I',a,4)[0];base=8+n*8;assert len(a)==len(b) and a[4:8]==b[4:8] and a[base:]==b[base:]
 assert (old/p.with_suffix('.index').name).read_bytes()==p.with_suffix('.index').read_bytes()
 for i in range(n):
  off,size=struct.unpack_from('<II',a,8+i*8);x,y=struct.unpack_from('<II',b,8+i*8)
  assert x%2097152==off and y%1024==size and not y>>31
 tiles+=n
with tempfile.TemporaryDirectory(prefix='kinder-row-metadata-')as td:
 t=Path(td);src=t/'check.c';src.write_text('#include "'+str(R/'ds/source/sprite_codec.h')+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static uint32_t read32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
int main(int argc,char **argv){
 unsigned count=0;
 for(int arg=1;arg<argc;arg++){
  FILE *f=fopen(argv[arg],"rb");assert(f);unsigned char h[8];assert(fread(h,1,8,f)==8&&!memcmp(h,"KFC5",4));
  uint32_t n=read32(h+4);assert(n&&n<=65536);unsigned char *table=malloc(n*8u);assert(table&&fread(table,8,n,f)==n);
  for(unsigned i=0;i<n;i++){
   uint32_t a=read32(table+i*8),b=read32(table+i*8+4),off=a&0x1fffffu,size=b&1023u;
   uint32_t opaque=(a>>21)|((b>>10)<<11),empty=opaque>>16;opaque&=65535;
   assert(!(b>>31)&&!(opaque&empty));unsigned char packet[2320] __attribute__((aligned(4)));
   uint16_t guarded[260] __attribute__((aligned(4)));guarded[0]=guarded[1]=guarded[258]=guarded[259]=0x1234;
   assert(size&&size<=sizeof(packet)&&!fseek(f,(long)(8+n*8u+off),SEEK_SET)&&fread(packet,1,size,f)==size);
   assert(sprite_codec_decode(packet,size,guarded+2,256));
   for(unsigned y=0;y<16;y++){
    unsigned alpha=0;for(unsigned x=0;x<16;x++)alpha+=(guarded[2+y*16+x]>>15)!=0;
    assert(((opaque>>y)&1u)==(alpha==16)&&((empty>>y)&1u)==(alpha==0));
   }
   assert(guarded[0]==0x1234&&guarded[1]==0x1234&&guarded[258]==0x1234&&guarded[259]==0x1234);count++;
  }
  free(table);fclose(f);
 }
 printf("%u\n",count);return 0;
}
''')
 exe=t/'check';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(src),'-o',str(exe)],check=True);actual=int(subprocess.check_output([str(exe),*map(str,paths)],text=True));assert actual==tiles
result=dict(scope=__doc__,maps=len(paths),decoded_tile_masks_exact=tiles,packet_payloads_exact=True,index_files_exact=True,asset_size_increase=0,sanitizers=['address','undefined'],limits=['Asset/counter correctness only; not a runtime speed measurement.'])
(R/'research/rendering/row-metadata-staged-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
