#include "physics.h"
#include <stddef.h>
#include <string.h>

_Static_assert(sizeof(PhysicsBody) == 72, "Original integrator layout");
_Static_assert(offsetof(PhysicsBody, friction_x) == 0x20, "Original friction offset");
_Static_assert(offsetof(PhysicsBody, min_vx) == 0x38, "Original velocity bounds offset");

/* Preserve x86 wrap without C signed-overflow behavior. */
static int32_t from_bits(uint32_t bits)
{
    int32_t value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}
static int32_t add(int32_t a, int32_t b)
{
    return from_bits((uint32_t)a + (uint32_t)b);
}
static int32_t friction(int32_t velocity, int32_t amount)
{
    if (velocity > 0) {
        velocity = from_bits((uint32_t)velocity - (uint32_t)amount);
        if (velocity < 0) velocity = 0;
    } else {
        velocity = add(velocity, amount);
        if (velocity > 0) velocity = 0;
    }
    return velocity;
}
void physics_integrate(PhysicsBody *body)
{
    body->vx = friction(add(body->vx, body->ax), body->friction_x);
    body->vy = friction(add(body->vy, add(body->ay, body->gravity)), body->friction_y);
    if (body->vx < body->min_vx) body->vx = body->min_vx;
    if (body->vx > body->max_vx) body->vx = body->max_vx;
    if (body->vy < body->min_vy) body->vy = body->min_vy;
    if (body->vy > body->max_vy) body->vy = body->max_vy;
    body->x = add(body->x, body->vx);
    body->y = add(body->y, body->vy);
    if (body->x < body->min_x) { body->x = body->min_x; body->vx = 0; }
    if (body->x > body->max_x) { body->x = body->max_x; body->vx = 0; }
    if (body->y < body->min_y) { body->y = body->min_y; body->vy = 0; }
    if (body->y > body->max_y) { body->y = body->max_y; body->vy = 0; }
}
