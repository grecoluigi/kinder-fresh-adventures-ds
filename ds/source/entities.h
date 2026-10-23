#ifndef KINDER_ENTITIES_H
#define KINDER_ENTITIES_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define ENTITY_RECORD_BYTES 186
/* Serialized native map object and its live state share this exact byte layout.
 * Accessors avoid alignment/pointer-size changes on ARM9 and host verifiers. */
typedef struct { uint8_t bytes[ENTITY_RECORD_BYTES]; } GameEntity;
typedef struct {
 int32_t score,health,ammo,shoot_latch,pickup_sound;
 uint16_t letters[6];
} EntityGlobals;
typedef bool (*EntityOverlap)(int x,int y,int width,int height,int mode,void *context);
typedef void (*EntityScorePopup)(int x,int y,int score,void *context);
typedef struct {
 int16_t first,last,width,height; /* Resource range 0 and frame-0 dimensions. */
 EntityOverlap overlap;
 EntityScorePopup popup;
 void *context;
} EntityEnvironment;
uint16_t entity_id(const GameEntity *entity);
int16_t entity_x(const GameEntity *entity);
int16_t entity_y(const GameEntity *entity);
int16_t entity_frame(const GameEntity *entity);
unsigned entity_layer(const GameEntity *entity);
unsigned entity_group(const GameEntity *entity);
bool entity_active(const GameEntity *entity);
bool entity_visible(const GameEntity *entity);
/* Native4311c0 registration order and overwrite semantics; NULL handle installs
 * the native default movement callback. Handles are IDs, never host pointers. */
void entities_register_callback(GameEntity *entities,size_t count,int id,uint32_t handle);
uint32_t entity_native_pickup_callback(unsigned id);
/* Native409050 registered for legacy NPC ID0. No shipped map instances.
 * Events16/32 select resource ranges0/1 in forward mode; returntrue permits
 * default movement. NULL ranges represent failed native resource lookup. */
bool entity_legacy_npc_event(GameEntity *entity,unsigned event,const int16_t ranges[2][2]);
/* Native map activation/reset430ca0/430c30 and path initializer430cf0. */
void entity_path_init(GameEntity *entity);
void entities_reset_map(GameEntity *entities,size_t count);
/* Native selected-list eligibility411938: geometry list only, not render list. */
size_t entities_select_geometry(const GameEntity *entities,size_t count,unsigned layer,uint16_t *indices,size_t capacity);
/* Native4337a1..43383f animation stage. Caller supplies engine extra delay.
 * Returns callback event4 normally,6 on infinite/no-count wrap,12 finite wrap. */
unsigned entity_advance_animation(GameEntity *entity,int16_t extra_delay);
/* Native4336f4..4337a1 pre-animation sound requests. Owner table contains
 * native object indices per channel. The request provider owns playback and
 * channel/object bookkeeping (433ac0), separately from this dispatch gate. */
typedef struct {
 bool enabled;
 const int16_t *channel_owners; /* 256 entries; NULL means unowned. */
 bool (*channel_active)(unsigned channel,void *context);
 void (*request)(GameEntity *entity,unsigned slot,void *context);
 void *context;
} EntityFrameSoundEnvironment;
void entity_frame_sound_step(GameEntity *entity,unsigned object_index,
 const EntityFrameSoundEnvironment *environment);
/* Native433e60 after camera projection434510. View dimensions remain source
 * pixels; this must never use the scaled DS256x192 viewport. */
void entity_sound_spatial(int32_t projected_x,int32_t projected_y,
 int16_t width,int16_t height,int32_t *attenuation,int32_t *pan);
typedef struct {
 int16_t object,slot;
} EntitySoundOwner;
/* Native431450 selects the first idle channel, otherwise rotates through
 * the configured pool. current is preserved as the engine signed16 field. */
unsigned entity_sound_allocate(int16_t *current,int16_t first,int16_t count,
 bool (*active)(unsigned channel,void *context),void *context);
typedef struct {
 bool enabled;
 const int16_t *sample_handles;
 size_t sample_count;
 EntitySoundOwner *owners; /* 256 entries. */
 unsigned (*allocate)(void *context);
 void (*spatial)(int x,int y,int32_t *attenuation,int32_t *pan,void *context);
 void (*pan)(unsigned channel,int32_t value,void *context);
 void (*volume)(unsigned channel,int32_t value,void *context);
 void (*play)(unsigned channel,int16_t sample,uint32_t repeats,void *context);
 void *context;
} EntitySoundPlaybackEnvironment;
/* Native433ac0. Valid metadata is required; corrupt sample/owner indices are
 * safely rejected instead of reproducing out-of-bounds x86 reads/writes. */
void entity_sound_playback(GameEntity *entities,size_t count,int index,int slot,
 uint32_t repeat_override,const EntitySoundPlaybackEnvironment *environment);
typedef struct {
 bool enabled;
 EntitySoundOwner *owners; /* 256 entries. */
 bool (*frame_size)(const GameEntity *entity,int16_t *width,int16_t *height,void *context);
 void (*spatial)(int x,int y,int32_t *attenuation,int32_t *pan,void *context);
 void (*pan)(unsigned channel,int32_t value,void *context);
 void (*volume)(unsigned channel,int32_t value,void *context);
 void (*stop)(unsigned channel,void *context);
 void *context;
} EntitySoundMaintenanceEnvironment;
/* Native433c60/433dd0. Maintenance uses range-first frame dimensions, even
 * when the object is inactive/hidden. Stop-all visits every configured channel. */
void entity_sound_maintain(GameEntity *entities,size_t count,int first,int channels,
 const EntitySoundMaintenanceEnvironment *environment);
void entity_sound_stop_all(GameEntity *entities,size_t count,int first,int channels,
 const EntitySoundMaintenanceEnvironment *environment);



/* Recovered callback bodies for48..58. Unsupported IDs return false.
 * Native callbacks run even for hidden respawning items; visibility is separate.
 * Contact is delegated to original41a3e0-compatible overlap provider. */
bool entity_pickup_callback(GameEntity *entity,EntityGlobals *globals,const EntityEnvironment *environment);
#endif
