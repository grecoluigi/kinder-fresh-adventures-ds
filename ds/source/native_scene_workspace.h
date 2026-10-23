#ifndef KINDER_NATIVE_SCENE_WORKSPACE_H
#define KINDER_NATIVE_SCENE_WORKSPACE_H
#include "native_bg_stream.h"
#include "depth_packets.h"
/* One native scene owns exactly these tile/cache and depth-packet structures.
 * Keep storage derived from the types so retired framebuffer sizes cannot
 * silently reserve RAM that should be available to streaming caches. */
typedef struct {NativeBGStream tiles;DepthPackets depth;} NativeSceneWorkspace;
#endif
