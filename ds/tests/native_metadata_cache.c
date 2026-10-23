#include "native_stream.h"
#include <assert.h>
#include <stdlib.h>
typedef struct {unsigned char bytes[32768];unsigned tail;} Arena;
static Arena arena;static NativeMetadataCache cache;
static unsigned char reference[160037],out[4096];
static unsigned reads,fail_reads;static uint32_t seed=2001;
static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static bool read_at(void *unused,uint32_t at,void *dest,uint32_t n){
 (void)unused;reads++;assert(at<=sizeof(reference)&&n<=sizeof(reference)-at);
 if(fail_reads){memset(dest,0xba,n/2);fail_reads--;return false;}
 memcpy(dest,reference+at,n);return true;
}
int main(void){
 arena.tail=0xabcd4321;native_metadata_assign(&cache,arena.bytes);
 for(unsigned i=0;i<sizeof(reference);i++)reference[i]=(unsigned char)(i*73u+i/199u);
 for(unsigned i=0;i<10000;i++){
  unsigned n=1+rnd()%sizeof(out),at=rnd()%(sizeof(reference)-n+1);
  if(i%71==0)native_metadata_forget(&cache);
  if(i%83==0)cache.clock=UINT32_MAX;
  if(i%67==0){native_metadata_forget(&cache);fail_reads=1;
   assert(!native_metadata_read(&cache,sizeof(reference),at,out,n,read_at,NULL));
   assert(!cache.valid);}
  assert(native_metadata_read(&cache,sizeof(reference),at,out,n,read_at,NULL));
  assert(!memcmp(out,reference+at,n));unsigned before=reads;
  assert(native_metadata_read(&cache,sizeof(reference),at,out,n,read_at,NULL));
  assert(before==reads&&!memcmp(out,reference+at,n)&&arena.tail==0xabcd4321);
 }
 assert(native_metadata_read(&cache,sizeof(reference),sizeof(reference)-1,out,1,read_at,NULL));assert(out[0]==reference[sizeof(reference)-1]);
 assert(!native_metadata_read(&cache,sizeof(reference),sizeof(reference)-1,out,2,read_at,NULL));
 assert(!native_metadata_read(&cache,sizeof(reference),UINT32_MAX,out,1,read_at,NULL));
 native_metadata_assign(&cache,NULL);assert(!cache.valid&&!native_metadata_read(&cache,sizeof(reference),0,out,1,read_at,NULL));
 printf("{\"random_requests\":10000,\"immediate_hits\":10000,\"failed_partial_reads_recovered\":150,\"arena_guards\":true,\"clock_overflow_and_rebind\":true,\"ASan_UBSan\":true}\n");
}
