#include "native_bottom.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
static unsigned u16(const uint8_t *p){return p[0]|(unsigned)p[1]<<8;}
static uint32_t u32(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
void native_bottom_close(NativeBottom *s){if(s){free(s->data);free(s->background);memset(s,0,sizeof(*s));}}
static bool validate(const NativeBottom *s){
 unsigned end=0;bool digits[3][10]={{false}};
 for(unsigned i=0;i<s->count;i++){
  const NativeBottomPatch *p=s->patches+i;
  if(p->offset!=end||!p->width||p->width>256||!p->height||p->height>192||p->resource>17)return false;
  for(unsigned row=0;row<p->height;row++){
   unsigned x=0;
   for(;;){
    if(end>s->bytes||s->bytes-end<4)return false;
    unsigned skip=u16(s->data+end),run=u16(s->data+end+2);end+=4;
    if(!run){if(skip)return false;break;}
    if(skip>p->width-x)return false;
    x+=skip;
    if(run>p->width-x||run>s->bytes-end)return false;
    for(unsigned j=0;j<run;j++)if(!s->data[end+j]||s->data[end+j]>=128)return false;
    x+=run;end+=run;
   }
  }
  int font=p->resource==14?0:p->resource==16?1:p->resource==17?2:-1;
  if(font>=0){if(p->frame>=10||digits[font][p->frame])return false;digits[font][p->frame]=true;}
 }
 if(end!=s->bytes)return false;
 for(unsigned f=0;f<3;f++)for(unsigned d=0;d<10;d++)if(!digits[f][d])return false;
 return true;
}
bool native_bottom_open(NativeBottom *s,const char *path){
 if(!s||!path)return false;
 NativeBottom next={0};FILE *f=fopen(path,"rb");uint8_t header[16],record[16];bool ok=false;
 if(!f)return false;
 if(fread(header,1,16,f)!=16||memcmp(header,"KHU8",4)||u32(header+4)!=1)goto done;
 next.count=u32(header+8);next.bytes=u32(header+12);
 if(!next.count||next.count>128||!next.bytes||next.bytes>131072)goto done;
 for(unsigned i=0;i<next.count;i++){
  if(fread(record,1,16,f)!=16)goto done;
  next.patches[i]=(NativeBottomPatch){u32(record),u16(record+4),u16(record+6),(int16_t)u16(record+8),(int16_t)u16(record+10),u16(record+12),u16(record+14)};
 }
 next.data=malloc(next.bytes);if(!next.data||fread(next.data,1,next.bytes,f)!=next.bytes||fgetc(f)!=EOF||!validate(&next))goto done;
 native_bottom_close(s);*s=next;memset(&next,0,sizeof(next));ok=true;
 done:fclose(f);native_bottom_close(&next);return ok;
}
/* Bounded decoder on both hosts and DS. BIOS decompression would trust packet
 * lengths/back-references; reject malformed input before any publication. */
static bool unpack(const uint8_t *p,unsigned bytes,uint8_t *out){
 if(bytes<4||p[0]!=16||(p[1]|(unsigned)p[2]<<8|(unsigned)p[3]<<16)!=49152)return false;
 unsigned in=4,at=0;
 while(at<49152){
  if(in>=bytes)return false;
  unsigned flags=p[in++];
  for(unsigned bit=128;bit&&at<49152;bit>>=1){
   if(flags&bit){
    if(bytes-in<2)return false;
    unsigned word=p[in]*256+p[in+1],count=(word>>12)+3,back=(word&4095)+1;in+=2;
    if(back>at||count>49152-at)return false;
    while(count--){out[at]=out[at-back];at++;}
   }else{if(in>=bytes)return false;out[at++]=p[in++];}
  }
 }
 return in==bytes;
}
bool native_bottom_background(NativeBottom *s,const char *path,unsigned world){
 if(!s||!s->data||!path||world>=4)return false;
 FILE *f=fopen(path,"rb");if(!f)return false;
 uint8_t header[12],pal[512];uint8_t *packed=NULL,*image=NULL;bool ok=false;
 if(fread(header,1,12,f)!=12||memcmp(header,"KHB8",4)||u16(header+4)!=256||u16(header+6)!=192||fread(pal,1,512,f)!=512)goto done;
 unsigned bytes=u32(header+8);if(bytes<4||bytes>65536)goto done;
 if(u16(pal))goto done;
 if(s->ready)for(unsigned i=0;i<128;i++)if(u16(pal+2*i)!=s->palette[i])goto done;
 for(unsigned i=128;i<256;i++)if(!(u16(pal+2*i)&32768))goto done;
 packed=malloc(bytes);image=malloc(49152);
 if(!packed||!image||fread(packed,1,bytes,f)!=bytes||fgetc(f)!=EOF||!unpack(packed,bytes,image))goto done;
 for(unsigned i=0;i<49152;i++)if(image[i]<128)goto done;
 /* A used HUD index must have an opaque palette entry. */
 for(unsigned i=0;i<s->count;i++){
  unsigned at=s->patches[i].offset;
  for(unsigned row=0;row<s->patches[i].height;row++)for(;;){
   unsigned run=u16(s->data+at+2);at+=4;if(!run)break;
   for(unsigned j=0;j<run;j++)if(!(u16(pal+s->data[at+j]*2)&32768))goto done;
   at+=run;
  }
 }
 free(s->background);s->background=image;image=NULL;
 for(unsigned i=0;i<256;i++)s->palette[i]=(uint16_t)u16(pal+i*2);
 s->world=world;s->ready=true;ok=true;
 done:free(packed);free(image);fclose(f);return ok;
}
static const NativeBottomPatch *find(const NativeBottom *s,unsigned resource,unsigned frame){
 for(unsigned i=0;i<s->count;i++)if(s->patches[i].resource==resource&&s->patches[i].frame==frame)return s->patches+i;
 return NULL;
}
static void draw_patch(const NativeBottom *s,uint8_t *out,const NativeBottomPatch *p,int x,int y){
 if(!p)return;
 unsigned at=p->offset;
 for(unsigned row=0;row<p->height;row++){
  unsigned col=0;
  for(;;){
   unsigned skip=u16(s->data+at),run=u16(s->data+at+2);at+=4;if(!run)break;col+=skip;
   int yy=y+(int)row,l=x+(int)col,r=l+(int)run;
   if(yy>=0&&yy<192&&r>0&&l<256){
    unsigned source=l<0?(unsigned)-l:0;int left=l<0?0:l,right=r>256?256:r;
    memcpy(out+(unsigned)yy*256+(unsigned)left,s->data+at+source,(size_t)(right-left));
   }
   at+=run;col+=run;
  }
 }
}
bool native_bottom_draw(const NativeBottom *s,uint8_t *out,size_t bytes,const HudState *hud){
 if(!s||!s->ready||!s->data||!s->background||!out||bytes<49152||!hud||hud->world<0||s->world!=(unsigned)hud->world%4)return false;
 memcpy(out,s->background,49152);
 const NativeBottomPatch *label=find(s,15,0);if(label)draw_patch(s,out,label,label->x,label->y);
 HudCommand commands[16];unsigned n=hud_layout(hud,commands);
 for(unsigned i=0;i<n;i++){
  HudCommand c=commands[i];
  if(c.resource==14){
   char text[16];snprintf(text,sizeof(text),"%d",(int)c.frame);unsigned font=0;
   for(int f=2;f>=0;f--){
    unsigned width=0;bool complete=true;
    for(unsigned j=0;text[j];j++)if(text[j]>='0'&&text[j]<='9'){
     const NativeBottomPatch *p=find(s,f==0?14:f==1?16:17,(unsigned)(text[j]-'0'));
     if(!p){complete=false;break;}width+=p->width;
    }
    if(complete&&width<=128){font=(unsigned)f;break;}
   }
   int x=124;
   for(unsigned j=0;text[j];j++)if(text[j]>='0'&&text[j]<='9'){
    const NativeBottomPatch *p=find(s,font==0?14:font==1?16:17,(unsigned)(text[j]-'0'));
    if(p){draw_patch(s,out,p,x,33);x+=p->width;}
   }
  }else{
   const NativeBottomPatch *p=find(s,(unsigned)c.resource,(unsigned)c.frame);if(p)draw_patch(s,out,p,p->x,p->y);
  }
 }
 return true;
}
bool native_bottom_switch_hit(const NativeBottom *s,int x,int y){
 if(!s||!s->data||x<0||y<0||x>=256||y>=192)return false;
 for(unsigned i=0;i<s->count;i++)if(s->patches[i].resource==11){
  const NativeBottomPatch *p=s->patches+i;
  if(x>=p->x&&y>=p->y&&x<p->x+p->width&&y<p->y+p->height)return true;
 }
 return false;
}
