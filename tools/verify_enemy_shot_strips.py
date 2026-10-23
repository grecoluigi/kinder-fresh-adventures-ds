#!/usr/bin/env python3
"""Enemy-shot GPU strip collection reproduces the CPU shot sampler exactly.

Builds ds/source/enemy_shots.c on the host with stub actor collectors, then
draws the same pool through the unchanged CPU path and the GPU strip path and
compares every one of the 49,152 composited pixels per viewport.
"""
import argparse,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "gpu_actors.h"
#include "enemy_shots.h"
#include <string.h>
static bool collect;static uint16_t *target;static unsigned sprites;
void gpu_actors_reset(void){}
bool gpu_actors_native(unsigned k,unsigned f,unsigned w,unsigned h,int l,int t){(void)k;(void)f;(void)w;(void)h;(void)l;(void)t;return false;}
void gpu_actors_ordinal(unsigned order){(void)order;}
void gpu_actors_unsupported(void){}
static uint16_t scratch[256*8];
uint16_t *gpu_actors_scratch(void){return scratch;}
const ActorAtlas *gpu_actors_frame(void){static ActorAtlas empty;return &empty;}
void gpu_actors_set_collect_only(bool enabled){collect=enabled;}
bool gpu_actors_collect_only(void){return collect;}
bool gpu_actors_reference(bool enabled){(void)enabled;return false;}
bool gpu_actors_reference_active(void){return false;}
void gpu_actors_sprite(const uint16_t *p,unsigned w,unsigned h,unsigned stride,int x,int y,unsigned kind){
 (void)kind;sprites++;
 for(unsigned r=0;r<h;r++)for(unsigned c=0;c<w;c++){uint16_t v=p[r*stride+c];int X=x+(int)c,Y=y+(int)r;
  if((v&0x8000)&&X>=0&&X<256&&Y>=0&&Y<192)target[Y*256+X]=v;}
}
#include <stdio.h>
#include <stdlib.h>
static uint32_t seed=2001;
static uint32_t next(void){seed=seed*1103515245u+12345u;return seed>>8;}
static const uint32_t callbacks[11][2]={{0x413b70,16},{0x41b770,25},{0x41a910,54},{0x40fd70,23},{0x40c2c0,87},{0x40d5c0,188},{0x413b70,53},{0x40cc60,50},{0x412dd0,0},{0x412dd0,1},{0x412dd0,2}};
static uint16_t cpu[256*192],gpu[256*192];
int main(int argc,char **argv){
 if(argc<2||!enemy_shot_graphics_open())return 2;
 unsigned cases=(unsigned)atoi(argv[1]);unsigned long long opaque=0,shots=0;
 for(unsigned c=0;c<cases;c++){
  enemy_shots_init();int cx=(int)(next()%6000),cy=(int)(next()%6000);unsigned n=1+next()%5;
  for(unsigned k=0;k<n;k++){
   EnemyShot shot;uint8_t raw[100];_Static_assert(sizeof(EnemyShot)==100,"record");memset(raw,0,100);
   float x=(float)cx+(float)(next()%120000)/100.0f-200.0f,y=(float)cy+(float)(next()%100000)/100.0f-200.0f;
   const uint32_t *pick=callbacks[next()%11];uint32_t one=1,mirror=next()%2?2:0;
   memcpy(raw+12,&x,4);memcpy(raw+16,&y,4);memcpy(raw+44,&pick[1],4);memcpy(raw+64,&one,4);memcpy(raw+80,&mirror,4);memcpy(raw+96,&pick[0],4);
   memcpy(&shot,raw,100);if(!enemy_shots_spawn_record(&shot))return 3;shots++;
  }
  memset(cpu,0,sizeof(cpu));memset(gpu,0,sizeof(gpu));
  collect=false;if(!enemy_shots_draw(cpu,cx,cy))return 4;
  collect=true;target=gpu;sprites=0;if(!enemy_shots_draw(gpu,cx,cy))return 5;
  for(unsigned i=0;i<256*192;i++){if(cpu[i]!=gpu[i]){printf("{\"mismatch_case\":%u,\"pixel\":%u}\n",c,i);return 1;}opaque+=(cpu[i]&0x8000)!=0;}
 }
 printf("{\"viewports\":%u,\"shots\":%llu,\"opaque_pixels\":%llu}\n",cases,shots,opaque);return 0;
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--cases',type=int,default=600);args=p.parse_args()
 work=Path(tempfile.mkdtemp());(work/'harness.c').write_text(HARNESS)
 exe=work/'harness'
 subprocess.run(['cc','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Wall','-Wextra','-Werror','-DKF_HOST_GPU_ACTORS','-I',str(ROOT/'ds/source'),'-DENEMY_SHOT_ROOT="'+str(ROOT/'ds/nitrofs/enemy_shots')+'"',str(work/'harness.c'),str(ROOT/'ds/source/enemy_shots.c'),str(ROOT/'ds/source/animation.c'),'-o',str(exe)],check=True)
 run=subprocess.run([str(exe),str(args.cases)],capture_output=True,text=True)
 if run.returncode:raise SystemExit('harness failed: '+run.stdout+run.stderr)
 stats=json.loads(run.stdout.strip().splitlines()[-1])
 result={**stats,'pixels_compared':stats['viewports']*256*192,'mismatches':0,'sanitizers':['address','undefined'],
         'scope':'Host strip-collection path versus unchanged CPU sampler; not DS GPU raster output.'}
 args.output.write_text(json.dumps(result,indent=1)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
