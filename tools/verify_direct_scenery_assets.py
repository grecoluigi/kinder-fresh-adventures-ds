"""Independently decode original, indexed and modeled GPU scenery pixels with C sanitizers."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--asset-dir',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();assets=args.asset_dir.resolve();manifest=json.loads((assets/'manifest.json').read_text())
with tempfile.TemporaryDirectory(prefix='kinder-direct-scenery-')as directory:
    work=Path(directory)
    (work/'test.c').write_text('#include "'+str(ROOT/'ds/source/sprite_codec.h')+'"\n'+r'''
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
static uint32_t r32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint8_t *load(const char *path,size_t *size){
 FILE *f=fopen(path,"rb");assert(f&&!fseek(f,0,SEEK_END));long n=ftell(f);assert(n>=8&&n<16*1024*1024);
 *size=(size_t)n;uint8_t *p=malloc(*size);assert(p&&!fseek(f,0,SEEK_SET)&&fread(p,1,*size,f)==*size);fclose(f);return p;
}
static const uint8_t *packet(const uint8_t *a,size_t bytes,unsigned tile,unsigned *size){
 unsigned n=r32(a+4);assert(tile<n&&n<=65536&&8u+n*8u<=bytes);
 unsigned offset=r32(a+8+tile*8u);*size=r32(a+12+tile*8u);
 if(!memcmp(a,"KFC5",4)){offset&=0x1fffffu;*size&=1023u;}
 else assert(!memcmp(a,"KFC4",4));
 unsigned start=8u+n*8u;assert(*size&&offset<=bytes-start&&*size<=bytes-start-offset);
 return a+start+offset;
}
int main(int argc,char **argv){
 assert(argc>1&&(argc-1)%3==0);unsigned total=0;
 for(int arg=1;arg<argc;arg+=3){
  size_t an,bn,in;uint8_t *a=load(argv[arg],&an),*b=load(argv[arg+1],&bn),*info=load(argv[arg+2],&in);
  unsigned n=r32(a+4),palettes=r32(info+12);assert(r32(b+4)==n&&in==32u+n*4u);
  assert(!memcmp(info,"KSGI",4)&&r32(info+4)==1&&r32(info+8)==n&&palettes&&palettes<=n);
  assert(r32(info+16)==32&&r32(info+20)==4&&r32(info+24)==in&&!r32(info+28));
  uint8_t *palette_seen=calloc(palettes,512);uint16_t *palette_sizes=calloc(palettes,sizeof(uint16_t));assert(palette_seen&&palette_sizes);
  for(unsigned tile=0;tile<n;tile++){
   unsigned sa,sb;const uint8_t *pa=packet(a,an,tile,&sa),*pb=packet(b,bn,tile,&sb);
   uint16_t old[260],converted[260],gpu[256];uint8_t indices[256] __attribute__((aligned(4)));
   for(unsigned j=0;j<260;j++)old[j]=converted[j]=0x1234;
   assert(sprite_codec_decode(pa,sa,old+2,256)&&sprite_codec_decode(pb,sb,converted+2,256));
   assert(old[0]==0x1234&&old[1]==0x1234&&old[258]==0x1234&&old[259]==0x1234);
   assert(converted[0]==0x1234&&converted[1]==0x1234&&converted[258]==0x1234&&converted[259]==0x1234);
   uint32_t record=r32(info+32+tile*4u);assert(!(record>>26));
   unsigned key=record&65535u,colors=((record>>16)&255u)+1u,bits=(record&(1u<<24))?8:4,transparent=(record>>25)&1u;
   assert(key<palettes&&pb[0]==bits&&!pb[1]&&tile_le16(pb+2)==colors&&colors<=1u<<bits);
   assert(transparent==!(tile_le16(pb+4)&32768u));
   unsigned prefix=4u+((colors*2u+3u)&~3u);assert(prefix<sb);
   assert(tile_decode_lz(pb+prefix,sb-prefix,indices,256u*bits/8u));
   uint8_t rgb[512]={0};unsigned palette_size=(colors*2u+15u)&~15u;
   for(unsigned j=0;j<colors;j++){
    uint16_t color=tile_le16(pb+4+j*2u)&32767u;rgb[j*2u]=(uint8_t)color;rgb[j*2u+1]=(uint8_t)(color>>8);
    if(j)assert(tile_le16(pb+4+j*2u)&32768u);
   }
   if(palette_sizes[key])assert(palette_sizes[key]==palette_size&&!memcmp(palette_seen+key*512u,rgb,palette_size));
   else{palette_sizes[key]=(uint16_t)palette_size;memcpy(palette_seen+key*512u,rgb,palette_size);}
   for(unsigned j=0;j<256;j++){
    unsigned index=bits==8?indices[j]:(indices[j/2]>>((j&1u)*4u))&15u;assert(index<colors);
    gpu[j]=transparent&&!index?0:(tile_le16(rgb+index*2u)|32768u);
    uint16_t normalized=(old[j+2]&32768u)?old[j+2]:0;
    assert(converted[j+2]==normalized&&gpu[j]==normalized);
   }
   if(!memcmp(b,"KFC5",4)){
    uint32_t aa=r32(a+8+tile*8u),ab=r32(a+12+tile*8u),ba=r32(b+8+tile*8u),bb=r32(b+12+tile*8u);
    assert(((aa>>21)|((ab>>10)<<11))==((ba>>21)|((bb>>10)<<11)));
   }
   assert(fwrite(gpu,2,256,stdout)==256);total++;
  }
  for(unsigned i=0;i<palettes;i++)assert(palette_sizes[i]);
  free(palette_sizes);free(palette_seen);free(info);free(b);free(a);
 }
 fprintf(stderr,"%u\n",total);return 0;
}
''')
    exe=work/'test'
    subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all',str(work/'test.c'),'-o',str(exe)],check=True)
    paths=[]
    for row in manifest['maps']:
        name=row['map'];source=ROOT/'ds/nitrofs/composite'/(name+'.atlas');target=assets/'nitrofs/composite'/(name+'.atlas')
        assert hashlib.sha256(source.read_bytes()).hexdigest()==row['source_sha256']
        assert hashlib.sha256(target.read_bytes()).hexdigest()==row['atlas_sha256']
        assert source.with_suffix('.index').read_bytes()==target.with_suffix('.index').read_bytes()
        paths.extend([str(source),str(target),str(target.with_suffix('.gpuinfo'))])
    result=subprocess.run([str(exe),*paths],capture_output=True,check=True);assert int(result.stderr)==manifest['tiles']
    at=0
    for row in manifest['maps']:
        for expected in row['normalized_tile_sha256']:
            pixels=result.stdout[at:at+512];at+=512;assert len(pixels)==512 and hashlib.sha256(pixels).hexdigest()==expected
    assert at==len(result.stdout)
report=dict(scope=__doc__,maps=len(manifest['maps']),tiles=manifest['tiles'],pixels=manifest['tiles']*256,
            asan_ubsan=True,normalized_source_CPU_GPU_pixels_exact=True,index_files_exact=True,
            limits=['GPU palette-alpha behavior is modeled; actual DS sampling and VRAM transitions remain unverified.',
                    'No production ROM/assets changed; this does not establish a rendering speedup.'])
args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
