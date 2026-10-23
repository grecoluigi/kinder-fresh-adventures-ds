"""Sanitize compressed native reads, cache boundaries, malformed metadata and tokens."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1];P=R/'research/rendering/resident-actors-prototype';O=R/'research/rendering/gpu-native-compressed-candidate'
packed=O/'nitrofs/native_actors/pages.gpu';original=R/'research/rendering/gpu-native-hinted-candidate/nitrofs/native_actors/pages.gpu'
with tempfile.TemporaryDirectory(prefix='kinder-native-blocks-')as directory:
 t=Path(directory);src=t/'test.c';exe=t/'test'
 src.write_text('#include "native_blocks.h"\n#include "native_source_cache.h"\n#include <assert.h>\n#include <stdlib.h>\n'+r'''
static uint8_t arena[32768],guard[32768+32];static NativeSourceCache cache;
static uint32_t seed=2001;static uint32_t rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static void u32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(i*8));}
static void negative(void){
 uint8_t raw[56]={0},out[16],h[32];uint32_t reads=0,bytes=0;NativeBlocks b;
 memcpy(raw,"KZB1",4);u32(raw+4,1);u32(raw+8,16);u32(raw+12,1024);u32(raw+16,1);u32(raw+20,32);u32(raw+24,56);
 u32(raw+32,48);u32(raw+36,0x80000008u);u32(raw+40,16);
 const uint8_t lz[8]={16,16,0,0,0x40,0x7f,0xc0,0};memcpy(raw+48,lz,8);
 FILE *f=tmpfile();assert(f);assert(fwrite(raw,1,56,f)==56);fflush(f);
 assert(native_blocks_open(&b,f,56,raw)&&native_blocks_read(&b,0,out,16,&reads,&bytes));for(unsigned i=0;i<16;i++)assert(out[i]==0x7f);
 for(unsigned at=0;at<32;at+=4){memcpy(h,raw,32);u32(h+at,UINT32_MAX);assert(!native_blocks_open(&b,f,56,h));}
 const unsigned record_at[]={32,36,40,44};
 for(unsigned i=0;i<4;i++){
  uint8_t copy[56];memcpy(copy,raw,56);u32(copy+record_at[i],UINT32_MAX);
  rewind(f);assert(fwrite(copy,1,56,f)==56);fflush(f);
  assert(native_blocks_open(&b,f,56,copy)&&!native_blocks_read(&b,0,out,16,&reads,&bytes));
 }
 for(unsigned length=0;length<8;length++)assert(!native_blocks_lz(lz,length,out,16));
 uint8_t bad[8];memcpy(bad,lz,8);bad[6]=0xcf;assert(!native_blocks_lz(bad,8,out,16));
 memcpy(bad,lz,8);bad[6]=0xf0;assert(!native_blocks_lz(bad,8,out,16));
 fclose(f);
}
int main(int argc,char **argv){
 assert(argc==3);negative();FILE *f=fopen(argv[1],"rb"),*reference=fopen(argv[2],"rb");assert(f&&reference);
 assert(!fseek(f,0,SEEK_END));long n=ftell(f);assert(n>=32&&n<INT32_MAX);rewind(f);
 uint8_t header[32];assert(fread(header,1,32,f)==32);NativeBlocks b;assert(native_blocks_open(&b,f,(uint32_t)n,header));
 uint8_t *expected=malloc(b.logical);assert(expected&&fread(expected,1,b.logical,reference)==b.logical&&fgetc(reference)==EOF);fclose(reference);
 uint32_t reads=0,bytes=0;
 for(uint32_t at=0;at<b.logical;){
  unsigned count=b.logical-at;if(count>32768)count=32768;
  assert(native_blocks_read(&b,at,guard+16,count,&reads,&bytes)&&!memcmp(guard+16,expected+at,count));
  assert(fwrite(guard+16,1,count,stdout)==count);at+=count;
 }
 assert(native_source_assign(&cache,arena,sizeof(arena)));
 for(unsigned i=0;i<5000;i++){
  unsigned count=1+rnd()%32768u,at=rnd()%(b.logical-count+1u),padding=16+(i&1u);
  if(i%37==0){memset(arena,0xcd,sizeof(arena));native_source_forget(&cache);}
  memset(guard,0xa5,sizeof(guard));
  assert(native_source_read_from(&cache,f,b.logical,at,guard+padding,count,&reads,&bytes,native_blocks_read,&b));
  assert(!memcmp(guard+padding,expected+at,count));
  for(unsigned j=0;j<padding;j++)assert(guard[j]==0xa5);
  for(unsigned j=padding+count;j<sizeof(guard);j++)assert(guard[j]==0xa5);
 }
 assert(!native_blocks_read(&b,b.logical,guard,1,&reads,&bytes));assert(!native_blocks_read(&b,UINT32_MAX,guard,1,&reads,&bytes));
 fprintf(stderr,"{\"logical_bytes\":%u,\"physical_bytes\":%u,\"random_cached_ranges\":5000,\"physical_read_requests\":%u,\"physical_bytes_read\":%u,\"host_context_bytes\":%zu}\n",b.logical,b.physical,reads,bytes,sizeof(b));
 free(expected);fclose(f);return 0;
}
''')
 subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(P),str(src),'-o',str(exe)],check=True)
 result=subprocess.run([str(exe),str(packed),str(original)],capture_output=True,check=True);report=json.loads(result.stderr)
 assert hashlib.sha256(result.stdout).digest()==hashlib.sha256(original.read_bytes()).digest()
 arm=t/'arm.c';arm.write_text('#include "native_blocks.h"\nunsigned char context_bytes[sizeof(NativeBlocks)];\nbool probe(NativeBlocks*b,uint32_t at,void*out,uint32_t n,uint32_t*r,uint32_t*bytes){return native_blocks_read(b,at,out,n,r,bytes);}\n')
 base=Path.home()/'.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin';sdk=Path.home()/'.local/share/wonderful/thirdparty/blocksds/core'
 subprocess.run([str(base/'arm-none-eabi-gcc'),'-mcpu=arm946e-s','-marm','-D__NDS__','-DARM9','-O2','-std=gnu11','-Wall','-Wextra','-Werror','-Wstack-usage=4096','-I'+str(P),'-I'+str(R/'ds/source'),'-I'+str(sdk/'libs/libnds/include'),'-c',str(arm),'-o',str(t/'arm.o')],check=True)
 nm=subprocess.check_output([str(base/'arm-none-eabi-nm'),'-S',str(t/'arm.o')],text=True)
 report['arm9_context_bytes']=next(int(line.split()[1],16)for line in nm.splitlines()if line.split()[-1]=='context_bytes')
 report.update(scope=__doc__,asan_ubsan=True,complete_logical_stream_exact=True,malformed_header_cases=8,malformed_record_cases=4,truncated_token_lengths=8,invalid_token_cases=2,source_sha256=hashlib.sha256((P/'native_blocks.h').read_bytes()).hexdigest(),pack_sha256=hashlib.sha256(packed.read_bytes()).hexdigest(),limits=['Host decoder/cache tests and target compilation; BIOS execution and DS storage latency require an actual ROM probe.','Block directory is cached in fixed32-record batches; source cache remains logically addressed.'])
 (R/'research/rendering/native-block-reader-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
