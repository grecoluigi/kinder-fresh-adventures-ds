#ifndef KINDER_GAME_SAVE_H
#define KINDER_GAME_SAVE_H
#include "persistence.h"
/* DS storage is one raw 8 KiB .sav beside the ROM (root fallback without argv). */
void game_save_init(void);
bool game_save_open_directory(const char *directory);
bool game_save_open_archive(const char *path,const char *legacy_directory);
/* 0 = no storage, 1 = saved/ready, 2 = storage failure. */
unsigned game_save_status(void);
const char *game_save_path(void);
PersistenceState *game_save_state(void);
bool game_save_available(void);
unsigned game_save_loaded_files(void);
unsigned game_save_flush(void);
bool game_save_flush_tutorials(void);
bool game_save_flush_highscores(unsigned world);
#endif
