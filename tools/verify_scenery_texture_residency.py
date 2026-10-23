"""Exercise inactive-bank tile residency on every map footprint with sanitizers."""
import argparse
import collections
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path
from tile_storage import unlz

ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include "scenery_texture.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static SceneryTexture cache;
static uint8_t memory[2][SCENERY_TEXTURE_BYTES+32],before[SCENERY_TEXTURE_BYTES];
static uint8_t *tiles;
static unsigned tile_count,calls,fail_at,uploads,frames,aborts,failures,borrows,hits;
static unsigned get(FILE *f,unsigned bytes){unsigned v=0;for(unsigned i=0;i<bytes;i++){int c=fgetc(f);assert(c!=EOF);v|=(unsigned)c<<(8*i);}return v;}
static bool upload(void *context,unsigned bank,uint16_t key,unsigned offset){
 (void)context;assert(bank<2&&bank!=cache.front&&key<tile_count&&offset<SCENERY_TEXTURE_BYTES&&!(offset&255));
 if(++calls==fail_at){memcpy(memory[bank]+offset,tiles+key*256u,128);return false;}
 memcpy(memory[bank]+offset,tiles+key*256u,256);uploads++;return true;
}
static void unchanged_front(void){assert(!memcmp(before,memory[cache.front],SCENERY_TEXTURE_BYTES));}
static void guards(void){for(unsigned b=0;b<2;b++)for(unsigned i=SCENERY_TEXTURE_BYTES;i<sizeof(memory[b]);i++)assert(memory[b][i]==0xa5);}
static void invariants(void){
 for(unsigned bank=0;bank<2;bank++){
  unsigned seen[SCENERY_TEXTURE_SLOTS]={0};SceneryTextureBank *b=cache.banks+bank;
  for(unsigned i=0;i<1024;i++)if(b->lookup[i]){unsigned slot=b->lookup[i]-1;assert(slot<SCENERY_TEXTURE_SLOTS&&!seen[slot]++&&(b->entries[slot].flags&1u));}
  for(unsigned i=0;i<SCENERY_TEXTURE_SLOTS;i++){
   SceneryTextureEntry *e=b->entries+i;if(!(e->flags&1u)){assert(!e->flags&&!seen[i]);continue;}
   assert(seen[i]&&e->key<tile_count&&!memcmp(memory[bank]+i*256u,tiles+e->key*256u,256));
   unsigned offset;assert(scenery_texture_find(&cache,bank,e->key,&offset)&&offset==i*256u);
   for(unsigned j=i+1;j<SCENERY_TEXTURE_SLOTS;j++)if(b->entries[j].flags&1u)assert(e->key!=b->entries[j].key);
  }
 }
 guards();
}
static bool prepare(const uint16_t *keys,unsigned n){
 assert(scenery_texture_begin(&cache)&&!scenery_texture_begin(&cache));
 unsigned bank=cache.front^1u;
 for(unsigned i=0;i<n;i++){
  unsigned offset,previous=calls;
  if(!scenery_texture_acquire(&cache,keys[i],upload,NULL,&offset))return false;
  if(previous==calls)hits++;
  assert(!memcmp(memory[bank]+offset,tiles+keys[i]*256u,256));
 }
 return true;
}
int main(int argc,char **argv){
 assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f&&get(f,4)==0x31545453u);unsigned maps=get(f,4);
 memset(memory,0xa5,sizeof(memory));
 for(unsigned map=0;map<maps;map++){
  tile_count=get(f,4);unsigned count=get(f,4);assert(tile_count&&tile_count<=65536&&count);
  tiles=malloc(tile_count*256u);assert(tiles&&fread(tiles,256,tile_count,f)==tile_count);scenery_texture_reset(&cache,0);
  for(unsigned tick=0;tick<count;tick++){
   unsigned n=get(f,2);assert(n<=SCENERY_TEXTURE_SLOTS);uint16_t keys[SCENERY_TEXTURE_SLOTS];
   for(unsigned i=0;i<n;i++){keys[i]=(uint16_t)get(f,2);assert(keys[i]<tile_count);}
   memcpy(before,memory[cache.front],SCENERY_TEXTURE_BYTES);
   if(tick%37==0){calls=fail_at=0;assert(prepare(keys,n));scenery_texture_abort(&cache);unchanged_front();invariants();aborts++;}
   if(tick%53==0&&n){
    scenery_texture_invalidate(&cache,cache.front^1u);calls=0;fail_at=n>1?2:1;
    assert(!prepare(keys,n)&&!scenery_texture_publish(&cache));scenery_texture_abort(&cache);unchanged_front();invariants();failures++;
   }
   calls=fail_at=0;assert(prepare(keys,n));unchanged_front();assert(scenery_texture_publish(&cache)&&!scenery_texture_publish(&cache));
   for(unsigned i=0;i<n;i++){unsigned offset;assert(scenery_texture_find(&cache,cache.front,keys[i],&offset)&&!memcmp(memory[cache.front]+offset,tiles+keys[i]*256u,256));}
   if(tick%211==0){
    unsigned bank=cache.front^1u;scenery_texture_invalidate(&cache,bank);memset(memory[bank],0xcd,SCENERY_TEXTURE_BYTES);
    assert(scenery_texture_adopt_bridge(&cache,bank));borrows++;invariants();
   }
   if(tick%257==0)invariants();guards();frames++;
  }
  invariants();free(tiles);
 }
 assert(fgetc(f)==EOF);fclose(f);
 tile_count=385;tiles=malloc(tile_count*256u);assert(tiles);
 for(unsigned i=0;i<tile_count;i++)memset(tiles+i*256u,(int)i,256);
 scenery_texture_reset(&cache,0);memcpy(before,memory[0],SCENERY_TEXTURE_BYTES);assert(scenery_texture_begin(&cache));calls=fail_at=0;unsigned offset;
 for(unsigned i=0;i<384;i++)assert(scenery_texture_acquire(&cache,(uint16_t)i,upload,NULL,&offset));
 assert(!scenery_texture_acquire(&cache,384,upload,NULL,&offset)&&!scenery_texture_publish(&cache));scenery_texture_abort(&cache);unchanged_front();invariants();
 assert(scenery_texture_begin(&cache));
 for(unsigned i=0;i<384;i++)assert(scenery_texture_acquire(&cache,(uint16_t)i,upload,NULL,&offset));
 assert(scenery_texture_publish(&cache));invariants();
 /* Borrowing the bank in the middle of a transaction forbids publication. */
 assert(scenery_texture_begin(&cache));scenery_texture_invalidate(&cache,cache.front^1u);assert(!scenery_texture_publish(&cache));scenery_texture_abort(&cache);invariants();
 free(tiles);assert(aborts&&failures&&borrows&&hits);
 printf("{\"frames\":%u,\"aborts\":%u,\"partial_upload_failures\":%u,\"borrowed_bank_epochs\":%u,\"cache_hits\":%u,\"uploads\":%u,\"cache_bytes\":%zu}\n",frames,aborts,failures,borrows,hits,uploads,sizeof(cache));return 0;
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=ROOT/'research/rendering/direct-scenery-runtime';staged=ROOT/'research/rendering/direct-indexed-scenery-assets/nitrofs/composite';paths=sorted(staged.glob('*.atlas'));rows=[]
    with tempfile.TemporaryDirectory(prefix='kinder-texture-residency-')as directory:
        work=Path(directory);trace=work/'trace.bin'
        with trace.open('wb')as f:
            f.write(struct.pack('<4sI',b'STT1',len(paths)))
            for path in paths:
                atlas=path.read_bytes();n=struct.unpack_from('<I',atlas,4)[0];index=path.with_suffix('.index').read_bytes();_,w,h,nc,_,_,_=struct.unpack_from('<4sHHIIHH',index);nx,ny=max(1,w-16+1),max(1,h-12+1);frames=nx*ny
                f.write(struct.pack('<II',n,frames))
                for tile in range(n):
                    a,b=struct.unpack_from('<II',atlas,8+tile*8);at=8+n*8+(a&0x1fffff);p=atlas[at:at+(b&1023)];bits,_,colors=struct.unpack_from('<BBH',p)
                    raw=unlz(p[4+((colors*2+3)&~3):]);assert len(raw)==256*bits//8;f.write(raw+bytes(256-len(raw)))
                pairs=list(struct.iter_unpack('<HH',index[20+nc*12:]));cells=[[]for _ in range(w*h)]
                for kind,first,count in struct.iter_unpack('<III',index[20:20+nc*12]):
                    if not kind:
                        for cell,tile in pairs[first:first+count]:cells[cell].append(tile)
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
                        keys=sorted(active);assert len(keys)<=384;f.write(struct.pack('<H',len(keys))+struct.pack('<'+'H'*len(keys),*keys));previous=x
                rows.append(dict(map=path.stem,frames=frames,tiles=n,index_sha256=hashlib.sha256(index).hexdigest(),atlas_sha256=hashlib.sha256(atlas).hexdigest()))
        (work/'test.c').write_text(C);exe=work/'test'
        subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(runtime),str(work/'test.c'),str(runtime/'scenery_texture.c'),'-o',str(exe)],check=True)
        result=subprocess.run([str(exe),str(trace)],capture_output=True,text=True,check=True);metrics=json.loads(result.stdout);assert metrics['frames']==sum(r['frames']for r in rows)
    sources=[runtime/'scenery_texture.c',runtime/'scenery_texture.h',Path(__file__)]
    report=dict(scope=__doc__,maps=rows,metrics=metrics,asan_ubsan=True,front_bank_preserved=True,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in sources},limits=['Host cache bytes and ownership only; no live GPU or gameplay speed proof.','Research module, not linked into the playable ROM.','Forced aborts/borrows/failures inflate uploads; counters are not a clean performance benchmark.'])
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(metrics))


if __name__=='__main__':main()
