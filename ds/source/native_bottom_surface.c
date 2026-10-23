#include "native_bottom_surface.h"
#include <nds.h>
static bool can_remap(void){return !(REG_DISPCNT&DISPLAY_BG1_ACTIVE);}
static void hide_sub(void){for(unsigned i=4;i<8;i++)bgHide((int)i);}
void native_bottom_surface_end_keyboard(NativeBottomSurface *s){
 if(!s||s->mode!=NATIVE_BOTTOM_KEYBOARD)return;
 keyboardHide();keyboardExit();hide_sub();s->mode=NATIVE_BOTTOM_RGB;s->visible_rgb=false;
 s->background=bgInitSub(3,BgType_Bmp16,BgSize_B16_256x256,0,0);bgWrapOff(s->background);bgHide(s->background);bgUpdate();
}
bool native_bottom_surface_rgb(NativeBottomSurface *s,const uint16_t *pixels,size_t words){
 if(!s||!pixels||words<49152)return false;
 if(s->mode==NATIVE_BOTTOM_RGB&&s->visible_rgb){
  /* Same mapping: replace the visible bitmap during VBlank instead of
   * hiding, remapping and re-showing it, which blanked a frame per redraw. */
  DC_FlushRange(pixels,49152u*2u);swiWaitForVBlank();
  dmaCopyWords(3,pixels,bgGetGfxPtr(s->background),49152u*2u);return true;
 }
 if(!can_remap())return false;
 native_bottom_surface_end_keyboard(s);swiWaitForVBlank();hide_sub();s->visible_rgb=false;
 vramSetBankH(VRAM_H_LCD);vramSetBankI(VRAM_I_LCD);vramSetBankC(VRAM_C_SUB_BG);s->scenery_epoch++;
 s->background=bgInitSub(3,BgType_Bmp16,BgSize_B16_256x256,0,0);bgWrapOff(s->background);bgHide(s->background);bgUpdate();
 volatile uint16_t *dest=bgGetGfxPtr(s->background);
 for(unsigned i=0;i<49152;i++)dest[i]=pixels[i];
 swiWaitForVBlank();bgShow(s->background);bgUpdate();s->mode=NATIVE_BOTTOM_RGB;s->visible_rgb=true;return true;
}
bool native_bottom_surface_hud(NativeBottomSurface *s,const NativeBottom *hud,const uint8_t *pixels,size_t bytes){
 if(!s||!hud||!hud->ready||!pixels||bytes<49152||s->mode==NATIVE_BOTTOM_KEYBOARD)return false;
 bool remap=s->mode!=NATIVE_BOTTOM_INDEXED;
 s->visible_rgb=false;
 if(remap&&!can_remap())return false;
 if(remap){
  swiWaitForVBlank();hide_sub();vramSetBankC(VRAM_C_MAIN_BG_0x06000000);
  vramSetBankH(VRAM_H_SUB_BG);vramSetBankI(VRAM_I_SUB_BG_0x06208000);s->scenery_epoch++;
  s->background=bgInitSub(3,BgType_Bmp8,BgSize_B8_256x256,0,0);bgWrapOff(s->background);bgHide(s->background);bgUpdate();
 }
 swiWaitForVBlank();
 for(unsigned i=0;i<256;i++)BG_PALETTE_SUB[i]=hud->palette[i];
 volatile uint16_t *dest=bgGetGfxPtr(s->background);
 /* Source may have byte alignment; VRAM receives halfwords exclusively. */
 for(unsigned i=0;i<24576;i++)dest[i]=(uint16_t)(pixels[i*2]|(unsigned)pixels[i*2+1]<<8);
 bgShow(s->background);bgUpdate();s->mode=NATIVE_BOTTOM_INDEXED;return true;
}
bool native_bottom_surface_keyboard(NativeBottomSurface *s){
 if(!s||s->mode!=NATIVE_BOTTOM_RGB||!can_remap())return false;
 swiWaitForVBlank();hide_sub();s->visible_rgb=false;Keyboard *keyboard=keyboardInit(NULL,0,BgType_Text4bpp,BgSize_T_256x512,20,0,false,true);
 if(!keyboard)return false;
 keyboard->scrollSpeed=0;keyboardShow();s->mode=NATIVE_BOTTOM_KEYBOARD;return true;
}
