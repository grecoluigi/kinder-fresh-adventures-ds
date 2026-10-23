#ifndef KINDER_MENU_GRAPHICS_H
#define KINDER_MENU_GRAPHICS_H
#include <stdint.h>
/* -1 is the normal menu,0..5 are original focus states. One aligned screen is
 * decoded on focus change; no filesystem I/O and no graphical differences. */
const uint16_t *menu_graphics_pixels(int focus);
#endif
