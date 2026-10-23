"""Sanitize decoded/file cache namespaces, shared ownership and stale hints."""
from pathlib import Path
import argparse,json,hashlib,subprocess,tempfile
R=Path(__file__).resolve().parents[1];H=R/'research/rendering/gpu-native-page-cached-candidate/native_source_cache.h'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--header',type=Path,default=H);parser.add_argument('--output',type=Path,default=R/'research/rendering/native-decoded-cache-verification.json');args=parser.parse_args();H=args.header.resolve()
with tempfile.TemporaryDirectory(prefix='kinder-decoded-cache-')as directory:
 t=Path(directory);src=t/'test.c';exe=t/'test'
 src.write_text('#include "'+str(H)+'"\n#include <assert.h>\n'+r'''
static NativeSourceCache c;static uint8_t arena[32768],reference[65536],decoded[4096],out[4096];
static uint32_t seed=2001;static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void){
 for(unsigned i=0;i<sizeof(reference);i++)reference[i]=(uint8_t)(i*137u+i/97u);
 for(unsigned i=0;i<sizeof(decoded);i++)decoded[i]=(uint8_t)(i*3u+0x45u);
 FILE *f=tmpfile();assert(f&&fwrite(reference,1,sizeof(reference),f)==sizeof(reference));fflush(f);
 assert(native_source_assign(&c,arena,sizeof(arena)));uint32_t reads=0,bytes=0;
 assert(native_source_store_decoded(&c,0,decoded,4096));
 /* A file read inside a decoded entry's numeric key range must read the file. */
 assert(native_source_read(&c,f,sizeof(reference),128,out,64,&reads,&bytes)&&!memcmp(out,reference+128,64));
 assert(native_source_decoded(&c,0,4096)&&!memcmp(native_source_decoded(&c,0,4096),decoded,4096));
 assert(!native_source_decoded(&c,128,64)&&!native_source_decoded(&c,0,64)&&!native_source_decoded(&c,0,1024));
 #ifdef KINDER_NATIVE_SOURCE_VIEW
 const uint8_t *view=native_source_cached(&c,128,64);assert(view&&!memcmp(view,reference+128,64));
 assert(!native_source_cached(&c,0,2048)&&!native_source_cached(&c,50000,64));
 #endif
 assert(!native_source_store_decoded(&c,1,arena,4096));
 unsigned overwritten=0;
 for(unsigned frame=0;frame<5000;frame++){
  unsigned key=rnd()%60000u,n=1+rnd()%4096u;
  for(unsigned i=0;i<n;i++)decoded[i]=(uint8_t)(key+i*41u);
  assert(native_source_store_decoded(&c,key,decoded,n));
  const uint8_t *p=native_source_decoded(&c,key,n);assert(p&&!memcmp(p,decoded,n));
  if(frame%17==0)memset(c.hints,255,sizeof(c.hints));
  p=native_source_decoded(&c,key,n);assert(p&&!memcmp(p,decoded,n));
  assert(native_source_read(&c,f,sizeof(reference),key,out,n,&reads,&bytes)&&!memcmp(out,reference+key,n));
  if(frame%19==0){p=native_source_decoded(&c,key,n);if(p){native_source_written(&c,p,n);memset((void *)p,0x93,n);assert(!native_source_decoded(&c,key,n));overwritten++;}}
  if(frame%101==0){c.clock=UINT32_MAX;assert(!native_source_decoded(&c,key,n)&&c.count==0);}
 }
 assert(sizeof(NativeSourceEntry)==16);
 printf("{\"mixed_operations\":5000,\"decoded_overwrite_checks\":%u,\"physical_reads\":%u,\"entry_bytes\":%zu,\"host_metadata_bytes\":%zu}\n",overwritten,reads,sizeof(NativeSourceEntry),sizeof(c));fclose(f);return 0;
}
''')
 subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(src),'-o',str(exe)],check=True)
 report=json.loads(subprocess.check_output([str(exe)],text=True));report.update(scope=__doc__,asan_ubsan=True,source_sha256=hashlib.sha256(H.read_bytes()).hexdigest(),limits=['Synthetic shared storage checks; renderer/BIOS behavior is verified separately.','Borrowed decoded pointers are consumed before any further cache operation.'])
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
