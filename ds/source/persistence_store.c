#include "persistence.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <errno.h>

static bool file_path(char *path, size_t capacity, const char *directory, unsigned file)
{
    int n;
    if (file < 4) n = snprintf(path, capacity, "%s/Highscore%u.dat", directory, file+1);
    else n = snprintf(path, capacity, "%s/%s", directory, file == 4 ? "Option.ini" : "tut.ini");
    return n >= 0 && (size_t)n < capacity;
}

/* FAT may reject rename over an existing destination. Keep the prior file
 * under .bak until the complete .tmp has been published; recover after an
 * interrupted replacement without changing original file contents/formats. */
static bool side_path(char out[512],const char *path,const char *suffix){
 int n=snprintf(out,512,"%s%s",path,suffix);return n>=0&&n<512;
}
static void recover_file(const char *path){
 char backup[512];struct stat info;
 if(!side_path(backup,path,".bak"))return;
 if(stat(path,&info)==0||errno!=ENOENT)return;
 if(stat(backup,&info)==0&&S_ISREG(info.st_mode))rename(backup,path);
}
static bool replace_file(const char *path,const char *data,size_t size){
 char temporary[512],backup[512];struct stat info;
 if(!side_path(temporary,path,".tmp")||!side_path(backup,path,".bak"))return false;
 recover_file(path);
 bool existed=stat(path,&info)==0;
 if((existed&&!S_ISREG(info.st_mode))||(!existed&&errno!=ENOENT))return false;
 FILE *stream=fopen(temporary,"wb");if(!stream)return false;
 bool valid=fwrite(data,1,size,stream)==size;
 if(fclose(stream)!=0)valid=false;
 if(!valid){remove(temporary);return false;}
 if(existed){
  if(stat(backup,&info)==0){
   if(!S_ISREG(info.st_mode)||remove(backup)!=0){remove(temporary);return false;}
  }else if(errno!=ENOENT){remove(temporary);return false;}
  if(rename(path,backup)!=0){remove(temporary);return false;}
 }
 if(rename(temporary,path)!=0){
  if(existed)rename(backup,path);
  remove(temporary);return false;
 }
 if(existed)remove(backup);
 return true;
}

unsigned persistence_load(const char *directory, PersistenceState *state)
{
    unsigned loaded = 0;
    for (unsigned file = 0; file < 6; ++file) {
        char path[512], data[2300];
        if (file == 5) memset(state->tutorials, 0, 4);
        if (!file_path(path, sizeof(path), directory, file)) continue;
        recover_file(path);
        FILE *stream = fopen(path, "rb"); if (!stream) continue;
        size_t size = fread(data, 1, file == 5 ? 4 : sizeof(data), stream);
        bool valid = !ferror(stream) && (file == 5 || size < sizeof(data) || feof(stream));
        if (fclose(stream) != 0) valid = false;
        if (!valid) continue;
        if (file < 4) valid = persistence_parse_highscores(&state->scores[file], data, size);
        else if (file == 4) valid = persistence_parse_options(state->options, data, size);
        else persistence_parse_tutorials(state->tutorials, (const uint8_t *)data, size);
        if (valid) loaded |= 1u << file;
    }
    return loaded;
}

static unsigned save_files(const char *directory, const PersistenceState *state, unsigned files)
{
    unsigned saved = 0;
    for (unsigned file = 0; file < 6; ++file) {
        if (!(files & (1u << file))) continue;
        char path[512], data[2300]; size_t size;
        if (!file_path(path, sizeof(path), directory, file)) continue;
        if (file < 4) size = persistence_write_highscores(&state->scores[file], data, sizeof(data));
        else if (file == 4) size = persistence_write_options(state->options, data, sizeof(data));
        else { memcpy(data, state->tutorials, 4); size = 4; }
        if (!size) continue;
        if (replace_file(path,data,size)) saved |= 1u << file;
    }
    return saved;
}

bool persistence_save_highscores(const char *directory, const PersistenceState *state, unsigned world)
{
    return world < 4 && save_files(directory,state,1u<<world) == (1u<<world);
}

unsigned persistence_save(const char *directory, const PersistenceState *state)
{
    return save_files(directory, state, PERSISTENCE_ALL_FILES);
}

bool persistence_save_tutorials(const char *directory, const PersistenceState *state)
{
    return save_files(directory, state, 1u << 5) == (1u << 5);
}
