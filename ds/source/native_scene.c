#include "native_scene.h"
#include "native_scene_definition.h"
static void (*service_callback)(void);
void native_scene_set_service_callback(void (*callback)(void)){service_callback=callback;}
void native_scene_service(void){if(service_callback)service_callback();}
#define NATIVE_BG_SERVICE() native_scene_service()
#include "native_bg_sample.h"
#include "native_scene_workspace.h"
#include "depth_packets.h"
#include "gpu_prefix.h"
#include "gpu_actors.h"
#include "ds_projection.h"
#include <nds.h>
#include <nds/system_counter.h>

static NativeSceneWorkspace *workspace;
static NativeSceneDefinition definition;
static NativeBGStream *stream;
static FILE *owned_file;
static char map_path[192];
static const DepthRect *mesh;
static unsigned mesh_count,mesh_visible;
static int mesh_dx,mesh_dy,view_x,view_y;
static bool prepared;
static volatile unsigned native_scene_frames,native_scene_cold_loads,native_scene_failures,native_scene_bridges;
static volatile unsigned native_scene_prepare_us,native_scene_tile_uploads,native_scene_asset_reads;

bool native_scene_active(void){return workspace&&definition.static_orders;}
unsigned native_scene_static_orders(void){return definition.static_orders;}
size_t native_scene_asset_bytes(void){return definition.event_count*sizeof(NativeSceneEvent);}
void native_scene_suspend(void){
 if(owned_file)fclose(owned_file);
 if(stream)stream->assets.file=NULL;
 owned_file=NULL;stream=NULL;prepared=false;mesh=NULL;mesh_count=mesh_visible=0;
}
void native_scene_close(void){
 native_scene_suspend();
 if(workspace)depth_packets_close(&workspace->depth);
 workspace=NULL;map_path[0]=0;native_scene_definition_close(&definition);
}
bool native_scene_open(const char *name,void *memory,size_t bytes){
 native_scene_close();
 if(!gpu_prefix_native_enabled()||!name||!memory||((uintptr_t)memory&3u)||bytes<sizeof(NativeSceneWorkspace))return false;
 char path[192];
 if(snprintf(path,sizeof(path),"nitro:/native_scenery/%s.nsc",name)>=(int)sizeof(path)||
    !native_scene_definition_open(&definition,path))goto failed;
 workspace=memory;memset(workspace,0,sizeof(*workspace));
 if(snprintf(path,sizeof(path),"nitro:/native_scenery/%s.mesh",name)>=(int)sizeof(path)||
    !depth_packets_open(&workspace->depth,path,definition.width,definition.height))goto failed;
 if(snprintf(map_path,sizeof(map_path),"nitro:/native_scenery/%s.ntb",name)>=(int)sizeof(map_path))goto failed;
 return true;
failed:native_scene_close();return false;
}
static bool write_tile(void *context,unsigned slot,const uint16_t *data){
 (void)context;native_scene_service();
 if(slot>=960||(stream->cache.entries[slot].flags&NATIVE_BG_FRONT))return false;
 volatile uint16_t *gfx=(volatile uint16_t *)0x06000000;
 for(unsigned i=0;i<32;i++)gfx[slot*32+i]=data[i];
 return true;
}
static bool write_map(void *context,unsigned at,uint16_t word){
 (void)context;if(at>=2048)return false;
 ((volatile uint16_t *)0x0600f000)[at]=word;return true;
}
bool native_scene_expand(volatile uint16_t *texture,int l,int t,int r,int b){
 native_scene_service();
 return stream&&native_bg_expand_region(stream,(volatile uint16_t *)0x06000000,960u*32u,texture,l,t,r,b);
}
bool native_scene_sample(uint16_t *out,int l,int t,int r,int b){
 return stream&&native_bg_sample_region(stream,(volatile uint16_t *)0x06000000,960u*32u,out,49152,256,l,t,r,b);
}
static bool load_mesh(void){
 DepthPackets *depth=&workspace->depth;
 if(!depth_packets_load(depth,view_x,view_y,&mesh_dx,&mesh_dy))return false;
 mesh=depth->rectangles;mesh_count=depth->count;mesh_visible=0;
 for(unsigned i=0;i<mesh_count;i++){
  const DepthRect *q=mesh+i;
  if(q->order>definition.static_orders)return false;
  if(q->right>mesh_dx&&q->left<mesh_dx+256&&q->bottom>mesh_dy&&q->top<mesh_dy+192)mesh_visible++;
 }
 return mesh_visible<=1536;
}
bool native_scene_render(uint16_t *out,int cx,int cy,NativeSceneCallback callback,void *context,SceneRenderStats *stats){
 prepared=false;
 if(!out||!stats||!native_scene_active()||cx<0||cy<0||cx>(int)definition.native_width-800||cy>(int)definition.native_height-600)return false;
 unsigned start=(unsigned)systemCounterGetTicks();
 if(!stream||!owned_file){
  native_scene_suspend();
  if(!gpu_prefix_native_acquire(out))goto failed;
  stream=&workspace->tiles;
  if(!native_bg_stream_open(stream,map_path,false))goto failed;
  owned_file=stream->assets.file;
  if(stream->assets.width*8u!=definition.width||stream->assets.height*8u!=definition.height||
     !gpu_prefix_native_palette(stream->assets.palette))goto failed;
  volatile uint16_t *gfx=(volatile uint16_t *)0x06000000,*map=(volatile uint16_t *)0x0600f000;
  for(unsigned i=0;i<32;i++)gfx[i]=0;
  for(unsigned i=0;i<2048;i++)map[i]=0;
  native_scene_cold_loads++;
 }
 int next_x=ds_world_pixel(cx),next_y=ds_world_pixel(cy);
 bool same_mesh=mesh&&next_x==view_x&&next_y==view_y;
 view_x=next_x;view_y=next_y;
 unsigned uploads=stream->cache.uploads,reads=stream->assets.block_fills;
 NativeBGStreamResult result=native_bg_stream_prepare(stream,view_x,view_y,write_tile,write_map,NULL);
 if(result==NATIVE_BG_STREAM_BRIDGE){
  native_scene_bridges++;
  if(!gpu_prefix_native_hold(out))goto failed;
  native_scene_suspend();stream=&workspace->tiles;
  if(!native_bg_stream_open(stream,map_path,false))goto failed;
  owned_file=stream->assets.file;
  if(!gpu_prefix_native_palette(stream->assets.palette))goto failed;
  volatile uint16_t *gfx=(volatile uint16_t *)0x06000000,*map=(volatile uint16_t *)0x0600f000;
  for(unsigned i=0;i<32;i++)gfx[i]=0;
  for(unsigned i=0;i<2048;i++)map[i]=0;
  uploads=reads=0;result=native_bg_stream_prepare(stream,view_x,view_y,write_tile,write_map,NULL);native_scene_cold_loads++;
 }
 if(result!=NATIVE_BG_STREAM_READY||((!same_mesh||!mesh)&&!load_mesh()))goto failed;
 prepared=true;gpu_actors_set_collect_only(true);
 unsigned cb_start=(unsigned)systemCounterGetTicks();
 for(unsigned i=0;i<definition.event_count;i++){
  /* Culled events are a few loads; drawn objects service audio themselves. */
  if(!(i&15u))native_scene_service();
  const NativeSceneEvent *event=definition.events+i;
  if(callback&&!callback(out,event->kind,event->argument,event->order,cx,cy,context))goto failed;
 }
 stats->callback_us=systemCounterTicksToUsec((unsigned)systemCounterGetTicks()-cb_start);
 native_scene_frames++;native_scene_prepare_us=systemCounterTicksToUsec((unsigned)systemCounterGetTicks()-start);
 native_scene_tile_uploads=stream->cache.uploads-uploads;native_scene_asset_reads=stream->assets.block_fills-reads;
 stats->setup_us=native_scene_prepare_us-stats->callback_us;return true;
failed:native_scene_failures++;native_scene_suspend();return false;
}
bool native_scene_prepared(void){return prepared&&stream&&owned_file;}
bool native_scene_mesh(const DepthRect **out,unsigned *count,int *dx,int *dy,unsigned *visible){
 if(!native_scene_prepared()||!mesh)return false;
 *out=mesh;*count=mesh_count;*dx=mesh_dx;*dy=mesh_dy;*visible=mesh_visible;return true;
}
void native_scene_camera(int *x,int *y){*x=view_x;*y=view_y;}
bool native_scene_publish(bool show){
 if(!stream||!stream->pending)return !show;
 bgSetScroll(1,view_x%512,view_y%256);
 if(show)bgShow(1);else bgHide(1);
 bgUpdate();return native_bg_stream_publish(stream);
}
