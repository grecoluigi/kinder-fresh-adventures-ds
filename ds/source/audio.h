#ifndef KINDER_AUDIO_H
#define KINDER_AUDIO_H
#include <stdbool.h>
#include <stdint.h>
/* Call after NitroFS init. Maxmod uses its default ARM7 FIFO and TIMER0. */
bool audio_init(void);
bool audio_play_menu(void);
/* Native 0x4dabd4:0 jungle,1 mountain,2 factory,3 valley,4..7 bosses. */
bool audio_play_world(unsigned native_world);
void audio_stop(void);
/* Main-loop I/O only. Call each frame, including menu/pause/world overlays.
 * False means no active track or file I/O failure. Never call from an IRQ. */
bool audio_poll(void);
void audio_set_volume(unsigned volume); /* Maxmod amplitude0..127 */
uint32_t audio_underrun_frames(void);
uint32_t audio_buffered_bytes(void);
/* Application's bounded PCM ring. Maxmod additionally owns its2048-frame buffer. */
#define AUDIO_RING_BYTES 16384u
#define AUDIO_STREAM_FRAMES 2048u
#endif
