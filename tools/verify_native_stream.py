"""Sanitize bounded native asset streaming against every encoded page and lookup."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,tempfile
R=Path(__file__).resolve().parents[1];A=R/'research/rendering/native-actor-pages-assets';H=R/'research/rendering/resident-actors-prototype/native_stream.h'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--header',type=Path,default=H);parser.add_argument('--output',type=Path,default=R/'research/rendering/native-stream-verification.json');parser.add_argument('--asset-dir',type=Path,default=A);parser.add_argument('--rect-pages',action='store_true');parser.add_argument('--pack',type=Path);args=parser.parse_args();H=args.header.resolve();A=args.asset_dir.resolve()
manifest=json.loads((A/'manifest.json').read_text());pages=manifest['pages'];lookups=sorted(A.glob('*.gpi'));pack=args.pack.resolve() if args.pack else A/'pages.gpu'
with tempfile.TemporaryDirectory(prefix='kinder-native-stream-')as td:
 t=Path(td);src=t/'test.c'
 src.write_text('#include "'+str(H)+'"\n#include "'+str(R/'research/rendering/resident-actors-prototype/native_page_decode.h')+'"\n'+r'''
#include <assert.h>
#include <stdlib.h>
static unsigned check_lookup(const char *path,unsigned pages){
 FILE *f=fopen(path,"rb");assert(f);assert(!fseek(f,0,SEEK_END));long n=ftell(f);assert(n>=32&&n<4*1024*1024);rewind(f);
 uint8_t *bytes=malloc((size_t)n),*copy=malloc((size_t)n);assert(bytes&&copy);assert(fread(bytes,1,(size_t)n,f)==(size_t)n);fclose(f);
 NativeStreamIndex index;assert(native_stream_index(&index,bytes,(size_t)n,pages));
 for(unsigned i=0;i<index.frames;i++){
  const uint8_t *f=bytes+32+i*24u;NativeStreamFrame frame;
  assert(native_stream_find(&index,native_stream_u32(f),native_stream_u32(f+4),&frame));
  assert(frame.width==native_stream_u16(f+8)&&frame.height==native_stream_u16(f+10)&&frame.first==native_stream_u32(f+12)&&frame.count==native_stream_u32(f+16));
 }
 NativeStreamFrame unused;assert(!native_stream_find(&index,3,0,&unused));assert(!native_stream_find(&index,0,UINT32_MAX,&unused));
 NativeStreamIndex bad;
 for(unsigned i=0;i<32;i++)assert(!native_stream_index(&bad,bytes,i,pages)&&!bad.bytes);
 assert(!native_stream_index(&bad,bytes,(size_t)n-1,pages));
 memcpy(copy,bytes,(size_t)n);copy[28]=1;assert(!native_stream_index(&bad,copy,(size_t)n,pages));
 if(index.frames){memcpy(copy,bytes,(size_t)n);copy[32]=3;assert(!native_stream_index(&bad,copy,(size_t)n,pages));}
 if(index.frames>1){memcpy(copy,bytes,(size_t)n);memcpy(copy+56,copy+32,8);assert(!native_stream_index(&bad,copy,(size_t)n,pages));}
 if(index.refs){memcpy(copy,bytes,(size_t)n);memset(copy+index.ref_offset,255,4);assert(!native_stream_index(&bad,copy,(size_t)n,pages));}
 unsigned frames=index.frames;free(copy);free(bytes);return frames;
}
static void attach_source(NativeStream *s){
 (void)s;
 #ifdef KINDER_NATIVE_SOURCE_CACHE_H
 static uint8_t arena[32768];static NativeSourceCache source_cache;
 assert(native_source_assign(&source_cache,arena,sizeof(arena)));s->source=&source_cache;
 #endif
 #ifdef KINDER_NATIVE_PACKET_WORKSPACE
 static uint8_t packet_memory[4096] __attribute__((aligned(4)));
 s->packet_memory=packet_memory;s->packet_capacity=sizeof(packet_memory);
 #endif
}
int main(int argc,char **argv){
 NativeStream s={0};uint8_t tex[4096],pal[512];uint16_t decoded[2048];NativeStreamPage p;
 if(argc==4&&!strcmp(argv[2],"--bad-record")){
  assert(native_stream_open(&s,argv[1]));attach_source(&s);
  assert(!native_stream_record(&s,(unsigned)strtoul(argv[3],NULL,10),&p));
  native_stream_close(&s);return 0;
 }
 if(argc==3&&!strcmp(argv[2],"--bad")){
  if(native_stream_open(&s,argv[1])){attach_source(&s);assert(!native_stream_page(&s,0,tex,sizeof(tex),pal,sizeof(pal),&p));}
  native_stream_close(&s);return 0;
 }
 assert(argc>=2&&native_stream_open(&s,argv[1]));
 attach_source(&s);
 for(unsigned i=0;i<s.pages;i++){
  assert(native_stream_page(&s,i,tex,sizeof(tex),pal,sizeof(pal),&p));
  #ifdef KINDER_NATIVE_PAGE_LZ10
  if(p.encoded_bytes&&i%197u==0){
   NativeSourceCache *saved=s.source;s.source=NULL;
   assert(!native_stream_texture(&s,&p,tex,sizeof(tex)));s.source=saved;
   unsigned before=saved->clock;
   assert(!native_stream_texture(&s,&p,saved->memory,NATIVE_SOURCE_BYTES)&&before==saved->clock);
   #ifdef KINDER_NATIVE_PACKET_WORKSPACE
   uint8_t *packet=s.packet_memory;unsigned packet_bytes=s.packet_capacity;
   native_source_forget(saved);s.packet_memory=tex;s.packet_capacity=sizeof(tex);
   assert(!native_stream_texture(&s,&p,tex,sizeof(tex)));
   s.packet_memory=packet+1;s.packet_capacity=packet_bytes;
   assert(!native_stream_texture(&s,&p,tex,sizeof(tex)));
   s.packet_memory=packet;s.packet_capacity=packet_bytes;
   #endif
  }
  #endif
  unsigned height=8;
  #ifdef KF_NATIVE_RECT_PAGES
  height=p.height;
  #endif
  assert(native_page_decode_rect(p.bits,p.width,height,tex,p.texture_bytes,p.palette_bytes?pal:NULL,p.palette_bytes,decoded,2048));
  assert(fwrite(decoded,2,p.width*height,stdout)==p.width*height);
  unsigned reads=s.reads;NativeStreamPage again;assert(native_stream_record(&s,i,&again));assert(s.reads==reads&&p.texture==again.texture&&p.palette==again.palette&&p.width==again.width&&p.bits==again.bits&&p.texture_crc==again.texture_crc&&p.palette_crc==again.palette_crc);
 }
 assert(!native_stream_record(&s,s.pages,&p));assert(!native_stream_page(&s,0,tex,0,pal,sizeof(pal),NULL));
 unsigned frames=0;for(int i=2;i<argc;i++)frames+=check_lookup(argv[i],s.pages);
 fprintf(stderr,"{\"pages\":%u,\"frames\":%u,\"reads\":%u,\"bytes_read\":%u,\"host_context_bytes\":%zu}\n",s.pages,frames,s.reads,s.read_bytes,sizeof(s));
 native_stream_close(&s);assert(!s.file&&!s.valid&&!native_stream_record(&s,0,&p));return 0;
}
''')
 exe=t/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),*(['-DKF_NATIVE_RECT_PAGES']if args.rect_pages else[]),'-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),'-o',str(exe)],check=True)
 result=subprocess.run([str(exe),str(pack),*[str(p)for p in lookups]],capture_output=True)
 if result.returncode:raise RuntimeError(result.stderr.decode())
 report=json.loads(result.stderr);at=0
 for p in pages:
  count=p['width']*p['height']*2;decoded=result.stdout[at:at+count];at+=count
  assert len(decoded)==count and hashlib.sha256(decoded).hexdigest()==p['decoded_normalized_sha256'],p['key']
 assert at==len(result.stdout)
 blob=pack.read_bytes();bad_files={}
 for size in (0,31,32,len(blob)-1):bad_files['truncated-'+str(size)]=blob[:size]
 b=bytearray(blob);b[24]=1;bad_files['reserved-header']=b
 b=bytearray(blob);b[40:42]=b'\0\0';bad_files['zero-width']=b
 if args.rect_pages:
  b=bytearray(blob);struct.pack_into('<H',b,42,12);bad_files['non-power-height']=b
  b=bytearray(blob);struct.pack_into('<HH',b,40,256,32);bad_files['scratch-area-overflow']=b
 b=bytearray(blob);tex_at=struct.unpack_from('<I',b,32)[0];b[tex_at]^=1;bad_files['texture-crc']=b
 if struct.unpack_from('<I',blob,4)[0]==3:
  b=bytearray(blob);b[56]^=1;bad_files['decoded-texture-crc']=b
  b=bytearray(blob);struct.pack_into('<H',b,46,65535);bad_files['encoded-size-overflow']=b
  b=bytearray(blob);struct.pack_into('<I',b,4,2);bad_files['encoded-in-legacy-version']=b
 pal_at=struct.unpack_from('<I',blob,36)[0]
 if pal_at:
  b=bytearray(blob);b[pal_at]^=1;bad_files['palette-crc']=b
 for name,b in bad_files.items():
  p=t/(name+'.gpu');p.write_bytes(b);subprocess.run([str(exe),str(p),'--bad'],check=True,capture_output=True)
 if struct.unpack_from('<I',blob,4)[0]==4:
  tall=next(i for i in range(len(pages))if struct.unpack_from('<HH',blob,40+i*32)==(32,64))
  for version in (1,2):
   b=bytearray(blob);struct.pack_into('<I',b,4,version)
   name='height64-under-version'+str(version);p=t/(name+'.gpu');p.write_bytes(b)
   subprocess.run([str(exe),str(p),'--bad-record',str(tall)],check=True,capture_output=True);bad_files[name]=b
  b=bytearray(blob);struct.pack_into('<HH',b,40+tall*32,16,128)
  name='height128-same-area';p=t/(name+'.gpu');p.write_bytes(b)
  subprocess.run([str(exe),str(p),'--bad-record',str(tall)],check=True,capture_output=True);bad_files[name]=b
 base=Path.home()/'.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin'
 arm_src=t/'arm_probe.c';arm_src.write_text('#include "'+str(H)+'"\nunsigned char native_context_bytes[sizeof(NativeStream)];\nint native_probe(NativeStream *s,const char *path,unsigned page,uint8_t *tex,size_t capacity,uint8_t *pal,size_t pal_capacity){return native_stream_open(s,path)&&native_stream_page(s,page,tex,capacity,pal,pal_capacity,0);}\n')
 subprocess.run([str(base/'arm-none-eabi-gcc'),'-mcpu=arm946e-s','-marm','-O2','-std=c11','-Wall','-Wextra','-Werror','-Wstack-usage=2048','-c',str(arm_src),'-o',str(t/'arm_probe.o')],check=True)
 nm=subprocess.check_output([str(base/'arm-none-eabi-nm'),'-S',str(t/'arm_probe.o')],text=True)
 report['arm9_context_bytes']=next(int(line.split()[1],16)for line in nm.splitlines()if line.split()[-1]=='native_context_bytes')
 report['arm9_compile']='GCC16.2 ARM946E-S ARM mode, O2, warnings-as-errors, stack warning2048 bytes'
 report.update(scope=__doc__,asan_ubsan=True,decoded_normalized_sha256_exact=True,map_lookups=len(lookups),negative_pack_cases=len(bad_files),source_sha256=hashlib.sha256(H.read_bytes()).hexdigest(),pack_sha256=hashlib.sha256(blob).hexdigest(),asset_directory=str(A),largest_lookup_bytes=max((p.stat().st_size for p in lookups),default=0),limits=['Host file access and decoder parity only; DS storage latency and VRAM/native drawing are not exercised.','Coverage follows the selected asset manifest; dynamic or absent frames still require fallback.','The host verifier may load lookups larger than the runtime resident budget; this does not prove they fit in DS RAM.'])
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
