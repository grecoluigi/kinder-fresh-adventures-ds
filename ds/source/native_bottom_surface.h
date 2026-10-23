#ifndef KINDER_NATIVE_BOTTOM_SURFACE_H
#define KINDER_NATIVE_BOTTOM_SURFACE_H
#include "native_bottom.h"
typedef enum {NATIVE_BOTTOM_UNSET,NATIVE_BOTTOM_RGB,NATIVE_BOTTOM_INDEXED,NATIVE_BOTTOM_KEYBOARD} NativeBottomMode;
/* visible_rgb: the RGB bitmap of the current mapping is initialised and shown. */
typedef struct {NativeBottomMode mode;int background;unsigned scenery_epoch;bool visible_rgb;} NativeBottomSurface;
/* Caller owns the main scene freeze/reload. C-bank remapping is refused while
 * main BG1 is enabled. Every remapping changes scenery_epoch: native scenery
 * and C-tail caches must be invalidated/rebuilt before main BG1 is shown. */
bool native_bottom_surface_rgb(NativeBottomSurface *s,const uint16_t *pixels,size_t words);
bool native_bottom_surface_hud(NativeBottomSurface *s,const NativeBottom *hud,const uint8_t *pixels,size_t bytes);
bool native_bottom_surface_keyboard(NativeBottomSurface *s);
void native_bottom_surface_end_keyboard(NativeBottomSurface *s);
#endif
