#include "performance.h"
#include "storage_profile.h"
#include <nds/system_counter.h>
#include <stdio.h>
#include <malloc.h>
#include <unistd.h>
#include "player_graphics.h"
#include "scene.h"
#include "game_save.h"
static uint32_t period,frames,fps,game_ticks,updates_per_second,audio,update,render,transfer;
/* Cumulative telemetry for automated input/replay probes; never drives gameplay. */
static volatile uint32_t performance_total_frames,performance_total_updates,performance_total_renders;
void performance_rendered_frame(void){performance_total_renders++;}
uint32_t performance_now(void){return (uint32_t)systemCounterGetTicks();}
void performance_frame(void){
 uint32_t now=performance_now();if(!period)period=now;
 performance_total_frames++;frames++;uint32_t elapsed=now-period;
 if(elapsed>=BUS_CLOCK/64){fps=(uint32_t)((uint64_t)frames*(BUS_CLOCK/64)/elapsed);updates_per_second=(uint32_t)((uint64_t)game_ticks*(BUS_CLOCK/64)/elapsed);game_ticks=0;frames=0;period=now;}
}
void performance_game_ticks(unsigned ticks){game_ticks+=ticks;performance_total_updates+=ticks;}
void performance_audio(uint32_t ticks){audio=systemCounterTicksToUsec(ticks);}
void performance_update(uint32_t ticks){update=systemCounterTicksToUsec(ticks);}
void performance_render(uint32_t ticks){render=systemCounterTicksToUsec(ticks);}
void performance_transfer(uint32_t ticks){transfer=systemCounterTicksToUsec(ticks);storage_profile_snapshot();}
static const uint8_t digits[10][7]={
 {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},{30,1,1,14,1,1,30},
 {2,6,10,18,31,2,2},{31,16,16,30,1,1,30},{14,16,16,30,17,17,14},{31,1,2,4,8,8,8},
 {14,17,17,14,17,17,14},{14,17,17,15,1,1,14}};
static const uint8_t letters[15][7]={{31,16,16,30,16,16,16},{14,17,17,31,17,17,17},{17,17,17,17,17,17,14},{30,17,17,30,20,18,17},{14,4,4,4,4,4,14},{30,17,17,30,16,16,16},{14,17,16,23,17,17,14},{31,4,4,4,4,4,4},{14,17,17,17,17,17,14},{15,16,16,14,1,1,30},{14,17,16,16,16,17,14},{17,17,17,17,17,10,4},{30,17,17,30,17,17,30},{17,17,17,31,17,17,17},{17,17,17,21,21,21,10}};
static unsigned long free_heap_kib(void){
 extern char __eheap_end;
 uintptr_t end=(uintptr_t)&__eheap_end,current=(uintptr_t)sbrk(0);
 struct mallinfo info=mallinfo();
 size_t available=info.fordblks+(current<end?end-current:0);
 return (unsigned long)(available/1024);
}
void performance_draw(uint16_t *pixels,unsigned reads,int state){
 char text[160];snprintf(text,sizeof(text),"F %lu V %lu A %lu U %lu R %lu G %lu I %u P %d",(unsigned long)fps,(unsigned long)updates_per_second,(unsigned long)(audio/1000),(unsigned long)(update/1000),(unsigned long)(render/1000),(unsigned long)(player_graphics_elapsed_us()/1000),reads,state);
 const SceneRenderStats *stats=scene_render_stats();
 size_t first_length=0;while(text[first_length])first_length++;
 snprintf(text+first_length,sizeof(text)-first_length,"\nT %lu W %u S %lu C %lu B %lu H %lu",(unsigned long)(stats->tiles_us/1000),game_save_status(),(unsigned long)(stats->setup_us/1000),(unsigned long)(stats->callback_us/1000),(unsigned long)(transfer/1000),free_heap_kib());
 first_length=0;while(text[first_length])first_length++;
 snprintf(text+first_length,sizeof(text)-first_length,"\nIO %lu S %lu R %lu I %lu",
  (unsigned long)((storage_frame_seek_us+storage_frame_read_us)/1000u),
  (unsigned long)(storage_frame_seek_us/1000u),(unsigned long)(storage_frame_read_us/1000u),(unsigned long)storage_frame_read_calls);
 for(int i=0;i<256*27;i++)pixels[i]=0x8000;
 unsigned column=0,line=0;
 for(unsigned i=0;text[i]&&line<3;i++){
  if(text[i]=='\n'){line++;column=0;continue;}
  unsigned current_column=column++;if(current_column>=42)continue;
  const uint8_t *glyph=NULL;char ch=text[i];
  if(ch>='0'&&ch<='9')glyph=digits[ch-'0'];
  else {const char *keys="FAURIPGTOSCVBHW";for(unsigned j=0;j<15;j++)if(ch==keys[j])glyph=letters[j];}
  if(!glyph)continue;
  for(int y=0;y<7;y++)for(int x=0;x<5;x++)if(glyph[y]&(16>>x))pixels[(y+1+line*9)*256+current_column*6+x]=0xffff;
 }
}
