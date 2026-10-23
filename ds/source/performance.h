#ifndef KINDER_PERFORMANCE_H
#define KINDER_PERFORMANCE_H
#include <stdint.h>
uint32_t performance_now(void);
void performance_frame(void);
void performance_rendered_frame(void);
void performance_game_ticks(unsigned ticks);
void performance_audio(uint32_t ticks);
void performance_update(uint32_t ticks);
void performance_render(uint32_t ticks);
void performance_transfer(uint32_t ticks);
void performance_draw(uint16_t *pixels,unsigned reads,int state);
#endif
