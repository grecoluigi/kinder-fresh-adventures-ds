#include "save_archive.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <errno.h>
#define SLOT_SIZE 4096
#define PAYLOAD_SIZE 1692
static const unsigned char magic[8]={'K','F','D','S','A','V',1,0};
static uint32_t get32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(i*8));}
static uint32_t checksum(const unsigned char *p,size_t n){
 uint32_t crc=~0u;for(size_t i=0;i<n;i++){crc^=p[i];for(unsigned b=0;b<8;b++)crc=(crc>>1)^((crc&1)?0xedb88320u:0);}return ~crc;
}
static void encode(unsigned char slot[SLOT_SIZE],const PersistenceState *state,uint32_t sequence){
 memset(slot,0xff,SLOT_SIZE);memcpy(slot,magic,8);put32(slot+8,sequence);put32(slot+12,PAYLOAD_SIZE);
 unsigned char *p=slot+20;
 for(unsigned w=0;w<4;w++){memcpy(p,state->scores[w].names,300);p+=300;memcpy(p,state->scores[w].score_text,100);p+=100;}
 for(unsigned i=0;i<22;i++){put32(p,(uint32_t)state->options[i]);p+=4;}
 memcpy(p,state->tutorials,4);
 /* Checksum includes sequence/length as well as payload. */
 put32(slot+16,checksum(slot+8,8)^checksum(slot+20,PAYLOAD_SIZE));
}
static bool decode(const unsigned char slot[SLOT_SIZE],PersistenceState *state,uint32_t *sequence){
 if(memcmp(slot,magic,8)||get32(slot+12)!=PAYLOAD_SIZE||get32(slot+16)!=(checksum(slot+8,8)^checksum(slot+20,PAYLOAD_SIZE)))return false;
 const unsigned char *p=slot+20;
 for(unsigned w=0;w<4;w++){memcpy(state->scores[w].names,p,300);p+=300;memcpy(state->scores[w].score_text,p,100);p+=100;}
 for(unsigned i=0;i<22;i++){state->options[i]=(int32_t)get32(p);p+=4;}
 memcpy(state->tutorials,p,4);*sequence=get32(slot+8);return true;
}
bool save_archive_uninitialized(const char *path){
 struct stat info;
 if(stat(path,&info)!=0)return errno==ENOENT;
 if(!S_ISREG(info.st_mode))return false;
 /* Empty loader placeholders and failed initial creations contain no save
  * record to preserve. Nonempty unsupported files remain protected. */
 if(info.st_size==0)return true;
 if(info.st_size!=SAVE_ARCHIVE_SIZE)return false;
 FILE *file=fopen(path,"rb");if(!file)return false;
 unsigned char block[512];bool empty=true;
 for(unsigned n=0;n<SAVE_ARCHIVE_SIZE/sizeof(block);n++){
  if(fread(block,1,sizeof(block),file)!=sizeof(block)){empty=false;break;}
  for(unsigned i=0;i<sizeof(block);i++)if(block[i]!=0&&block[i]!=255){empty=false;break;}
  if(!empty)break;
 }
 if(fclose(file)!=0)empty=false;
 return empty;
}
bool save_archive_load(const char *path,PersistenceState *state,uint32_t *sequence){
 FILE *file=fopen(path,"rb");if(!file)return false;
 unsigned char slot[SLOT_SIZE];PersistenceState candidate;uint32_t serial=0,best=0;bool found=false;
 for(unsigned i=0;i<2;i++){
  if(fread(slot,1,SLOT_SIZE,file)!=SLOT_SIZE)break;
  if(decode(slot,&candidate,&serial)&&(!found||(int32_t)(serial-best)>0)){*state=candidate;best=serial;found=true;}
 }
 if(ferror(file))found=false;
 if(fclose(file)!=0)found=false;
 if(found)*sequence=best;
 return found;
}
bool save_archive_write(const char *path,const PersistenceState *state,uint32_t *sequence){
 struct stat info;bool exists=stat(path,&info)==0;
 if((exists&&(!S_ISREG(info.st_mode)||(info.st_size!=0&&info.st_size!=SAVE_ARCHIVE_SIZE)))||(!exists&&errno!=ENOENT))return false;
 bool initialize=!exists||info.st_size==0;
 FILE *file=fopen(path,initialize?"w+b":"r+b");if(!file)return false;
 unsigned char slot[SLOT_SIZE];uint32_t next=*sequence+1;bool valid=true;
 if(initialize){
  memset(slot,0xff,sizeof(slot));
  valid=fwrite(slot,1,sizeof(slot),file)==sizeof(slot)&&fwrite(slot,1,sizeof(slot),file)==sizeof(slot);
 }
 encode(slot,state,next);
 if(valid)valid=fseek(file,(long)(next&1u)*SLOT_SIZE,SEEK_SET)==0&&fwrite(slot,1,sizeof(slot),file)==sizeof(slot);
 if(fclose(file)!=0)valid=false;
 if(valid)*sequence=next;
 return valid;
}
bool save_archive_path(char *out,size_t capacity,const char *rom,const char *drive){
 if(!out||!capacity||!drive)return false;
 const char *base=rom;
 /* Loader argument must describe a writable drive, never NitroFS. */
 if(!base||(!strstr(base,"fat:/")&&!strstr(base,"sd:/")))base=NULL;
 if(base&&strncmp(base,"fat:/",5)&&strncmp(base,"sd:/",4))base=NULL;
 if(base){
  const char *slash=strrchr(base,'/'),*dot=strrchr(base,'.');
  if(dot&&slash&&dot>slash&&(!strcmp(dot,".nds")||!strcmp(dot,".NDS"))){
   size_t n=(size_t)(dot-base);if(n+5>capacity)return false;
   memcpy(out,base,n);memcpy(out+n,".sav",5);return true;
  }
 }
 int n=snprintf(out,capacity,"%skinder_fresh.sav",drive);return n>=0&&(size_t)n<capacity;
}
