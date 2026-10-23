#ifndef KINDER_SOUND_EVENTS_H
#define KINDER_SOUND_EVENTS_H
#include "player.h"
/* Stable DS sample keys are original WAV-path virtual addresses, not the
 * Windows manager's transient signed16 allocation handles. */
unsigned sound_global_key(unsigned native_world,unsigned original_global);
int16_t sound_key_handle(unsigned key);
void sound_prepare_player(Player *player,unsigned native_world);
void sound_events_event(void *context,PlayerEventType type,int id,int argument);
bool sound_channel_active(unsigned channel);
bool sound_last_load_ok(void);
bool sound_play(unsigned channel,unsigned key,unsigned repeat);
void sound_channel_stop(unsigned channel);
void sound_channel_volume(unsigned channel,int attenuation_db);
void sound_events_stop(void);
/* Main-loop producer and22050Hz signed16 mono IRQ consumer. */
void sound_events_poll(void);
void sound_events_mix(int16_t *samples,unsigned frames,unsigned music_volume);
uint32_t sound_effect_underruns(void);
/* Hardware channels reserved for effects/voices; audio_init locks them from Maxmod. */
unsigned sound_effect_channel_mask(void);
#endif
