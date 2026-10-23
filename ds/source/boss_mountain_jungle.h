#ifndef KINDER_BOSS_MOUNTAIN_JUNGLE_H
#define KINDER_BOSS_MOUNTAIN_JUNGLE_H
#include "entities.h"
#include "enemy_shots.h"
typedef struct {
 int16_t ranges[19][2];
 int32_t *health,*score,*defeated;
 uint32_t *ice_trigger_bits;
 int32_t *ice_block_state,*collapse_trigger,*yeti_hit;
 bool (*contact)(int,int,int,int,int,void *);
 int (*projectiles)(int,int,int,int,int,void *);
 int (*random)(void *);
 bool (*audio_load)(unsigned,int,void *);
 bool (*audio_active)(int,void *);
 void (*audio_volume)(int,int,void *);
 void (*audio_stop)(int,void *);
 void (*audio_play)(int,int,int,void *);
 /* Shared200-slot pool: provider returns an available slot or NULL. */
 EnemyShot *(*allocate_shot)(void *);
 uint32_t entity_handle;
 GameEntity *(*object_at)(unsigned,void *);
 void *context;
 int16_t gorilla_walk,gorilla_hit,yeti_hit_sample,yeti_land,gorilla_reflect;
} MountainJungleBossEnvironment;
/* Native9=mountain Yeti,10=jungle Gorilla. Animation advances before callback. */
bool boss_mountain_jungle_tick(GameEntity *,const MountainJungleBossEnvironment *);
bool boss_gorilla_shot_tick(EnemyShot *,GameEntity *owner,const MountainJungleBossEnvironment *,const EnemyShotEnvironment *);
#endif
