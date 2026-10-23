#include "game_clock.h"
#include <assert.h>
#include <stdio.h>
static unsigned take(GameClock *c,unsigned limit){unsigned count=0;while(count<limit&&game_clock_take_tick(c,60000))count++;return count;}
int main(void){
 GameClock c;unsigned ticks=0;game_clock_reset(&c,0);
 for(uint64_t now=1000;now<=60000;now+=1000){game_clock_advance(&c,now);ticks+=take(&c,8);}assert(ticks==60);
 game_clock_reset(&c,0);ticks=0;
 for(uint64_t now=4000;now<=60000;now+=4000){game_clock_advance(&c,now);ticks+=take(&c,8);}assert(ticks==60);
 game_clock_reset(&c,0);game_clock_advance(&c,12000);assert(take(&c,8)==8);assert(take(&c,8)==4);assert(take(&c,8)==0);
 game_clock_reset(&c,500000);game_clock_advance(&c,501000);assert(take(&c,8)==1);
 game_clock_reset(&c,0);ticks=0;uint64_t now=0;const unsigned intervals[]={17,8,71,29,125};
 for(unsigned i=0;now<60000;i++){uint64_t dt=intervals[i%5]*60;if(dt>60000-now)dt=60000-now;now+=dt;game_clock_advance(&c,now);ticks+=take(&c,8);}
 ticks+=take(&c,100);assert(ticks==60);
 puts("60 Hz updates remain independent of render cadence; backlog and pause checks pass.");
}
