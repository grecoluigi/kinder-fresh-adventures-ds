"""Independently decode exported GPU pages in sanitized C; reassemble source frames."""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import hashlib,json,struct,subprocess,tempfile,zlib
import numpy as np
R=Path(__file__).resolve().parents[1]
A=R/'research/rendering/native-actor-pages-assets'
H=R/'research/rendering/resident-actors-prototype/native_pack_decode.h'
manifest=json.loads((A/'manifest.json').read_text())
pages=manifest['pages'];rom=resolve_rom(R / 'ds');rom_sha=hashlib.sha256(rom.read_bytes()).hexdigest()
assert rom_sha==manifest['rom_sha256']
with tempfile.TemporaryDirectory(prefix='kinder-native-page-proof-') as td:
 t=Path(td);src=t/'test.c'
 src.write_text('#include "'+str(H)+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static uint8_t texels[4096],palette[512];
static uint16_t output[2050];
static uint16_t packed_output[2050];
static unsigned read_u32(FILE *f){uint8_t h[4];assert(fread(h,1,4,f)==4);return (unsigned)h[0]|(unsigned)h[1]<<8|(unsigned)h[2]<<16|(unsigned)h[3]<<24;}
int main(int argc,char **argv){
 assert(argc==4);FILE *in=fopen(argv[1],"rb"),*out=fopen(argv[2],"wb"),*pf=fopen(argv[3],"rb");assert(in&&out&&pf);
 assert(!fseek(pf,0,SEEK_END));long length=ftell(pf);assert(length>=32&&length<64*1024*1024);rewind(pf);
 uint8_t *pack=malloc((size_t)length);assert(pack&&fread(pack,1,(size_t)length,pf)==(size_t)length&&!fclose(pf));
 unsigned count=read_u32(in);
 for(unsigned n=0;n<count;n++){
  unsigned bits=read_u32(in),width=read_u32(in),bytes=read_u32(in),pal=read_u32(in);
  assert(bytes<=sizeof(texels)&&pal<=sizeof(palette));
  assert(fread(texels,1,bytes,in)==bytes&&fread(palette,1,pal,in)==pal);
  output[0]=0xa55a;output[2049]=0x5aa5;
  assert(native_page_decode(bits,width,texels,bytes,palette,pal,output+1,2048));
  packed_output[0]=0xa55a;packed_output[2049]=0x5aa5;
  assert(native_pack_decode(pack,(size_t)length,n,packed_output+1,2048));
  assert(!memcmp(output+1,packed_output+1,width*8u*2u));
  assert(packed_output[0]==0xa55a&&packed_output[2049]==0x5aa5);
  assert(!native_pack_decode(pack,(size_t)length-1,n,packed_output+1,2048));
  uint8_t *record=pack+32+(size_t)n*32;uint8_t saved[4];memcpy(saved,record,4);memset(record,255,4);
  assert(!native_pack_decode(pack,(size_t)length,n,packed_output+1,2048));memcpy(record,saved,4);
  assert(output[0]==0xa55a&&output[2049]==0x5aa5);
  assert(fwrite(output+1,2,width*8u,out)==width*8u);
  assert(!native_page_decode(bits,width,texels,bytes-1,palette,pal,output+1,2048));
  assert(!native_page_decode(bits,width,texels,bytes,palette,pal,output+1,width*8u-1));
  if(bits<16)assert(!native_page_decode(bits,width,texels,bytes,palette,pal-1,output+1,2048));
 }
 assert(!native_page_decode(3,8,texels,32,palette,32,output,2048));
 assert(!native_page_decode(4,9,texels,36,palette,32,output,2048));
 assert(!native_pack_decode(pack,(size_t)length,count,packed_output+1,2048));
 assert(!native_pack_decode(pack,31,0,packed_output+1,2048));
 free(pack);assert(fgetc(in)==EOF);assert(!fclose(in)&&!fclose(out));return 0;
}
''')
 input=t/'input.bin';decoded=t/'decoded.bin'
 with input.open('wb') as f:
  f.write(struct.pack('<I',len(pages)))
  for p in pages:
   tex=(A/p['texels']).read_bytes();pal=(A/p['palette']).read_bytes() if p['palette'] else b''
   assert len(tex)==p['texel_bytes'] and len(pal)==p['palette_bytes']
   assert hashlib.sha256(bytes([p['bits']])+p['width'].to_bytes(2,'little')+tex+pal).hexdigest()==p['key']
   f.write(struct.pack('<4I',p['bits'],p['width'],len(tex),len(pal)));f.write(tex);f.write(pal)
 exe=t/'verify'
 subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),'-o',str(exe)],check=True)
 subprocess.run([str(exe),str(input),str(decoded),str(A/'pages.gpu')],check=True)
 arrays={}
 with decoded.open('rb') as f:
  for p in pages:
   raw=f.read(p['width']*8*2)
   assert hashlib.sha256(raw).hexdigest()==p['decoded_normalized_sha256']
   arrays[p['key']]=np.frombuffer(raw,dtype='<u2').reshape(8,p['width'])
  assert not f.read(1)
 packed=(A/'pages.gpu').read_bytes()
 magic,version,count,record_size,records_off,total,r0,r1=struct.unpack_from('<4s7I',packed)
 assert (magic,version,count,record_size,records_off,total,r0,r1)==(b'KGP1',1,len(pages),32,32,len(packed),0,0)
 for i,p in enumerate(pages):
  tex,pal,w,h,bits,flags,res,nt,npal,tcrc,pcrc=struct.unpack_from('<IIHHBBHIIII',packed,32+i*32)
  assert (w,h,bits,flags,res,nt,npal)==(p['width'],8,p['bits'],int(p['bits']<16),0,p['texel_bytes'],p['palette_bytes'])
  assert zlib.crc32(packed[tex:tex+nt])==tcrc and zlib.crc32(packed[pal:pal+npal])==pcrc
 frames=0
 for name,bindings in manifest['bindings'].items():
  lookup=(A/(name+'.gpi')).read_bytes()
  magic,version,nframes,nrefs,foff,roff,total,res=struct.unpack_from('<4s7I',lookup)
  assert (magic,version,nframes,foff,roff,total,res)==(b'KAF1',1,len(bindings),32,32+24*nframes,len(lookup),0)
  assert roff+12*nrefs==len(lookup)
  seen=set()
  for i in range(nframes):
   kind,frameid,width,height,first,n,res=struct.unpack_from('<IIHHIII',lookup,foff+24*i)
   binding=bindings[f'{kind}:{frameid}'];assert (kind,frameid) not in seen;seen.add((kind,frameid))
   assert (width,height,res)==(binding['width'],binding['height'],0) and first+n<=nrefs
   image=np.zeros((binding['height'],binding['width']),dtype='<u2');covered=np.zeros_like(image,dtype=bool)
   for j in range(first,first+n):
    page,x,y,w,h=struct.unpack_from('<I4H',lookup,roff+12*j)
    assert page<len(pages) and 0<=y<y+h<=len(image) and 0<=x<x+w<=image.shape[1] and not covered[y:y+h,x:x+w].any()
    image[y:y+h,x:x+w]=arrays[pages[page]['key']][:h,:w];covered[y:y+h,x:x+w]=True
   assert hashlib.sha256(image.tobytes()).hexdigest()==binding['source_normalized_sha256'],(name,binding['kind'],binding['frame_id'])
   frames+=1
result={'scope':__doc__,'rom_sha256':rom_sha,'rom_unchanged':hashlib.sha256(rom.read_bytes()).hexdigest()==rom_sha,'manifest_sha256':hashlib.sha256((A/'manifest.json').read_bytes()).hexdigest(),'pack_sha256':hashlib.sha256(packed).hexdigest(),'decoder_sha256':hashlib.sha256(H.read_bytes()).hexdigest(),'pages':len(pages),'source_frame_bindings':frames,'asan_ubsan':True,'exact_normalized_pixels':True,'limits':['Transparent RGB bits normalized to zero, as they are discarded by native alpha/color-zero transparency.','Reference decoder and binary frame lookup reassembly only; GPU palettes, VRAM allocation and rendered geometry remain untested.']}
(R/'research/rendering/native-actor-pages-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
