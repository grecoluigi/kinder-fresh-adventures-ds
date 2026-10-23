#ifndef KINDER_FRAME_TRANSFER_H
#define KINDER_FRAME_TRANSFER_H
#include <stdint.h>
/* Both buffers must be32-byte aligned. Writes VRAM in full words only. */
void frame_transfer(uint16_t *vram,const uint16_t *pixels);
/* Exact foreground transfer, omitting only zero rows outside both the current
 * image and the preceding published image. CPU rendering still clears and
 * draws a full frame. Call forget before external writes to the destination;
 * ordinary frame_transfer calls already forget automatically. */
void frame_transfer_foreground(uint16_t *vram,const uint16_t *pixels);
void frame_forget_foreground_transfer(void);
/* Freeze the currently displayed bitmap layers before their resources change.
 * Background is256x256; its visible192rows wrap horizontally at offset. */
void frame_snapshot_background(uint16_t *pixels,const volatile uint16_t *foreground,
                               const volatile uint16_t *background,unsigned offset);
void frame_skip_foreground_transfer(void);
#endif
