#include "credits.h"
#include <stdio.h>
#include <string.h>
#ifndef CREDITS_ROOT
#define CREDITS_ROOT "nitro:/credits"
#endif
void credits_begin(CreditsState *state){if(state){state->page=0;state->active=true;}}
bool credits_step(CreditsState *state,bool next,bool back){
 if(!state||!state->active)return false;
 if(back){state->active=false;return true;}
 if(!next)return false;
 if(++state->page>=CREDITS_PAGES)state->active=false;
 return true;
}
bool credits_draw(uint16_t pixels[256*192],unsigned page){
 if(!pixels||page>=CREDITS_PAGES)return false;
 char path[256];int length=snprintf(path,sizeof(path),"%s/%u.bin",CREDITS_ROOT,page);
 if(length<0||(size_t)length>=sizeof(path))return false;
 FILE *file=fopen(path,"rb");if(!file)return false;
 setvbuf(file,NULL,_IONBF,0);
 unsigned char header[8];bool valid=fread(header,1,8,file)==8&&
  !memcmp(header,"KFC1",4)&&header[4]==0&&header[5]==1&&header[6]==192&&header[7]==0;
 if(valid)valid=fread(pixels,2,256u*192u,file)==256u*192u;
 if(fclose(file)!=0)valid=false;
 return valid;
}
