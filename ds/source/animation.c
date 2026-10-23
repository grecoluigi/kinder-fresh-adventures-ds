#include "animation.h"
#include <stddef.h>
#include <string.h>

_Static_assert(sizeof(Animation) == 100, "Original animation-instance size");
_Static_assert(offsetof(Animation, repeats) == 0x24, "Original repetition offset");
_Static_assert(offsetof(Animation, callback_handle) == 0x60, "Original callback offset");

/* 0x40adc0; resource count is supplied instead of reading an x86 pointer. */
void animation_init(Animation *a, uint32_t resource, int frame_count, int x, int y)
{
    memset(a, 0, sizeof(*a));
    a->resource = resource; a->x = x; a->y = y;
    a->repeats = -1; a->mode = 1;
    if (resource) a->last = frame_count - 1;
    a->delay = a->timer = 2;
}

/* 0x40ae10; frame delay -1 freezes progression but still invokes callbacks. */
void animation_tick(Animation *a, AnimationCallback callback, void *context)
{
    if (callback) callback(a, context);
    if (a->delay == -1) return;
    if (a->timer != 0) { --a->timer; return; }
    a->timer = a->delay;
    switch (a->mode) {
    case 1:
        if (++a->frame <= a->last) return;
        if (a->repeats == 0) { a->frame = a->last; return; }
        if (a->repeats > 0) --a->repeats;
        a->frame = a->first;
        break;
    case 2:
        if (--a->frame >= a->first) return;
        if (a->repeats == 0) { a->frame = a->first; return; }
        if (a->repeats > 0) --a->repeats;
        a->frame = a->last;
        break;
    case 3:
        if (++a->frame <= a->last) return;
        if (a->repeats == 0) { a->frame = a->last; return; }
        if (a->repeats > 0) --a->repeats;
        a->frame -= 2;
        a->mode = 4;
        if (a->frame < a->first) a->frame = a->first;
        break;
    case 4:
        if (--a->frame >= a->first) return;
        if (a->repeats == 0) { a->frame = a->first; return; }
        if (a->repeats > 0) --a->repeats;
        a->frame += 2;
        if (a->frame > a->last) a->frame = a->last;
        a->mode = 3;
        break;
    default: break;
    }
}
