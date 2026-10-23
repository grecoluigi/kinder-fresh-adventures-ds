#ifndef KINDER_GAME_CLOCK_H
#define KINDER_GAME_CLOCK_H
#include <stdbool.h>
#include <stdint.h>
typedef struct { uint64_t last, accumulated; } GameClock;
void game_clock_reset(GameClock *clock,uint64_t now);
void game_clock_advance(GameClock *clock,uint64_t now);
bool game_clock_take_tick(GameClock *clock,uint32_t frequency);
/* Retain at most max_ticks whole updates plus the existing fractional tick.
 * Normal timing is unchanged. Returns discarded whole ticks after overload. */
uint64_t game_clock_limit_backlog(GameClock *clock,uint32_t frequency,uint32_t max_ticks);
#endif
