/* Time public stdio calls, including their backend work. Never drive gameplay.
 * Nested stdio calls belong to the outer call; do not count their time twice. */
#if defined(__NDS__) || defined(KINDER_STORAGE_PROFILE_TEST)
#include "storage_profile.h"
#include <stdio.h>
#ifdef __NDS__
#include <nds/system_counter.h>
static uint32_t now(void){return (uint32_t)systemCounterGetTicks();}
static uint32_t usec(uint32_t ticks){return systemCounterTicksToUsec(ticks);}
#else
extern uint32_t storage_profile_test_now(void);
static uint32_t now(void){return storage_profile_test_now();}
static uint32_t usec(uint32_t ticks){return ticks;}
#endif
volatile uint32_t storage_frame_seek_us,storage_frame_read_us;
volatile uint32_t storage_frame_seek_calls,storage_frame_read_calls,storage_frame_read_bytes;
static volatile uint32_t seek_ticks,read_ticks,seek_calls,read_calls,read_bytes;
static uint32_t last_seek_ticks,last_read_ticks,last_seek_calls,last_read_calls,last_read_bytes;
static unsigned depth;
volatile unsigned storage_profile_enabled;
void storage_profile_enable(bool enabled){
 storage_profile_enabled=enabled;
 last_seek_ticks=seek_ticks;last_read_ticks=read_ticks;last_seek_calls=seek_calls;last_read_calls=read_calls;last_read_bytes=read_bytes;
 storage_frame_seek_us=storage_frame_read_us=storage_frame_seek_calls=storage_frame_read_calls=storage_frame_read_bytes=0;
}
extern int __real_fseek(FILE *file,long offset,int whence);
extern size_t __real_fread(void *out,size_t size,size_t count,FILE *file);
int __wrap_fseek(FILE *file,long offset,int whence){
 if(!storage_profile_enabled)return __real_fseek(file,offset,whence);
 unsigned outer=depth++==0;uint32_t start=outer?now():0;
 int result=__real_fseek(file,offset,whence);
 if(outer){seek_ticks+=now()-start;seek_calls++;}
 depth--;return result;
}
size_t __wrap_fread(void *out,size_t size,size_t count,FILE *file){
 if(!storage_profile_enabled)return __real_fread(out,size,count,file);
 unsigned outer=depth++==0;uint32_t start=outer?now():0;
 size_t result=__real_fread(out,size,count,file);
 if(outer){read_ticks+=now()-start;read_calls++;read_bytes+=(uint32_t)(size*result);}
 depth--;return result;
}
void storage_profile_snapshot(void){
 if(!storage_profile_enabled)return;
 uint32_t s=seek_ticks,r=read_ticks,sc=seek_calls,rc=read_calls,b=read_bytes;
 storage_frame_seek_us=usec(s-last_seek_ticks);storage_frame_read_us=usec(r-last_read_ticks);
 storage_frame_seek_calls=sc-last_seek_calls;storage_frame_read_calls=rc-last_read_calls;storage_frame_read_bytes=b-last_read_bytes;
 last_seek_ticks=s;last_read_ticks=r;last_seek_calls=sc;last_read_calls=rc;last_read_bytes=b;
}
#endif
