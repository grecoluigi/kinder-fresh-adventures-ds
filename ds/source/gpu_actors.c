#include "native_actors.h"
#include "world.h"
#include "gpu_actors.h"
#if KF_GPU_ACTORS_ENABLED
static uint16_t pixels[256*64] __attribute__((aligned(4)));
/* Main-thread-only shared strip scratch; never a 96KiB DS stack allocation. */
static uint16_t scratch[256*8] __attribute__((aligned(4)));
static ActorAtlas atlas;
static unsigned ordinal;
static bool collect_only,reference;
static volatile unsigned gpu_actor_unsupported,gpu_actor_draws,gpu_actor_source_pixels;
void gpu_actors_reset(void){
 if(reference)return;
 gpu_native_reset(world_map_name());gpu_native_source(pixels,sizeof(pixels));gpu_native_allow(true);
 collect_only=false;
 actor_atlas_reset(&atlas,pixels);ordinal=0;
 gpu_actor_unsupported=gpu_actor_draws=gpu_actor_source_pixels=0;
}
void gpu_actors_ordinal(unsigned order){if(reference)return;if(order>255||order<ordinal)atlas.failed=true;else ordinal=order;}
void gpu_actors_unsupported(void){if(reference)return;atlas.failed=true;gpu_actor_unsupported++;}
uint16_t *gpu_actors_scratch(void){return scratch;}
const ActorAtlas *gpu_actors_frame(void){return &atlas;}
void gpu_actors_sprite(const uint16_t *image,unsigned width,unsigned height,unsigned stride,int left,int top,unsigned kind){
 if(reference||!collect_only)return;
 (void)kind;
 if(left>=256||top>=192||left<=-(int)width||top<=-(int)height)return;
 #ifndef KF_NATIVE_FAST_REFERENCE
 if(gpu_native_enabled()){
  if(kind>2){
   unsigned first=atlas.count;
   if(!actor_atlas_append(&atlas,image,width,height,stride,left,top,ordinal)){gpu_native_skip_source();return;}
   for(unsigned i=first;i<atlas.count;i++)gpu_native_transient(atlas.pieces+i);
   gpu_native_skip_source();gpu_actor_draws++;gpu_actor_source_pixels+=width*height;return;
  }
  gpu_native_sprite(width,height,left,top,kind,ordinal);gpu_native_skip_source();
  /* Indexed native frames do not consume the RGB transient atlas. */
  gpu_actor_draws++;gpu_actor_source_pixels+=width*height;return;
 }
 #endif
 gpu_native_forget_source();
 gpu_native_sprite(width,height,left,top,kind,ordinal);
 gpu_actor_draws++;gpu_actor_source_pixels+=width*height;
 actor_atlas_append(&atlas,image,width,height,stride,left,top,ordinal);
}

bool gpu_actors_native(unsigned kind,unsigned frame,unsigned width,unsigned height,int left,int top){
 #ifdef KF_NATIVE_FAST_REFERENCE
 return false;
 #endif
 if(reference||!collect_only||!gpu_native_enabled())return false;
 gpu_native_try(kind,frame,width,height,left,top,ordinal);gpu_native_skip_source();
 /* Native texture capacity is checked by gpu_native_prepare. */
 gpu_actor_draws++;gpu_actor_source_pixels+=width*height;return true;
}
void gpu_actors_set_collect_only(bool enabled){collect_only=enabled;}
bool gpu_actors_collect_only(void){return collect_only&&!reference;}
bool gpu_actors_reference(bool enabled){bool previous=reference;reference=enabled;return previous;}
bool gpu_actors_reference_active(void){return reference;}

#endif
