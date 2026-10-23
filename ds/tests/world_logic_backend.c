/* Host navigation tests load the real scene definition but never render.
 * Calling the display service is an error, not a substitute renderer. */
#include "native_scene.h"
#include "native_scene_definition.h"
#ifndef NATIVE_SCENERY_ROOT
#error Define the generated native scenery directory for host logic tests
#endif
static NativeSceneDefinition logic_definition;
bool native_scene_open(const char *name,void *memory,size_t bytes){
 (void)memory;(void)bytes;
 native_scene_close();
 if(!name||strchr(name,'/')||strchr(name,'\\'))return false;
 char path[512];
 return snprintf(path,sizeof(path),"%s/%s.nsc",NATIVE_SCENERY_ROOT,name)<(int)sizeof(path)&&
        native_scene_definition_open(&logic_definition,path);
}
void native_scene_close(void){native_scene_definition_close(&logic_definition);}
bool native_scene_active(void){return logic_definition.static_orders!=0;}
size_t native_scene_asset_bytes(void){return logic_definition.event_count*sizeof(NativeSceneEvent);}
void native_scene_set_service_callback(void (*callback)(void)){(void)callback;}
bool native_scene_render(uint16_t *out,int x,int y,NativeSceneCallback callback,void *context,SceneRenderStats *stats){
 (void)out;(void)x;(void)y;(void)callback;(void)context;(void)stats;
 fputs("Host navigation tests must not invoke rendering\n",stderr);abort();
}
