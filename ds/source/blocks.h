#ifndef KINDER_BLOCKS_H
#define KINDER_BLOCKS_H
#include "entities.h"
typedef int (*BlockTile)(int layer,int x,int y,void *context);
typedef void (*BlockProjectiles)(int x,int y,int width,int height,unsigned mode,void *context);
typedef struct {
 int16_t width,height,first,last;
 BlockTile tile;
 BlockProjectiles projectiles;
 void (*sound)(int channel,int sample,int repeat,void *context);
 void *context;
 uint8_t *switch_flags; /* 256 entries; native index is raw byte42. */
 int switch_sample;
} BlockEnvironment;
/* Native414e50: IDs76/78/86/87. Caller advances animation separately.
 * bool reports supported ID; original callback returns0 (suppresses default). */
bool block_physical_tick(GameEntity *entity,const BlockEnvironment *environment);
/* Native4151f0: ID83, animation-controlled switch; original return0. */
bool block_switch_tick(GameEntity *entity,const BlockEnvironment *environment);
/* Native430d90 default movement. Event callback observes native0x20/0x10
 * horizontal endpoints; no body carrying or terrain collision is performed. */
void block_default_movement(GameEntity *entity,void (*event)(GameEntity*,int,void*),void *context);
#endif
