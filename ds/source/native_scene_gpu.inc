/* Included after the existing texture/bitmap helpers; private renderer state
 * stays in gpu_prefix.c so A/B and F/G have one publication owner. */
#include "native_occlusion.h"
#include "native_scenery_cache.h"
static ActorRegion native_occlusion_before[256];
static volatile unsigned gpu_scenery_cells_sampled;
/* At most 1,536 depth quads are visible (load_mesh admission limit). */
#define OCCLUDER_LIMIT 1536u
static ClippedOccluder occluder_list[OCCLUDER_LIMIT];
#ifdef NATIVE_VERIFY_SCENERY
static volatile unsigned native_scenery_verify_views,native_scenery_verify_mismatches,native_scenery_verify_failures;
#endif
bool gpu_prefix_native_enabled(void){return gpu_prefix_initialized;}
static bool native_raw_bitmap(const uint16_t *pixels){
 native_scenery_cache_invalidate(native_scenery_cells+(front_texture^1u));
 gpu_native_bg_pending=false;return gpu_prefix_prepare_bitmap(pixels);
}
static bool native_capture_hold(uint16_t *pixels){
 if(!gpu_prefix_initialized||!pixels)return false;
 unsigned bank=front_texture^1u;
 if(bank)vramSetBankB(VRAM_B_LCD);else vramSetBankA(VRAM_A_LCD);
 REG_DISPCAPCNT=DCAP_ENABLE|DCAP_MODE(DCAP_MODE_A)|DCAP_SRC_A(DCAP_SRC_A_COMPOSITED)|DCAP_SIZE(DCAP_SIZE_256x192)|DCAP_BANK(bank);
 unsigned attempts=0;while((REG_DISPCAPCNT&DCAP_ENABLE)&&attempts++<4)swiWaitForVBlank();
 bool ok=!(REG_DISPCAPCNT&DCAP_ENABLE);
 if(ok)frame_transfer(pixels,bank?VRAM_B:VRAM_A);else REG_DISPCAPCNT=0;
 if(bank)vramSetBankB(VRAM_B_TEXTURE_SLOT1);else vramSetBankA(VRAM_A_TEXTURE_SLOT0);
 gpu_native_invalidate(bank);native_scenery_cache_invalidate(native_scenery_cells+bank);
 if(!ok||!native_raw_bitmap(pixels))return false;
 swiWaitForVBlank();gpu_prefix_publish(true);bgHide(1);bgHide(3);bgUpdate();return true;
}
bool gpu_prefix_native_hold(uint16_t *pixels){return native_capture_hold(pixels);}
bool gpu_prefix_native_freeze(uint16_t *pixels){
 if(!gpu_native_bg_storage)return false;
 if(!native_capture_hold(pixels))return false;
 native_scene_suspend();return true;
}
bool gpu_prefix_native_acquire(uint16_t *pixels){
 if((!gpu_native_bg_storage||(REG_DISPCNT&DISPLAY_BG1_ACTIVE))&&!native_capture_hold(pixels))return false;
 return true;
}
bool gpu_prefix_native_palette(const uint16_t *palette){
 if(!palette||(REG_DISPCNT&DISPLAY_BG1_ACTIVE))return false;
 native_scenery_cache_invalidate(native_scenery_cells);native_scenery_cache_invalidate(native_scenery_cells+1);
 vramSetBankE(VRAM_E_LCD);
 for(unsigned i=0;i<4096;i++)VRAM_E[4096+i]=palette[i];
 vramSetBankE(VRAM_E_BG_EXT_PALETTE);REG_DISPCNT|=DISPLAY_BG_EXT_PALETTE;
 bgInit(1,BgType_Text8bpp,BgSize_T_512x256,30,0);bgSetPriority(1,1);bgSetPriority(0,0);bgHide(1);bgUpdate();
 gpu_native_bg_storage=true;return true;
}

typedef struct {uint16_t *pixels;volatile uint16_t *texture;int x,y;unsigned written;} NativeSceneryCopy;
/* Expand the visible part [l,r)x[t,b) of one world cell into its ring texels. */
static bool native_scenery_cell(int wx,int wy,int l,int t,int r,int b,void *context){
 NativeSceneryCopy *c=context;(void)wx;(void)wy;
 if(!native_scene_expand(c->texture,l,t,r,b))return false;
 c->written+=(unsigned)((r-l)*(b-t));return true;
}
static bool native_gpu_prepare(uint16_t *pixels){
 const DepthRect *mesh;unsigned mesh_count,visible;int dx,dy;
 if(!native_scene_mesh(&mesh,&mesh_count,&dx,&dy,&visible))return false;
 const ActorAtlas *actors=gpu_actors_frame();
 bool use_actors=gpu_actors_collect_only()&&!actors->failed&&!gpu_actor_force_fallback;
 unsigned native_count=0;const NativeDraw *native=gpu_native_draws(&native_count);
 if(visible+(gpu_native_available()?native_count:actors->count)>=1536)use_actors=false;
 if(!use_actors){gpu_actor_capacity_fallback++;return false;}
 int x,y;native_scene_camera(&x,&y);
 if(!native_occlusion_regions(native_occlusion_before,256,native_scene_static_orders()+1u,actors,native,gpu_native_available()?native_count:0))return false;
 /* Clip each depth rectangle once; the list feeds residency and quads. */
 unsigned occluders=0;
 for(unsigned i=0;i<mesh_count&&occluders<OCCLUDER_LIMIT;i++){
  int l,t,r,b;
  if(mesh[i].order<=255&&actor_occlusion_clip(mesh+i,dx,dy,native_occlusion_before[mesh[i].order],&l,&t,&r,&b))
   occluder_list[occluders++]=(ClippedOccluder){(int16_t)l,(int16_t)t,(int16_t)r,(int16_t)b,mesh[i].order};
 }
 unsigned bank=front_texture^1u,written=0;
 if(bank)vramSetBankB(VRAM_B_LCD);else vramSetBankA(VRAM_A_LCD);
 volatile uint16_t *texture=bank?VRAM_B:VRAM_A;
 /* BG1 supplies the base; these textures hold only the foreground texels
  * under this frame's clipped occluder quads, made resident on demand. */
 NativeSceneryCopy copy={pixels,texture,x,y,0};unsigned sampled_cells=0;
 bool ok=native_scenery_cache_need(native_scenery_cells+bank,x,y,occluder_list,occluders,native_scenery_cell,&copy,&sampled_cells);
 written=copy.written;gpu_scenery_cells_sampled=sampled_cells;
#ifdef NATIVE_VERIFY_SCENERY
 /* Verification builds compare every requested texel with a fresh sample. */
 if(ok&&occluders){
  if(native_scene_sample(pixels,0,0,256,192)){
   for(unsigned i=0;i<occluders;i++){
    int l=occluder_list[i].l,t=occluder_list[i].t,r=occluder_list[i].r,b=occluder_list[i].b;
    if(l<0)l=0;
    if(t<0)t=0;
    if(r>256)r=256;
    if(b>192)b=192;
    for(int row=t;row<b;row++)for(int col=l;col<r;col++)
     if(texture[(((unsigned)(y+row))&255u)*256u+(((unsigned)(x+col))&255u)]!=pixels[row*256+col])native_scenery_verify_mismatches++;
   }
   native_scenery_verify_views++;
  }else native_scenery_verify_failures++;
 }
#endif
 gpu_native_active=false;
 if(ok&&gpu_palette_owned&&gpu_native_available()){
  if(bank)vramSetBankG(VRAM_G_LCD);else vramSetBankF(VRAM_F_LCD);
  gpu_native_active=gpu_native_prepare(bank,y,gpu_palette_epoch,texture,bank?VRAM_G:VRAM_F,gpu_actors_scratch());
  if(bank)vramSetBankG(VRAM_G_TEX_PALETTE_SLOT1);else vramSetBankF(VRAM_F_TEX_PALETTE_SLOT0);
 }
 if(ok&&!gpu_native_active&&gpu_native_skipped_sources())ok=false;
 if(ok&&!gpu_native_active){
  gpu_native_invalidate(bank);
  for(unsigned i=0;i<actors->count;i++){
   ActorPiece p=actors->pieces[i];
   for(unsigned row=0;row<p.height;row++)texture_copy_rgb555(texture+(((unsigned)y+192u+p.y+row)&255u)*256u+p.x,actors->pixels+(p.y+row)*256u+p.x,p.width);
  }
 }
 /* Actor pages/strips above occupy the 64 rows below this view. */
 native_scenery_cache_overwrite(native_scenery_cells+bank,y);
 if(bank)vramSetBankB(VRAM_B_TEXTURE_SLOT1);else vramSetBankA(VRAM_A_TEXTURE_SLOT0);
 if(!ok)return false;
 unsigned draw_count=gpu_native_active?native_count:actors->count,rank=0,piece=0;
 for(unsigned order=0;order<256;order++){
  static_rank[order]=(uint16_t)rank++;
  while(piece<draw_count&&(gpu_native_active?native[piece].order:actors->pieces[piece].order)==order)piece_rank[piece++]=(uint16_t)rank++;
 }
 if(piece!=draw_count)return false;
 pending_texture=bank;gpu_actor_pending=true;gpu_bitmap_pending=false;gpu_native_bg_pending=true;
 gpu_actor_pieces=draw_count;gpu_actor_upload_pixels=written;gpu_depth_mesh_active=true;gpu_depth_mesh_quads=0;
 gpu_prefix_x=(unsigned)x;gpu_prefix_y=(unsigned)y;gpu_prefix_bank=bank;gpu_prefix_pixels=written;
 glBindTexture(0,0);glBindTexture(0,textures[bank]);glColor(RGB15(31,31,31));glPolyFmt(POLY_ALPHA(31)|POLY_CULL_NONE|POLY_ID(0));
 glBegin(GL_QUAD);unsigned tx=(unsigned)x&255u,ty=(unsigned)y&255u;
 for(unsigned i=0;i<occluders;i++){
  int l=occluder_list[i].l,t=occluder_list[i].t,r=occluder_list[i].r,b=occluder_list[i].b;
  v16 vl=(v16)(l*64),vr=(v16)(r*64),vt=(v16)((t*256+2)/3),vb=(v16)((b*256+2)/3),z=(v16)(static_rank[occluder_list[i].order]*4);
  glTexCoord2i(tx+l,ty+t);glVertex3v16(vl,vt,z);
  glTexCoord2i(tx+l,ty+b);glVertex2v16(vl,vb);
  glTexCoord2i(tx+r,ty+b);glVertex2v16(vr,vb);
  glTexCoord2i(tx+r,ty+t);glVertex2v16(vr,vt);gpu_depth_mesh_quads++;
 }
 if(gpu_native_active){
  for(unsigned i=0;i<native_count;i++){
   const NativeDraw *p=native+i;int l=p->x,r=l+p->w,t=p->y,b=t+p->h;
   v16 vl=(v16)(l*64),vr=(v16)(r*64),vt=(v16)((t*256+2)/3),vb=(v16)((b*256+2)/3),z=(v16)(piece_rank[i]*4);
   int u0=p->mirror?(int)p->u+p->w-1:p->u,u1=p->mirror?(int)p->u-1:(int)p->u+p->w;
   glEnd();GFX_TEX_FORMAT=p->format;GFX_PAL_FORMAT=p->palette;glBegin(GL_QUAD);
   glTexCoord2t16((t16)(u0*16),(t16)(p->v*16));glVertex3v16(vl,vt,z);
   glTexCoord2t16((t16)(u0*16),(t16)((p->v+p->h)*16));glVertex2v16(vl,vb);
   glTexCoord2t16((t16)(u1*16),(t16)((p->v+p->h)*16));glVertex2v16(vr,vb);
   glTexCoord2t16((t16)(u1*16),(t16)(p->v*16));glVertex2v16(vr,vt);
  }
 }else for(unsigned i=0;i<actors->count;i++){
  ActorPiece p=actors->pieces[i];int l=p.screen_x,r=l+p.width,t=p.screen_y,b=t+p.height;
  unsigned u=p.x,v=((unsigned)y+192u+p.y)&255u;
  v16 vl=(v16)(l*64),vr=(v16)(r*64),vt=(v16)((t*256+2)/3),vb=(v16)((b*256+2)/3),z=(v16)(piece_rank[i]*4);
  glTexCoord2i(u,v);glVertex3v16(vl,vt,z);glTexCoord2i(u,v+p.height);glVertex2v16(vl,vb);
  glTexCoord2i(u+p.width,v+p.height);glVertex2v16(vr,vb);glTexCoord2i(u+p.width,v);glVertex2v16(vr,vt);
 }
 glEnd();glFlush(GL_TRANS_MANUALSORT|GL_ZBUFFERING);return true;
}
