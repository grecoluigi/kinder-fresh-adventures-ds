#include "collision.h"
#include <stddef.h>
#include <stdbool.h>
static const CollisionMap *streamed_map;
static unsigned resident_layer;
static CollisionCellReader streamed_reader;
static void *reader_context;
void collision_bind_layer(const CollisionMap *map,unsigned layer,CollisionCellReader reader,void *context){
 streamed_map=map;resident_layer=layer;streamed_reader=reader;reader_context=context;
}
void collision_unbind_layer(const CollisionMap *map){
 if(streamed_map==map){streamed_map=NULL;streamed_reader=NULL;reader_context=NULL;}
}
const uint8_t *collision_cell(const CollisionMap *map,unsigned layer,unsigned x,unsigned y){
 if(!map||layer>=map->layers||x>=map->width||y>=map->height)return NULL;
 if(map==streamed_map){
  if(layer==resident_layer)return map->tiles+((size_t)y*map->width+x)*3;
  return streamed_reader?streamed_reader(reader_context,layer,x,y):NULL;
 }
 return map->tiles?map->tiles+((size_t)(layer*map->height+y)*map->width+x)*3:NULL;
}

uint8_t collision_point(const CollisionMap *map, unsigned layer, int x, int y)
{
    if (x < 0 || y < 0 || x >= map->width * map->tile_width ||
        y >= map->height * map->tile_height) return 1;
    if (layer >= map->layers) return 0;
    bool native_tiles=map->tile_width==32&&map->tile_height==32;
    const uint8_t *tile=collision_cell(map,layer,native_tiles?(unsigned)x>>5:(unsigned)x/map->tile_width,
        native_tiles?(unsigned)y>>5:(unsigned)y/map->tile_height);
    if(!tile)return 0;
    unsigned packed = tile[1] | ((unsigned)tile[2] << 8);
    if (packed == 0xffff) return 0;
    uint8_t result = (tile[0] & 0x80) ? 2 : 0;
    if (!(tile[0] & 0x20)) return result;
    unsigned dx = native_tiles ? (unsigned)x & 31u : (unsigned)x % map->tile_width;
    unsigned dy = native_tiles ? (unsigned)y & 31u : (unsigned)y % map->tile_height;
    if ((packed >> 9) & 2) return result | (dy == 0 ? 4 : 0);
    unsigned bank = tile[0] & 7;
    if (bank >= 4) return result;
    const CollisionAtlas *atlas = &map->atlas[bank];
    if (!atlas->bits || !atlas->width) return result;
    unsigned columns = native_tiles ? atlas->width >> 5 : atlas->width / map->tile_width;
    if (!columns) return result;
    unsigned index = packed & 0x1ff;
    if (tile[0] & 8) dx = map->tile_width - 1 - dx;
    if (tile[0] & 16) dy = map->tile_height - 1 - dy;
    /* All48 shipped map/bank selections use640x480 atlases (20 columns).
     * Constant division compiles to integer multiply/shift on ARM9. */
    unsigned column=columns==20?index%20:index%columns;
    unsigned row=columns==20?index/20:index/columns;
    unsigned sx = native_tiles ? (column << 5) + dx : column * map->tile_width + dx;
    unsigned sy = native_tiles ? (row << 5) + dy : row * map->tile_height + dy;
    if (sx >= atlas->width || sy >= atlas->height) return result;
    unsigned pixel = sy * atlas->width + sx;
    return result | ((atlas->bits[pixel >> 3] >> (pixel & 7)) & 1);
}
