"""Compare the bounded C scenery loader with original colors/ownership, under ASan/UBSan."""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import hashlib,json,struct,subprocess,tempfile
import numpy as np
from build_premerged_blocks import merged_planes,build,encode_block,HEADER as PACK_HEADER,ENTRY
R=Path(__file__).resolve().parents[1]
HEADER=R/'research/rendering/premerged-block-prototype/merged_scenery.h'
PACKS=R/'research/rendering/premerged-block-assets'
SOURCE=r'''
#include "merged_scenery.h"
#include <assert.h>
#include <stdlib.h>
static MergedScenery state;
static uint16_t colors[4096];static uint8_t owners[4096],actual[4096];
static uint32_t seed=2001;
static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static void save(const char *path,const uint8_t *data,size_t n){FILE *f=fopen(path,"wb");assert(f);assert(fwrite(data,1,n,f)==n);assert(!fclose(f));}
int main(int argc,char **argv){
 assert(argc==7);unsigned width=(unsigned)atoi(argv[3]),height=(unsigned)atoi(argv[4]),passes=(unsigned)atoi(argv[5]);
 assert(smc_open(&state,argv[1],width,height,passes));FILE *expected=fopen(argv[2],"rb");assert(expected);
 unsigned blocks=0,cells=0;
 for(unsigned y=0;y<state.rows;y++)for(unsigned x=0;x<state.cols;x++){
  assert(smc_load(&state,x,y));unsigned reads=state.reads;assert(smc_load(&state,x,y)&&reads==state.reads);
  assert(fread(colors,2,4096,expected)==4096&&fread(owners,1,4096,expected)==4096);
  assert(!memcmp(colors,state.pixels,sizeof(colors)));memset(actual,0,sizeof(actual));
  for(unsigned cy=0;cy<4;cy++)for(unsigned cx=0;cx<4;cx++){
   const uint16_t *offsets=smc_cell(&state,cx,cy);assert(offsets);const uint16_t *runs=offsets+passes+1;
   for(unsigned pass=0;pass<passes;pass++)for(unsigned i=offsets[pass];i<offsets[pass+1];i++){
    unsigned v=runs[i],yy=cy*16+(v>>9),left=cx*16+(v&15),right=cx*16+((v>>4)&31);
    for(unsigned xx=left;xx<right;xx++){assert(!actual[yy*64+xx]);actual[yy*64+xx]=(uint8_t)(pass+1);}
   }
   cells++;
  }
  assert(!memcmp(actual,owners,sizeof(owners)));blocks++;
 }
 assert(fgetc(expected)==EOF);fclose(expected);unsigned reads=state.reads;smc_close(&state);
 assert(!smc_open(&state,argv[1],UINT_MAX,height,passes));
 /* Mutate a small valid pack; each trial uses fresh immutable source bytes.
  * Acceptance is allowed for harmless changes (e.g. source SHA), never OOB. */
 FILE *f=fopen(argv[6],"rb");assert(f);assert(!fseek(f,0,SEEK_END));long n=ftell(f);assert(n>76&&n<20000);rewind(f);
 uint8_t *original=malloc((size_t)n),*mutation=malloc((size_t)n);assert(original&&mutation);assert(fread(original,1,(size_t)n,f)==(size_t)n);fclose(f);
 char path[4096];assert(snprintf(path,sizeof(path),"%s.fuzz",argv[6])<(int)sizeof(path));unsigned accepted=0,rejected=0;
 for(unsigned test=0;test<3000;test++){
  memcpy(mutation,original,(size_t)n);unsigned length=(unsigned)n;
  if(test%7==0)length=rnd()%(unsigned)n;
  else for(unsigned i=0;i<1+test%6;i++)mutation[rnd()%(unsigned)n]^=(uint8_t)(1u<<(rnd()%8));
  save(path,mutation,length);
  bool ok=smc_open(&state,path,4,4,2)&&smc_load(&state,0,0);if(ok)accepted++;else rejected++;smc_close(&state);
 }
 remove(path);free(original);free(mutation);assert(accepted&&rejected);
 printf("{\"blocks\":%u,\"cells\":%u,\"reads\":%u,\"fuzz_accepted\":%u,\"fuzz_rejected\":%u,\"loader_bytes\":%zu}\n",blocks,cells,reads,accepted,rejected,sizeof(state));
 return 0;
}
'''
def main():
 rom=resolve_rom(R / 'ds');sha=hashlib.sha256(rom.read_bytes()).hexdigest();manifest=json.loads((PACKS/'manifest.json').read_text());results=[];boundaries=[]
 with tempfile.TemporaryDirectory(prefix='kinder-premerged-proof-') as td:
  t=Path(td);src=t/'test.c';src.write_text(SOURCE);exe=t/'test'
  subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(HEADER.parent),str(src),'-o',str(exe)],check=True)
  # A tiny valid KFLD map exercising interleaved native ownership and alpha.
  # Reuse the actual producer so fuzzing targets its file-format contract.
  # Use an existing source atlas and two actual tiles, keeping dimensions and
  # command ordering synthetic only.
  atlas=(R/'ds/nitrofs/composite'/ (manifest['maps'][0]['map']+'.atlas')).read_bytes()
  index=struct.pack('<4sHHIIHH',b'KFLD',4,4,2,2,0,0)+struct.pack('<III',0,0,1)+struct.pack('<III',0,1,1)+struct.pack('<4H',0,0,5,1)
  fuzz,_=build(index,atlas);fuzz_path=t/'small.smc';fuzz_path.write_bytes(fuzz)
  # Force the separate-read fallback with an incompressible color block and
  # detailed masks. Real generated blocks currently all fit the joint read.
  rng=np.random.default_rng(2001);color=rng.integers(32768,65536,(64,64),dtype=np.uint16).astype('<u2');owner=rng.integers(1,3,(64,64),dtype=np.uint8)
  a,b,words,flags,_=encode_block(color,owner,2);assert ((len(a)+3)&~3)+len(b)>8900
  payload=a+bytes(-len(a)%4)+b;payload+=bytes(-len(payload)%4);length=76+len(payload)
  data=PACK_HEADER.pack(b'SMC1',4,4,4,2,1,1,1,12,76,length)+bytes(32)+ENTRY.pack(76,len(a),len(b),words,flags)+payload
  large=t/'large.smc';large.write_bytes(data);expected=t/'large-expected.bin';expected.write_bytes(color.tobytes()+owner.tobytes())
  boundary=json.loads(subprocess.check_output([str(exe),str(large),str(expected),'4','4','2',str(fuzz_path)],text=True));boundary['case']='joint_packet_exceeds_scratch';boundaries.append(boundary)
  for m in manifest['maps']:
   base=R/'ds/nitrofs/composite'/m['map'];index=base.with_name(base.name+'.index').read_bytes();atlas=base.with_name(base.name+'.atlas').read_bytes()
   assert hashlib.sha256(index+atlas).hexdigest()==m['source_sha256']
   pack=PACKS/(m['map']+'.smc');assert hashlib.sha256(pack.read_bytes()).hexdigest()==m['sha256']
   color,owner,passes=merged_planes(index,atlas);expected=t/'expected.bin'
   with expected.open('wb') as f:
    for y in range(0,color.shape[0],64):
     for x in range(0,color.shape[1],64):
      c=np.zeros((64,64),dtype='<u2');o=np.zeros((64,64),dtype='u1');part=color[y:y+64,x:x+64];own=owner[y:y+64,x:x+64];c[:part.shape[0],:part.shape[1]]=part;o[:own.shape[0],:own.shape[1]]=own;f.write(c.tobytes());f.write(o.tobytes())
   result=json.loads(subprocess.check_output([str(exe),str(pack),str(expected),str(m['width_cells']),str(m['height_cells']),str(passes),str(fuzz_path)],text=True));assert result['blocks']==m['blocks'];result['map']=m['map'];results.append(result);print(json.dumps(result),flush=True)
 assert hashlib.sha256(rom.read_bytes()).hexdigest()==sha
 report={'scope':__doc__,'maps':results,'boundary_cases':boundaries,'blocks':sum(m['blocks'] for m in results),'cells':sum(m['cells'] for m in results),'sanitizers':['address','undefined'],'pixel_and_ownership_mismatches':0,'canonical_rom_unchanged':True,'rom_sha256':sha,'header_sha256':hashlib.sha256(HEADER.read_bytes()).hexdigest(),'limits':['Host proof of file decoding and exact static ownership only.','Runtime scrolling, ARM9 cost and memory admission remain unmeasured.','Corruption accepted when structurally valid is not an integrity/authenticity proof.']}
 (R/'research/rendering/premerged-block-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='maps'}))
if __name__=='__main__':main()
