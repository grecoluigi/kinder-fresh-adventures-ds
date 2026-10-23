#ifndef KINDER_ENEMIES_H
#define KINDER_ENEMIES_H
#include "entities.h"
typedef bool (*EnemyContact)(int x,int y,int width,int height,int damage,void *context);
typedef void (*EnemySound)(int channel,int sound,void *context);
typedef int (*EnemyRandom)(void *context);
typedef bool (*EnemyAllocate)(void *context);
typedef void (*EnemySpawn)(const GameEntity *owner,float x,float y,float vx,float vy,void *context);
typedef struct {
 int16_t ranges[18][2];
 EnemyContact contact, projectile;
 EntityScorePopup popup;
 EnemySound sound;
 int16_t hit_sound, fall_sound;
 void *context;
 int32_t player_x,player_y;
 EnemyRandom random;
 EnemyAllocate allocate;
 EnemySpawn spawn;
 int16_t throw_sound;
} EnemyEnvironment;
/* Native snake callback 41b3e0. Animation advancement remains the engine's
 * entity_advance_animation stage. Contact provider owns player damage. */
bool enemy_snake_callback(GameEntity *entity,EntityGlobals *globals,const EnemyEnvironment *environment);
bool enemy_kong_callback(GameEntity *entity,EntityGlobals *globals,const EnemyEnvironment *environment);
bool enemy_parrot_callback(GameEntity *entity,EntityGlobals *globals,const EnemyEnvironment *environment);
#endif
