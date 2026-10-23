#include "body.h"
#include <stddef.h>

_Static_assert(offsetof(GameBody, motion) == 0x24, "Original body motion offset");
_Static_assert(offsetof(GameBody, slope_limit_fixed) == 0x6c, "Original slope limit offset");
_Static_assert(sizeof(GameBody) == 0x84, "Original body layout");

bool body_map_probe(void *context, int layer, int x, int y, unsigned mode)
{
    static const unsigned masks[14] = {0,0,0,7,0,3,0,0,0,0,0,5,0,1};
    if (mode >= 14 || layer < 0) return false;
    return (collision_point(context, (unsigned)layer, x, y) & masks[mode]) != 0;
}

/* 0x431ed0: the player's state machine queries its origin using vertical mode. */
bool body_has_contact(const GameBody *body, BodyProbe probe, void *context)
{
    if ((uint32_t)body->kind > 1) return false;
    unsigned mode = ((unsigned)body->kind & 1) | (body->motion.vy < 0 ? 4 : 2);
    return probe(context, body->layer, body->motion.x / 4096, body->motion.y / 4096, mode);
}

/* 0x432110: sample a vertical side from top to bottom at the stored spacing. */
static bool side(BodyProbe probe, void *context, int layer, int x, int y,
                 int stride, int count, unsigned mode)
{
    y -= stride * count;
    while (count != 0) {
        y += stride;
        if (probe(context, layer, x, y, mode)) return true;
        --count;
    }
    return false;
}

/* 0x431f50: move along the terrain contour, one source pixel per iteration. */
static unsigned contour(BodyProbe probe, void *context, int layer, int *x, int *y,
                        int delta, int limit, unsigned mode)
{
    unsigned result = 0;
    int step = delta < 0 ? -1 : 1;
    if (delta < 0) delta = -delta;
    while (delta-- != 0) {
        int next_x = *x + step, sy = *y;
        bool current = probe(context, layer, *x, sy, mode);
        bool next = probe(context, layer, next_x, sy, mode);
        if (current) result |= 4;
        if (current && next) {
            int remaining = limit;
            --sy;
            while (remaining >= 0 && probe(context, layer, next_x, sy, mode)) {
                --sy; --remaining;
            }
            if (remaining < 0) return result;
            *x = next_x; *y = sy + 1;
        } else if (current) {
            int remaining = limit - 1;
            ++sy;
            while (remaining >= 0 && !probe(context, layer, next_x, sy, mode)) {
                ++sy; --remaining;
            }
            *x = next_x;
            if (remaining >= 0) *y = sy;
        } else if (next) {
            int remaining = limit;
            --sy;
            while (remaining >= 0 && probe(context, layer, next_x, sy, mode)) {
                --sy; --remaining;
            }
            if (remaining < 0) return result;
            result |= 4;
            *x = next_x; *y = sy + 1;
        } else {
            *x = next_x;
        }
        result |= 1;
    }
    return result | 2;
}

void body_step(GameBody *body, BodyProbe probe, void *context)
{
    if ((uint32_t)body->kind > 1) return;
    PhysicsBody *m = &body->motion;
    int x = m->x / 4096, y = m->y / 4096;
    physics_integrate(m);
    int target_x = m->x / 4096, target_y = m->y / 4096;
    unsigned mode = (unsigned)body->kind & 1;
    if (target_y < y) {
        mode |= 4;
        y -= body->height; target_y -= body->height;
        while (y != target_y && !probe(context, body->layer, x, y, mode)) --y;
        y += body->height; target_y += body->height;
    } else {
        mode |= 2;
        while (y != target_y && !probe(context, body->layer, x, y, mode)) ++y;
    }
    if (y != target_y) { m->vy = 0; m->y = y * 4096; }
    if (x == target_x) return;
    int step = x < target_x ? 1 : -1;
    unsigned adjust_y = 0;
    do {
        unsigned side_mode = ((unsigned)body->kind & 1) | 4;
        if (side(probe, context, body->layer, x + step * body->half_width,
                 y - body->probe_offset, body->probe_stride, body->probe_count, side_mode)) break;
        unsigned result = contour(probe, context, body->layer, &x, &y,
                                  step, body->slope_limit_fixed / 4096, mode);
        adjust_y |= result & 4;
        if (!(result & 2)) break;
    } while (x != target_x);
    if (x != target_x) { m->x = x * 4096; m->vx = 0; }
    if (adjust_y) { m->y = y * 4096; m->vy = 0; }
}
