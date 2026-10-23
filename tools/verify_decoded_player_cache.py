"""Stress the bounded decoded player arena against fresh packet decodes under sanitizers."""
from pathlib import Path
import json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-player-arena-')as tmp:
 t=Path(tmp);src=t/'probe.c';exe=t/'probe'
 src.write_text('#include "'+str(R/'ds/source/player_graphics.c')+'"\n'+r'''
#include <assert.h>
int main(void){
 assert(player_graphics_open());uint16_t *reference=malloc(capacity*2);uint8_t *packet=malloc(compressed_capacity);
 assert(reference&&packet);unsigned checks=0,hits=0;uint16_t pixels[49152];
 for(unsigned pass=0;pass<3;pass++)for(unsigned i=0;i<586;i++){
  unsigned character=i&1,frame=(i*73+pass*17)%counts[character],facing=(i/2)&1;
  const Raster *f=&frames[character][frame].raster[facing];unsigned n=(unsigned)f->w*f->h;
  assert(!fseek(files[character],f->offset,SEEK_SET)&&fread(packet,1,f->compressed,files[character])==f->compressed);
  assert(sprite_codec_decode(packet,f->compressed,reference,n));
  PlayerPacket before[PACKET_CACHE_ENTRIES];memcpy(before,packets,sizeof(before));
  const uint8_t *cached=player_packet(character,frame,facing,f);
  for(unsigned a=0;a<PACKET_CACHE_ENTRIES;a++)if(before[a].data)
   for(unsigned b=0;b<PACKET_CACHE_ENTRIES;b++)if(packets[b].data&&packets[b].key==before[a].key)assert(packets[b].data==before[a].data);assert(cached&&!memcmp(cached,reference,n*2));
  uint32_t decoded=frame_decodes,reads=packet_reads;
  assert(player_packet(character,frame,facing,f)==cached&&frame_decodes==decoded&&packet_reads==reads);hits++;
  assert(player_graphics_draw(pixels,(int)character,(int)frame,(int)facing,500,550,87,24));
  assert(frame_decodes==decoded&&packet_reads==reads);
  size_t used=0;
  for(unsigned a=0;a<PACKET_CACHE_ENTRIES;a++)if(packets[a].data){
   assert(packets[a].data>=packet_arena&&packets[a].data+packets[a].bytes<=packet_arena+PACKET_CACHE_BYTES);
   assert(!((uintptr_t)packets[a].data&3));used+=packets[a].bytes;
   for(unsigned b=a+1;b<PACKET_CACHE_ENTRIES;b++)if(packets[b].data)
    assert(packets[a].data+packets[a].bytes<=packets[b].data||packets[b].data+packets[b].bytes<=packets[a].data);
  }
  assert(used==packet_used&&used<=PACKET_CACHE_BYTES);checks++;
 }
 printf("{\"fresh_image_comparisons\":%u,\"repeat_hits_without_read_or_decode\":%u,\"arena_bytes\":%u,\"decoded_misses\":%u}\n",checks,hits,PACKET_CACHE_BYTES,frame_decodes);
 free(reference);free(packet);player_graphics_close();return 0;
}
''')
 subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ds/source'),f'-DPLAYER_ROOT="{R}/ds/nitrofs/players"',str(src),'-o',str(exe)],check=True)
 d=json.loads(subprocess.check_output([str(exe)],text=True));d['scope']=__doc__;d['limits']=['Host memory/cache checks; independent PNG projection and DS timing have separate checks.']
 (R/'research/rendering/decoded-player-cache-verification.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
