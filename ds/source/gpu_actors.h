#ifndef KINDER_GPU_ACTORS_H
#define KINDER_GPU_ACTORS_H
#include "actor_atlas.h"
#if defined(__NDS__) || defined(KF_HOST_GPU_ACTORS)
#define KF_GPU_ACTORS_ENABLED 1
void gpu_actors_reset(void);
bool gpu_actors_native(unsigned kind,unsigned frame,unsigned width,unsigned height,int left,int top);
void gpu_actors_ordinal(unsigned order);
void gpu_actors_unsupported(void);
void gpu_actors_sprite(const uint16_t *pixels,unsigned width,unsigned height,unsigned stride,int left,int top,unsigned kind);
uint16_t *gpu_actors_scratch(void);
const ActorAtlas *gpu_actors_frame(void);
void gpu_actors_set_collect_only(bool enabled);
bool gpu_actors_collect_only(void);
bool gpu_actors_reference(bool enabled);
bool gpu_actors_reference_active(void);
#else
#define KF_GPU_ACTORS_ENABLED 0
/* Ordinary host gameplay verifiers retain CPU pixels without extra modules.
 * The specialized actor fixture opts in with KF_HOST_GPU_ACTORS. */
static inline void gpu_actors_reset(void){}
static inline bool gpu_actors_native(unsigned k,unsigned f,unsigned w,unsigned h,int l,int t){(void)k;(void)f;(void)w;(void)h;(void)l;(void)t;return false;}
static inline void gpu_actors_ordinal(unsigned order){(void)order;}
static inline void gpu_actors_unsupported(void){}
static inline void gpu_actors_sprite(const uint16_t *p,unsigned w,unsigned h,unsigned stride,int x,int y,unsigned kind){(void)p;(void)w;(void)h;(void)stride;(void)x;(void)y;(void)kind;}
static inline uint16_t *gpu_actors_scratch(void){return NULL;}
static inline const ActorAtlas *gpu_actors_frame(void){static const ActorAtlas empty={0};return &empty;}
static inline void gpu_actors_set_collect_only(bool enabled){(void)enabled;}
static inline bool gpu_actors_collect_only(void){return false;}
static inline bool gpu_actors_reference(bool enabled){(void)enabled;return false;}
static inline bool gpu_actors_reference_active(void){return false;}
#endif
#endif
