#include "geometry.h"
#include <stddef.h>
_Static_assert(sizeof(GeometryRect) == 32, "native rectangle stride");
_Static_assert(offsetof(GeometryRect, object_index) == 24, "native object index");
uint32_t geometry_query(const GeometryRect *r, int32_t count,
                       int32_t x, int32_t y, uint32_t mode) {
    uint32_t mask = (mode == 3 || mode == 11) ? 6 :
                    (mode == 5 || mode == 13) ? 2 : 0;
    if (!r || !mask) return 0;
    for (int32_t i = count; i > 0;) {
        --i;
        if ((r[i].flags & mask) && x >= r[i].left && x < r[i].right &&
            y >= r[i].top && y < r[i].bottom)
            return 0x08000000u | ((uint32_t)i + 1);
    }
    return 0;
}
int32_t geometry_build(GeometryRect *out, int32_t capacity,
                       const GeometryObject *objects, int32_t count,
                       int32_t left, int32_t top, int32_t right, int32_t bottom) {
    int32_t n = 0;
    for (int32_t i = count; i > 0;) {
        const GeometryObject *o = &objects[--i];
        if (!o->active || !o->solid) continue;
        int32_t l = (int32_t)o->x + o->align_x, t = (int32_t)o->y + o->align_y;
        int32_t r = l + o->width, b = t + o->height;
        if (l >= right || r <= left || t >= bottom || b <= top) continue;
        if (n >= capacity) break;
        uint32_t flags;
        if (o->id == 76 || o->id == 78 || o->id == 86 || o->id == 87) {
            t += o->top_trim; flags = 2;
        } else if (o->id == 83) {
            flags = 2;
        } else {
            t += o->top_trim; b = t + 1; flags = 4;
        }
        out[n++] = (GeometryRect){l, r, t, b, flags, 0, o->object_index, 0};
    }
    return n;
}
