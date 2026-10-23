#ifndef KINDER_WORLD_H
#define KINDER_WORLD_H
#include <stdbool.h>
#include <stdint.h>
bool world_open(unsigned world);
/* Explicit tutorial/main stage for restored progression and bounded checks. */
bool world_open_stage(unsigned world,bool tutorial);
const char *world_map_name(void);
int world_transition_target(void);
void world_close(void);
bool world_tick(unsigned original_input);
bool world_render(uint16_t *pixels);
int world_player_state(void);
bool world_finished(void);
unsigned world_result_world(void);
int32_t world_result_score(void);
bool world_render_hud(uint16_t *pixels,bool force);
#endif
