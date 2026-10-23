#ifndef KINDER_CREDITS_H
#define KINDER_CREDITS_H
#include <stdbool.h>
#include <stdint.h>
#define CREDITS_PAGES 4u
typedef struct { unsigned page;bool active; } CreditsState;
void credits_begin(CreditsState *state);
/* Return whether page/active state changed; back takes precedence over next. */
bool credits_step(CreditsState *state,bool next,bool back);
/* Original Credit1..4 images, proportionally sampled for a256x192 DS screen. */
bool credits_draw(uint16_t pixels[256*192],unsigned page);
#endif
