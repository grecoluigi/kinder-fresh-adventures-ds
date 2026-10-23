#ifndef KINDER_BODY_H
#define KINDER_BODY_H
#include "physics.h"
#include "collision.h"
#include <stdbool.h>

/* Native body layout through 0x80. Opaque fields retain their original slots. */
typedef struct {
    int32_t kind, opaque_04, layer, contacts;
    int32_t platform_dx, platform_dy, opaque_18, opaque_1c, opaque_20;
    PhysicsBody motion;
    int32_t slope_limit_fixed, height, half_width, probe_offset, probe_count, probe_stride;
} GameBody;
typedef bool (*BodyProbe)(void *context, int layer, int x, int y, unsigned mode);

/* Recovered 0x432350 tick; callback includes tile and dynamic-object collision. */
void body_step(GameBody *body, BodyProbe probe, void *context);
bool body_has_contact(const GameBody *body, BodyProbe probe, void *context);
bool body_map_probe(void *context, int layer, int x, int y, unsigned mode);
#endif
