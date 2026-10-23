#ifndef KINDER_ANIMATION_H
#define KINDER_ANIMATION_H
#include <stdint.h>

/* Native 100-byte animation-instance layout; resource/callback handles remain
 * opaque identifiers. Actual asset access and callbacks belong to the runtime. */
typedef struct {
    uint32_t resource, opaque_04, opaque_08;
    int32_t x, y;
    uint32_t opaque_14, opaque_18, opaque_1c, opaque_20;
    int32_t repeats, mode, frame, first, last, timer, delay;
    uint32_t opaque_40, opaque_44, opaque_48, opaque_4c, opaque_50,
             opaque_54, opaque_58, opaque_5c, callback_handle;
} Animation;
typedef void (*AnimationCallback)(Animation *animation, void *context);
void animation_init(Animation *animation, uint32_t resource, int frame_count, int x, int y);
void animation_tick(Animation *animation, AnimationCallback callback, void *context);
#endif
