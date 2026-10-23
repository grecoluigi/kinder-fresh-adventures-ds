"""Packed palette expansion vs retained previous decoder, with alignment/length/error boundaries."""
from pathlib import Path
import subprocess,tempfile,json,hashlib
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-palette-pairs-')as td:
 t=Path(td);src=t/'check.c';exe=t/'check'
 src.write_text('#include "sprite_codec.h"\n#undef KINDER_SPRITE_CODEC_H\n#define sprite_codec_decode previous_decode\n#include "'+str(R/'research/rendering/sprite_codec_before_pair_expansion.h')+'"\n#undef sprite_codec_decode\n'+r'''
#include <assert.h>
#include <stdio.h>
static uint32_t seed=2001;
static unsigned random_value(void){seed=seed*1664525u+1013904223u;return seed;}
static uint8_t packet[8192] __attribute__((aligned(4))),raw[4096];
static uint16_t current[4104] __attribute__((aligned(4))),previous[4104] __attribute__((aligned(4)));
static void le16(uint8_t*p,unsigned x){p[0]=(uint8_t)x;p[1]=(uint8_t)(x>>8);}
static unsigned encode(uint8_t*p,unsigned bits,unsigned colors,unsigned pixels){
 p[0]=(uint8_t)bits;p[1]=0;le16(p+2,colors);
 for(unsigned c=0;c<colors;c++)le16(p+4+c*2,random_value());
 unsigned prefix=4+((colors*2+3)&~3u),bytes=bits==8?pixels:(pixels+1)/2;
 memset(raw,0,bytes);
 for(unsigned i=0;i<pixels;i++){unsigned index=random_value()%colors;if(bits==8)raw[i]=(uint8_t)index;else raw[i/2]|=(uint8_t)(index<<((i&1)*4));}
 uint8_t *lz=p+prefix;lz[0]=16;lz[1]=(uint8_t)bytes;lz[2]=(uint8_t)(bytes>>8);lz[3]=0;unsigned at=4;
 for(unsigned i=0;i<bytes;){lz[at++]=0;for(unsigned j=0;j<8&&i<bytes;j++)lz[at++]=raw[i++];}
 return prefix+at;
}
static void compare(const uint8_t*p,unsigned bytes,unsigned pixels,unsigned alignment,bool exact){
 for(unsigned i=0;i<4104;i++)current[i]=previous[i]=0x1234;
 bool a=sprite_codec_decode(p,bytes,current+2+alignment,pixels),b=previous_decode(p,bytes,previous+2+alignment,pixels);assert(a==b);
 if(exact){assert(a);assert(!memcmp(current,previous,sizeof(current)));}
 for(unsigned i=0;i<2+alignment;i++)assert(current[i]==0x1234);
 for(unsigned i=2+alignment+pixels;i<4104;i++)assert(current[i]==0x1234);
}
int main(void){
 unsigned valid=0,invalid=0;
 for(unsigned bits=4;bits<=8;bits+=4)for(unsigned pixels=1;pixels<=4096;pixels+=pixels<129?1:37){
  unsigned colors=1+random_value()%(1u<<bits);
  for(unsigned offset=0;offset<2;offset++){
   unsigned bytes=encode(packet+offset,bits,colors,pixels);
   for(unsigned alignment=0;alignment<2;alignment++){
    compare(packet+offset,bytes,pixels,alignment,true);valid++;
    compare(packet+offset,bytes-1,pixels,alignment,false);invalid++;
    le16(packet+offset+2,0);compare(packet+offset,bytes,pixels,alignment,false);invalid++;
    le16(packet+offset+2,colors);
   }
  }
 }
 /* A valid LZ stream whose indices exceed a one-color palette must be rejected
  * before a palette access. Both decoders may leave different partial images. */
 for(unsigned bits=4;bits<=8;bits+=4){
  unsigned bytes=encode(packet,bits,1,257),prefix=8;packet[prefix+5]=255;
  compare(packet,bytes,257,0,false);assert(!sprite_codec_decode(packet,bytes,current+2,257));invalid++;
 }
 printf("{\"valid_alignment_length_cases\":%u,\"error_boundary_cases\":%u,\"exact\":true,\"guards_intact\":true}\n",valid,invalid);
}
''')
 subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ds/source'),str(src),'-o',str(exe)],check=True)
 d=json.loads(subprocess.check_output([str(exe)],text=True));d['scope']=__doc__;d['previous_header_sha256']=hashlib.sha256((R/'research/rendering/sprite_codec_before_pair_expansion.h').read_bytes()).hexdigest();d['limits']=['Reference decoder and adversarial packet vectors; actual original asset pixels and emulated DS timing checked separately.']
 (R/'research/rendering/sprite-pair-expansion-verification.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
