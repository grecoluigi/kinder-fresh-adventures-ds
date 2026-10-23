#include "native_scene.h"
#include "native_actors.h"
#include <nds/system_counter.h>
#include "actor_occlusion.h"
#include "world.h"
#include "gpu_actors.h"
#include "texture_window.h"
#include "native_scenery_cache.h"

#include "gpu_prefix.h"

#include "frame_transfer.h"
#include <nds.h>

static int textures[2];
static bool gpu_actor_pending,gpu_bitmap_pending;
/* F/G hold independent16KiB texture palettes while world BG2 is hidden.
 * UI writes invalidate all future palette residency through the lease epoch.
 * Acquisition is at publication: the first world frame uses RGB555 and must
 * not submit indexed geometry before this ownership has been established. */
static volatile bool gpu_palette_owned;
static volatile uint32_t gpu_palette_epoch;
static void palette_storage(bool world){
 if(world==gpu_palette_owned)return;
 if(world){vramSetBankF(VRAM_F_TEX_PALETTE_SLOT0);vramSetBankG(VRAM_G_TEX_PALETTE_SLOT1);}
 else{vramSetBankF(VRAM_F_MAIN_BG_0x06010000);vramSetBankG(VRAM_G_MAIN_BG_0x06014000);}
 gpu_palette_owned=world;gpu_palette_epoch++;gpu_native_allow(world);
}

static volatile bool gpu_bitmap_visible;
static volatile bool gpu_actor_visible;
static volatile bool gpu_actor_force_fallback;
static volatile unsigned gpu_actor_pieces,gpu_actor_upload_pixels,gpu_actor_capacity_fallback;
static uint16_t static_rank[256],piece_rank[NATIVE_DRAW_LIMIT];
static volatile bool gpu_native_active;
static volatile unsigned gpu_depth_mesh_quads,gpu_depth_mesh_active;
static unsigned front_texture,pending_texture;
static volatile bool gpu_prefix_initialized;
static unsigned saved_frame_bank;
/* Frame-boundary debugger telemetry, without adding checksum work to drawing. */
static volatile unsigned gpu_prefix_pixels,gpu_prefix_bank,gpu_prefix_x,gpu_prefix_y;
static volatile bool gpu_prefix_visible;
/* Request1 captures only3D; request2 captures all displayed main layers.
 * Readbacks compare actual raster output, not just uploaded texture memory. */

bool gpu_prefix_init(void){
 vramSetBankA(VRAM_A_TEXTURE_SLOT0);vramSetBankB(VRAM_B_TEXTURE_SLOT1);
 if(!glInit()||!glGenTextures(2,textures))goto failed;
 for(unsigned bank=0;bank<2;bank++){
  glBindTexture(0,textures[bank]);
  if(!glTexImageNtr2D(GL_RGBA,256,256,GL_TEXTURE_WRAP_S|GL_TEXTURE_WRAP_T,NULL,NULL))goto failed;
  if(glGetTexturePointer(textures[bank])!=(bank?(void *)VRAM_B:(void *)VRAM_A))goto failed;
 }
 glEnable(GL_TEXTURE_2D);glDisable(GL_ANTIALIAS|GL_BLEND|GL_OUTLINE|GL_FOG);
 glViewport(0,0,255,191);glClearColor(0,0,0,0);glClearDepth(GL_MAX_DEPTH);glClearPolyID(63);
 glMatrixMode(GL_PROJECTION);glLoadIdentity();
 /* A square normalized projection uses exact +/-1/2 coefficients. A3-unit
  * height rounds2/3 in fixed point and clips the final scanline. Texture UVs
  * still span256x192pixels in the physical256x192viewport: no aspect change. */
 glOrthof32(0,inttof32(4),inttof32(4),0,inttof32(-1),inttof32(1));
 glMatrixMode(GL_MODELVIEW);glLoadIdentity();
 front_texture=0;pending_texture=0;gpu_prefix_initialized=true;
 REG_DISPCNT&=~DISPLAY_BG0_ACTIVE;return true;
 failed:glDeinit();return false;
}

static volatile uint32_t gpu_bitmap_phase_us[4];
static NativeOccluderCells native_scenery_cells[2];
static volatile bool gpu_native_bg_storage,gpu_native_bg_visible,gpu_native_bg_pending;

/* The inactive bank is never sampled while CPU/DMA owns it. This first
 * bridge keeps the old foreground bitmap available for UI and failure paths. */
bool gpu_prefix_prepare_bitmap(const uint16_t *pixels){
 if(!gpu_prefix_initialized||!pixels)return false;
 uint32_t phase=(uint32_t)systemCounterGetTicks();
 unsigned bank=front_texture^1u,count=49152;int x=0,y=0;
 if(bank)vramSetBankB(VRAM_B_LCD);else vramSetBankA(VRAM_A_LCD);
 frame_transfer(bank?VRAM_B:VRAM_A,pixels);native_scenery_cache_invalidate(native_scenery_cells+bank);gpu_native_invalidate(bank);
 if(bank)vramSetBankB(VRAM_B_TEXTURE_SLOT1);else vramSetBankA(VRAM_A_TEXTURE_SLOT0);
 unsigned tx=(unsigned)x&255u,ty=(unsigned)y&255u;
 pending_texture=bank;gpu_actor_pending=false;gpu_bitmap_pending=true;
 gpu_native_active=false;gpu_actor_pieces=gpu_actor_upload_pixels=0;gpu_depth_mesh_active=false;gpu_depth_mesh_quads=1;
 gpu_prefix_x=(unsigned)x;gpu_prefix_y=(unsigned)y;gpu_prefix_bank=bank;gpu_prefix_pixels=count;
 gpu_bitmap_phase_us[0]=systemCounterTicksToUsec((uint32_t)systemCounterGetTicks()-phase);phase=(uint32_t)systemCounterGetTicks();
 glBindTexture(0,0);glBindTexture(0,textures[bank]);glColor(RGB15(31,31,31));
 gpu_bitmap_phase_us[1]=systemCounterTicksToUsec((uint32_t)systemCounterGetTicks()-phase);phase=(uint32_t)systemCounterGetTicks();
 glPolyFmt(POLY_ALPHA(31)|POLY_CULL_NONE|POLY_ID(0));
 glBegin(GL_QUAD);
 glTexCoord2i(tx,ty);glVertex3v16(0,0,-8);
 glTexCoord2i(tx,ty+192);glVertex2v16(0,inttov16(4));
 glTexCoord2i(tx+256,ty+192);glVertex2v16(inttov16(4),inttov16(4));
 glTexCoord2i(tx+256,ty);glVertex2v16(inttov16(4),0);
 glEnd();gpu_bitmap_phase_us[2]=systemCounterTicksToUsec((uint32_t)systemCounterGetTicks()-phase);phase=(uint32_t)systemCounterGetTicks();
 glFlush(GL_TRANS_MANUALSORT|GL_ZBUFFERING);gpu_bitmap_phase_us[3]=systemCounterTicksToUsec((uint32_t)systemCounterGetTicks()-phase);return true;
}
/* With no actor depth geometry, keep the original CPU BG2 overlay rather
 * than copying it into the scenery texture. F/G ownership changes only at
 * publication, before main.c transfers the prepared CPU foreground. */

bool gpu_prefix_pending_texture_only(void){return gpu_actor_pending||gpu_bitmap_pending;}
bool gpu_prefix_bitmap_visible(void){return gpu_bitmap_visible;}
#include "native_scene_gpu.inc"
static volatile unsigned gpu_prepare_failures;
bool gpu_prefix_prepare(uint16_t *pixels){
 if(!gpu_prefix_initialized||!native_scene_prepared())return false;
 palette_storage(true);
 if(native_gpu_prepare(pixels))return true;
 gpu_prepare_failures++;return false;
}
void gpu_prefix_publish(bool visible){
 if(!gpu_prefix_initialized)return;
 bool native_on=visible&&gpu_native_bg_pending;
 if(!native_scene_publish(native_on)||!native_on)bgHide(1);
 gpu_native_bg_visible=native_on;
 gpu_prefix_visible=visible;gpu_actor_visible=visible&&gpu_actor_pending;gpu_bitmap_visible=visible&&gpu_bitmap_pending;
 if(gpu_actor_visible||gpu_bitmap_visible){bgHide(2);palette_storage(true);}
 else{palette_storage(false);bgShow(2);}
 if(visible){front_texture=pending_texture;bgShow(0);}else bgHide(0);
}
void gpu_prefix_hide(void){native_scene_suspend();bgHide(1);gpu_native_bg_visible=gpu_native_bg_pending=false;
 if(gpu_native_bg_storage){vramSetBankE(VRAM_E_MAIN_BG);REG_DISPCNT&=~DISPLAY_BG_EXT_PALETTE;gpu_native_bg_storage=false;}
 if(gpu_prefix_initialized){gpu_prefix_visible=false;gpu_actor_visible=gpu_actor_pending=gpu_bitmap_visible=gpu_bitmap_pending=false;bgHide(0);palette_storage(false);bgShow(2);}}
bool gpu_prefix_is_visible(void){return gpu_prefix_initialized&&gpu_prefix_visible;}
void gpu_prefix_save_frame(const uint16_t *pixels){
 saved_frame_bank=front_texture^1u;
 if(saved_frame_bank)vramSetBankB(VRAM_B_LCD);else vramSetBankA(VRAM_A_LCD);
 frame_transfer(saved_frame_bank?VRAM_B:VRAM_A,pixels);
 if(saved_frame_bank)vramSetBankB(VRAM_B_TEXTURE_SLOT1);else vramSetBankA(VRAM_A_TEXTURE_SLOT0);
}
void gpu_prefix_restore_frame(uint16_t *pixels){
 if(saved_frame_bank)vramSetBankB(VRAM_B_LCD);else vramSetBankA(VRAM_A_LCD);
 frame_transfer(pixels,saved_frame_bank?VRAM_B:VRAM_A);
 if(saved_frame_bank)vramSetBankB(VRAM_B_TEXTURE_SLOT1);else vramSetBankA(VRAM_A_TEXTURE_SLOT0);
}


bool gpu_prefix_pending_actors(void){return gpu_actor_pending;}
bool gpu_prefix_actors_visible(void){return gpu_actor_visible;}
/* Capture the complete displayed frame before destroying world assets. This
 * avoids relying on stale/undrawn foreground VRAM during results/keyboard UI. */
bool gpu_prefix_snapshot_frame(uint16_t *pixels){
 if(!pixels||!gpu_prefix_visible||(!gpu_actor_visible&&!gpu_bitmap_visible))return false;
 unsigned bank=front_texture^1u;
 if(bank)vramSetBankB(VRAM_B_LCD);else vramSetBankA(VRAM_A_LCD);
 REG_DISPCAPCNT=DCAP_ENABLE|DCAP_MODE(DCAP_MODE_A)|DCAP_SRC_A(DCAP_SRC_A_COMPOSITED)|DCAP_SIZE(DCAP_SIZE_256x192)|DCAP_BANK(bank);
 unsigned attempts=0;while((REG_DISPCAPCNT&DCAP_ENABLE)&&attempts++<3)swiWaitForVBlank();
 bool okay=!(REG_DISPCAPCNT&DCAP_ENABLE);
 if(okay)frame_transfer(pixels,bank?VRAM_B:VRAM_A);else REG_DISPCAPCNT=0;
 if(bank)vramSetBankB(VRAM_B_TEXTURE_SLOT1);else vramSetBankA(VRAM_A_TEXTURE_SLOT0);
 gpu_native_invalidate(bank);native_scenery_cache_invalidate(native_scenery_cells+bank);return okay;
}
