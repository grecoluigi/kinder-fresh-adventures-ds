#ifndef KINDER_NATIVE_ACTORS_H
#define KINDER_NATIVE_ACTORS_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "actor_atlas.h"
#define NATIVE_DRAW_LIMIT 384u
typedef struct {uint16_t page;int16_t x,y;uint16_t u,v,w,h,order;uint32_t format,palette;uint16_t source_at,mirror;} NativeDraw;
#if defined(__NDS__) || defined(KF_HOST_NATIVE_ACTORS)
void gpu_native_reset(const char *map);
void gpu_native_transient(const ActorPiece *piece);
void gpu_native_allow(bool enabled);
void gpu_native_source(void *memory,size_t bytes);
void gpu_native_forget_source(void);
bool gpu_native_try(unsigned kind,unsigned frame,unsigned width,unsigned height,int left,int top,unsigned order);
bool gpu_native_skipped_sources(void);
bool gpu_native_enabled(void);
void gpu_native_skip_source(void);
void gpu_native_identity(unsigned kind,unsigned frame);
void gpu_native_sprite(unsigned width,unsigned height,int left,int top,unsigned kind,unsigned order);
void gpu_native_invalidate(unsigned bank);
bool gpu_native_prepare(unsigned bank,int camera_y,unsigned epoch,volatile uint16_t *texture,volatile uint16_t *palette,uint16_t *scratch);
bool gpu_native_available(void);
const NativeDraw *gpu_native_draws(unsigned *count);
#else
static inline void gpu_native_reset(const char *map){(void)map;}
static inline void gpu_native_transient(const ActorPiece *p){(void)p;}
static inline void gpu_native_allow(bool b){(void)b;}
static inline void gpu_native_source(void *p,size_t n){(void)p;(void)n;}
static inline void gpu_native_forget_source(void){}
static inline bool gpu_native_try(unsigned k,unsigned f,unsigned w,unsigned h,int l,int t,unsigned o){(void)k;(void)f;(void)w;(void)h;(void)l;(void)t;(void)o;return false;}
static inline bool gpu_native_skipped_sources(void){return false;}
static inline bool gpu_native_enabled(void){return false;}
static inline void gpu_native_skip_source(void){}
static inline void gpu_native_identity(unsigned k,unsigned f){(void)k;(void)f;}
static inline void gpu_native_sprite(unsigned w,unsigned h,int x,int y,unsigned k,unsigned o){(void)w;(void)h;(void)x;(void)y;(void)k;(void)o;}
static inline void gpu_native_invalidate(unsigned b){(void)b;}
#endif
#endif
