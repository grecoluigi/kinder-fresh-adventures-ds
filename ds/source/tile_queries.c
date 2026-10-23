#include "tile_queries.h"
#include <stddef.h>
static const uint8_t *cell(const CollisionMap *m,unsigned layer,int x,int y){
 if(layer>=m->layers||x<0||y<0||x>=m->width*m->tile_width||y>=m->height*m->tile_height)return NULL;
 return collision_cell(m,layer,m->tile_width==32?(unsigned)x>>5:(unsigned)x/m->tile_width,
  m->tile_height==32?(unsigned)y>>5:(unsigned)y/m->tile_height);
}
int map_tile_solid(const CollisionMap *m,unsigned layer,int x,int y){
 if(x<0||y<0||x>=m->width*m->tile_width||y>=m->height*m->tile_height)return 1;
 const uint8_t *p=cell(m,layer,x,y);if(!p)return -1;
 if((p[1]==255&&p[2]==255)||(p[0]&64))return -1;
 return (p[0]>>5)&1;
}
unsigned map_tile_property(const CollisionMap *m,unsigned layer,int x,int y){
 const uint8_t *p=cell(m,layer,x,y);if(!p||(p[1]==255&&p[2]==255)||(p[0]&64))return 0;
 return ((p[1]|(unsigned)p[2]<<8)>>9)&127;
}
