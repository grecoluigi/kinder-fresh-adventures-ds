"""Verify bounded catalog lookups/reference batches against the full asset index."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,tempfile
from native_catalog_index import dense_index
R=Path(__file__).resolve().parents[1];P=R/'research/rendering/resident-actors-prototype';A=R/'research/rendering/native-actor-catalog-assets'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dense',action='store_true');parser.add_argument('--output',type=Path,default=R/'research/rendering/native-catalog-reader-verification.json');args=parser.parse_args()
blob=(A/'global.gpi').read_bytes();manifest=json.loads((A/'manifest.json').read_text());pages=len(manifest['pages'])
with tempfile.TemporaryDirectory(prefix='kinder-catalog-reader-')as directory:
 t=Path(directory);src=t/'test.c';exe=t/'test';input_path=A/'global.gpi'
 if args.dense:input_path=t/'dense.gpi';input_path.write_bytes(dense_index(blob,pages))
 src.write_text('#include "native_catalog.h"\n#include <assert.h>\n#include <stdlib.h>\n'+r'''
typedef struct {FILE *file;uint32_t bytes,reads,max_request;} Store;
static bool read_bytes(void *context,uint32_t at,void *out,uint32_t bytes){
 Store *s=context;
 assert(at<=s->bytes&&bytes<=s->bytes-at&&bytes<=NATIVE_CATALOG_BATCH*12u);
 s->reads++;if(bytes>s->max_request)s->max_request=bytes;
 return !fseek(s->file,(long)at,SEEK_SET)&&fread(out,1,bytes,s->file)==bytes;
}
int main(int argc,char **argv){
 assert(argc==3);Store s={0};s.file=fopen(argv[1],"rb");assert(s.file);
 assert(!fseek(s.file,0,SEEK_END));long bytes=ftell(s.file);assert(bytes>0&&bytes<INT32_MAX);s.bytes=(uint32_t)bytes;
 NativeCatalog c;assert(native_catalog_init(&c,read_bytes,&s,s.bytes,(unsigned)strtoul(argv[2],NULL,10)));
 NativeCatalogFrame f;NativeCatalogRef refs[NATIVE_CATALOG_BATCH];unsigned references=0,valid_frames=0;
 assert(!native_catalog_find(&c,3,0,&f)&&!native_catalog_find(&c,0,UINT32_MAX,&f));
 for(unsigned i=0;i<c.frames;i++){
  NativeCatalogFrame expected;
  if(!native_catalog_record(&c,i,&expected)){
   assert(c.frame_offset==64);unsigned kind=0;while(kind<2&&i>=c.kind_first[kind+1])kind++;
   assert(!native_catalog_find(&c,kind,i-c.kind_first[kind],&f));continue;
  }
  valid_frames++;
  assert(native_catalog_find(&c,expected.kind,expected.id,&f));
  assert(f.first==expected.first&&f.count==expected.count&&f.width==expected.width&&f.height==expected.height);
  unsigned reads=s.reads;assert(native_catalog_find(&c,f.kind,f.id,&f)&&reads==s.reads);
  for(unsigned first=0;first<f.count;){
   unsigned n=f.count-first;if(n>NATIVE_CATALOG_BATCH)n=NATIVE_CATALOG_BATCH;
   assert(native_catalog_refs(&c,&f,first,n,refs));
   for(unsigned j=0;j<n;j++)assert(fwrite(refs+j,sizeof(*refs),1,stdout)==1);
   first+=n;references+=n;
  }
  assert(!native_catalog_refs(&c,&f,f.count,1,refs));
  assert(!native_catalog_refs(&c,&f,0,33,refs));
 }
 fprintf(stderr,"{\"frames\":%u,\"references\":%u,\"host_context_bytes\":%zu,\"max_read_bytes\":%u,\"read_requests\":%u}\n",valid_frames,references,sizeof(c),s.max_request,s.reads);
 fclose(s.file);return 0;
}
''')
 common=['-std=c11','-Wall','-Wextra','-Werror','-I'+str(P)]
 subprocess.run(['cc','-O1','-g',*common,'-fsanitize=address,undefined',str(src),'-o',str(exe)],check=True)
 result=subprocess.run([str(exe),str(input_path),str(pages)],capture_output=True,check=True);report=json.loads(result.stderr)
 frames,refs=struct.unpack_from('<II',blob,8);ref_offset=struct.unpack_from('<I',blob,20)[0]
 expected=bytearray()
 for i in range(frames):
  first,count=struct.unpack_from('<II',blob,32+i*24+12);expected.extend(blob[ref_offset+first*12:ref_offset+(first+count)*12])
 assert result.stdout==expected and report['frames']==3616
 # Mutable memory fixture tests corruption/truncation without trusting a FILE
 # reader to silently clamp bounds. Its callback rejects every invalid range.
 negative=t/'negative.c';negative.write_text('#include "native_catalog.h"\n#include <assert.h>\n'+r'''
static uint8_t data[100];static unsigned available=sizeof(data);
static bool read_memory(void *unused,uint32_t at,void *out,uint32_t n){(void)unused;if(at>available||n>available-at)return false;memcpy(out,data+at,n);return true;}
static void u32(unsigned at,uint32_t n){for(unsigned i=0;i<4;i++)data[at+i]=(uint8_t)(n>>(i*8));}
static void setup(void){memset(data,0,sizeof(data));memcpy(data,"KAF1",4);u32(4,1);u32(8,1);u32(12,1);u32(16,32);u32(20,56);u32(24,68);data[40]=data[42]=8;u32(48,1);data[64]=data[66]=8;available=68;}
static void setup_dense(void){setup();memmove(data+64,data+32,36);memset(data+32,0,32);memcpy(data,"KAD1",4);u32(16,64);u32(20,88);u32(24,100);u32(36,1);u32(40,1);u32(44,1);u32(56,1);available=100;}
int main(void){NativeCatalog c;NativeCatalogFrame f;NativeCatalogRef r;
 setup();assert(native_catalog_init(&c,read_memory,0,68,1));assert(native_catalog_find(&c,0,0,&f));assert(native_catalog_refs(&c,&f,0,1,&r));
 for(unsigned n=0;n<32;n++){setup();available=n;assert(!native_catalog_init(&c,read_memory,0,68,1));}
 const unsigned bad_header[]={4,8,12,16,20,24,28};
 for(unsigned i=0;i<7;i++){setup();u32(bad_header[i],UINT32_MAX);assert(!native_catalog_init(&c,read_memory,0,68,1));}
 const unsigned bad_record[]={32,40,44,48,52};
 for(unsigned i=0;i<5;i++){setup();u32(bad_record[i],UINT32_MAX);assert(native_catalog_init(&c,read_memory,0,68,1));assert(!native_catalog_find(&c,0,0,&f));}
 const unsigned bad_ref[]={56,60,64};
 for(unsigned i=0;i<3;i++){setup();u32(bad_ref[i],UINT32_MAX);assert(native_catalog_init(&c,read_memory,0,68,1));assert(native_catalog_find(&c,0,0,&f));assert(!native_catalog_refs(&c,&f,0,1,&r));}
 setup_dense();assert(native_catalog_init(&c,read_memory,0,100,1));assert(native_catalog_find(&c,0,0,&f));assert(native_catalog_refs(&c,&f,0,1,&r));
 const unsigned bad_dense[]={32,36,40,44,48,52,56,60};
 for(unsigned i=0;i<8;i++){setup_dense();u32(bad_dense[i],UINT32_MAX);assert(!native_catalog_init(&c,read_memory,0,100,1));}
 setup_dense();u32(68,1);assert(native_catalog_init(&c,read_memory,0,100,1));assert(!native_catalog_find(&c,0,0,&f));
 setup();assert(native_catalog_init(&c,read_memory,0,68,1));available=40;assert(!native_catalog_find(&c,0,0,&f));
 setup();assert(native_catalog_init(&c,read_memory,0,68,1));assert(native_catalog_find(&c,0,0,&f));available=60;assert(!native_catalog_refs(&c,&f,0,1,&r));return 0;}
''')
 subprocess.run(['cc','-O1','-g',*common,'-fsanitize=address,undefined',str(negative),'-o',str(t/'negative')],check=True)
 subprocess.run([str(t/'negative')],check=True)
 arm=t/'arm.c';arm.write_text('#include "native_catalog.h"\nunsigned char context_bytes[sizeof(NativeCatalog)];\nbool probe(NativeCatalog*c,unsigned k,unsigned id,NativeCatalogFrame*f,NativeCatalogRef*r){return native_catalog_find(c,k,id,f)&&(!f->count||native_catalog_refs(c,f,0,1,r));}\n')
 base=Path.home()/'.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin'
 subprocess.run([str(base/'arm-none-eabi-gcc'),'-mcpu=arm946e-s','-marm','-O2',*common,'-Wstack-usage=1024','-c',str(arm),'-o',str(t/'arm.o')],check=True)
 nm=subprocess.check_output([str(base/'arm-none-eabi-nm'),'-S',str(t/'arm.o')],text=True)
 report['arm9_context_bytes']=next(int(line.split()[1],16)for line in nm.splitlines()if line.split()[-1]=='context_bytes')
report.update(scope=__doc__,asan_ubsan=True,all_reference_bytes_exact=True,negative_header_mutations=7,negative_record_mutations=5,negative_reference_mutations=3,truncated_header_sizes=32,mid_operation_truncation_cases=2,dense_index=args.dense,negative_dense_header_mutations=8,lookup_bytes=len(dense_index(blob,pages) if args.dense else blob),lookup_sha256=hashlib.sha256(dense_index(blob,pages) if args.dense else blob).hexdigest(),source_sha256=hashlib.sha256((P/'native_catalog.h').read_bytes()).hexdigest(),limits=['Lookup bounds, cache hits and exact reference bytes only; no renderer integration, gameplay or DS storage timing.','The storage callback must refer to immutable data and remain valid until context reinitialization.'])
args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
