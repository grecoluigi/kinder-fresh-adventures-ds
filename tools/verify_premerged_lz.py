"""Check BIOS preflight acceptance against bounded software decoding for real and mutated scenery streams."""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import hashlib,json,struct,subprocess,tempfile
R=Path(__file__).resolve().parents[1];H=R/'research/rendering/premerged-block-prototype/merged_scenery.h'
SOURCE=r'''
/* Exercise the actual __NDS__ dispatch without including ARM headers or
 * executing a SWI on the host. The stub independently uses bounded output. */
#define __NDS__
#define KINDER_TILE_CODEC_H
static void tile_lz_wram(const void *source,void *dest);
#include "merged_scenery.h"
#include <assert.h>
#include <stdlib.h>
static uint8_t original[9004],input[9004] __attribute__((aligned(4))),output[9024] __attribute__((aligned(4))),expected[9024];
static unsigned bios_calls,input_bytes,expected_size;
static void tile_lz_wram(const void *source,void *dest){
 bios_calls++;assert(smc_lz_software(source,input_bytes,dest,expected_size));
}
static uint32_t seed=2001;
static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static unsigned check(unsigned n,unsigned size){
 memset(output,0xa5,sizeof(output));
 bool scan=smc_lz_validate(input,n,size),decode=smc_lz_software(input,n,output,size);
 assert(scan==decode);
 for(unsigned i=size;i<sizeof(output);i++)assert(output[i]==0xa5);
 memcpy(expected,output,sizeof(output));memset(output,0xa5,sizeof(output));
 unsigned before=bios_calls;input_bytes=n;expected_size=size;
 assert(smc_lz(input,n,output,size)==scan);
 assert(bios_calls-before==(unsigned)(scan&&size));
 if(scan)assert(!memcmp(expected,output,sizeof(output)));
 else for(unsigned i=0;i<sizeof(output);i++)assert(output[i]==0xa5);
 return scan;
}
int main(int argc,char **argv){
 assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);uint8_t header[8];unsigned streams=0,accepted=0,rejected=0;
 while(fread(header,1,8,f)==8){
  unsigned n=smc_u32(header),size=smc_u32(header+4);assert(n<=9000&&size<=8900&&size);
  assert(fread(original,1,n,f)==n);memcpy(input,original,n);assert(check(n,size));streams++;
  for(unsigned trial=0;trial<12;trial++){
   memcpy(input,original,n);unsigned count=n,want=size;
   if(trial==0)count=rnd()%n;
   else if(trial==1)want=size?size-1:1;
   else if(trial==2)count=3;
   else for(unsigned i=0;i<1+trial%4;i++)input[rnd()%n]^=(uint8_t)(1u<<(rnd()%8));
   if(check(count,want))accepted++;else rejected++;
  }
 }
 assert(feof(f));fclose(f);assert(streams&&accepted&&rejected);
 /* Explicit malformed backreference before any output, and trailing data. */
 const uint8_t bad[]={16,3,0,0,128,0,0};memcpy(input,bad,sizeof(bad));assert(!check(sizeof(bad),3));
 const uint8_t trailing[]={16,1,0,0,0,42,99};memcpy(input,trailing,sizeof(trailing));assert(!check(sizeof(trailing),1));
 printf("{\"valid_streams\":%u,\"mutation_trials\":%u,\"mutations_accepted\":%u,\"mutations_rejected\":%u,\"acceptance_mismatches\":0,\"output_guard_failures\":0}\n",streams,accepted+rejected,accepted,rejected);
 return 0;
}
'''
def main():
 rom=resolve_rom(R / 'ds');sha=hashlib.sha256(rom.read_bytes()).hexdigest();streams={}
 for p in (R/'research/rendering/premerged-block-assets').glob('*.smc'):
  data=p.read_bytes();blocks=struct.unpack_from('<I',data,16)[0]
  for i in range(blocks):
   at,colors,spans,words,flags=struct.unpack_from('<I4H',data,64+12*i);color=data[at:at+colors];bits,mode,n=struct.unpack_from('<BBH',color)
   if not mode:
    start=4 if bits==16 else 4+((n*2+3)&~3);stream=color[start:];streams[stream]=8192 if bits==16 else 4096*bits//8
   if flags:
    start=at+((colors+3)&~3);streams[data[start:start+spans]]=words*2
 with tempfile.TemporaryDirectory(prefix='kinder-lz-proof-') as td:
  t=Path(td);source=t/'test.c';source.write_text(SOURCE);corpus=t/'streams.bin'
  with corpus.open('wb') as f:
   for data,size in sorted(streams.items()):f.write(struct.pack('<II',len(data),size)+data)
  exe=t/'test';subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(H.parent),'-I'+str(R/'ds/source'),str(source),'-o',str(exe)],check=True)
  report=json.loads(subprocess.check_output([str(exe),str(corpus)],text=True))
 assert hashlib.sha256(rom.read_bytes()).hexdigest()==sha
 report.update(scope=__doc__,sanitizers=['address','undefined'],bios_dispatch_stubbed=True,invalid_streams_reach_bios_stub=False,header_sha256=hashlib.sha256(H.read_bytes()).hexdigest(),rom_unchanged=True,rom_sha256=sha,limits=['Validates actual aligned __NDS__ dispatch using a software stub; BIOS SWI execution remains untested.','No emulator or physical DS timing claim.'])
 (R/'research/rendering/premerged-lz-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
