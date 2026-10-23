#ifndef KINDER_COLLISION_H
#define KINDER_COLLISION_H
#include <stdint.h>

typedef struct {
    uint16_t width, height;
    const uint8_t *bits; /* Row-major, LSB first; one bit per original RGB565 pixel. */
} CollisionAtlas;
typedef struct {
    uint16_t width, height, tile_width, tile_height, layers;
    const uint8_t *tiles; /* Full layer-major cells, or the registered resident layer. */
    CollisionAtlas atlas[4]; /* Already selected by the W02 bank-selection header. */
} CollisionMap;
typedef const uint8_t *(*CollisionCellReader)(void *context,unsigned layer,unsigned x,unsigned y);
/* One streamed scene may register its resident layer and reader; independent
 * full-array maps retain the original ABI and address calculation. */
void collision_bind_layer(const CollisionMap *map,unsigned layer,CollisionCellReader reader,void *context);
void collision_unbind_layer(const CollisionMap *map);
const uint8_t *collision_cell(const CollisionMap *map,unsigned layer,unsigned x,unsigned y);

/* Original 0x434240 output bits; names deliberately avoid unproven semantics.
 * Directional acceptance of these bits belongs to the separate body solver. */
uint8_t collision_point(const CollisionMap *map, unsigned layer, int x, int y);
#endif
