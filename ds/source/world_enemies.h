#ifndef KINDER_WORLD_ENEMIES_H
#define KINDER_WORLD_ENEMIES_H
#include "enemies.h"
#include "enemy_shots.h"
/* Native callbacks; caller advances animation before invoking these bodies.
 * Eagle uses throw_sound for the native dive sample (global 4e0a90).
 * Ordinary octopus has a second, frame-specific contact shape. */
bool enemy_eagle_callback(GameEntity *,EntityGlobals *,const EnemyEnvironment *);
bool enemy_small_octopus_callback(GameEntity *,EntityGlobals *,const EnemyEnvironment *);
typedef void (*EnemyAmbient)(int x,int y,int slot,void *context);
typedef struct { EnemyEnvironment enemy; int16_t frame_width,frame_height,base_width,base_height; EnemyAmbient ambient; } WorldEnemyEnvironment;
bool enemy_bee_callback(GameEntity *,EntityGlobals *,const WorldEnemyEnvironment *);
bool enemy_small_robot_callback(GameEntity *,EntityGlobals *,const EnemyEnvironment *);
bool enemy_flying_robot_callback(GameEntity *,EntityGlobals *,const WorldEnemyEnvironment *);
bool enemy_small_yeti_callback(GameEntity *,EntityGlobals *,const EnemyEnvironment *);
typedef struct { int32_t squared_distance[16]; int32_t camera_offset_x,camera_offset_y; } EnemyAmbientState;
void enemy_ambient_reset(EnemyAmbientState *,int32_t camera_offset_x,int32_t camera_offset_y);
void enemy_ambient_contribute(EnemyAmbientState *,int32_t x,int32_t y,unsigned slot);
int enemy_ambient_volume(const EnemyAmbientState *,unsigned slot);
/* Zero means no native looping ambient sample at this world/channel. */
uint32_t enemy_ambient_sample_global(unsigned world,unsigned channel);
bool enemy_snowman_callback(GameEntity *,EntityGlobals *,const EnemyEnvironment *);
bool enemy_egg_robot_callback(GameEntity *,EntityGlobals *,const EnemyEnvironment *);
/* Native general-animation initializers and callbacks for ownerIDs7/8/12.
 * Parent owns the shared200slotpool and advances animation after callback. */
bool world_enemy_shot_init(EnemyShot *,unsigned owner_id,uint32_t owner_handle,float x,float y,float vx,float vy);
bool world_enemy_shot_callback(EnemyShot *,const EnemyShotEnvironment *);
#endif
