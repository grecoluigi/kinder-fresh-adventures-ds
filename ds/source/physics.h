#ifndef KINDER_PHYSICS_H
#define KINDER_PHYSICS_H
#include <stdint.h>

/* Original 0x431bf0 argument layout, beginning at body + 0x24.
 * Values use 12 fractional bits. Collision is handled separately. */
typedef struct {
    int32_t x, y, vx, vy, ax, ay, gravity, reserved;
    int32_t friction_x, friction_y;
    int32_t min_x, max_x, min_y, max_y;
    int32_t min_vx, max_vx, min_vy, max_vy;
} PhysicsBody;
void physics_integrate(PhysicsBody *body);
#endif
