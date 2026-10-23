#include "tile_codec.h"
#include "menu_graphics.h"
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
#ifdef __NDS__
#include <nds/bios.h>
#endif
#include "menu_normal_lz_bin.h"
#include "menu_focus_0_patch_bin.h"
#include "menu_focus_1_patch_bin.h"
#include "menu_focus_2_patch_bin.h"
#include "menu_focus_3_patch_bin.h"
#include "menu_focus_4_patch_bin.h"
#include "menu_focus_5_patch_bin.h"
static uint16_t image[49152] __attribute__((aligned(32)));
static int cached_focus=-2;
static uint16_t le16(const uint8_t *p){return (uint16_t)(p[0]|p[1]<<8);}
static uint32_t le32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static bool decode_base(void){
 const uint8_t *source=menu_normal_lz_bin;size_t bytes=menu_normal_lz_bin_size;
 if(bytes<4||source[0]!=16||(le32(source)>>8)!=sizeof(image))return false;
#ifdef __NDS__
 tile_lz_wram(source,image);return true;
#else
 size_t at=4,out=0;uint8_t *dest=(uint8_t *)image;
 while(out<sizeof(image)){
  if(at>=bytes)return false;
  unsigned flags=source[at++];
  for(unsigned mask=128;mask&&out<sizeof(image);mask>>=1){
   if(flags&mask){
    if(at+2>bytes)return false;
    unsigned value=(unsigned)source[at]<<8|source[at+1];at+=2;
    unsigned count=(value>>12)+3,distance=(value&4095)+1;
    if(distance>out||count>sizeof(image)-out)return false;
    while(count--){dest[out]=dest[out-distance];out++;}
   }else{if(at>=bytes)return false;dest[out++]=source[at++];}
  }
 }
 return at==bytes;
#endif
}
const uint16_t *menu_graphics_pixels(int focus){
 if(focus< -1||focus>5)return NULL;
 if(cached_focus==focus)return image;
 cached_focus=-2;if(!decode_base())return NULL;
 if(focus>=0){
  const uint8_t *patches[6]={menu_focus_0_patch_bin,menu_focus_1_patch_bin,menu_focus_2_patch_bin,
   menu_focus_3_patch_bin,menu_focus_4_patch_bin,menu_focus_5_patch_bin};
  const size_t sizes[6]={menu_focus_0_patch_bin_size,menu_focus_1_patch_bin_size,menu_focus_2_patch_bin_size,
   menu_focus_3_patch_bin_size,menu_focus_4_patch_bin_size,menu_focus_5_patch_bin_size};
  const uint8_t *p=patches[focus];size_t bytes=sizes[focus],at=8;
  if(bytes<8||memcmp(p,"KFMP",4))return NULL;
  uint32_t count=le32(p+4);if(count>49152)return NULL;
  while(count--){
   if(at+4>bytes)return NULL;
   unsigned first=le16(p+at),length=le16(p+at+2);at+=4;
   if(first+length>49152||at+length*2>bytes)return NULL;
   memcpy(image+first,p+at,length*2);at+=length*2;
  }
  if(at!=bytes)return NULL;
 }
 cached_focus=focus;return image;
}
