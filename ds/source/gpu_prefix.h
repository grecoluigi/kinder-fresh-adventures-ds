#ifndef KINDER_GPU_PREFIX_H
#define KINDER_GPU_PREFIX_H
#include <stdbool.h>
#include <stdint.h>
bool gpu_prefix_init(void);
bool gpu_prefix_prepare(uint16_t *reference_pixels);
bool gpu_prefix_prepare_bitmap(const uint16_t *pixels);
bool gpu_prefix_pending_texture_only(void);
bool gpu_prefix_bitmap_visible(void);
void gpu_prefix_publish(bool visible);
void gpu_prefix_hide(void);
bool gpu_prefix_is_visible(void);
void gpu_prefix_save_frame(const uint16_t *pixels);
void gpu_prefix_restore_frame(uint16_t *pixels);
bool gpu_prefix_pending_actors(void);
bool gpu_prefix_actors_visible(void);
bool gpu_prefix_snapshot_frame(uint16_t *pixels);
#endif

bool gpu_prefix_native_enabled(void);
bool gpu_prefix_native_hold(uint16_t *);
bool gpu_prefix_native_freeze(uint16_t *);
bool gpu_prefix_native_acquire(uint16_t *);
bool gpu_prefix_native_palette(const uint16_t *);
