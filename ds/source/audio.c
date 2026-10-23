#include "audio.h"
#include <maxmod9.h>
#include <nds.h>
#include <stdio.h>
#include <string.h>
#include "sound_events.h"
#include "adpcm_codec.h"

static uint8_t ring[AUDIO_RING_BYTES] __attribute__((aligned(4)));
static volatile uint32_t produced,consumed,underruns;
static FILE *music;
/* KFM1: 16-byte header, then independently decodable 2,048-frame IMA-ADPCM
 * blocks of 1,028 bytes. Decoding happens here in the main loop; the IRQ
 * consumer only copies finished PCM. */
#define MUSIC_BLOCK_FRAMES 2048u
#define MUSIC_BLOCK_BYTES 1028u
static uint32_t music_frames,music_blocks,next_block;
static bool initialized,stream_open;
static unsigned music_volume=127;
static uint8_t music_packet[MUSIC_BLOCK_BYTES] __attribute__((aligned(4)));
static int16_t music_pcm[MUSIC_BLOCK_FRAMES] __attribute__((aligned(4)));
static uint32_t le32(const uint8_t *p)
{return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static bool read_header(void)
{
    uint8_t h[16];
    if(fread(h,1,16,music)!=16||memcmp(h,"KFM1",4)||le32(h+8)!=22050)return false;
    music_frames=le32(h+4);music_blocks=le32(h+12);next_block=0;
    return music_frames&&music_blocks==(music_frames+MUSIC_BLOCK_FRAMES-1)/MUSIC_BLOCK_FRAMES;
}
/* Producer never writes into memory already published to the interrupt consumer. */
static bool fill_ring(void)
{
    /* Decode whole blocks only, retaining at least 12KiB of queued PCM. */
    while(AUDIO_RING_BYTES-(produced-consumed)>=MUSIC_BLOCK_FRAMES*2u) {
        if(next_block==music_blocks) {
            if(fseek(music,16,SEEK_SET))return false;
            next_block=0;
        }
        uint32_t frames=music_frames-next_block*MUSIC_BLOCK_FRAMES;
        if(frames>MUSIC_BLOCK_FRAMES)frames=MUSIC_BLOCK_FRAMES;
        if(fread(music_packet,1,MUSIC_BLOCK_BYTES,music)!=MUSIC_BLOCK_BYTES)return false;
        music_pcm[0]=(int16_t)(music_packet[0]|(music_packet[1]<<8));
        if(frames>1&&!adpcm_decode_block(music_packet,MUSIC_BLOCK_BYTES,frames-1,music_pcm+1))return false;
        next_block++;
        uint32_t bytes=frames*2u,at=produced%AUDIO_RING_BYTES,first=AUDIO_RING_BYTES-at;
        if(first>bytes)first=bytes;
        memcpy(ring+at,music_pcm,first);
        if(bytes>first)memcpy(ring,(uint8_t *)music_pcm+first,bytes-first);
        __asm__ volatile("" ::: "memory");
        produced+=bytes;
    }
    return true;
}
/* Runs in Maxmod IRQ. File reads, decoding and seeking stay in audio_poll. */
static mm_word stream_callback(mm_word frames,mm_addr destination,mm_stream_formats format)
{
    (void)format;
    uint8_t *dest=destination;
    uint32_t requested=frames*2u;
    uint32_t available=produced-consumed;
    uint32_t copy=requested<available?requested:available;
    uint32_t first=AUDIO_RING_BYTES-consumed%AUDIO_RING_BYTES;
    if(first>copy)first=copy;
    memcpy(dest,ring+consumed%AUDIO_RING_BYTES,first);
    if(copy>first)memcpy(dest+first,ring,copy-first);
    memset(dest+copy,0,requested-copy);
    __asm__ volatile("" ::: "memory");
    consumed+=copy;
    underruns+=(requested-copy)/2u;
    return frames;
}

bool audio_init(void)
{
    if(initialized)return true;
    initialized=mmInitNoSoundbank();
    if(initialized)mmLockChannels(sound_effect_channel_mask());
    return initialized;
}
void audio_stop(void)
{
    if(stream_open) {mmStreamClose();stream_open=false;}
    if(music) {fclose(music);music=NULL;}
    produced=consumed=0;
    sound_events_stop();
}
static bool play(const char *path,unsigned volume)
{
    audio_stop();
    if(!audio_init())return false;
    music=fopen(path,"rb");
    if(!music)return false;
    if(!read_header()||!fill_ring()) {audio_stop();return false;}
    underruns=0;
    mm_stream stream={.sampling_rate=22050,.buffer_length=AUDIO_STREAM_FRAMES,
        .callback=stream_callback,.format=MM_STREAM_16BIT_MONO,
        .timer=MM_TIMER0,.manual=false};
    mmStreamOpen(&stream);stream_open=true;audio_set_volume(volume);
    return true;
}
bool audio_play_menu(void) {return play("nitro:/audio/Start.kfm",127);}
bool audio_play_world(unsigned world)
{
    static const char *const paths[]={"nitro:/audio/Dschungel.kfm","nitro:/audio/Eis.kfm",
        "nitro:/audio/Fabrik.kfm","nitro:/audio/Phantasie.kfm","nitro:/audio/endgegner.kfm"};
    if(world>7) {audio_stop();return false;}
    /* Native worlds0..3 volume-10dB:round(127*10^(-10/20))=40.
     * Bosses4..7 native volume0dB. Global user attenuation is caller supplied. */
    return play(paths[world<4?world:4],world<4?40:127);
}
bool audio_poll(void)
{
    sound_events_poll();
    if(!music||!stream_open)return false;
    if(!fill_ring()) {audio_stop();return false;}
    return true;
}
void audio_set_volume(unsigned volume)
{
    music_volume=volume>127?127:volume;
    /* Effects use their own hardware channels, so the stream carries only music. */
    if(stream_open)mmStreamVolume(music_volume);
}
uint32_t audio_underrun_frames(void) {return underruns;}
uint32_t audio_buffered_bytes(void) {return produced-consumed;}
