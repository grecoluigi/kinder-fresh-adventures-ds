#include "sound_events.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sound_assets.inc"
#ifdef __NDS__
#include <nds.h>
#include <nds/system_counter.h>
#endif
#ifndef SOUND_PACK
#define SOUND_PACK "nitro:/sounds/samples.hw"
#endif
/* Effects and voices play on ARM7 hardware channels from a RAM sample cache,
 * as the original DirectSound buffers did; nothing is streamed or mixed on the
 * ARM9. samples.hw (KFH1) holds one DS sample per asset, IMA-ADPCM or PCM16,
 * in sound_assets order. A slot's playback state follows elapsed 22,050 Hz
 * frames, so callers observe the same active/repeat semantics as before. */
#define CHANNELS 19u
#define SAMPLE_RATE 22050u
#ifndef SOUND_CACHE_BYTES
#define SOUND_CACHE_BYTES (384u*1024u)
#endif
#define ASSET_COUNT (sizeof(sound_assets)/sizeof(sound_assets[0]))
enum {FORMAT_PCM16=0,FORMAT_ADPCM=2};
typedef struct {uint32_t frames,offset,bytes;uint8_t format;} PackEntry;
typedef struct {uint32_t at,bytes,age;uint16_t asset;bool used;} CacheEntry;
typedef struct {
 bool active;int hardware;uint16_t asset;uint8_t repeat;
 uint32_t start,frames;unsigned volume;
} SoundChannel;
static SoundChannel channels[CHANNELS];
static PackEntry entries[ASSET_COUNT];
static CacheEntry cache[ASSET_COUNT];
/* Static, so the ARM7 can always read it: on DSi/3DS the heap may extend
 * past the first 4 MiB of main RAM. */
static uint8_t arena[SOUND_CACHE_BYTES] __attribute__((aligned(32)));
/* Maxmod reserves only its stream channel (4, and 5 for stereo). Effects use
 * the remaining 14 channels, locked away from Maxmod in audio_init(). */
#define EFFECT_CHANNEL_MASK 0xffcfu
static uint32_t cache_age;
static FILE *pack;
static bool pack_ready,load_ok;
static volatile uint32_t sound_plays,sound_dropped,sound_loads,sound_load_bytes,sound_evictions;
#ifndef __NDS__
/* Host builds advance a deterministic clock through sound_events_mix. */
static uint32_t host_frames;
static uint32_t now_frames(void){return host_frames;}
#else
static uint32_t now_frames(void){
 /* 64-bit product keeps full precision; the result wraps like the counter. */
 return (uint32_t)(systemCounterGetTicks()*(uint64_t)SAMPLE_RATE/(BUS_CLOCK/64u));
}
#endif
static uint32_t le32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static bool open_pack(void){
 if(pack_ready)return true;
 pack=fopen(SOUND_PACK,"rb");if(!pack)return false;
 uint8_t header[16];
 if(fread(header,1,16,pack)!=16||memcmp(header,"KFH1",4)||le32(header+4)!=ASSET_COUNT||le32(header+8)!=16u+20u*ASSET_COUNT)goto fail;
 uint32_t total=le32(header+12);
 for(unsigned i=0;i<ASSET_COUNT;i++){
  uint8_t r[20];if(fread(r,1,20,pack)!=20)goto fail;
  PackEntry e={le32(r+4),le32(r+8),le32(r+12),r[16]};
  if(le32(r)!=sound_assets[i].va||e.frames!=sound_assets[i].frames||(e.format!=FORMAT_PCM16&&e.format!=FORMAT_ADPCM)||
     (e.offset&3u)||(e.bytes&3u)||e.bytes<8||e.offset>total||e.bytes>total-e.offset||r[17]||r[18]||r[19])goto fail;
  if(e.format==FORMAT_PCM16?e.bytes!=((e.frames*2u+3u)&~3u):e.bytes!=((4u+(e.frames+1u)/2u+3u)&~3u))goto fail;
  entries[i]=e;
 }
 memset(cache,0,sizeof(cache));pack_ready=true;return true;
fail:
 fclose(pack);pack=NULL;return false;
}
static bool playing(unsigned asset){
 for(unsigned i=0;i<CHANNELS;i++)if(channels[i].active&&channels[i].asset==asset)return true;
 return false;
}
/* First-fit placement among resident samples; evicts the least recently
 * used sample that no hardware channel is reading. */
static uint8_t *load(unsigned asset){
 if(!open_pack()||asset>=ASSET_COUNT)return NULL;
 CacheEntry *c=cache+asset;
 if(c->used){c->age=++cache_age;return arena+c->at;}
 uint32_t bytes=entries[asset].bytes;if(bytes>SOUND_CACHE_BYTES)return NULL;
 for(;;){
  uint32_t here=0;bool placed=false;
  for(;;){
   uint32_t next=SOUND_CACHE_BYTES;unsigned blocker=ASSET_COUNT;
   for(unsigned i=0;i<ASSET_COUNT;i++)if(cache[i].used&&cache[i].at+cache[i].bytes>here&&cache[i].at<next){next=cache[i].at;blocker=i;}
   if(next>=here+bytes){placed=true;break;}
   if(blocker==ASSET_COUNT)break;
   here=cache[blocker].at+cache[blocker].bytes;
  }
  if(placed){
#ifdef __NDS__
   /* Clean before the read (a DMA-based reader bypasses the cache) and after
    * it (a CPU copy goes through it); the ARM7 reads main RAM directly. */
   DC_FlushRange(arena+here,bytes);
#endif
   if(fseek(pack,(long)entries[asset].offset,SEEK_SET)||fread(arena+here,1,bytes,pack)!=bytes)return NULL;
#ifdef __NDS__
   DC_FlushRange(arena+here,bytes);
#endif
   *c=(CacheEntry){here,bytes,++cache_age,(uint16_t)asset,true};sound_loads++;sound_load_bytes+=bytes;
   return arena+here;
  }
  unsigned victim=ASSET_COUNT;
  for(unsigned i=0;i<ASSET_COUNT;i++)if(cache[i].used&&!playing(i)&&(victim==ASSET_COUNT||cache[i].age<cache[victim].age))victim=i;
  if(victim==ASSET_COUNT)return NULL;
  cache[victim].used=false;sound_evictions++;
 }
}
static const SoundAsset *asset(unsigned key)
{
    if(key>0&&key<=ASSET_COUNT)return &sound_assets[key-1];
    for(unsigned i=0;i<ASSET_COUNT;++i)
        if(sound_assets[i].va==key)return &sound_assets[i];
    return NULL;
}
int16_t sound_key_handle(unsigned key)
{
    const SoundAsset *a=asset(key);
    return a?(int16_t)(a-sound_assets+1):0;
}
unsigned sound_global_key(unsigned world,unsigned address)
{
    for(unsigned i=0;i<sizeof(sound_bindings)/sizeof(sound_bindings[0]);++i)
        if(sound_bindings[i].world==world&&sound_bindings[i].address==address)
            return sound_bindings[i].va;
    return 0;
}
void sound_prepare_player(Player *p,unsigned world)
{
    p->jump_sound=(int)sound_global_key(world,0x4dac74);
    p->glide_sound=(int)sound_global_key(world,0x4dac3e);
    p->shot_sound=(int)sound_global_key(world,0x4dac6e);
    p->push_sound=(int)sound_global_key(world,0x4dac40);
    p->penguin_hurt_sound=(int)sound_global_key(world,0x4e0b0e);
    p->milk_hurt_sound=(int)sound_global_key(world,0x4dac4c);
    /* Load this world's bound samples during map loading, not mid-play. */
    for(unsigned i=0;i<sizeof(sound_bindings)/sizeof(sound_bindings[0]);++i)
        if(sound_bindings[i].world==world){const SoundAsset *a=asset(sound_bindings[i].va);if(a)load((unsigned)(a-sound_assets));}
}
#ifdef __NDS__
static unsigned hardware_volume(unsigned gain){return (gain*127u+16384u)>>15;}
#endif
static void release(SoundChannel *c){
#ifdef __NDS__
 if(c->active&&c->hardware>=0)soundKill(c->hardware);
#endif
 c->active=false;c->hardware=-1;
}
/* Finite playback ends after (repeat+1) passes; repeat 255 loops forever. */
static bool expired(const SoundChannel *c){
 if(!c->active||c->repeat==255)return false;
 return now_frames()-c->start>=c->frames*((uint32_t)c->repeat+1u);
}
static void refresh(SoundChannel *c){
 if(!expired(c))return;
 /* A one-shot channel stops by itself; finite loops are stopped here. */
 if(c->repeat)release(c);else{c->active=false;c->hardware=-1;}
}
#ifdef __NDS__
/* A free locked channel, else the one whose slot started earliest (finite
 * playback preferred over loops); that slot is stopped first. */
static int pick_hardware_channel(void){
 uint32_t busy=0;
 for(unsigned i=0;i<CHANNELS;i++){refresh(&channels[i]);if(channels[i].active&&channels[i].hardware>=0)busy|=1u<<channels[i].hardware;}
 for(int ch=0;ch<16;ch++)if(((EFFECT_CHANNEL_MASK>>ch)&1u)&&!((busy>>ch)&1u))return ch;
 SoundChannel *victim=NULL;
 for(unsigned i=0;i<CHANNELS;i++){SoundChannel *c=&channels[i];if(!c->active||c->hardware<0)continue;
  if(!victim||(victim->repeat==255&&c->repeat!=255)||((victim->repeat==255)==(c->repeat==255)&&(int32_t)(c->start-victim->start)<0))victim=c;}
 int ch=victim->hardware;release(victim);sound_evictions++;return ch;
}
#endif
void sound_channel_stop(unsigned slot)
{
    if(slot>=CHANNELS||slot==16)return;
    SoundChannel *c=&channels[slot];refresh(c);release(c);
    memset(c,0,sizeof(*c));c->hardware=-1;c->volume=32768;
}
void sound_events_stop(void)
{for(unsigned i=0;i<CHANNELS;++i)sound_channel_stop(i);}
bool sound_play(unsigned slot,unsigned key,unsigned repeat)
{
    load_ok=false;
    if(slot>=CHANNELS||slot==16)return false;
    const SoundAsset *a=asset(key);if(!a)return false;
    sound_channel_stop(slot);SoundChannel *c=&channels[slot];
    unsigned index=(unsigned)(a-sound_assets);const uint8_t *data=load(index);
    if(!data){sound_dropped++;return false;}
    const PackEntry *e=&entries[index];int hardware=-1;
#ifdef __NDS__
    /* ADPCM loops restart after the 4-byte header with the saved state. */
    hardware=pick_hardware_channel();
    hardware=soundPlaySampleChannel(hardware,data,e->format==FORMAT_ADPCM?SoundFormat_ADPCM:SoundFormat_16Bit,e->bytes,SAMPLE_RATE,
                                    127,64,repeat!=0,e->format==FORMAT_ADPCM?1:0);
    if(hardware<0){sound_dropped++;return false;}
#else
    (void)data;
#endif
    *c=(SoundChannel){true,hardware,(uint16_t)index,(uint8_t)(repeat>255?255:repeat),now_frames(),e->frames,32768};
    sound_plays++;load_ok=true;return true;
}
bool sound_channel_active(unsigned slot)
{
    if(slot>=CHANNELS||slot==16)return false;
    refresh(&channels[slot]);return channels[slot].active;
}
bool sound_last_load_ok(void) {return load_ok;}
void sound_channel_volume(unsigned slot,int db)
{
    /* Native42339e clamps-100..0dB. Q15 gain preserves the original dB curve, including quiet ambience. */
    static const uint16_t gains[]={32768,29205,26029,23198,20675,18427,16423,14637,13045,11627,10362,9235,8231,7336,6538,5827,5193,4629,4125,3677,3277,2920,2603,2320,2068,1843,1642,1464,1305,1163,1036,924,823,734,654,583,519,463,413,368,328,292,260,232,207,184,164,146,130,116,104,92,82,73,65,58,52,46,41,37,33,29,26,23,21,18,16,15,13,12,10,9,8,7,7,6,5,5,4,4,3,3,3,2,2,2,2,1,1,1,1,1,1,1,1,1,1,0,0,0,0};
    if(slot>=CHANNELS||slot==16)return;
    if(db>0)db=0;
    SoundChannel *c=&channels[slot];unsigned gain=db< -100?0:gains[-db];
    if(c->volume==gain)return;
    c->volume=gain;refresh(c);
#ifdef __NDS__
    if(c->active&&c->hardware>=0)soundSetVolume(c->hardware,(u8)hardware_volume(gain));
#endif
}
void sound_events_event(void *context,PlayerEventType type,int id,int arg)
{
    (void)context;
    switch(type) {
    case PLAYER_SOUND_PLAY:sound_play((unsigned)arg,(unsigned)id,0);break;
    case PLAYER_SOUND_STOP:sound_channel_stop((unsigned)id);break;
    case PLAYER_SOUND_LOAD:sound_play((unsigned)arg,(unsigned)id,0);break;
    case PLAYER_SOUND_VOLUME:sound_channel_volume((unsigned)id,arg);break;
    case PLAYER_UNSUPPORTED:break;
    }
}
void sound_events_poll(void)
{for(unsigned slot=0;slot<CHANNELS;++slot)refresh(&channels[slot]);}
void sound_events_mix(int16_t *samples,unsigned frames,unsigned music_volume)
{
    /* Hardware channels mix effects. Host builds use this call as their clock. */
    (void)samples;(void)music_volume;
#ifndef __NDS__
    host_frames+=frames;
#else
    (void)frames;
#endif
}
uint32_t sound_effect_underruns(void) {return sound_dropped;}
unsigned sound_effect_channel_mask(void) {return EFFECT_CHANNEL_MASK;}
