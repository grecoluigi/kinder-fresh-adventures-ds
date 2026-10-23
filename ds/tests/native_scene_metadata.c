/* Exercise actual scene loader/resolvers/submission against complete raw banks.
 * The native scene/display service is stubbed: this is not a GPU pixel test. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "scene.c"
static unsigned submitted[4],draw_calls;
static int draw_x,draw_y;
static bool accepting=true,collecting=true,scene_active;
bool gpu_actors_native(unsigned kind,unsigned frame,unsigned w,unsigned h,int x,int y){
 submitted[0]=kind;submitted[1]=frame;submitted[2]=w;submitted[3]=h;
 draw_x=x;draw_y=y;draw_calls++;return accepting;
}
bool gpu_actors_collect_only(void){return collecting;}
void gpu_actors_ordinal(unsigned order){(void)order;}
void native_scene_close(void){scene_active=false;}
bool native_scene_open(const char *name,void *memory,size_t bytes){(void)name;(void)memory;(void)bytes;scene_active=true;return true;}
bool native_scene_active(void){return scene_active;}
size_t native_scene_asset_bytes(void){return 0;}
void native_scene_set_service_callback(void (*callback)(void)){(void)callback;}
bool native_scene_render(uint16_t *pixels,int x,int y,NativeSceneCallback callback,void *context,SceneRenderStats *stats){
 (void)pixels;(void)x;(void)y;(void)callback;(void)context;(void)stats;return false;
}
static void put16(uint8_t *p,unsigned n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
#ifndef KF_METADATA_BASELINE
static uint8_t *load(const char *path){
 FILE *f=fopen(path,"rb");assert(f&&!fseek(f,0,SEEK_END));long size=ftell(f);assert(size>0&&!fseek(f,0,SEEK_SET));
 uint8_t *p=malloc((size_t)size);assert(p&&fread(p,1,(size_t)size,f)==(size_t)size);fclose(f);return p;
}
/* Independent projection oracle, without production ds_projection helpers. */
static int project(int n){int v=n*8+12;return v>=0?v/25:-((-v+24)/25);}
static unsigned checked_views,checked_geometry,checked_ranges,checked_bounds;
static const int positions[][4]={{0,0,0,0},{400,300,0,0},{-100,-40,0,0},
 {800,600,0,0},{700,450,13,7},{23,17,7,13},{-5,17,-25,50},{1,2,24,25},{900,500,350,110}};
static void check_bank(const uint8_t *raw,bool enemies){
 unsigned resources=read_le16(raw+4),stride=enemies?40u:48u,rs=enemies?84u:12u;
 const uint8_t *original_frames=raw+12+resources*rs;
 for(unsigned resource=0;resource<resources;resource++){
  const uint8_t *r=raw+12+resource*rs;
  unsigned id=read_le16(r),first=read_le16(r+2),count=read_le16(r+4);
  uint8_t *e=live_entities[0].bytes;
  memset(e,0,ENTITY_RECORD_BYTES);put16(e,id);put16(e+6,1);e[45]=1;
  build_render_routes();
  RenderBounds expected={INT16_MAX,INT16_MAX,INT16_MIN,INT16_MIN,(uint16_t)count};
  for(unsigned frame=first;frame<first+count;frame++)for(unsigned facing=0;facing<2;facing++){
   const uint8_t *g=original_frames+frame*stride+(enemies?16:24)+facing*16;
   int w=read_le16(g),h=read_le16(g+2),x=(int16_t)read_le16(g+4),y=(int16_t)read_le16(g+6);
   if(x<expected.left)expected.left=(int16_t)x;
   if(y<expected.top)expected.top=(int16_t)y;
   if(x+w>expected.right)expected.right=(int16_t)(x+w);
   if(y+h>expected.bottom)expected.bottom=(int16_t)(y+h);
  }
  RenderBounds actual=enemies?enemy_bounds[resource]:pickup_bounds[resource];
  assert(actual.left==expected.left&&actual.right==expected.right&&actual.top==expected.top&&actual.bottom==expected.bottom&&actual.frames==count);checked_bounds++;
  EntityEnvironment env={0};assert(scene_entity_environment(0,&env));
  const uint8_t *origin=original_frames+first*stride+(enemies?0:8);
  assert(env.width==(int16_t)read_le16(origin)&&env.height==(int16_t)read_le16(origin+2));
  assert(env.first==(int16_t)read_le16(r+(enemies?8:6))&&env.last==(int16_t)read_le16(r+(enemies?10:8)));
  if(enemies){
   EnemyEnvironment enemy={0};assert(scene_enemy_environment(0,&enemy));
   for(unsigned range=0;range<19;range++){
    int16_t a,b;assert(scene_enemy_animation_range(0,range,&a,&b));
    assert(a==(int16_t)read_le16(r+8+range*4)&&b==(int16_t)read_le16(r+10+range*4));
    if(range<18)assert(enemy.ranges[range][0]==a&&enemy.ranges[range][1]==b);
    checked_ranges++;
   }
  }
  for(unsigned local=0;local<count;local++)for(unsigned facing=0;facing<2;facing++){
   unsigned number=first+local;const uint8_t *frame=original_frames+number*stride;
   const uint8_t *native=frame+(enemies?0:8),*g=frame+(enemies?16:24)+facing*16;
   put16(e+14,local);e[43]=(uint8_t)facing;
   GeometryObject geometry;assert(scene_geometry_object(0,&geometry));
   int ax=(int16_t)read_le16(native+4);
   if(facing)ax=(int16_t)(read_le16(r+(enemies?6:10))-read_le16(native)-ax);
   assert(geometry.id==(int16_t)id&&geometry.width==(int16_t)read_le16(native)&&geometry.height==(int16_t)read_le16(native+2));
   assert(geometry.align_x==ax&&geometry.align_y==(int16_t)read_le16(native+6));checked_geometry++;
   for(unsigned position=0;position<sizeof(positions)/sizeof(positions[0]);position++){
    const int *v=positions[position];put16(e+2,(unsigned)v[0]);put16(e+4,(unsigned)v[1]);
    unsigned w=read_le16(g),h=read_le16(g+2);
    int left=project(v[0])-project(v[2])+(int16_t)read_le16(g+4),top=project(v[1])-project(v[3])+(int16_t)read_le16(g+6);
    bool visible=left<256&&top<192&&left+(int)w>0&&top+(int)h>0;
    view_dx=project(v[2]);view_dy=project(v[3]);if(event_culled(0))assert(!visible);
    unsigned before=draw_calls;
    bool ok=enemies?draw_enemy_object(NULL,0,v[2],v[3]):draw_live_object(NULL,0,v[2],v[3]);assert(ok);
    assert(draw_calls==before+(visible?1u:0u));
    if(visible){assert(submitted[0]==(enemies?1u:2u)&&submitted[1]==number*2+facing&&submitted[2]==w&&submitted[3]==h&&draw_x==left&&draw_y==top);}
    checked_views++;
   }
  }
  unsigned before=draw_calls;
  put16(e+6,0);assert(draw_live_object(NULL,0,0,0)&&draw_calls==before);
  put16(e+6,1);e[45]=0;assert(draw_live_object(NULL,0,0,0)&&draw_calls==before);
  e[45]=1;e[185]=1;assert(draw_live_object(NULL,0,0,0)&&draw_calls==before);e[185]=0;
 }
}
#endif
/* Stable binary trace for comparing old/new production geometry on all maps.
 * Original object metadata wins when present, as in real gameplay. */
static void emit_geometry(size_t index,int frame){
 int32_t out[20]={0};GeometryObject g;
 out[0]=scene_geometry_object(index,&g);
 if(out[0]){int32_t fields[]={g.id,g.x,g.y,g.active,g.width,g.height,g.align_x,g.align_y,g.solid,g.top_trim,g.object_index};memcpy(out+1,fields,sizeof(fields));}
 EntityEnvironment env={0};out[12]=scene_entity_environment(index,&env);
 if(out[12]){out[13]=env.first;out[14]=env.last;out[15]=env.width;out[16]=env.height;}
 out[17]=scene_entity_update_region(index,0,0);out[18]=scene_entity_update_region(index,600,300);out[19]=frame;
 assert(fwrite(out,sizeof(out),1,stdout)==1);
}
int main(int argc,char **argv){
 assert(argc>=2);
 if(!strcmp(argv[1],"--maps")){
  for(int map=2;map<argc;map++){
   scene_enable_live_enemies(true);scene_enable_background_parallax(false);assert(scene_open(argv[map]));
   assert(fwrite(live_indices,sizeof(live_indices[0]),metadata.static_object_count,stdout)==metadata.static_object_count);
   assert(fwrite(live_static_indices,sizeof(live_static_indices[0]),live_count,stdout)==live_count);
   for(size_t i=0;i<live_count;i++){
    uint8_t *e=live_entities[i].bytes;emit_geometry(i,(int16_t)read_le16(e+14));
    unsigned id=read_le16(e);if(id>=1024||object_resource_lookup[id]<0)continue;
    unsigned count=read_le16(object_metadata+8+object_resource_lookup[id]*8+4);
    for(unsigned frame=0;frame<count;frame++)for(unsigned facing=0;facing<2;facing++){put16(e+14,frame);e[43]=(uint8_t)facing;emit_geometry(i,(int)frame);}
   }
   scene_close();
  }
  return 0;
 }
#ifndef KF_METADATA_BASELINE
 if(!strcmp(argv[1],"--open")){
  assert(argc==4);uint8_t *memory=NULL;size_t bytes=0;
  bool ok=open_actor_metadata(argv[2],!strcmp(argv[2],"enemies.frames"),&memory,&bytes);
  assert(ok==(argv[3][0]=='1'));free(memory);return 0;
 }
 char path[4096];snprintf(path,sizeof(path),"%s/enemies.frames",argv[1]);uint8_t *raw_enemy=load(path);
 snprintf(path,sizeof(path),"%s/pickups.frames",argv[1]);uint8_t *raw_pickup=load(path);
 assert(!memcmp(raw_enemy,"KFES",4)&&!memcmp(raw_pickup,"KFSP",4));
 live_count=1;live_entities=calloc(1,sizeof(*live_entities));assert(live_entities);put16(live_entities[0].bytes,3);
 live_enemies_enabled=true;live_static_indices[0]=UINT16_MAX;
 assert(open_enemies()&&open_actor_metadata("pickups.frames",false,&pickup_pack,&pickup_bytes));
 pickup_resource_count=read_le16(pickup_pack+4);pickup_frame_count=read_le16(pickup_pack+6);
 unsigned bytes;assert(scene_native_cache(&bytes)&&bytes==128u*1024u);
 check_bank(raw_enemy,true);check_bank(raw_pickup,false);
 collecting=false;assert(!draw_live_object(NULL,0,0,0));collecting=true;
 accepting=false;put16(live_entities[0].bytes,3);put16(live_entities[0].bytes+14,0);put16(live_entities[0].bytes+2,400);put16(live_entities[0].bytes+4,300);live_entities[0].bytes[43]=0;
 assert(!draw_enemy_object(NULL,0,0,0));accepting=true;
 scene_close();assert(!scene_native_cache(&bytes)&&!bytes);
 const size_t budgets[]={0,256u*1024u,384u*1024u,512u*1024u,1024u*1024u};
 for(unsigned i=0;i<sizeof(budgets)/sizeof(budgets[0]);i++){
  scene_set_sprite_cache_bytes(budgets[i]);live_count=1;live_entities=calloc(1,sizeof(*live_entities));assert(live_entities);put16(live_entities[0].bytes,3);assert(open_enemies());
  unsigned expected=budgets[i]<128u*1024u?128u*1024u:budgets[i]>512u*1024u?512u*1024u:(unsigned)budgets[i];assert(scene_native_cache(&bytes)&&bytes==expected);scene_close();
 }
 free(raw_enemy);free(raw_pickup);
 printf("{\"clipped_views\":%u,\"geometry_facings\":%u,\"animation_ranges\":%u,\"resource_bounds\":%u,\"cache_budget_cases\":5}\n",checked_views,checked_geometry,checked_ranges,checked_bounds);return 0;
#else
 return 1;
#endif
}
