#include <stdio.h>

#include "hud.h"
#include "hud_native_bridge.h"
#ifndef HUD_NATIVE_ROOT
#ifdef __NDS__
#define HUD_NATIVE_ROOT "nitro:/native_bottom"
#else
#define HUD_NATIVE_ROOT "ds/nitrofs/native_bottom"
#endif
#endif
static NativeBottom indexed_hud;
static bool indexed_enabled;
void hud_native_enable(bool enabled){indexed_enabled=enabled;}
const NativeBottom *hud_native_state(void){return indexed_enabled?&indexed_hud:NULL;}
unsigned hud_layout(const HudState *s,HudCommand c[16]){
 unsigned n=0;c[n++]=(HudCommand){0,0};c[n++]=(HudCommand){14,s->score};
 if(s->boss>0){c[n++]=(HudCommand){1,0};if(s->boss_energy>=0)c[n++]=(HudCommand){12,s->boss_energy};c[n++]=(HudCommand){13,s->world%4};}
 else for(int i=0;i<6;i++)c[n++]=(HudCommand){2+i,s->letters[i]>0};
 if(s->health>0)c[n++]=(HudCommand){8,(s->health-1)/20>4?4:(s->health-1)/20};
 if(s->ammo>0)c[n++]=(HudCommand){s->shot_variant>0?10:9,s->ammo-1};
 c[n++]=(HudCommand){11,s->actor};return n;
}

bool hud_open(void){return native_bottom_open(&indexed_hud,HUD_NATIVE_ROOT "/hud.nhp");}
void hud_close(void){native_bottom_close(&indexed_hud);}
bool hud_set_world_background(unsigned world){
 static const char *names[]={"jungle","ice","factory","fantasy"};
 if(world>=4)return false;
 char path[192];snprintf(path,sizeof(path),"%s/%s.nbh",HUD_NATIVE_ROOT,names[world]);return native_bottom_background(&indexed_hud,path,world);
}
bool hud_switch_hit(int x,int y){return native_bottom_switch_hit(&indexed_hud,x,y);}
void hud_draw_bottom(uint16_t pixels[256*192],const HudState *s){
 uint8_t *indices=(uint8_t *)pixels;
 if(!native_bottom_draw(&indexed_hud,indices,49152,s))return;
 /* The existing bitmap backend consumes RGB555. Expand backwards in place
  * so GPU initialization failure needs no duplicate legacy HUD or scratch. */
 if(!indexed_enabled)for(unsigned i=49152;i--;)pixels[i]=indexed_hud.palette[indices[i]];
}
void hud_draw(uint16_t pixels[256*192],const HudState *s){hud_draw_bottom(pixels,s);}
