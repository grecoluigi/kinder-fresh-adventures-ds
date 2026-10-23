#ifndef KINDER_PLAYER_GRAPHICS_H
#define KINDER_PLAYER_GRAPHICS_H
#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>
bool player_graphics_open(void);
void player_graphics_close(void);
uint32_t player_graphics_elapsed_us(void);
/* Body origin and camera are in original source pixels.
 * facing0 mirrors horizontally, matching native animation mode2. KFP4 stores
 * both offline-scaled facing geometries; pixels live in native GPU pages. */
bool player_graphics_draw(uint16_t *pixels,int character,int frame,int facing,int body_x,int body_y,int camera_x,int camera_y);
/* Conservative clipped rectangle written by the most recent draw; empty on failure. */
void player_graphics_last_bounds(int bounds[4]);
/* Dedicated native source arena, valid until player_graphics_close. */
void *player_graphics_native_cache(unsigned *bytes);
#endif
