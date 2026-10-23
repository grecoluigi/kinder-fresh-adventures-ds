#ifndef KINDER_PERSISTENCE_H
#define KINDER_PERSISTENCE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PERSISTENCE_WORLDS 4
#define PERSISTENCE_RANKS 10
#define PERSISTENCE_OPTIONS 22
typedef struct {
    char names[PERSISTENCE_RANKS][30];
    char score_text[PERSISTENCE_RANKS][10];
} HighscoreTable;
typedef struct {
    HighscoreTable scores[PERSISTENCE_WORLDS];
    int32_t options[PERSISTENCE_OPTIONS];
    uint8_t tutorials[PERSISTENCE_WORLDS];
} PersistenceState;
/* File status bits: score tables bits0..3, options bit4, tutorials bit5. */
enum { PERSISTENCE_ALL_FILES = 63 };
void persistence_defaults(PersistenceState *state, bool input_device_available);
/* Native 409bf0 repairs -1 input sentinels after loading, then caller saves. */
void persistence_normalize_options(int32_t options[22], bool input_device_available);
int32_t persistence_decimal(const char *text);
int persistence_rank(const HighscoreTable *table, int32_t score);
/* Native 4091b0 inserts a blank name and sorts; returns original insertion rank.
 * -1 means did not qualify; -2 means score would overflow the native text slot. */
int persistence_qualify(HighscoreTable *table, int32_t score);
bool persistence_set_name(HighscoreTable *table, unsigned rank, const char *name);
bool persistence_parse_highscores(HighscoreTable *table, const char *data, size_t size);
size_t persistence_write_highscores(const HighscoreTable *table, char *data, size_t capacity);
bool persistence_parse_options(int32_t options[22], const char *data, size_t size);
size_t persistence_write_options(const int32_t options[22], char *data, size_t capacity);
void persistence_parse_tutorials(uint8_t flags[4], const uint8_t *data, size_t size);
/* Portable stdio backend: caller supplies an existing writable directory.
 * load returns successfully loaded file bits, retaining defaults for missing files.
 * save returns successfully saved file bits. Replacements use .tmp/.bak and load
 * recovers a missing canonical file from its backup. FAT power-loss durability
 * still requires device testing. Caller handles FAT init/directory setup. */
unsigned persistence_load(const char *directory, PersistenceState *state);
unsigned persistence_save(const char *directory, const PersistenceState *state);
/* Original tutorial completion writes only tut.ini, preserving other files. */
bool persistence_save_tutorials(const char *directory, const PersistenceState *state);
/* Native409ee0 writes only the selected world table. */
bool persistence_save_highscores(const char *directory, const PersistenceState *state, unsigned world);
#endif
