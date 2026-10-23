#ifndef KINDER_BOSS_VALLEY_H
#define KINDER_BOSS_VALLEY_H
#include "entities.h"
typedef struct { uint8_t bytes[100]; } BossValleyShot;
typedef struct { int32_t score,boss_energy,completed; } BossValleyGlobals;
/* Native service IDs preserve ordered calls. Values are source numeric handles,
 * not host pointers. Contact41a3e0/projectile41a5e0 use five source integers;
 * allocator410fb0 returns boolean and selects environment.shot; voices4243b1
 * return -1 for unavailable. Range430b20 gets [range,mode]; initializer40adc0
 * gets [resource=0,float-x bits,float-y bits]. Player-query41a8c0 has no args. */
typedef int32_t (*BossValleyService)(uint32_t address,const int32_t *arguments,unsigned count,void *context);
typedef struct {
 int16_t ranges[19][2];
 int32_t player_x,player_y;
 int16_t hit_sound,fall_sound,bear_idle_sound,bear_throw_sound,octopus_sound,octopus_throw_sound;
 uint32_t owner_handle;
 BossValleyShot *shot;
 BossValleyService service;
 void *context;
} BossValleyEnvironment;
bool boss_valley_bear_tick(GameEntity *entity,BossValleyGlobals *globals,const BossValleyEnvironment *environment);
bool boss_valley_octopus_tick(GameEntity *entity,BossValleyGlobals *globals,const BossValleyEnvironment *environment);
/* Native413b70 and40cc60 share these services and100-byte float-shot layout. */
void boss_valley_shot_tick(BossValleyShot *shot,const BossValleyEnvironment *environment);
#endif
