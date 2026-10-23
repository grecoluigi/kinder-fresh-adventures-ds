#ifndef KINDER_WORLD_ROUTES_H
#define KINDER_WORLD_ROUTES_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {
 const char *map_name; /* Case-sensitive name used by the extracted DS assets. */
 const char *geometry_path; /* Exact original W01 path. */
 const char *objects_path; /* Exact original W02 path. */
 unsigned base_world;
 bool tutorial, arena;
} WorldRoute;
/* Native411671..411893: zero tutorial flag selects the introductory map.
 * A NULL flag array means a fresh profile. Invalid world numbers return NULL. */
const WorldRoute *world_route_select(unsigned world,const uint8_t tutorials[4]);
/* Native411365..41139b: all six nonzero ingredients enter world+4. */
int world_arena_target(unsigned world,const int16_t ingredients[6]);
typedef struct {int boss,camera_locked,camera_x,camera_y;} WorldArenaStartup;
/* Native411964..4119cd camera origins and4125a9..412626 arena flags. */
bool world_arena_startup(unsigned world,WorldArenaStartup *startup);
#endif
