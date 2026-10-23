#ifndef KINDER_SCENE_EVENTS_H
#define KINDER_SCENE_EVENTS_H
#include "scene.h"
/* pixels, kind, argument, painter order, camera x/y, context. The callback sets
 * the actor ordinal itself, so events it skips cost no ordinal update. */
typedef bool (*NativeSceneCallback)(uint16_t *,unsigned,unsigned,unsigned,int,int,void *);
#endif
