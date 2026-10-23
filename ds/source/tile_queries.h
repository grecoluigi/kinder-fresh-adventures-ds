#ifndef KINDER_TILE_QUERIES_H
#define KINDER_TILE_QUERIES_H
#include "collision.h"
int map_tile_solid(const CollisionMap *map,unsigned layer,int x,int y);
unsigned map_tile_property(const CollisionMap *map,unsigned layer,int x,int y);
#endif
