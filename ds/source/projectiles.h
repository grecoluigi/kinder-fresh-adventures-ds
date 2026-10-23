#ifndef KINDER_PROJECTILES_H
#define KINDER_PROJECTILES_H
#include <stdbool.h>
#include <stdint.h>
/* Native100-byte animation slots at4e0b48; x/y/vx/vy are float aliases. */
typedef struct {
 uint32_t resource,opaque04,opaque08;
 float x,y,vx,vy;
 uint32_t opaque1c,opaque20;
 int32_t repeats,mode,frame,first,last,timer,delay;
 int32_t active,lifetime;
 uint32_t opaque48,opaque4c,opaque50,opaque54,opaque58,opaque5c,callback;
} Projectile;
typedef struct { Projectile slots[10]; } Projectiles;
typedef struct {
 int (*solid)(void *context,int x,int y);
 unsigned (*property)(void *context,int x,int y);
 void *context;
} ProjectileEnvironment;
void projectiles_init(Projectiles *pool);
/* Returns false when all ten native slots are occupied, or invalid velocity. */
bool projectiles_spawn(Projectiles *pool,int x,int y,float vx,float vy,int variant);
void projectiles_tick(Projectiles *pool,const ProjectileEnvironment *environment);
/* Native41a5e0 inclusive rectangle; flags1 consume, flags2 reflect. */
int projectiles_hit(Projectiles *pool,int x,int y,int width,int height,unsigned flags);
bool projectile_graphics_open(void);
void projectile_graphics_close(void);
bool projectiles_draw(const Projectiles *pool,uint16_t *pixels,int camera_x,int camera_y);
/* Conservative union of clipped projectile rectangles from the latest draw. */
void projectiles_last_bounds(int bounds[4]);
#endif
