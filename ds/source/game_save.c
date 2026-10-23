#include "game_save.h"
#include "save_archive.h"
#include <string.h>
#include <stdio.h>
#include <sys/stat.h>
#ifdef __NDS__
#include <fat.h>
#include <nds/system.h>
#endif
static PersistenceState state;
static char save_directory[256];
static bool available;
static unsigned loaded;
static char archive_path[256];
static PersistenceState committed;
static uint32_t archive_sequence;
static unsigned storage_status;
#ifndef __NDS__
/* Host tools only: original per-file persistence in a directory. */
bool game_save_open_directory(const char *directory)
{
    persistence_defaults(&state,true);
    available=false;loaded=0;save_directory[0]=0;archive_path[0]=0;storage_status=0;
    if(!directory||strlen(directory)>=sizeof(save_directory))return false;
    struct stat info;
    if(stat(directory,&info)!=0){
        if(mkdir(directory,0777)!=0)return false;
    }else if(!S_ISDIR(info.st_mode))return false;
    strcpy(save_directory,directory);
    loaded=persistence_load(save_directory,&state);
    persistence_normalize_options(state.options,true);
    available=true;
    return true;
}
#endif
bool game_save_open_archive(const char *path,const char *legacy_directory)
{
    persistence_defaults(&state,true);available=false;loaded=0;archive_path[0]=0;save_directory[0]=0;archive_sequence=0;storage_status=2;
    if(!path||strlen(path)>=sizeof(archive_path))return false;
    strcpy(archive_path,path);
    if(save_archive_load(path,&state,&archive_sequence))loaded=PERSISTENCE_ALL_FILES;
    else{
        /* Never overwrite an incompatible or wholly damaged existing save. */
        if(!save_archive_uninitialized(path))return false;
        if(legacy_directory)loaded=persistence_load(legacy_directory,&state);
    }
    persistence_normalize_options(state.options,true);
    committed=state;
    /* Create immediately, even if the player has not finished a tutorial. */
    if(!save_archive_write(archive_path,&state,&archive_sequence))return false;
    available=true;storage_status=1;return true;
}
void game_save_init(void)
{
    persistence_defaults(&state,true);
    available=false;loaded=0;save_directory[0]=0;archive_path[0]=0;storage_status=0;
#ifdef __NDS__
    /* One 4 KiB page keeps the storage cache bounded on the DS. */
    storage_status=2;
    if(fatInit(1,false)){
        /* Release builds read and write only the raw .sav; no legacy folder
         * is read, migrated or created. */
        const char *rom=NULL;char path[256];
        if(__system_argv->argvMagic==ARGV_MAGIC&&__system_argv->argc>0&&__system_argv->argv)rom=__system_argv->argv[0];
        if(save_archive_path(path,sizeof(path),rom,fatGetDefaultDrive()))game_save_open_archive(path,NULL);
    }
#endif
}
PersistenceState *game_save_state(void){return &state;}
bool game_save_available(void){return available;}
unsigned game_save_loaded_files(void){return loaded;}
unsigned game_save_status(void){return storage_status;}
const char *game_save_path(void){return archive_path;}
static bool archive_flush(unsigned files){
    if(!available)return false;
    PersistenceState next=committed;
    for(unsigned i=0;i<4;i++)if(files&(1u<<i))next.scores[i]=state.scores[i];
    if(files&16)memcpy(next.options,state.options,sizeof(next.options));
    if(files&32)memcpy(next.tutorials,state.tutorials,sizeof(next.tutorials));
    bool ok=save_archive_write(archive_path,&next,&archive_sequence);
    storage_status=ok?1:2;if(ok)committed=next;return ok;
}
unsigned game_save_flush(void){
    if(archive_path[0])return archive_flush(PERSISTENCE_ALL_FILES)?PERSISTENCE_ALL_FILES:0;
#ifndef __NDS__
    return available?persistence_save(save_directory,&state):0;
#else
    return 0;
#endif
}
bool game_save_flush_highscores(unsigned world)
{
    if(world>=4)return false;
    if(archive_path[0])return archive_flush(1u<<world);
#ifndef __NDS__
    return available && persistence_save_highscores(save_directory,&state,world);
#else
    return false;
#endif
}
bool game_save_flush_tutorials(void)
{
    if(archive_path[0])return archive_flush(32);
#ifndef __NDS__
    return available && persistence_save_tutorials(save_directory,&state);
#else
    return false;
#endif
}
