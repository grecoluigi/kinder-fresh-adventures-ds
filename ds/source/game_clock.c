#include "game_clock.h"
void game_clock_reset(GameClock *c,uint64_t now){c->last=now;c->accumulated=0;}
void game_clock_advance(GameClock *c,uint64_t now){
 if(now<c->last){game_clock_reset(c,now);return;}
 c->accumulated+=(now-c->last)*60;c->last=now;
}
bool game_clock_take_tick(GameClock *c,uint32_t frequency){
 if(!frequency||c->accumulated<frequency)return false;
 c->accumulated-=frequency;return true;
}

uint64_t game_clock_limit_backlog(GameClock *c,uint32_t frequency,uint32_t max_ticks){
 if(!frequency||c->accumulated<((uint64_t)max_ticks+1)*frequency)return 0;
 uint64_t whole=c->accumulated/frequency,fraction=c->accumulated%frequency;
 c->accumulated=(uint64_t)max_ticks*frequency+fraction;
 return whole-max_ticks;
}
