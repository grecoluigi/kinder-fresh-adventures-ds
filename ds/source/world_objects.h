#ifndef KINDER_WORLD_OBJECTS_H
#define KINDER_WORLD_OBJECTS_H
#include "entities.h"
#include "platforms.h"
/* Resource ranges and dimensions are supplied by scene metadata. Native range
 * reset changes first/last/frame/mode, leaving animation timer/delay intact. */
typedef struct {
 int16_t first,last,width,height;
 int16_t frozen_first,frozen_last; /* native animation range17 for drops */
 int player_x,player_y;
 uint8_t *switch_flags;
 uint32_t *ice_trigger_bits; /* native4e0b20, iceSpike2 trigger mask */
 int32_t *ice_block_state,*collapse_trigger;
 uint32_t *pipe_entity; /* map index+1 equivalent of native4e0b28 */
 uint32_t entity_handle;
 GameBody **bodies;size_t body_count;BodyProbe probe;
 int (*tile)(int layer,int x,int y,void *context);
 bool (*damage)(int x,int y,int width,int height,int damage,void *context);
 int (*random)(void *context);
 /* Native412ee0 contributes distance to an ambient channel, not particles. */
 void (*ambient)(int x,int y,int channel,void *context);
 void (*sound)(int channel,int sample,int repeat,void *context);
 void *context;
 int clamp_sample,pipe_sample,crumble_sample;
 int16_t talking_first,talking_last; /* native range16 */
 int32_t progress_flag,world;
 int32_t *dialogue_state; /* native4e1034:0 free/1 speaking/2 skip */
 bool (*voice_load)(unsigned path_key,void *context);
 bool (*voice_active)(void *context);
 void (*voice_play)(void *context);
 void (*voice_stop)(void *context);
 uint8_t *completion_flags; /*4 bytes; native45ed4c */
 int32_t *target_world,*game_mode;
 EntityGlobals *pickup_globals;
 int32_t boss_defeated; /*4dab18 drop trigger, read only */
 int32_t *seventh_item_state,*snowballs_available,*finish_timer;
 void (*score_popup)(int x,int y,int score,void *context);


} WorldObjectEnvironment;
bool world_object_supported(unsigned id);
/* Native callbacks75/77/79/80/82/84/85/88/89/265/352/354/355/356/414.
 * Caller performs the original engine animation/blink stages before callback.
 * Native return0 suppresses defaultmovement for these supported records. */
bool world_object_tick(GameEntity *entity,const WorldObjectEnvironment *environment);
#endif
