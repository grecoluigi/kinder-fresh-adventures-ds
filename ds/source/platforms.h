#ifndef KINDER_PLATFORMS_H
#define KINDER_PLATFORMS_H
#include "entities.h"
#include "body.h"
/* Exact 432160 collision-constrained external displacement, fixed coordinates. */
void platform_body_displace(GameBody *body,int32_t dx,int32_t dy,unsigned mode,BodyProbe probe,void *context);
/* Native416670 pixelwise movement/carry. Probe is the scene's collision query
 * at object-callback time (the player's temporary geometry list is cleared). */
void platform_transport(GameEntity *entity,int width,GameBody **bodies,size_t count,int dx,int dy,BodyProbe probe,void *context);
typedef struct {
 int16_t width;
 GameBody **bodies;
 size_t body_count;
 BodyProbe probe;
 void *context;
 /* Native41b250 path-end event, 3 horizontal /12 vertical. */
 void (*path_event)(GameEntity *entity,int event,void *context);
} PlatformEnvironment;
/* Native41b250 wait/reverse/mirror mutation. */
void platform_path_end(GameEntity *entity,int event);
/* Native416a20, registered for IDs200,201,202,210,220. */
bool platform_spring_tick(GameEntity *entity,const PlatformEnvironment *environment);
#endif
