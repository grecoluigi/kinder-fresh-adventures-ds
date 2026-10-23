#include "native_scene.h"
#include "native_scene_workspace.h"
#include "native_actors.h"
#include "gpu_actors.h"
#include "hot_code.h"
#include "ds_projection.h"
#include "scene.h"

#include "tile_codec.h"
#include "scene_actor_metadata.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#ifdef __NDS__
#include <nds/system_counter.h>
#include <nds/bios.h>
#endif
static uint32_t profile_ticks(void) {
#ifdef __NDS__
    return (uint32_t)systemCounterGetTicks();
#else
    return 0;
#endif
}
static uint32_t profile_us(uint32_t ticks) {
#ifdef __NDS__
    return systemCounterTicksToUsec(ticks);
#else
    (void)ticks; return 0;
#endif
}
#ifndef SCENE_ROOT
#define SCENE_ROOT "nitro:/scenes"
#endif
#define MAX_OBJECTS 1024
#define MAX_LAYERS 8

typedef struct { uint16_t id,w,h; uint8_t layer,group; int32_t x,y; uint32_t sprite; } StaticObject;
static SceneRenderStats render_stats;
const SceneRenderStats *scene_render_stats(void) { return &render_stats; }
static SceneMetadata metadata;
static CollisionMap collision;
static StaticObject objects[MAX_OBJECTS];
static uint16_t live_indices[MAX_OBJECTS];
static uint16_t live_static_indices[MAX_OBJECTS];
static GameEntity *live_entities;
static int16_t live_initial_x[MAX_OBJECTS],live_initial_y[MAX_OBJECTS];
static size_t live_count;
static uint8_t *pickup_pack;
static size_t pickup_bytes;
static uint16_t pickup_resource_count,pickup_frame_count;
static bool live_enemies_enabled;
void scene_enable_live_enemies(bool enabled){live_enemies_enabled=enabled;}
static uint8_t *enemy_metadata;
static uint16_t enemy_resources,enemy_frames;
static size_t enemy_metadata_bytes,native_cache_capacity;
static int16_t enemy_resource_lookup[1024];
static uint8_t *object_metadata;
static size_t object_metadata_bytes;
typedef struct {int32_t left,top,right,bottom;} ObjectRegion;
static ObjectRegion *object_regions;
static size_t object_region_bytes;
static int16_t object_resource_lookup[1024];
static uint16_t object_resource_count,object_frame_count;
#define NATIVE_CACHE_LIMIT (512u*1024u)
/* This arena belongs exclusively to the immutable native source cache. */
static uint8_t *native_cache_arena;
static size_t native_cache_budget=128u*1024u;
void scene_set_sprite_cache_bytes(size_t bytes){
    if(bytes<128u*1024u)bytes=128u*1024u;
    native_cache_budget=bytes>NATIVE_CACHE_LIMIT?NATIVE_CACHE_LIMIT:bytes;
}
static FILE *map_file;
/* View culling for object draw events. Each live entity is routed once at load
 * to the same enemy/pickup draw path draw_live_object selects; bounds cover
 * every frame raster and facing of that resource. A culled event is one whose
 * draw would return true without drawing; anything uncertain is dispatched. */
typedef struct {int16_t left,top,right,bottom;uint16_t frames;} RenderBounds;
enum {ROUTE_DISPATCH,ROUTE_ENEMY,ROUTE_PICKUP};
static RenderBounds enemy_bounds[64],pickup_bounds[16];
static uint8_t live_route[MAX_OBJECTS],live_route_resource[MAX_OBJECTS];
static int view_dx,view_dy;
static volatile unsigned scene_events_culled,scene_events_dispatched;
#ifdef SCENE_VERIFY_CULL
static volatile unsigned scene_cull_mismatches;
#endif


static uint32_t tile_offset;
static unsigned collision_resident_layer;
static uint8_t streamed_cell[3];
static uint16_t *background;
static uint8_t *background_pack;
static bool background_indexed,background_scaled;
static size_t background_bytes;
static bool ready;
static volatile uint16_t *hardware_background;
static bool hardware_background_ready;
static unsigned hardware_background_x;
static volatile uint32_t hardware_background_hash;
void scene_set_hardware_background(uint16_t *arena,size_t bytes){
    hardware_background=arena&&bytes>=256u*256u*2u&&!((uintptr_t)arena&1)?arena:NULL;
    hardware_background_ready=false;hardware_background_x=0;hardware_background_hash=0;
}
bool scene_hardware_background_active(void){return ready&&hardware_background_ready;}
unsigned scene_hardware_background_offset(void){return hardware_background_x;}
static bool prepare_hardware_background(void);
static bool background_parallax;
void scene_enable_background_parallax(bool enabled){background_parallax=enabled;}
static NativeSceneWorkspace native_scene_memory __attribute__((aligned(32)));


static int callback_layer=-1;


static SceneLayerCallback layer_callback;
static void *layer_context;
void scene_set_layer_callback(SceneLayerCallback callback,void *context) {
    layer_callback=callback; layer_context=context; callback_layer=-1;
}
void scene_set_layer_callback_at_layer(SceneLayerCallback callback,void *context,int layer) {
    layer_callback=callback;layer_context=context;callback_layer=layer;
}
void scene_release_renderer(void) {
    native_scene_close();


}

static uint16_t read_le16(const uint8_t *p) { return (uint16_t)(p[0] | p[1]<<8); }
static uint32_t read_le32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24; }
static void (*service_callback)(void);
void scene_set_service_callback(void (*callback)(void)){
    service_callback=callback;native_scene_set_service_callback(callback);
}
static bool read_at(FILE *f,long offset,void *dest,size_t bytes) {
    render_stats.read_calls++; render_stats.read_bytes+=(uint32_t)bytes;
    bool ok=f && fseek(f,offset,SEEK_SET)==0 && fread(dest,1,bytes,f)==bytes;
    if(service_callback)service_callback();
    return ok;
}
static FILE *open_file(const char *name) {
    char path[256];
    if (snprintf(path,sizeof(path),"%s/%s",SCENE_ROOT,name)>=(int)sizeof(path)) return NULL;
    return fopen(path,"rb");
}
static const uint8_t *read_collision_cell(void *context,unsigned layer,unsigned x,unsigned y){
    (void)context;
    long offset=tile_offset+((long)layer*metadata.width_cells*metadata.height_cells+(long)y*metadata.width_cells+x)*3;
    return read_at(map_file,offset,streamed_cell,3)?streamed_cell:NULL;
}

void scene_close(void) {
    hardware_background_ready=false;hardware_background_x=0;hardware_background_hash=0;


    free(background);background=NULL;free(background_pack);background_pack=NULL;background_bytes=0;background_scaled=false;

    collision_unbind_layer(&collision);
    scene_release_renderer();
    free(enemy_metadata);enemy_metadata=NULL;enemy_metadata_bytes=0;enemy_resources=enemy_frames=0;
    free(object_metadata);object_metadata=NULL;object_metadata_bytes=0;object_regions=NULL;object_region_bytes=0;
    free(native_cache_arena);native_cache_arena=NULL;native_cache_capacity=0;
    free(live_entities);live_entities=NULL;live_count=0;
    free(pickup_pack);pickup_pack=NULL;pickup_bytes=0;pickup_resource_count=pickup_frame_count=0;
    if (map_file) fclose(map_file);
    map_file=NULL;

    free((void *)collision.tiles);
    for (int i=0;i<4;i++) free((void *)collision.atlas[i].bits);
    memset(&collision,0,sizeof(collision));


    ready=false;
}
const CollisionMap *scene_collision_map(void) { return ready ? &collision : NULL; }
const SceneMetadata *scene_metadata(void) { return ready ? &metadata : NULL; }
size_t scene_resident_asset_bytes(void){
    if(!ready)return 0;
    size_t bytes=(size_t)collision.width*collision.height*3+live_count*sizeof(*live_entities)+pickup_bytes+native_scene_asset_bytes()+background_bytes+(background?256u*192u*2u:0);
    for(unsigned i=0;i<4;i++)bytes+=((size_t)collision.atlas[i].width*collision.atlas[i].height+7)/8;
    return bytes+object_metadata_bytes+object_region_bytes+(native_cache_arena?native_cache_capacity:0)+enemy_metadata_bytes;
}
GameEntity *scene_entities(size_t *count){if(count)*count=live_count;return live_entities;}
static const uint8_t *pickup_resource(unsigned id){
    if(!pickup_pack)return NULL;
    for(unsigned i=0;i<pickup_resource_count;i++){const uint8_t *r=pickup_pack+12+i*12;if(read_le16(r)==id)return r;}
    return NULL;
}
static const uint8_t *enemy_resource(unsigned id);
static bool live_obstacle(unsigned id){
    return (id>=6&&id<=18)||id==59||id==200||id==201||id==202||id==210||id==220||(id>=230&&id<=233)||id==76||id==77||id==78||id==83||id==86||id==87||id==60||id==75||id==79||id==80||id==82||id==84||id==85||id==88||id==89||id==265||id==352||id==354||id==355||id==356||id==414;
}
bool scene_entity_environment(size_t index,EntityEnvironment *env){
    if(index>=live_count||!env)return false;
    unsigned id=read_le16(live_entities[index].bytes);const uint8_t *r=pickup_resource(id);
    if(!r){
        r=enemy_resource(id);if(!r)return false;
        const uint8_t *f=enemy_metadata+12+enemy_resources*84+read_le16(r+2)*SCENE_ACTOR_FRAME_BYTES;
        unsigned native=0;
        env->first=(int16_t)read_le16(r+8);env->last=(int16_t)read_le16(r+10);
        env->width=(int16_t)read_le16(f+native);env->height=(int16_t)read_le16(f+native+2);return true;
    }
    const uint8_t *f=pickup_pack+12+pickup_resource_count*12+read_le16(r+2)*SCENE_ACTOR_FRAME_BYTES;
    env->first=(int16_t)read_le16(r+6);env->last=(int16_t)read_le16(r+8);env->width=(int16_t)read_le16(f);env->height=(int16_t)read_le16(f+2);return true;
}
static const uint8_t *enemy_resource(unsigned id){
    if(!enemy_metadata||id>=1024||enemy_resource_lookup[id]<0)return NULL;
    return enemy_metadata+12+(unsigned)enemy_resource_lookup[id]*84;
}
bool scene_geometry_object(size_t index,GeometryObject *object){
    if(index>=live_count||!object)return false;
    const uint8_t *e=live_entities[index].bytes;
    unsigned id=read_le16(e);int frame=(int16_t)read_le16(e+14);
    const uint8_t *resource=enemy_resource(id),*f=NULL;
    int width=0,height=0,ax=0,ay=0;
    const uint8_t *all_resource=NULL;
    if(object_metadata&&id<1024&&object_resource_lookup[id]>=0)all_resource=object_metadata+8+object_resource_lookup[id]*8;
    if(all_resource){
        if(frame<0||frame>=read_le16(all_resource+4))return false;
        f=object_metadata+8+object_resource_count*8+(read_le16(all_resource+2)+(unsigned)frame)*8;
        width=read_le16(f);height=read_le16(f+2);ax=(int16_t)read_le16(f+4);ay=(int16_t)read_le16(f+6);
        if(e[43])ax=(int16_t)(read_le16(all_resource+6)-width-ax);
    }else if(resource){
        if(frame<0||frame>=read_le16(resource+4))return false;
        f=enemy_metadata+12+enemy_resources*84+(read_le16(resource+2)+(unsigned)frame)*SCENE_ACTOR_FRAME_BYTES;
        unsigned native=0;
        width=read_le16(f+native);height=read_le16(f+native+2);
        ax=(int16_t)read_le16(f+native+4);ay=(int16_t)read_le16(f+native+6);
        if(e[43])ax=(int16_t)(read_le16(resource+6)-width-ax);
    }else if((resource=pickup_resource(id))!=NULL){
        if(frame<0||frame>=read_le16(resource+4))return false;
        /* Original geometry is independent of the two scaled draw facings. */
        f=pickup_pack+12+pickup_resource_count*12+(read_le16(resource+2)+(unsigned)frame)*SCENE_ACTOR_FRAME_BYTES;
        unsigned native=0;
        width=read_le16(f+native);height=read_le16(f+native+2);
        ax=(int16_t)read_le16(f+native+4);ay=(int16_t)read_le16(f+native+6);
        if(e[43])ax=(int16_t)(read_le16(resource+10)-width-ax);
    }else{
        bool found=false;
        unsigned i=live_static_indices[index];
        if(i<metadata.static_object_count){
            /* Existing static pack retains its script-selected frame. Full AOM
             * current-frame metadata replaces this fallback in the next pack. */
            width=objects[i].w;height=objects[i].h;
            ax=(int16_t)(objects[i].x-live_initial_x[index]);
            ay=(int16_t)(objects[i].y-live_initial_y[index]);found=true;
        }
        if(!found)return false;
    }
    *object=(GeometryObject){.id=(int16_t)id,.x=(int16_t)read_le16(e+2),
        .y=(int16_t)read_le16(e+4),.active=(int16_t)read_le16(e+6),
        .width=(int16_t)width,.height=(int16_t)height,.align_x=(int16_t)ax,
        .align_y=(int16_t)ay,.solid=e[26],.top_trim=e[42],.object_index=(int32_t)index};
    return true;
}
/* Inline the existing resolver here so the compiler can remove unused output
 * fields and stack stores. Keep its exact frame/mirror/fallback semantics. */
__attribute__((flatten)) KF_ITCM_CODE bool scene_entity_update_region(size_t index,int camera_x,int camera_y){
    if(index>=live_count)return false;
    const uint8_t *entity=live_entities[index].bytes;
    unsigned id=read_le16(entity);
    /* All-frame/all-facing bounds only reject impossible overlaps. Persistent
     * entities and uncertain/boundary cases retain exact frame validation. */
    if(object_regions&&!entity[184]&&id<1024&&object_resource_lookup[id]>=0){
        const ObjectRegion *r=object_regions+object_resource_lookup[id];
        int x=(int16_t)read_le16(entity+2),y=(int16_t)read_le16(entity+4);
        if(r->left<=r->right&&r->top<=r->bottom&&
           (x+r->right<=camera_x-350||x+r->left>=camera_x+1150||
            y+r->bottom<=camera_y-350||y+r->top>=camera_y+950))return false;
    }
    GeometryObject object;if(!scene_geometry_object(index,&object))return false;
    if(live_entities[index].bytes[184])return true;
    int left=object.x+object.align_x,top=object.y+object.align_y;
    return left+object.width>camera_x-350&&left<camera_x+800+350&&
           top+object.height>camera_y-350&&top<camera_y+600+350;
}
bool scene_enemy_animation_range(size_t index,unsigned range,int16_t *first,int16_t *last){
    if(index>=live_count||range>=19||!first||!last)return false;
    const uint8_t *r=enemy_resource(read_le16(live_entities[index].bytes));if(!r)return false;
    *first=(int16_t)read_le16(r+8+range*4);*last=(int16_t)read_le16(r+10+range*4);return true;
}
bool scene_enemy_environment(size_t index,EnemyEnvironment *env){
    if(index>=live_count||!env)return false;
    const uint8_t *r=enemy_resource(read_le16(live_entities[index].bytes));if(!r)return false;
    for(unsigned i=0;i<18;i++){env->ranges[i][0]=(int16_t)read_le16(r+8+i*4);env->ranges[i][1]=(int16_t)read_le16(r+10+i*4);}
    return true;
}
static bool open_actor_metadata(const char *name,bool enemies,uint8_t **data,size_t *bytes){
    FILE *file=open_file(name);if(!file)return false;
    uint8_t header[12];size_t size=0;
    bool ok=read_at(file,0,header,sizeof(header))&&scene_actor_metadata_size(header,enemies,&size);
    uint8_t *memory=ok?malloc(size):NULL;
    ok=ok&&memory&&read_at(file,0,memory,size);
    if(ok)ok=fgetc(file)==EOF&&!ferror(file)&&scene_actor_metadata_valid(memory,size,enemies);
    fclose(file);
    if(!ok){free(memory);return false;}
    *data=memory;*bytes=size;return true;
}
static bool open_enemies(void){
    bool needed=false;for(size_t i=0;i<live_count;i++){unsigned id=read_le16(live_entities[i].bytes);if((live_enemies_enabled&&id>=3&&id<=5)||live_obstacle(id))needed=true;}
    if(!needed)return true;
    if(!open_actor_metadata("enemies.frames",true,&enemy_metadata,&enemy_metadata_bytes))return false;
    enemy_resources=read_le16(enemy_metadata+4);enemy_frames=read_le16(enemy_metadata+6);
    native_cache_capacity=native_cache_budget;
    native_cache_arena=malloc(native_cache_capacity);if(!native_cache_arena)return false;
    memset(enemy_resource_lookup,0xff,sizeof(enemy_resource_lookup));
    for(unsigned i=0;i<enemy_resources;i++){
        const uint8_t *r=enemy_metadata+12+i*84;
        enemy_resource_lookup[read_le16(r)]=(int16_t)i;
    }
    return true;
}
static bool open_object_metadata(void){
    FILE *f=open_file("objects.geometry");if(!f)return true; /* Old packs remain usable during staged migration. */
    uint8_t h[8];bool ok=read_at(f,0,h,8)&&!memcmp(h,"KFOG",4);if(!ok){fclose(f);return false;}
    object_resource_count=read_le16(h+4);object_frame_count=read_le16(h+6);
    object_metadata_bytes=8+(size_t)object_resource_count*8+(size_t)object_frame_count*8;
    if(object_resource_count>1024||object_metadata_bytes>100000){fclose(f);return false;}
    object_region_bytes=(size_t)object_resource_count*sizeof(*object_regions);
    object_metadata=malloc(object_metadata_bytes+object_region_bytes);
    if(object_metadata)object_regions=(ObjectRegion *)(object_metadata+object_metadata_bytes);
    else{object_region_bytes=0;object_metadata=malloc(object_metadata_bytes);}
    ok=object_metadata&&read_at(f,0,object_metadata,object_metadata_bytes);fclose(f);if(!ok)return false;
    memset(object_resource_lookup,0xff,sizeof(object_resource_lookup));
    for(unsigned i=0;i<object_resource_count;i++){const uint8_t *r=object_metadata+8+i*8;unsigned id=read_le16(r);if(id>=1024||(unsigned)read_le16(r+2)+read_le16(r+4)>object_frame_count)return false;object_resource_lookup[id]=(int16_t)i;}
    if(object_regions)for(unsigned i=0;i<object_resource_count;i++){
        const uint8_t *r=object_metadata+8+i*8;
        ObjectRegion bounds={INT32_MAX,INT32_MAX,INT32_MIN,INT32_MIN};
        for(unsigned j=0;j<read_le16(r+4);j++){
            const uint8_t *frame=object_metadata+8+object_resource_count*8+(read_le16(r+2)+j)*8;
            int width=(int16_t)read_le16(frame),height=(int16_t)read_le16(frame+2),ay=(int16_t)read_le16(frame+6);
            for(unsigned mirror=0;mirror<2;mirror++){
                int ax=(int16_t)read_le16(frame+4);
                if(mirror)ax=(int16_t)(read_le16(r+6)-read_le16(frame)-ax);
                int right=ax+width,bottom=ay+height;
                if(ax<bounds.left)bounds.left=ax;
                if(right<bounds.left)bounds.left=right;
                if(ax>bounds.right)bounds.right=ax;
                if(right>bounds.right)bounds.right=right;
                if(ay<bounds.top)bounds.top=ay;
                if(bottom<bounds.top)bounds.top=bottom;
                if(ay>bounds.bottom)bounds.bottom=ay;
                if(bottom>bounds.bottom)bounds.bottom=bottom;
            }
        }
        object_regions[i]=bounds;
    }
    return true;
}
static bool open_entities(const char *name){
    char filename[96];snprintf(filename,sizeof(filename),"%s.entities",name);FILE *f=open_file(filename);uint8_t header[12];
    bool ok=read_at(f,0,header,8);if(!ok||memcmp(header,"KFE1",4)){if(f)fclose(f);return false;}
    live_count=read_le32(header+4);if(live_count>MAX_OBJECTS){fclose(f);return false;}
    live_entities=malloc(live_count*sizeof(*live_entities));ok=live_entities&&fread(live_entities,sizeof(*live_entities),live_count,f)==live_count;fclose(f);if(!ok)return false;
    for(size_t i=0;i<live_count;i++){
        live_initial_x[i]=(int16_t)read_le16(live_entities[i].bytes+2);
        live_initial_y[i]=(int16_t)read_le16(live_entities[i].bytes+4);
        /* Native4118e0..41191c consumes start markers and deactivates them. */
        if(read_le16(live_entities[i].bytes)==1000){live_entities[i].bytes[6]=0;live_entities[i].bytes[7]=0;}
    }
    if(!open_actor_metadata("pickups.frames",false,&pickup_pack,&pickup_bytes))return false;
    pickup_resource_count=read_le16(pickup_pack+4);pickup_frame_count=read_le16(pickup_pack+6);
    return true;
}
static RenderBounds raster_bounds(const uint8_t *frames,unsigned first,unsigned count){
    RenderBounds b={INT16_MAX,INT16_MAX,INT16_MIN,INT16_MIN,(uint16_t)count};
    for(unsigned i=first;i<first+count;i++)for(unsigned mirror=0;mirror<2;mirror++){
        const uint8_t *r=frames+i*SCENE_ACTOR_FRAME_BYTES+8+mirror*8;
        int w=read_le16(r),h=read_le16(r+2),x=(int16_t)read_le16(r+4),y=(int16_t)read_le16(r+6);
        if(x<b.left)b.left=(int16_t)x;
        if(y<b.top)b.top=(int16_t)y;
        if(x+w>b.right)b.right=(int16_t)(x+w);
        if(y+h>b.bottom)b.bottom=(int16_t)(y+h);
    }
    return b;
}
static void build_render_routes(void){
    memset(live_route,ROUTE_DISPATCH,sizeof(live_route));
    if(enemy_metadata)for(unsigned i=0;i<enemy_resources;i++){
        const uint8_t *r=enemy_metadata+12+i*84;
        enemy_bounds[i]=raster_bounds(enemy_metadata+12+enemy_resources*84,read_le16(r+2),read_le16(r+4));
    }
    if(pickup_pack)for(unsigned i=0;i<pickup_resource_count&&i<16;i++){
        const uint8_t *r=pickup_pack+12+i*12;
        pickup_bounds[i]=raster_bounds(pickup_pack+12+pickup_resource_count*12,read_le16(r+2),read_le16(r+4));
    }
    for(size_t i=0;i<live_count;i++){
        unsigned id=read_le16(live_entities[i].bytes);const uint8_t *r;
        if((live_enemies_enabled&&id>=3&&id<=5)||(live_obstacle(id)&&enemy_resource(id))){
            if((r=enemy_resource(id))!=NULL){live_route[i]=ROUTE_ENEMY;live_route_resource[i]=(uint8_t)((r-(enemy_metadata+12))/84);}
        }else if((r=pickup_resource(id))!=NULL&&pickup_resource_count<=16){
            live_route[i]=ROUTE_PICKUP;live_route_resource[i]=(uint8_t)((r-(pickup_pack+12))/12);
        }
    }
}
/* True only when draw_live_object would return true without drawing. */
static inline bool event_culled(unsigned index){
    if(index>=live_count)return false;
    const uint8_t *e=live_entities[index].bytes;
    /* Every disjunct alone makes the draw a no-op, so test the first cache
     * line (active, frame, position) before bytes 45 and 185. */
    if(!read_le16(e+6))return true;
    unsigned route=live_route[index];
    if(route!=ROUTE_DISPATCH){
        const RenderBounds *b=route==ROUTE_ENEMY?enemy_bounds+live_route_resource[index]:pickup_bounds+live_route_resource[index];
        int frame=(int16_t)read_le16(e+14),first=route==ROUTE_ENEMY?(int16_t)read_le16(e+10):0;
        if(frame>=0&&frame<b->frames&&first>=0&&first<b->frames){
            int x=ds_world_pixel((int16_t)read_le16(e+2))-view_dx,y=ds_world_pixel((int16_t)read_le16(e+4))-view_dy;
            if(x+b->left>=256||x+b->right<=0||y+b->top>=192||y+b->bottom<=0)return true;
        }
    }
    return e[185]||!e[45];
}
bool scene_open(const char *name) {
    scene_close();
    if (!name || strchr(name,'/') || strchr(name,'\\') || strlen(name)>64) return false;
    char filename[96]; snprintf(filename,sizeof(filename),"%s.scene",name);
    map_file=open_file(filename);
    uint8_t header[64];
    if (!read_at(map_file,0,header,sizeof(header)) || memcmp(header,"KFS1",4)) goto fail;
    metadata.width_cells=read_le16(header+4); metadata.height_cells=read_le16(header+6);
    metadata.layers=read_le16(header+8); metadata.tile_width=read_le16(header+10); metadata.tile_height=read_le16(header+12);
    metadata.static_object_count=read_le16(header+14); metadata.start_x=(int32_t)read_le32(header+18); metadata.start_y=(int32_t)read_le32(header+22);
    tile_offset=read_le32(header+26);
    metadata.width_pixels=metadata.width_cells*metadata.tile_width;
    metadata.height_pixels=metadata.height_cells*metadata.tile_height;
    if (metadata.layers>MAX_LAYERS || !metadata.layers || metadata.static_object_count>MAX_OBJECTS ||
        metadata.tile_width!=32 || metadata.tile_height!=32 || !metadata.width_cells || !metadata.height_cells ||
        read_le32(header+30)!=(uint32_t)metadata.width_cells*metadata.height_cells*metadata.layers*3 ||
        tile_offset!=64u+20u*metadata.static_object_count) goto fail;
    for (unsigned i=0;i<metadata.static_object_count;i++) {
        uint8_t raw[20];
        if (fread(raw,1,sizeof(raw),map_file)!=sizeof(raw)) goto fail;
        objects[i]=(StaticObject){.id=read_le16(raw),.layer=raw[2],.group=raw[3],.x=(int32_t)read_le32(raw+4),
            .y=(int32_t)read_le32(raw+8),.sprite=read_le32(raw+12),.w=read_le16(raw+16),.h=read_le16(raw+18)};
    }
    char key[29]; memcpy(key,header+34,28); key[28]=0;
    if (!key[0] || strchr(key,'/') || strchr(key,'\\')) goto fail;
    bool ok;
    if(background_parallax){
        snprintf(filename,sizeof(filename),"%s.par",key);FILE *bg=open_file(filename);
        if(!bg)goto fail;
        ok=!fseek(bg,0,SEEK_END);long size=ok?ftell(bg):-1;
        ok=size>=1544&&size<=400000;
        if(ok){background_bytes=(size_t)size;background_pack=malloc(background_bytes);ok=background_pack&&read_at(bg,0,background_pack,background_bytes);}
        fclose(bg);
        background_scaled=ok&&!memcmp(background_pack,"KFB4",4);
        if(!ok||read_le16(background_pack+4)!=(background_scaled?256:800)||read_le16(background_pack+6)!=192)goto fail;
        background_indexed=!memcmp(background_pack,"KFB3",4);
        if(!background_scaled&&!background_indexed&&memcmp(background_pack,"KFB2",4))goto fail;
        size_t prefix=background_indexed?3080:1544;
        if(background_bytes<prefix)goto fail;
        size_t payload=background_bytes-prefix;
        for(unsigned y=0;y<192;y++){
            const uint8_t *record=background_pack+8+y*(background_indexed?16:8);
            size_t offset=read_le32(record),bytes=read_le32(record+4);unsigned bits=16;
            if((offset&3)||bytes<4||offset>payload||bytes>payload-offset)goto fail;
            if(background_indexed){
                bits=record[14];unsigned colors=read_le16(record+12);size_t palette=read_le32(record+8);
                if((bits!=4&&bits!=8&&bits!=16)||palette>payload||colors*2u>payload-palette)goto fail;
                if((bits==16&&colors)||(bits!=16&&(!colors||colors>(1u<<bits))))goto fail;
            }
            const uint8_t *row=background_pack+prefix+offset;
            if(row[0]!=16||(read_le32(row)>>8)!=(background_scaled?256u:800u)*bits/8)goto fail;
        }
    }else{
        snprintf(filename,sizeof(filename),"%s.bg",key);FILE *bg=open_file(filename);
        background=malloc(256u*192u*2u);ok=background&&read_at(bg,0,background,256u*192u*2u);if(bg)fclose(bg);
        if(!ok)goto fail;
    }
    if(!prepare_hardware_background())goto fail;
    collision.width=metadata.width_cells; collision.height=metadata.height_cells;
    collision.tile_width=32; collision.tile_height=32; collision.layers=metadata.layers;
    uint32_t bytes=read_le32(header+30);
    size_t layer_bytes=(size_t)collision.width*collision.height*3;
    if(bytes!=layer_bytes*collision.layers||fseek(map_file,0,SEEK_END))goto fail;
    long file_bytes=ftell(map_file);if(file_bytes<0||(uint64_t)file_bytes<(uint64_t)tile_offset+bytes)goto fail;
    collision_resident_layer=collision.layers>2?2:0;
    collision.tiles=malloc(layer_bytes);
    if(!collision.tiles||!read_at(map_file,tile_offset+collision_resident_layer*layer_bytes,(void *)collision.tiles,layer_bytes))goto fail;
    collision_bind_layer(&collision,collision_resident_layer,read_collision_cell,NULL);
    snprintf(filename,sizeof(filename),"%s.collision",name);
    FILE *cf=open_file(filename); uint8_t masks[308];
    ok=read_at(cf,0,masks,sizeof(masks)); if(cf) fclose(cf);
    if(!ok || memcmp(masks,"KFC1",4)) goto fail;
    for(int i=0;i<4;i++) {
        const uint8_t *record=masks+4+i*76;
        CollisionAtlas *atlas=&collision.atlas[i];
        atlas->width=read_le16(record); atlas->height=read_le16(record+2);
        char maskname[73]; memcpy(maskname,record+4,72); maskname[72]=0;
        if(strchr(maskname,'/') || strchr(maskname,'\\')) goto fail;
        size_t size=((size_t)atlas->width*atlas->height+7)/8;
        atlas->bits=malloc(size); if(!atlas->bits) goto fail;
        FILE *mf=open_file(maskname); ok=read_at(mf,0,(void *)atlas->bits,size); if(mf) fclose(mf);
        if(!ok) goto fail;
    }
    if(!open_entities(name)||!open_enemies()||!open_object_metadata())goto fail;
    memset(live_indices,0xff,sizeof(live_indices));
    memset(live_static_indices,0xff,sizeof(live_static_indices));
    size_t next=0;
    for(unsigned i=0;i<metadata.static_object_count;i++){
        const StaticObject *o=&objects[i];
        for(size_t j=next;j<live_count;j++){
            const uint8_t *e=live_entities[j].bytes;
            if(read_le16(e)!=o->id||e[25]!=o->layer||e[23]!=o->group)continue;
            if(o->id>=48&&o->id<=58){const uint8_t *r=pickup_resource(o->id);const uint8_t *f=pickup_pack+12+pickup_resource_count*12+(read_le16(r+2)+read_le16(r+6))*SCENE_ACTOR_FRAME_BYTES;
                if((int16_t)read_le16(e+2)+(int16_t)read_le16(f+4)!=o->x||(int16_t)read_le16(e+4)+(int16_t)read_le16(f+6)!=o->y)continue;
            }
            live_indices[i]=(uint16_t)j;live_static_indices[j]=(uint16_t)i;next=j+1;break;
        }
    }
    build_render_routes();
    ready=true;
#ifndef SCENE_FORCE_GENERAL
    bool jungle_art=false;
    if(live_enemies_enabled)for(size_t i=0;i<live_count;i++){unsigned id=read_le16(live_entities[i].bytes);if(id>=3&&id<=5)jungle_art=true;}
    char scene_name[96];snprintf(scene_name,sizeof(scene_name),"%s%s",name,jungle_art?".enemy":"");
    if(!native_scene_open(scene_name,&native_scene_memory,sizeof(native_scene_memory)))goto fail;
#endif
    return true;
fail:
    scene_close(); return false;
}

static bool background_decode_row(const uint8_t *s,size_t bytes,uint16_t *dest,size_t size){
    if(bytes<4||s[0]!=16||(read_le32(s)>>8)!=size)return false;
#ifdef __NDS__
    /* Packed row offsets need not be word aligned; BIOS requires aligned input.
     * Copy only an unaligned row, keeping the bounded scratch buffer in WRAM. */
    uint8_t aligned[1804] __attribute__((aligned(4)));
    if(bytes>sizeof(aligned))return false;
    if((uintptr_t)s&3u){memcpy(aligned,s,bytes);s=aligned;}
    tile_lz_wram(s,dest);return true;
#else
    size_t in=4,out=0;uint8_t *d=(uint8_t *)dest;
    while(out<size){if(in>=bytes)return false;unsigned flags=s[in++];for(unsigned bit=128;bit&&out<size;bit>>=1){
        if(flags&bit){if(in+2>bytes)return false;unsigned word=s[in]*256+s[in+1];in+=2;unsigned length=(word>>12)+3,distance=(word&4095)+1;if(distance>out||out+length>size)return false;while(length--){d[out]=d[out-distance];out++;}}
        else{if(in>=bytes)return false;d[out++]=s[in++];}
    }}return true;
#endif
}
static bool prepare_hardware_background(void){
    if(!hardware_background||!background_scaled)return true;
    uint16_t row[256] __attribute__((aligned(4)));
    for(unsigned y=0;y<192;y++){
        const uint8_t *record=background_pack+8+y*8;
        if(!background_decode_row(background_pack+1544+read_le32(record),read_le32(record+4),row,512))return false;
        for(unsigned x=0;x<256;x++)hardware_background[y*256+x]=row[x];
    }
    for(unsigned i=256*192;i<256*256;i++)hardware_background[i]=0;
    /* Once-per-load readback lets the debugger validate mapped VRAM even when
     * its memory protocol cannot expose the VRAM address range directly. */
    uint32_t hash=2166136261u;
    for(unsigned i=0;i<256*256;i++)hash=(hash^hardware_background[i])*16777619u;
    hardware_background_hash=hash;
    hardware_background_ready=true;hardware_background_x=0;return true;
}
void scene_entity_visual_step(size_t index){
    if(index>=live_count)return;
    uint8_t *e=live_entities[index].bytes;
    if(e[46]){e[45]^=1;e[46]--;}else e[45]=1;
}


static KF_ITCM_CODE bool draw_enemy_object(uint16_t *pixels,unsigned index,int cx,int cy){
    (void)pixels;
    if(!gpu_actors_collect_only())return false;
    const uint8_t *e=live_entities[index].bytes;if(!read_le16(e+6)||e[185]||!e[45])return true;
    const uint8_t *r=enemy_resource(read_le16(e));if(!r)return false;
    int frame=(int16_t)read_le16(e+14),first=(int16_t)read_le16(e+10);if(frame<0||first<0||frame>=read_le16(r+4)||first>=read_le16(r+4))return false;
    unsigned number=read_le16(r+2)+(unsigned)frame;const uint8_t *f=enemy_metadata+12+enemy_resources*84+number*SCENE_ACTOR_FRAME_BYTES;
    unsigned mirror=e[43]?1:0;const uint8_t *raster=f+8+mirror*8;
    int w=read_le16(raster),h=read_le16(raster+2);
    int left=ds_relative_pixel((int16_t)read_le16(e+2),cx)+(int16_t)read_le16(raster+4);
    int top=ds_relative_pixel((int16_t)read_le16(e+4),cy)+(int16_t)read_le16(raster+6);
    if(left>=256||top>=192||left+w<=0||top+h<=0)return true;
    return gpu_actors_native(1,number*2u+mirror,(unsigned)w,(unsigned)h,left,top);
}

static KF_ITCM_CODE bool draw_live_object(uint16_t *pixels,unsigned index,int cx,int cy){
    if(!gpu_actors_collect_only())return false;
    if(service_callback)service_callback();
    if(index>=live_count)return false;
    const uint8_t *e=live_entities[index].bytes;unsigned native_id=read_le16(e);if((live_enemies_enabled&&native_id>=3&&native_id<=5)||(live_obstacle(native_id)&&enemy_resource(native_id)))return draw_enemy_object(pixels,index,cx,cy);
    if(!read_le16(e+6)||e[185]||!e[45])return true;
    unsigned id=read_le16(e);const uint8_t *resource=pickup_resource(id);if(!resource)return false;
    int frame=(int16_t)read_le16(e+14);if(frame<0||frame>=read_le16(resource+4))return false;
    unsigned number=read_le16(resource+2)+(unsigned)frame;const uint8_t *f=pickup_pack+12+pickup_resource_count*12+number*SCENE_ACTOR_FRAME_BYTES;
    unsigned mirror=e[43]?1:0;const uint8_t *raster=f+8+mirror*8;
    int w=read_le16(raster),h=read_le16(raster+2);
    int left=ds_relative_pixel((int16_t)read_le16(e+2),cx)+(int16_t)read_le16(raster+4);
    int top=ds_relative_pixel((int16_t)read_le16(e+4),cy)+(int16_t)read_le16(raster+6);
    if(left>=256||top>=192||left+w<=0||top+h<=0)return true;
    return gpu_actors_native(2,number*2u+mirror,(unsigned)w,(unsigned)h,left,top);
}

static bool scene_dispatch_event(uint16_t *pixels,unsigned kind,unsigned index,unsigned order,int cx,int cy,void *context){
    (void)context;if(kind==1){
        if(event_culled(index)){
            scene_events_culled++;
#ifdef SCENE_VERIFY_CULL
            gpu_actors_ordinal(order);
            /* Verification builds still draw culled events; any effect is a defect. */
            unsigned native=0,atlas=gpu_actors_frame()->count;gpu_native_draws(&native);
            bool ok=draw_live_object(pixels,index,cx,cy);unsigned after=0;gpu_native_draws(&after);
            if(!ok||after!=native||gpu_actors_frame()->count!=atlas)scene_cull_mismatches++;
#endif
            return true;
        }
        scene_events_dispatched++;gpu_actors_ordinal(order);return draw_live_object(pixels,index,cx,cy);
    }
    gpu_actors_ordinal(order);
    if(kind==2){
        if(layer_callback)layer_callback(pixels,index,cx,cy,layer_context);
        else {}
    }
    return true;
}

/* Native parallax advances at half the original camera X, with fixed Y. */

static bool background_fill_impl(uint16_t *pixels,int camera_x){
    (void)pixels;
    if(!background_pack)return true;
    if(!hardware_background_ready)return false;
    int offset=ds_world_pixel(camera_x/2)%256;if(offset<0)offset+=256;
    hardware_background_x=(unsigned)offset;return true;
}
static bool background_fill(uint16_t *pixels,int camera_x){
    uint32_t started=profile_ticks();
    bool ok=background_fill_impl(pixels,camera_x);
    render_stats.background_us=profile_us(profile_ticks()-started);
    return ok;
}
bool scene_render_layers(uint16_t *pixels,const int camera_xs[8],const int camera_ys[8]) {
    if(!ready||!pixels||!camera_xs||!camera_ys||!native_scene_active())return false;
    for(int i=1;i<8;i++)if(camera_xs[i]!=camera_xs[0]||camera_ys[i]!=camera_ys[0])return false;
    if(layer_callback&&callback_layer!=2)return false;
    memset(&render_stats,0,sizeof(render_stats));
    view_dx=ds_world_pixel(camera_xs[0]);view_dy=ds_world_pixel(camera_ys[0]);

    if(!native_scene_render(pixels,camera_xs[0],camera_ys[0],scene_dispatch_event,NULL,&render_stats))return false;
    return background_fill(pixels,camera_xs[2]);
}

bool scene_render(uint16_t *pixels,int camera_x,int camera_y) {
    int camera_xs[8],camera_ys[8];
    for(int i=0;i<8;i++) { camera_xs[i]=camera_x; camera_ys[i]=camera_y; }
    return scene_render_layers(pixels,camera_xs,camera_ys);
}

void *scene_native_cache(unsigned *bytes){*bytes=native_cache_arena?(unsigned)native_cache_capacity:0;return native_cache_arena;}
