#include "gpu_actors.h"
#include "end_titles.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef END_TITLE_ROOT
#define END_TITLE_ROOT "nitro:/end_titles"
#endif
static uint16_t *image;
static int loaded_frame=-1;
static int loaded_left,sample_width;
static int first_sample(int target,int count);
void end_title_tick(EndTitle *t)
{
    switch(t->action){
    case 1:case 2:
        t->frame=t->action-1;t->x=t->frame?204:191;t->y=-100;t->vy=0;t->action=10;break;
    case 10:{
        double v=(double)t->vy+0.4000000059604645;
        t->vy=v>40?40:(float)v;
        double y=(double)t->y+t->vy;t->y=(float)y;
        if(y>300)t->action=11;
        break;
    }
    case 11:{
        double v=(double)t->vy-2;t->vy=v< -20?-20:(float)v;
        double y=(double)t->y+t->vy;t->y=(float)y;
        if(y<300)t->action=100;
        break;
    }
    default:break;
    }
}
void end_title_close(void){free(image);image=NULL;loaded_frame=-1;}
static bool load_frame(int frame,int left)
{
    if(frame<0||frame>1)return false;
    if(frame==loaded_frame&&left==loaded_left)return true;
    unsigned width=frame?392:418;
    int x0=first_sample(left,256),x1=first_sample(left+(int)width,256),sw=x1-x0;
    if(sw<0||sw>135)return false;
    if(!sw){loaded_frame=frame;loaded_left=left;sample_width=0;return true;}
    /* X stays fixed during a title's bounce. Retain exactly the columns the
     * DS samples, with all51 source rows for every possible vertical phase. */
    if(!image){image=malloc(135u*51u*2u);if(!image)return false;}
    char path[256];snprintf(path,sizeof(path),"%s/%d.bin",END_TITLE_ROOT,frame);
    FILE *f=fopen(path,"rb");if(!f)return false;
    unsigned char header[8];
    bool ok=fread(header,1,8,f)==8&&!memcmp(header,"KFT1",4)&&
        (unsigned)(header[4]|header[5]<<8)==width&&header[6]==51&&header[7]==0;
    uint16_t row[418] __attribute__((aligned(4)));
    if(ok){
        loaded_frame=-1;
        for(unsigned y=0;y<51;y++){
            if(fread(row,2,width,f)!=width){ok=false;break;}
            for(int x=x0;x<x1;x++)image[y*(unsigned)sw+(unsigned)(x-x0)]=row[((2*x+1)*25)/16-left];
        }
        if(ok)ok=fgetc(f)==EOF;
    }
    fclose(f);if(ok){loaded_frame=frame;loaded_left=left;sample_width=sw;}return ok;
}
static int first_sample(int target,int count)
{
    int lo=0,hi=count;while(lo<hi){int mid=(lo+hi)/2;
        if(((2*mid+1)*25)/16<target)lo=mid+1;else hi=mid;
    }return lo;
}
static bool end_title_draw_cpu(const EndTitle *t,uint16_t *pixels)
{
    if(!t->action)return true;
    if(!pixels||!load_frame(t->frame,(int)t->x))return false;
    int width=t->frame?392:418,left=(int)t->x,top=(int)t->y;
    int x0=first_sample(left,256),x1=first_sample(left+width,256);
    int y0=first_sample(top,192),y1=first_sample(top+51,192);
    for(int y=y0;y<y1;y++){
        int sy=((2*y+1)*25)/16-top;
        for(int x=x0;x<x1;x++){
            uint16_t pixel=image[sy*sample_width+x-x0];if(pixel&0x8000)pixels[y*256+x]=pixel;
        }
    }return true;
}

bool end_title_draw(const EndTitle *t,uint16_t *pixels)
{
 if(!gpu_actors_collect_only())return end_title_draw_cpu(t,pixels);
 const bool cpu_draw=!gpu_actors_collect_only();
    if(!t->action)return true;
    if(!pixels||!load_frame(t->frame,(int)t->x))return false;
    int width=t->frame?392:418,left=(int)t->x,top=(int)t->y;
    int x0=first_sample(left,256),x1=first_sample(left+width,256);
    int y0=first_sample(top,192),y1=first_sample(top+51,192);
    if(x0>=x1||y0>=y1)return true;
    gpu_actors_ordinal(255);
    for(int strip=y0;strip<y1;strip+=8){
      int end=strip+8;if(end>y1)end=y1;unsigned sw=(unsigned)(x1-x0);
      uint16_t *temporary=gpu_actors_scratch();memset(temporary,0,sw*(unsigned)(end-strip)*2);
      for(int y=strip;y<end;y++){
        int sy=((2*y+1)*25)/16-top;
        for(int x=x0;x<x1;x++){
            uint16_t pixel=image[sy*sample_width+x-x0];if(cpu_draw&&(pixel&0x8000))pixels[y*256+x]=pixel;temporary[(y-strip)*sw+(unsigned)(x-x0)]=pixel;
        }
    }gpu_actors_sprite(temporary,sw,(unsigned)(end-strip),sw,x0,strip,5);
    }return true;
}
