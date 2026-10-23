"""Last-page lookup hints retain packet bytes, page tags/ages and I/O exactly."""
from pathlib import Path
import json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
RESULTS={}
with tempfile.TemporaryDirectory(prefix='kinder-page-hint-') as td:
 t=Path(td)
 for kind in ('composite','sound_events'):
  candidate=R/'research/rendering/page-hint-candidate'/f'{kind}.c'
  for variant in ('linear','hint'):
   source=R/'ds/source'/f'{kind}.c' if variant=='linear' else candidate
   header='#include "'+str(source)+'"\n#include <assert.h>\n#include <stdio.h>\n#include <stdlib.h>\n'
   if kind=='composite':
    setup='''atlas=tmpfile();assert(atlas);assert(fwrite(original,1,bytes,atlas)==bytes);atlas_size=bytes;
    atlas_pages=ATLAS_PAGE_COUNT;atlas_page=malloc(8192);atlas_extra_pages=malloc((atlas_pages-1)*8192);assert(atlas_page&&atlas_extra_pages);
    for(unsigned i=0;i<atlas_pages;i++)atlas_page_offset[i]=UINT32_MAX;scaled_tiles=true;'''
    call='''const uint8_t *p=read_packet(offset,n,&stats);assert(p&&!memcmp(p,original+offset,n));
    for(unsigned i=0;i<atlas_pages;i++){hash=(hash^atlas_page_offset[i])*16777619u;hash=(hash^atlas_page_age[i])*16777619u;hash=(hash^atlas_page_bytes[i])*16777619u;}'''
    end='printf("{\\"hash\\":%u,\\"reads\\":%u,\\"read_bytes\\":%u}\\n",hash,stats.read_calls,stats.read_bytes);free(atlas_page);free(atlas_extra_pages);fclose(atlas);'
   else:
    setup='FILE *f=tmpfile();assert(f);assert(fwrite(original,1,bytes,f)==bytes);'
    call='''uint8_t packet[2320];assert(pack_read(f,offset,packet,n));assert(!memcmp(packet,original+offset,n));
    for(unsigned i=0;i<SOUND_PAGE_COUNT;i++){hash=(hash^sound_page_offsets[i])*16777619u;hash=(hash^sound_page_ages[i])*16777619u;hash=(hash^sound_page_lengths[i])*16777619u;}'''
    end='printf("{\\"hash\\":%u,\\"reads\\":%u,\\"read_bytes\\":%u}\\n",hash,sound_pack_reads,sound_pack_bytes);fclose(f);'
   # Deterministic temporal runs, random seeks, page splits and final short page.
   body='''int main(void){unsigned bytes=8192*37+37;uint8_t *original=malloc(bytes);assert(original);
   for(unsigned i=0;i<bytes;i++)original[i]=(uint8_t)(i*29u+(i>>8));
   SceneRenderStats stats={0};(void)stats;
   SETUP
   uint32_t hash=2166136261u,rng=2001,offset=0;
   for(unsigned i=0;i<50000;i++){
    rng=rng*1664525u+1013904223u;unsigned n=1+rng%2320;
    if(i%7==0)offset=(rng%(bytes-n))&~3u;
    else if(i%11==0)offset=bytes-n;
    else offset=(offset+4)%(bytes-n);
    CALL
   }
   END
   free(original);return 0;
   }'''.replace('SETUP',setup).replace('CALL',call).replace('END',end)
   # Sound headers do not include scene stats.
   if kind=='sound_events':body=body.replace('SceneRenderStats stats={0};(void)stats;','')
   src=t/f'{kind}-{variant}.c';src.write_text(header+body)
   exe=src.with_suffix('');subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ds/source'),str(src),'-o',str(exe)],check=True)
   RESULTS[f'{kind}-{variant}']=json.loads(subprocess.check_output([str(exe)],text=True))
  assert RESULTS[f'{kind}-linear']==RESULTS[f'{kind}-hint'],kind
 report={'scope':__doc__,'packet_requests':200000,'results':RESULTS,'sanitizers':['address','undefined'],'same_bytes_tags_ages_and_reads':True,'limits':['Synthetic packet bytes, not a gameplay or hardware timing test.']}
 (R/'research/rendering/page-hint-packet-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
