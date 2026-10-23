#ifndef KINDER_STORAGE_PROFILE_H
#define KINDER_STORAGE_PROFILE_H
#include <stdint.h>
#include <stdbool.h>
#define KINDER_STORAGE_PROFILE_OPTIN 1
extern volatile unsigned storage_profile_enabled;
void storage_profile_enable(bool enabled);
extern volatile uint32_t storage_frame_seek_us,storage_frame_read_us;
extern volatile uint32_t storage_frame_seek_calls,storage_frame_read_calls,storage_frame_read_bytes;
void storage_profile_snapshot(void);
#endif
