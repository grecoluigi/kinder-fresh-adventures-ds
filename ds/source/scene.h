#ifndef KINDER_SCENE_H
#define KINDER_SCENE_H
#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>
#include "collision.h"
#include "geometry.h"
#include "entities.h"
#include "enemies.h"
typedef struct {
    uint32_t read_calls, read_bytes, tile_misses, sprite_misses, sprite_cache_bytes;
    /* Actual DS system-counter timings; zero in host builds. */
    uint32_t setup_us, tiles_us, objects_us, callback_us;
    uint32_t sample_misses, sample_cache_bytes;
    /* Includes live sprites and exposed parallax background rows. */
    uint32_t live_row_decodes, live_row_hits;
    uint32_t background_us;
} SceneRenderStats;
/* Last render counters for scene asset reads only; sprite_misses counts rows.
 * Caller/player/audio reads are outside these counters. */
const SceneRenderStats *scene_render_stats(void);
typedef struct {
    uint16_t width_cells, height_cells, layers, tile_width, tile_height;
    int32_t width_pixels, height_pixels, start_x, start_y;
    uint16_t static_object_count;
} SceneMetadata;
/* Caller initializes NitroFS on DS; map_name is an exact original filename,
 * e.g. Welt1.W02. Entry zero only. Failure closes partially opened resources. */
bool scene_open(const char *map_name);
/* Main-thread service points between completed asset reads/render batches.
 * Callback must not re-enter scene rendering. */
void scene_set_service_callback(void (*callback)(void));
/* Camera is in original 800x600 viewport pixels; no camera behavior is invented.
 * Produces opaque DS RGB555 pixels at exactly uniform 256x192 proportions.
 * Returns false on failed/short asset reads; never replaces missing graphics. */
bool scene_render(uint16_t *pixels, int camera_x, int camera_y);
/* Production worlds enable proven half-speed X / fixed-Y background parallax
 * before scene_open. Static asset-reference fixtures can retain viewport frame4. */
void scene_enable_background_parallax(bool enabled);
bool scene_render_layers(uint16_t *pixels, const int camera_xs[8], const int camera_ys[8]);
/* Native rendering callback slot: after subgroup0 and before subgroup2.
 * Caller selects active entity/layer; no callback is installed by default. */
typedef void (*SceneLayerCallback)(uint16_t *pixels, unsigned layer,
                                   int camera_x, int camera_y, void *context);
void scene_set_layer_callback(SceneLayerCallback callback, void *context);
/* Native world dispatch currently requires the player callback on layer2. */
void scene_set_layer_callback_at_layer(SceneLayerCallback callback,void *context,int layer);
/* Release native renderer resources; collision metadata has its own lifetime. */
void scene_release_renderer(void);
size_t scene_resident_asset_bytes(void);
GameEntity *scene_entities(size_t *count);
bool scene_geometry_object(size_t index,GeometryObject *object);
/* Caller gates activity/layer. Retains current-frame validity before flag184. */
bool scene_entity_update_region(size_t index,int camera_x,int camera_y);
bool scene_entity_environment(size_t index,EntityEnvironment *environment);
bool scene_enemy_animation_range(size_t index,unsigned range,int16_t *first,int16_t *last);
bool scene_enemy_environment(size_t index,EnemyEnvironment *environment);
void scene_enable_live_enemies(bool enabled);
/* Dedicated native source-cache arena. Set before scene_open: main maps384KiB,
 * tutorials256KiB, arenas512KiB. No decoded actor pixels share this arena. */
void scene_set_sprite_cache_bytes(size_t bytes);
/* Caller-owned256x256 RGB555 parallax plane. Upload once per scene;
 * render publishes its horizontal offset. Gameplay requires a valid plane. */
void scene_set_hardware_background(uint16_t *arena,size_t bytes);
bool scene_hardware_background_active(void);
unsigned scene_hardware_background_offset(void);
/* Native perframe blink progression4339de; call once per simulationtick. */
void scene_entity_visual_step(size_t index);
const SceneMetadata *scene_metadata(void);
/* Full-resolution masks remain valid until close. tiles holds the resident layer;
 * access cells on every layer through collision_cell(), including streamed layers. */
const CollisionMap *scene_collision_map(void);
void scene_close(void);
/* Arena remains valid until scene_close; caller forgets it before close. */
void *scene_native_cache(unsigned *bytes);
#endif
