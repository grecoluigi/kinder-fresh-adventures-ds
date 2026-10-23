#ifndef KINDER_NATIVE_BOTTOM_H
#define KINDER_NATIVE_BOTTOM_H
#include "hud.h"
#include <stddef.h>
typedef struct {uint32_t offset;uint16_t width,height;int16_t x,y;uint16_t resource,frame;} NativeBottomPatch;
typedef struct {
 NativeBottomPatch patches[128];unsigned count,bytes,world;
 uint8_t *data,*background;uint16_t palette[256];bool ready;
} NativeBottom;
/* Zero-initialize before use. Failed loads preserve the previous valid state. */
bool native_bottom_open(NativeBottom *state,const char *path);
bool native_bottom_background(NativeBottom *state,const char *path,unsigned world);
void native_bottom_close(NativeBottom *state);
/* WRAM output only: VRAM byte stores are not supported. Transfer in halfwords
 * at publication. This module never remaps VRAM or changes visible palettes. */
bool native_bottom_draw(const NativeBottom *state,uint8_t *pixels,size_t bytes,const HudState *hud);
bool native_bottom_switch_hit(const NativeBottom *state,int x,int y);
#endif
