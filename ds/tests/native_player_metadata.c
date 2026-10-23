/* Check native player submission against independent full KFP3 source banks. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "player_graphics.h"
static int submitted[6];
static unsigned calls;
static bool accept=true;
bool gpu_actors_native(unsigned kind,unsigned frame,unsigned w,unsigned h,int x,int y){
 submitted[0]=(int)kind;submitted[1]=(int)frame;submitted[2]=(int)w;
 submitted[3]=(int)h;submitted[4]=x;submitted[5]=y;calls++;return accept;
}
static unsigned u16(const uint8_t *p){return p[0]|(unsigned)p[1]<<8;}
/* Independent floor-rounded projection; intentionally not ds_projection.h. */
static int project(int n){int value=n*8+12;return value>=0?value/25:-((-value+24)/25);}
static void empty_bounds(void){int b[4];player_graphics_last_bounds(b);for(unsigned i=0;i<4;i++)assert(!b[i]);}
int main(int argc,char **argv){
 assert(argc==2||argc==3);
 bool opened=player_graphics_open();
 if(argc==3){assert(opened==(argv[2][0]=='1'));player_graphics_close();return 0;}
 assert(opened);unsigned bytes;assert(player_graphics_native_cache(&bytes)&&bytes==128u*1024u);
 uint16_t pixels[256*192];memset(pixels,0x5a,sizeof(pixels));
 const int positions[][4]={{0,0,0,0},{400,240,300,100},{-100,-40,0,0},{800,600,0,0},{700,450,13,7},{23,17,7,13},{-5,17,-25,50},{1,2,24,25},{900,500,350,110}};
 unsigned views=0;
 for(unsigned c=0;c<2;c++){
  char path[4096];snprintf(path,sizeof(path),"%s/%s.frames",argv[1],c?"milchschnitte":"pinguin");FILE *f=fopen(path,"rb");assert(f);
  uint8_t header[8];assert(fread(header,1,8,f)==8&&!memcmp(header,"KFP3",4));unsigned count=u16(header+4);
  for(unsigned index=0;index<count;index++){
   uint8_t frame[40];assert(fread(frame,1,40,f)==40);
   for(unsigned facing=0;facing<2;facing++)for(unsigned p=0;p<sizeof(positions)/sizeof(positions[0]);p++){
    const uint8_t *r=frame+16+facing*16;int w=(int)u16(r),h=(int)u16(r+2);
    const int *v=positions[p];int left=project(v[0])-project(v[2])+(int16_t)u16(r+4),top=project(v[1])-project(v[3])+(int16_t)u16(r+6);
    unsigned before=calls;assert(player_graphics_draw(pixels,(int)c,(int)index,(int)facing,v[0],v[1],v[2],v[3]));assert(calls==before+1);
    assert(submitted[0]==0&&submitted[1]==(int)((index*2+c)*2+facing)&&submitted[2]==w&&submitted[3]==h&&submitted[4]==left&&submitted[5]==top);
    int expected[4]={0},actual[4],x0=left<0?0:left,y0=top<0?0:top,x1=left+w,y1=top+h;
    if(x1>256)x1=256;
    if(y1>192)y1=192;
    if(x0<x1&&y0<y1){expected[0]=x0;expected[1]=y0;expected[2]=x1;expected[3]=y1;}
    player_graphics_last_bounds(actual);assert(!memcmp(expected,actual,sizeof(actual)));views++;
   }
  }
  fclose(f);
 }
 for(unsigned i=0;i<256*192;i++)assert(pixels[i]==0x5a5a);
 accept=false;assert(!player_graphics_draw(pixels,0,0,0,0,0,0,0));empty_bounds();
 assert(!player_graphics_draw(pixels,-1,0,0,0,0,0,0));empty_bounds();
 assert(!player_graphics_draw(pixels,0,-1,0,0,0,0,0));empty_bounds();
 assert(!player_graphics_draw(pixels,0,512,0,0,0,0,0));empty_bounds();
 player_graphics_close();assert(!player_graphics_native_cache(&bytes)&&!bytes);
 assert(!player_graphics_draw(pixels,0,0,0,0,0,0,0));empty_bounds();
 printf("{\"clipped_views\":%u,\"software_pixel_writes\":0,\"native_cache_bytes\":131072}\n",views);return 0;
}
