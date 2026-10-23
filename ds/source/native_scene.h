#ifndef KINDER_NATIVE_SCENE_H
#define KINDER_NATIVE_SCENE_H
#include "scene.h"
#include "scene_events.h"
#include "depth_mesh.h"
bool native_scene_open(const char *,void *,size_t);
void native_scene_close(void);
void native_scene_suspend(void);
bool native_scene_active(void);
unsigned native_scene_static_orders(void);
size_t native_scene_asset_bytes(void);
void native_scene_set_service_callback(void (*)(void));
void native_scene_service(void);
bool native_scene_render(uint16_t *,int,int,NativeSceneCallback,void *,SceneRenderStats *);
bool native_scene_prepared(void);
bool native_scene_sample(uint16_t *,int,int,int,int);
bool native_scene_expand(volatile uint16_t *,int,int,int,int);
bool native_scene_mesh(const DepthRect **,unsigned *,int *,int *,unsigned *);
void native_scene_camera(int *,int *);
bool native_scene_publish(bool);
#endif
