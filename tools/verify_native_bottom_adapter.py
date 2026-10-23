"""Check full-game HUD adapter in indexed and in-place RGB bitmap modes."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
C=r'''
#include "hud_native_bridge.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned char expected[49152];
static uint16_t guarded[49168];
int main(int argc,char **argv){
 assert(argc==3&&hud_open());FILE *f=fopen(argv[1],"rb");assert(f);unsigned count,world=99;uint16_t palette[256];
 assert(fread(&count,4,1,f)==1);
 for(unsigned i=0;i<count;i++){
  HudState state;assert(fread(&state,1,44,f)==44&&fread(expected,1,49152,f)==49152);
  unsigned next=(unsigned)state.world%4;
  if(next!=world){
   char path[512];snprintf(path,sizeof(path),"%s/%u.nbh",argv[2],next);FILE *pal=fopen(path,"rb");assert(pal&&fseek(pal,12,SEEK_SET)==0&&fread(palette,2,256,pal)==256);fclose(pal);
   assert(hud_set_world_background(next));world=next;
  }
  for(unsigned mode=0;mode<2;mode++){
   for(unsigned j=0;j<49168;j++)guarded[j]=0x6969;
   hud_native_enable(mode!=0);hud_draw_bottom(guarded+8,&state);
   if(mode){
    assert(!memcmp(guarded+8,expected,49152));
    const unsigned char *bytes=(const unsigned char *)(guarded+8);for(unsigned j=49152;j<98304;j++)assert(bytes[j]==0x69);
   }else for(unsigned j=0;j<49152;j++)assert(guarded[8+j]==palette[expected[j]]);
   for(unsigned j=0;j<8;j++)assert(guarded[j]==0x6969&&guarded[49160+j]==0x6969);
  }
 }
 assert(fgetc(f)==EOF);fclose(f);hud_close();hud_close();
 printf("{\"states\":%u,\"backend_cases\":%u,\"pixel_checks\":%u,\"guards_intact\":true,\"in_place_rgb_expansion\":true}\n",count,count*2,count*2*49152);
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();candidate=a.candidate.resolve();fixture=R/'research/rendering/native-bottom-hardware-fixture-v3/nitrofs';assets=candidate/'nitrofs/native_bottom'
 with tempfile.TemporaryDirectory(prefix='kinder-bottom-adapter-')as td:
  t=Path(td);(t/'test.c').write_text(C)
  cmd=['cc','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Wall','-Wextra','-Werror','-I'+str(candidate/'source'),'-DHUD_NATIVE_ROOT="'+str(assets)+'"',str(candidate/'source/hud.c'),str(candidate/'source/native_bottom.c'),str(t/'test.c'),'-o',str(t/'test')];subprocess.run(cmd,check=True)
  report=json.loads(subprocess.check_output([str(t/'test'),str(fixture/'cases.bin'),str(fixture)],text=True))
 report.update(scope=__doc__,sanitizers=['address','undefined'],source_sha256={n:hashlib.sha256((candidate/'source'/n).read_bytes()).hexdigest()for n in('hud.c','native_bottom.c','hud_native_bridge.h')},limits=['Host checks both adapters; does not prove GPU initialization failure recovery on the DS.'])
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
