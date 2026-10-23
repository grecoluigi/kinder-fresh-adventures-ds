#ifndef KINDER_HUD_H
#define KINDER_HUD_H
#include <stdbool.h>
#include <stdint.h>
typedef struct { int32_t score,health,ammo,actor,shot_variant,boss,boss_energy,world; int16_t letters[6]; } HudState;
typedef struct { int32_t resource,frame; } HudCommand;
/* Original 4089c0 draw order. Resources 0 base, 1 boss base, 2..7 letters,
 * 8 health, 9/10 shots, 11 actor, 12 boss energy, 13 boss portrait, 14 score. */
unsigned hud_layout(const HudState *state,HudCommand commands[16]);
bool hud_open(void);
void hud_close(void);
/* Load one static, pre-darkened backdrop at world opening; no draw-time IO. */
bool hud_set_world_background(unsigned world);
/* Invisible rectangular touch target around the displayed switch portrait. */
bool hud_switch_hit(int x,int y);
/* Clears the screen and draws the larger DS bottom layout. */
void hud_draw_bottom(uint16_t pixels[256*192],const HudState *state);
void hud_draw(uint16_t pixels[256*192],const HudState *state);
#endif
