#ifndef KINDER_ENEMY_SHOTS_H
#define KINDER_ENEMY_SHOTS_H
#include "projectiles.h"
#include "enemies.h"
#include "geometry.h"
/* Native general animation pool410fb0:200slots,100bytes each. */
#define ENEMY_SHOTS_CAPACITY 200
typedef Projectile EnemyShot;
typedef struct {
 int (*solid)(void *context,int x,int y);
 unsigned (*property)(void *context,int x,int y);
 bool (*obstacle)(void *context,int x,int y);
 EnemyContact contact;
 void *context;
} EnemyShotEnvironment;
bool enemy_shot_obstacle_test(const GeometryObject *objects,int count,int x,int y);
void enemy_shots_init(void);
void enemy_score_popup(int x,int y,int score,void *context);
void enemy_score_popup_tick(EnemyShot *shot);
bool enemy_shots_allocate(void);
/* Native allocator exposes an inactive slot; the initializer activates it. */
EnemyShot *enemy_shots_free_slot(void);
bool enemy_shots_spawn(uint32_t owner_handle,float x,float y,float vx,float vy);
bool enemy_shots_spawn_record(const EnemyShot *record);
typedef void (*EnemyShotCallback)(EnemyShot *,const EnemyShotEnvironment *);
void enemy_shots_tick_with(const EnemyShotEnvironment *environment,EnemyShotCallback callback);
void enemy_shots_tick(const EnemyShotEnvironment *environment);
/* Standalone exact413b70 primitive for the native verifier. */
void enemy_shot_callback(EnemyShot *shot,const EnemyShotEnvironment *environment);
const EnemyShot *enemy_shots_slots(void);
bool enemy_shot_graphics_open(void);
void enemy_shot_graphics_close(void);
bool enemy_shots_draw(uint16_t *pixels,int camera_x,int camera_y);
/* Native40af50 owner-resource frame16 uses surface alignment zero, independently
 * of AOM collision alignment. Surface20x51. Mirror mode2 uses x-width. */
bool enemy_shot_draw_command(const EnemyShot *shot,int camera_x,int camera_y,int *left,int *top,bool *mirror);
#endif
