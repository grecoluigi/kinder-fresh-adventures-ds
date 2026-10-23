"""ASan/UBSan proof for shared native source-cache memory and bounded file reads."""
from pathlib import Path
import argparse,json,hashlib,subprocess,tempfile
R=Path(__file__).resolve().parents[1];H=R/'research/rendering/resident-actors-prototype/native_source_cache.h'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--header',type=Path,default=H);parser.add_argument('--output',type=Path,default=R/'research/rendering/native-source-cache-verification.json');args=parser.parse_args();H=args.header.resolve()
with tempfile.TemporaryDirectory(prefix='kinder-source-cache-')as td:
 t=Path(td);src=t/'test.c';src.write_text('#include "'+str(H)+'"\n'+r'''
#include <assert.h>
#include <stdlib.h>
static uint8_t arena[32768],extra[65536],other[131072],large[40000],reference[160037],output[8192];static NativeSourceCache c;
typedef struct {uint8_t *p;bool valid;} Owner;
static Owner owners[3];static unsigned notified;
static void before_write(void *p,size_t bytes){
 notified++;uintptr_t a=(uintptr_t)p,b=a+bytes;
 for(unsigned i=0;i<3;i++)if(owners[i].valid){uintptr_t x=(uintptr_t)owners[i].p;if(a<x+1024&&x<b)owners[i].valid=false;}
}
static uint32_t seed=2001;static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void){
 FILE *f=tmpfile();assert(f);for(unsigned i=0;i<sizeof(reference);i++)reference[i]=(uint8_t)(i*137u+i/97u);
 assert(fwrite(reference,1,sizeof(reference),f)==sizeof(reference));fflush(f);
 assert(!native_source_assign(&c,arena,100));assert(native_source_assign(&c,arena,sizeof(arena)));
 uint32_t reads=0,bytes=0;unsigned hits=0;
 #ifdef KINDER_NATIVE_SOURCE_DISCARD_COVERED
 /* A containing replacement keeps one useful range; partial overlaps retain
  * the old uncovered tail and must still serve it without another file read. */
 assert(native_source_read(&c,f,sizeof(reference),1024,output,1024,&reads,&bytes));
 assert(native_source_read(&c,f,sizeof(reference),0,output,3072,&reads,&bytes));
 assert(c.count==1&&!memcmp(output,reference,3072));
 uint32_t covered_reads=reads;
 assert(native_source_read(&c,f,sizeof(reference),1024,output,1024,&reads,&bytes));
 assert(reads==covered_reads&&!memcmp(output,reference+1024,1024));
 native_source_forget(&c);
 assert(native_source_read(&c,f,sizeof(reference),1024,output,2048,&reads,&bytes));
 assert(native_source_read(&c,f,sizeof(reference),0,output,2048,&reads,&bytes));
 assert(c.count==2);
 covered_reads=reads;
 assert(native_source_read(&c,f,sizeof(reference),2048,output,1024,&reads,&bytes));
 assert(reads==covered_reads&&!memcmp(output,reference+2048,1024));
 native_source_forget(&c);
 #endif
 for(unsigned frame=0;frame<5000;frame++){
  if(frame%37==0){memset(arena,0xcd,sizeof(arena));memset(extra,0xe3,sizeof(extra));memset(other,0xf3,sizeof(other));memset(owners,0,sizeof(owners));native_source_forget(&c);}
  if(frame%101==0)native_source_pools(&c,frame%202?extra:NULL,frame%202?sizeof(extra):0,frame%303?other:NULL,frame%303?sizeof(other):0,before_write);
  if(frame%17==0){unsigned i=frame%3;uint8_t *p=(i==0?arena:i==1?extra:other)+192;
   native_source_written(&c,p,1024);memset(p,0xb2,1024);owners[i]=(Owner){p,true};
  }
  if(frame==4095)c.clock=UINT32_MAX;
 #ifdef NATIVE_SOURCE_HINTS
  if(frame%41==0)memset(c.hints,255,sizeof(c.hints));
 #endif
  unsigned n=1+rnd()%sizeof(output),at=rnd()%(sizeof(reference)-n+1);
  assert(native_source_read(&c,f,sizeof(reference),at,output,n,&reads,&bytes));assert(!memcmp(output,reference+at,n));
  for(unsigned i=0;i<3;i++)if(owners[i].valid)for(unsigned n=0;n<1024;n++)assert(owners[i].p[n]==0xb2);
  uint32_t before=reads;assert(native_source_read(&c,f,sizeof(reference),at,output,n,&reads,&bytes));assert(reads==before);hits++;
 }
 assert(!native_source_read(&c,f,sizeof(reference),sizeof(reference)-10,output,11,&reads,&bytes));
 assert(!native_source_read(&c,f,sizeof(reference),UINT32_MAX,output,1,&reads,&bytes));
 assert(native_source_read(&c,f,sizeof(reference),sizeof(reference)-1,output,1,&reads,&bytes)&&output[0]==reference[sizeof(reference)-1]);
 assert(native_source_read(&c,f,sizeof(reference),17,large,sizeof(large),&reads,&bytes)&&!memcmp(large,reference+17,sizeof(large)));
 printf("{\"requests\":10000,\"immediate_cache_hits\":%u,\"file_reads\":%u,\"bytes_read\":%u,\"arena_bytes\":%zu,\"host_metadata_bytes\":%zu}\n",hits,reads,bytes,sizeof(arena),sizeof(c));fclose(f);
}
''');exe=t/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),'-o',str(exe)],check=True)
 report=json.loads(subprocess.check_output([str(exe)],text=True));report.update(optional_extra_arena_bytes=65536,optional_third_arena_bytes=131072,bidirectional_overwrite_checks=True,scope=__doc__,asan_ubsan=True,source_sha256=hashlib.sha256(H.read_bytes()).hexdigest(),limits=['Shared arena writes must invalidate the cache before reuse; actual collector ownership needs separate runtime tests.'])
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
