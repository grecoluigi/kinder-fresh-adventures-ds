#ifndef KINDER_BOSS_FACTORY_H
#define KINDER_BOSS_FACTORY_H
#include "entities.h"
#include "projectiles.h"
typedef struct {
 int player_x,player_y;
 GameEntity *pipe;
 int32_t *health,*defeated,*score;
 int16_t intro_first,intro_last,freeze_first,freeze_last,death_first,death_last;
 int shot_sample,beam_sample,hit_sample,death_loop_sample,death_sample;
 uint32_t owner_handle;
 bool (*contact)(int x,int y,int width,int height,int damage,void *context);
 int (*projectile)(int x,int y,int width,int height,unsigned flags,void *context);
 int (*random)(void *context);
 Projectile *(*allocate)(void *context);
 bool (*voice_load)(unsigned key,void *context);
 bool (*voice_active)(void *context);
 void (*play)(int channel,int volume,void *context);
 void (*stop)(int channel,void *context);
 void (*sound)(int channel,int sample,int repeat,void *context);
 void *context;
} FactoryBossEnvironment;
/* Original40d6b0, ID14, custom return0. Engine animation precedes this. */
bool boss_factory_tick(GameEntity *entity,const FactoryBossEnvironment *environment);
/* Original40d5c0 bullet callback; native100-byte slot initialized by spawn. */
void boss_factory_shot_init(Projectile *shot,uint32_t owner,float x,float y,float vx,float vy);
bool boss_factory_shot_tick(Projectile *shot,const ProjectileEnvironment *terrain,
 bool (*contact)(int,int,int,int,int,void *),void *context);
#endif
