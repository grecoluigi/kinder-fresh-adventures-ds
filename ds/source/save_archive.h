#ifndef KINDER_SAVE_ARCHIVE_H
#define KINDER_SAVE_ARCHIVE_H
#include "persistence.h"
/* Raw 8 KiB game save, two independently checksummed 4 KiB records. */
#define SAVE_ARCHIVE_SIZE 8192
bool save_archive_uninitialized(const char *path);
bool save_archive_load(const char *path, PersistenceState *state, uint32_t *sequence);
bool save_archive_write(const char *path, const PersistenceState *state, uint32_t *sequence);
bool save_archive_path(char *out, size_t size, const char *rom_path, const char *drive);
#endif
