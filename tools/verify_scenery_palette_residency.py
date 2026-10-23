"""Sanitizer-check the proposed bounded palette cache against all map footprints.

Includes front-color protection, failed/partial uploads, cancellation, budget
rejection and complete-capacity pressure. This is not a GPU timing test.
"""
import argparse
import collections
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include "scenery_palette.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static SceneryPalette cache;
static uint8_t memory[65536],before[65536],protected_bytes[65536];
static uint8_t **colors;
static unsigned *lengths,groups,calls,fail_at;
static unsigned frames,retries,fallbacks,aborts,uploaded_total,upload_peak,front_checks,budget_checks,partial_checks;
static unsigned get(FILE *f,unsigned bytes){unsigned v=0;for(unsigned i=0;i<bytes;i++){int c=fgetc(f);assert(c!=EOF);v|=(unsigned)c<<(i*8);}return v;}
static void front(void){
 memset(protected_bytes,0,sizeof(protected_bytes));
 for(unsigned i=0;i<SCENERY_PALETTE_ENTRIES;i++){
  SceneryPaletteEntry *e=cache.entries+i;
  if(!(e->pins&(1u<<cache.front)))continue;
  assert(e->key<groups&&e->blocks*16u==lengths[e->key]);
  assert(!memcmp(memory+e->block*16u,colors[e->key],lengths[e->key]));
  memset(protected_bytes+e->block*16u,1,lengths[e->key]);
 }
 memcpy(before,memory,sizeof(memory));front_checks++;
}
static void unchanged_front(void){for(unsigned i=0;i<65536;i++)if(protected_bytes[i])assert(before[i]==memory[i]);}
static bool upload(void *context,uint16_t key,unsigned offset,unsigned bytes){
 (void)context;assert(key<groups&&bytes==lengths[key]&&offset+bytes<=65536&&!(offset&15u));
 for(unsigned i=offset;i<offset+bytes;i++)assert(!protected_bytes[i]);
 if(++calls==fail_at){/* Simulate a failed write after a partial DMA/copy. */
  memcpy(memory+offset,colors[key],bytes/2);return false;
 }
 memcpy(memory+offset,colors[key],bytes);return true;
}
static void invariants(void){
 uint8_t blocks[4096]={0},seen[SCENERY_PALETTE_ENTRIES]={0};
 for(unsigned i=0;i<1024;i++)if(cache.lookup[i]){
  unsigned slot=cache.lookup[i]-1;assert(slot<SCENERY_PALETTE_ENTRIES&&!seen[slot]++&&(cache.entries[slot].flags&1u));
 }
 for(unsigned i=0;i<SCENERY_PALETTE_ENTRIES;i++){
  SceneryPaletteEntry *e=cache.entries+i;if(!(e->flags&1u)){assert(!e->pins);continue;}
  assert(seen[i]&&e->blocks&&e->blocks<=32&&e->block+e->blocks<=4096);
  for(unsigned j=e->block;j<e->block+e->blocks;j++)assert(!blocks[j]++);
  for(unsigned j=i+1;j<SCENERY_PALETTE_ENTRIES;j++)if(cache.entries[j].flags&1u)assert(cache.entries[j].key!=e->key);
 }
 for(unsigned i=0;i<4096;i++)assert((!!(cache.occupied[i>>5]&(1u<<(i&31))))==!!blocks[i]);
}
static bool prepare(const uint16_t *keys,unsigned n){
 assert(scenery_palette_begin(&cache));assert(!scenery_palette_begin(&cache));
 for(unsigned i=0;i<n;i++){
  assert(keys[i]<groups);unsigned offset;
  if(!scenery_palette_acquire(&cache,keys[i],lengths[keys[i]],&offset))return false;
  assert(offset+lengths[keys[i]]<=65536&&!(offset&15u));
 }
 return true;
}
static void check_requested(const uint16_t *keys,unsigned n){
 for(unsigned i=0;i<n;i++){
  unsigned offset,bytes;assert(scenery_palette_find(&cache,keys[i],&offset,&bytes));
  assert(bytes==lengths[keys[i]]&&!memcmp(memory+offset,colors[keys[i]],bytes));
 }
}
int main(int argc,char **argv){
 assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f&&get(f,4)==0x31545053u);unsigned maps=get(f,4);
 for(unsigned map=0;map<maps;map++){
  groups=get(f,4);unsigned count=get(f,4);assert(groups&&groups<65536&&count);
  colors=calloc(groups,sizeof(*colors));lengths=calloc(groups,sizeof(*lengths));assert(colors&&lengths);
  for(unsigned i=0;i<groups;i++){
   lengths[i]=get(f,2);assert(lengths[i]&&lengths[i]<=512&&!(lengths[i]&15));
   colors[i]=malloc(lengths[i]);assert(colors[i]&&fread(colors[i],1,lengths[i],f)==lengths[i]);
  }
  scenery_palette_reset(&cache);memset(memory,0xcd,sizeof(memory));
  for(unsigned tick=0;tick<count;tick++){
   unsigned n=get(f,2);uint16_t keys[512];assert(n<=512);
   for(unsigned i=0;i<n;i++)keys[i]=(uint16_t)get(f,2);
   front();
   if(tick%37==0){
    bool ok=prepare(keys,n);(void)ok;scenery_palette_abort(&cache);unchanged_front();invariants();aborts++;
   }
   if(!prepare(keys,n)){
    /* A discontinuous camera jump or fragmentation may require a complete
     * RGB555 bridge. Only after that bridge removes indexed consumers can
     * the real renderer reset its palette epoch. No front colors are evicted. */
    unchanged_front();scenery_palette_abort(&cache);invariants();fallbacks++;
    scenery_palette_reset(&cache);front();assert(prepare(keys,n));retries++;
   }
   if(tick%41==0){
    unsigned dirty=0;
    for(unsigned i=0;i<SCENERY_PALETTE_ENTRIES;i++)if(cache.entries[i].flags&2u)dirty+=cache.entries[i].blocks*16u;
    if(dirty){unsigned done=123;calls=0;assert(!scenery_palette_commit(&cache,dirty-1,upload,NULL,&done));assert(done==0&&!calls);unchanged_front();budget_checks++;}
   }
   if(tick%53==0){
    unsigned dirty=0;for(unsigned i=0;i<SCENERY_PALETTE_ENTRIES;i++)dirty+=!!(cache.entries[i].flags&2u);
    if(dirty){
     calls=0;fail_at=dirty>1?2:1;unsigned done;
     assert(!scenery_palette_commit(&cache,65536,upload,NULL,&done));unchanged_front();
     scenery_palette_abort(&cache);invariants();assert(prepare(keys,n));partial_checks++;
    }
   }
   calls=0;fail_at=0;unsigned done;assert(scenery_palette_commit(&cache,65536,upload,NULL,&done));
   uploaded_total+=done;if(done>upload_peak)upload_peak=done;
   unchanged_front();check_requested(keys,n);assert(!scenery_palette_publish(NULL));assert(scenery_palette_publish(&cache));assert(!scenery_palette_publish(&cache));
   if(tick%257==0)invariants();frames++;
  }
  front();invariants();
  for(unsigned i=0;i<groups;i++)free(colors[i]);free(colors);free(lengths);
 }
 assert(fgetc(f)==EOF);fclose(f);
 /* Fill every byte with displayed512-byte palettes, then require a new one.
  * The new request must fail without mutating or evicting any front entry. */
 groups=129;colors=calloc(groups,sizeof(*colors));lengths=calloc(groups,sizeof(*lengths));assert(colors&&lengths);
 for(unsigned i=0;i<groups;i++){lengths[i]=512;colors[i]=malloc(512);assert(colors[i]);memset(colors[i],(int)i,512);}
 scenery_palette_reset(&cache);assert(scenery_palette_begin(&cache));
 for(unsigned i=0;i<128;i++){unsigned at;assert(scenery_palette_acquire(&cache,(uint16_t)i,512,&at));}
 front();calls=fail_at=0;unsigned done;assert(scenery_palette_commit(&cache,65536,upload,NULL,&done)&&done==65536);assert(scenery_palette_publish(&cache));
 front();assert(scenery_palette_begin(&cache));unsigned at;assert(!scenery_palette_acquire(&cache,128,512,&at));scenery_palette_abort(&cache);unchanged_front();invariants();
 for(unsigned i=0;i<groups;i++)free(colors[i]);free(colors);free(lengths);
 /* Exhaust metadata slots while palette RAM remains mostly empty. Reusing
  * current keys must still work; a new key needs an explicit fallback. */
 groups=513;colors=calloc(groups,sizeof(*colors));lengths=calloc(groups,sizeof(*lengths));assert(colors&&lengths);
 for(unsigned i=0;i<groups;i++){lengths[i]=16;colors[i]=malloc(16);assert(colors[i]);memset(colors[i],(int)i,16);}
 scenery_palette_reset(&cache);front();assert(scenery_palette_begin(&cache));
 for(unsigned i=0;i<512;i++)assert(scenery_palette_acquire(&cache,(uint16_t)i,16,&at));
 calls=fail_at=0;assert(scenery_palette_commit(&cache,65536,upload,NULL,&done)&&done==8192);assert(scenery_palette_publish(&cache));
 front();assert(scenery_palette_begin(&cache));assert(!scenery_palette_acquire(&cache,512,16,&at));
 assert(!scenery_palette_acquire(&cache,0,0,&at));assert(!scenery_palette_acquire(&cache,0,32,&at));assert(!scenery_palette_acquire(&cache,0,528,&at));
 for(unsigned i=0;i<512;i++)assert(scenery_palette_acquire(&cache,(uint16_t)i,16,&at));
 calls=0;assert(scenery_palette_commit(&cache,0,upload,NULL,&done)&&!done&&!calls);
 scenery_palette_abort(&cache);unchanged_front();invariants();
 for(unsigned i=0;i<groups;i++)free(colors[i]);free(colors);free(lengths);
 assert(aborts&&budget_checks&&partial_checks);
 printf("{\"frames\":%u,\"fallbacks\":%u,\"bridge_retries\":%u,\"aborts\":%u,\"budget_rejections\":%u,\"partial_upload_failures\":%u,\"uploaded_bytes\":%u,\"peak_upload_bytes\":%u,\"front_checks\":%u,\"cache_bytes\":%zu}\n",frames,fallbacks,retries,aborts,budget_checks,partial_checks,uploaded_total,upload_peak,front_checks,sizeof(cache));
 return 0;
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=ROOT/'research/rendering/direct-scenery-runtime';staged=ROOT/'research/rendering/direct-indexed-scenery-assets/nitrofs/composite';paths=sorted(staged.glob('*.gpuinfo'));rows=[]
    with tempfile.TemporaryDirectory(prefix='kinder-palette-residency-')as directory:
        work=Path(directory);trace=work/'trace.bin'
        with trace.open('wb')as f:
            f.write(struct.pack('<4sI',b'SPT1',len(paths)))
            for path in paths:
                info=path.read_bytes();n,ngroups=struct.unpack_from('<II',info,8);records=struct.unpack_from('<'+'I'*n,info,32);atlas=path.with_suffix('.atlas').read_bytes();palettes={}
                for tile,record in enumerate(records):
                    group=record&65535
                    if group in palettes:continue
                    a,b=struct.unpack_from('<II',atlas,8+tile*8);at=8+n*8+(a&0x1fffff);p=atlas[at:at+(b&1023)];colors=((record>>16)&255)+1
                    rgb=(np.frombuffer(p,dtype='<u2',count=colors,offset=4)&32767).astype('<u2').tobytes();rgb+=bytes(-len(rgb)%16);palettes[group]=rgb
                assert len(palettes)==ngroups
                index=path.with_suffix('.index').read_bytes();_,w,h,nc,_,_,_=struct.unpack_from('<4sHHIIHH',index);pairs=list(struct.iter_unpack('<HH',index[20+nc*12:]));cells=[[]for _ in range(w*h)]
                for kind,first,count in struct.iter_unpack('<III',index[20:20+nc*12]):
                    if not kind:
                        for cell,tile in pairs[first:first+count]:cells[cell].append(records[tile]&65535)
                nx,ny=max(1,w-16+1),max(1,h-12+1);frames=nx*ny
                f.write(struct.pack('<II',ngroups,frames))
                for key in range(ngroups):f.write(struct.pack('<H',len(palettes[key]))+palettes[key])
                for y in range(ny):
                    xs=range(nx)if y%2==0 else range(nx-1,-1,-1);start=0 if y%2==0 else nx-1;active=collections.Counter()
                    for yy in range(y,min(y+13,h)):
                        for xx in range(start,min(start+17,w)):active.update(cells[yy*w+xx])
                    previous=None
                    for x in xs:
                        if previous is not None:
                            remove=previous if x>previous else previous+16;add=x+16 if x>previous else x
                            for yy in range(y,min(y+13,h)):
                                if remove<w:
                                    for key in cells[yy*w+remove]:
                                        active[key]-=1
                                        if not active[key]:del active[key]
                                if add<w:active.update(cells[yy*w+add])
                        keys=sorted(active);assert len(keys)<=512
                        f.write(struct.pack('<H',len(keys))+struct.pack('<'+'H'*len(keys),*keys));previous=x
                rows.append(dict(map=path.stem,frames=frames,palette_groups=ngroups,index_sha256=hashlib.sha256(index).hexdigest()))
        (work/'test.c').write_text(C);exe=work/'test'
        subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(runtime),str(work/'test.c'),str(runtime/'scenery_palette.c'),'-o',str(exe)],check=True)
        result=subprocess.run([str(exe),str(trace)],capture_output=True,text=True,check=True);metrics=json.loads(result.stdout)
        assert metrics['frames']==sum(r['frames']for r in rows)
    report=dict(scope=__doc__,maps=rows,metrics=metrics,asan_ubsan=True,front_colors_preserved=True,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [*runtime.glob('*.[ch]'),Path(__file__)]},limits=['Research runtime module only; no production renderer or assets changed.','The bridge fallback is a host epoch reset after preserving the front; a real RGB555 publication must precede that reset.','No proof of VBlank upload budget, live GPU palette publication or hardware speed.'])
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(metrics))


if __name__=='__main__':main()
