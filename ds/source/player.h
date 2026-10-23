#ifndef KINDER_PLAYER_H
#define KINDER_PLAYER_H
#include "animation.h"
#include "body.h"
/* Original input bits collected at 0x417486..0x4174f9. */
enum { PLAYER_UP=1,PLAYER_DOWN=2,PLAYER_LEFT=4,PLAYER_RIGHT=8,
       PLAYER_JUMP=16,PLAYER_SHOOT=32,PLAYER_SWITCH=64 };
typedef struct {
    Animation penguin, milk;
    int32_t state, character, facing, control_y;
    int32_t platform_jump_y, jump_hold, glide_hold, jump_debounce;
    int32_t jump_release, projectile_variant, fatal, jump_sound, glide_sound;
    int32_t switch_latch, shoot_latch, direction_latch, vertical_latch;
    int32_t penguin_status, milk_status, inventory, milk_facing, switch_available, puff_frame, shot_sound, push_sound;
    /* Native globals45f014,4e0b44,4e102c,45f008,4daba8. Health starts100,
     * death_timer starts-1, game_mode is the surrounding game dispatcher. */
    int32_t health,death_timer,knockback_timer,game_mode,death_actor;
    int32_t penguin_hurt_sound,milk_hurt_sound,hit_feet,hit_middle,hit_head;
} Player;
typedef enum { PLAYER_SOUND_PLAY,PLAYER_SOUND_STOP,PLAYER_UNSUPPORTED,PLAYER_SOUND_LOAD,PLAYER_SOUND_VOLUME } PlayerEventType;
typedef void (*PlayerEvent)(void *context, PlayerEventType type, int id, int argument);
typedef struct {
    bool grounded;
    bool ladder;
    /* Original calls 0x431ce0 for Milch walking: caller must supply dynamic geometry. */
    bool milk_obstacle;
    /* Values returned by original sound manager and scene. */
    bool voice_active, sound_load_ok;
    int32_t world_stage;
    int32_t (*random)(void *context);
    /* Original 0x41a1d0 projectile request; velocity is native pixel/frame. */
    void (*projectile)(void *context,int x,int y,float vx,float vy,int variant);
    PlayerEvent event;
    void *context;
    /* Climbing: original ladder 41a830, tile solid 434180, tile property
     * 434200 and body contact 431ed0. Coordinates are original pixels. */
    int32_t (*climb_probe)(void *context,int query,int x,int y);
    /* Native dynamic point lookup -> world object resolution -> object vx.
     * Query preserves the original encoded index; resolve returns zero for
     * a missing object, otherwise a caller-owned opaque handle. */
    int32_t (*push_query)(void *context,int x,int y,int mode);
    uint32_t (*push_resolve)(void *context,int32_t index);
    void (*push_velocity)(void *context,uint32_t handle,float vx);
    /* Native430470 visual particle request, original pixels/float velocity. */
    void (*particle)(void *context,int x,int y,float vx,float vy);
} PlayerEnvironment;
enum { PLAYER_PROBE_LADDER,PLAYER_PROBE_TILE_SOLID,PLAYER_PROBE_TILE_PROPERTY,
       PLAYER_PROBE_CONTACT };
/* Original 41a830 ladder predicate, using TILE_PROPERTY on layer2. The caller
 * can use this helper when servicing PLAYER_PROBE_LADDER and idle routing. */
bool player_ladder_at(const PlayerEnvironment *environment,int x,int y);
/* Native417419..417479. Run before input filtering/dispatch. */
void player_death_tick(Player *player);
/* Original40af50 draw preamble; advance once per simulation tick after the
 * active animation update, even if the renderer skips a frame. Returns whether
 * the active character is visible. Keeps milk_status's native alias coherent. */
bool player_blink_tick(Player *player);
/* DS presentation: avoid sampling only one native blink phase when multiple
 * 60Hz simulation updates share a displayed frame. Does not change Player. */
typedef struct {uint32_t remaining;int32_t character;bool active,visible;} PlayerBlinkView;
bool player_blink_present(PlayerBlinkView *view,const Player *player,
                          bool native_visible,bool simulation_advanced);
/* 0x41775e..0x41782f: release-cleared action latches and five-tick jump
 * window. Call once per update before dispatch, with the original input bits.
 * input_enabled corresponds to native global 0x45f014 != 0. */
unsigned player_filter_input(Player *player,GameBody *body,unsigned raw,bool input_enabled);
/* One recovered native switch case. Caller retains velocity_y across transitions
 * in this update, mirroring [esp+0x18]. Returns false before unsupported work. */
bool player_case(Player *player, GameBody *body, unsigned *input,
                 int32_t *velocity_y, const PlayerEnvironment *environment);
/* Native common tail helpers. Damage effects run after body/animation/shots and
 * camera, before other entity callbacks. Released particle renderer is no-op. */
void player_sync_facing(Player *player);
bool player_damage_effects_tick(Player *player,const GameBody *body,const PlayerEnvironment *environment);
/* Dispatches changed states until stable, as 0x419d78. Does not advance body or
 * animations, perform input latching, or silently replace unsupported states. */
bool player_dispatch(Player *player, GameBody *body, unsigned *input,
                     const PlayerEnvironment *environment);
#endif
