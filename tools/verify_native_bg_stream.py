"""Compare live streamed views against independent pixel references, with partial tile/map failures."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--prototype-dir',type=Path,default=R/'ds/source');p.add_argument('--sample-foreground',action='store_true');p.add_argument('--profile-io',action='store_true');p.add_argument('--service-probe',action='store_true');p.add_argument('--read-block',type=int,choices=[1024,2048,4096,8192]);p.add_argument('--read-cache',type=int,choices=[65536,131072,262144]);a=p.parse_args();headers=a.prototype_dir.resolve()
C=r'''
#include "native_bg_stream.h"
#include <assert.h>
#include <stdlib.h>
static NativeBGStream stream;
static uint8_t graphics[960][64];static uint16_t map[2048],expected[49152],front_expected[49152];
static unsigned old_checks,pixel_checks,tile_failures,map_failures,aborts,bridges;
static bool tile_fail,map_fail;
static void check(const uint16_t *reference){
 if(!stream.visible)return;
 for(unsigned y=0;y<192;y++)for(unsigned x=0;x<256;x++){
  unsigned wx=(unsigned)stream.front_x+x,wy=(unsigned)stream.front_y+y;uint16_t word=map[native_bg_map_at(wx/8,wy/8)];unsigned slot=word&1023;assert(slot<960);
  unsigned idx=graphics[slot][(wy%8)*8+wx%8];uint16_t color=idx?(uint16_t)(32768|(stream.assets.palette[(word>>12)*256+idx]&32767)):(uint16_t)(32768|((x/16)%32)|(((y/8)%32)<<5)|(5<<10));
  assert(color==reference[y*256+x]);pixel_checks++;
 }
 old_checks++;
}
static bool write_tile(void *context,unsigned slot,const uint16_t *pixels){
 (void)context;assert(slot&&slot<960&&!(stream.cache.entries[slot].flags&NATIVE_BG_FRONT));
 if(tile_fail){tile_fail=false;tile_failures++;memset(graphics[slot],0xfe,17);return false;}
 memcpy(graphics[slot],pixels,64);return true;
}
static bool write_map(void *context,unsigned at,uint16_t word){
 (void)context;assert(at<2048);
 if(map_fail){map_fail=false;map_failures++;map[at]=(uint16_t)(word^0xff);return false;}
 map[at]=word;return true;
}
static unsigned read_u32(FILE *f){uint8_t p[4];assert(fread(p,1,4,f)==4);return native_bg_u32(p);}
int main(int argc,char **argv){
 assert(argc==2);char file[4096],loaded[4096]={0};snprintf(file,sizeof(file),"%s/cases.bin",argv[1]);FILE *f=fopen(file,"rb");assert(f);unsigned n=read_u32(f),published=0;
 for(unsigned frame=0;frame<n;frame++){
  unsigned length=read_u32(f);char name[128];assert(length<sizeof(name)&&fread(name,1,length,f)==length);name[length]=0;
  unsigned x=read_u32(f),y=read_u32(f);assert(fread(expected,1,sizeof(expected),f)==sizeof(expected));assert(!strncmp(name,"nitro:/",7));snprintf(file,sizeof(file),"%s/%s",argv[1],name+7);
  bool cold=!stream.visible||strcmp(loaded,file)||(int)x<stream.front_x-16||(int)x>stream.front_x+16||(int)y<stream.front_y-16||(int)y>stream.front_y+16;
  if(cold){assert(native_bg_stream_close(&stream,false));assert(native_bg_stream_open(&stream,file,false));strcpy(loaded,file);memset(graphics,0,sizeof(graphics));memset(map,0,sizeof(map));}
  else{
   assert(!native_bg_stream_open(&stream,file,true)&&!native_bg_stream_close(&stream,true));check(front_expected);
   if(frame%7==0)tile_fail=true;if(frame%11==0)map_fail=true;
  }
  unsigned attempts=0;
  while(native_bg_stream_prepare(&stream,(int)x,(int)y,write_tile,write_map,NULL)!=NATIVE_BG_STREAM_READY){
   assert(++attempts<=2&&!stream.pending&&!stream.cache.state);check(front_expected);aborts++;
  }
  check(front_expected);
  if(frame%13==0){native_bg_stream_abort(&stream);check(front_expected);aborts++;assert(native_bg_stream_prepare(&stream,(int)x,(int)y,write_tile,write_map,NULL)==NATIVE_BG_STREAM_READY);}
  assert(native_bg_stream_prepare(&stream,(int)x,(int)y,write_tile,write_map,NULL)==NATIVE_BG_STREAM_BAD&&stream.pending);
  assert(native_bg_stream_publish(&stream)&&!native_bg_stream_publish(&stream));check(expected);memcpy(front_expected,expected,sizeof(expected));published++;
  assert(native_bg_stream_prepare(&stream,-1,(int)y,write_tile,write_map,NULL)==NATIVE_BG_STREAM_BAD);check(front_expected);
  int jump=stream.front_x+17;
  if((unsigned)jump<=stream.assets.width*8-256){assert(native_bg_stream_prepare(&stream,jump,stream.front_y,write_tile,write_map,NULL)==NATIVE_BG_STREAM_BRIDGE);check(front_expected);bridges++;}
 }
 assert(fgetc(f)==EOF);fclose(f);assert(native_bg_stream_close(&stream,false));assert(published==n&&tile_failures&&map_failures&&aborts&&bridges);
 printf("{\"views\":%u,\"frame_checks\":%u,\"pixel_checks\":%u,\"partial_tile_failures\":%u,\"partial_map_failures\":%u,\"aborts\":%u,\"large_jump_guards\":%u,\"stream_bytes\":%zu}\n",published,old_checks,pixel_checks,tile_failures,map_failures,aborts,bridges,sizeof(stream));
}
'''.replace('   if(frame%7==0)tile_fail=true;if(frame%11==0)map_fail=true;','   if(frame%7==0)tile_fail=true;\n   if(frame%11==0)map_fail=true;')
if a.sample_foreground:
 C=C.replace('#include "native_bg_stream.h"','#include "native_bg_sample.h"')
 C=C.replace('static uint8_t graphics[960][64];','static uint16_t graphics[960][32],sampled[49152+16],merged[49152+16];')
 C=C.replace('unsigned idx=graphics[slot][(wy%8)*8+wx%8];','unsigned idx=((uint8_t *)graphics[slot])[(wy%8)*8+wx%8];')
 C=C.replace('static unsigned old_checks,pixel_checks,tile_failures,map_failures,aborts,bridges;','static unsigned old_checks,pixel_checks,tile_failures,map_failures,aborts,bridges;\nstatic unsigned sampled_checks;')
 sample=r"""  memset(sampled,0x5a,sizeof(sampled));
  assert(!native_bg_sample_region(&stream,(uint16_t *)graphics,960*32,sampled,49151,256,0,0,256,192));
  assert(native_bg_sample_region(&stream,(uint16_t *)graphics,960*32,sampled,49152,256,-3,-2,259,194));
  for(unsigned yy=0;yy<192;yy++)for(unsigned xx=0;xx<256;xx++){
   uint16_t color=sampled[yy*256+xx];
   if(!color)color=(uint16_t)(32768|((xx/16)%32)|(((yy/8)%32)<<5)|(5<<10));
   assert(color==expected[yy*256+xx]);sampled_checks++;
  }
  for(unsigned i=49152;i<49152+16;i++)assert(sampled[i]==0x5a5a);
  memset(merged,0x5a,sizeof(merged));
  assert(native_bg_merge_region(&stream,(uint16_t *)graphics,960*32,merged,49152,256,0,0,256,192));
  for(unsigned i=0;i<49152;i++)assert(merged[i]==(sampled[i]?sampled[i]:0x5a5a));
  for(unsigned i=49152;i<49152+16;i++)assert(merged[i]==0x5a5a);
  memset(sampled,0x5a,sizeof(sampled));
  assert(native_bg_sample_region(&stream,(uint16_t *)graphics,960*32,sampled,49152,256,253,190,270,210));
  for(unsigned yy=0;yy<192;yy++)for(unsigned xx=0;xx<256;xx++)if(xx<253||yy<190)assert(sampled[yy*256+xx]==0x5a5a);
"""
 C=C.replace('  assert(native_bg_stream_prepare(&stream,(int)x,(int)y,write_tile,write_map,NULL)==NATIVE_BG_STREAM_BAD&&stream.pending);',sample+'\n  assert(native_bg_stream_prepare(&stream,(int)x,(int)y,write_tile,write_map,NULL)==NATIVE_BG_STREAM_BAD&&stream.pending);')
 C=C.replace('assert(published==n&&tile_failures', 'assert(sampled_checks==published*49152);assert(published==n&&tile_failures')

if a.profile_io:
 C=C.replace('static bool tile_fail,map_fail;', 'static bool tile_fail,map_fail;\nstatic unsigned warm_blocks,warm_bytes,total_blocks,total_bytes;')
 C='\n'.join(line for line in C.splitlines()if 'if(frame%7==0)tile_fail=true;'not in line and 'if(frame%11==0)map_fail=true;'not in line and 'if(frame%13==0){'not in line)+'\n'
 C=C.replace('  unsigned attempts=0;', '  unsigned before_blocks=stream.assets.block_fills,before_bytes=stream.assets.block_bytes;\n  unsigned attempts=0;')
 C=C.replace('  assert(native_bg_stream_publish(&stream)', '  unsigned blocks=stream.assets.block_fills-before_blocks,bytes=stream.assets.block_bytes-before_bytes;total_blocks+=blocks;total_bytes+=bytes;if(!cold){warm_blocks+=blocks;warm_bytes+=bytes;}\n  assert(native_bg_stream_publish(&stream)')
 C=C.replace('published==n&&tile_failures&&map_failures&&aborts&&bridges','published==n&&bridges')
 lines=C.splitlines()
 for i,line in enumerate(lines):
  if line.startswith(' printf('):
   lines[i]=r' printf("{\"views\":%u,\"pixel_checks\":%u,\"warm_block_fills\":%u,\"warm_block_bytes\":%u,\"all_block_fills\":%u,\"all_block_bytes\":%u,\"stream_bytes\":%zu}\n",published,pixel_checks,warm_blocks,warm_bytes,total_blocks,total_bytes,sizeof(stream));'
 C='\n'.join(lines)+'\n'

if a.service_probe:
 C='static void service_probe(void);\n#define NATIVE_BG_SERVICE() service_probe()\n'+C
 probe=r'''
static unsigned service_calls;
static void service_probe(void){
 service_calls++;if(!stream.visible)return;
 for(unsigned i=0;i<64;i++){
  unsigned x=(i*29u+service_calls*3u)%256u,y=(i*83u+service_calls)%192u;
  unsigned wx=(unsigned)stream.front_x+x,wy=(unsigned)stream.front_y+y;
  uint16_t word=map[native_bg_map_at(wx/8u,wy/8u)];unsigned slot=word&1023u;
  assert(slot<960&&(stream.cache.entries[slot].flags&NATIVE_BG_FRONT));
  unsigned index=((uint8_t *)graphics[slot])[(wy%8u)*8u+wx%8u];
  uint16_t color=index?(uint16_t)(32768u|(stream.assets.palette[(word>>12)*256u+index]&32767u)):(uint16_t)(32768u|((x/16u)%32u)|(((y/8u)%32u)<<5)|(5u<<10));
  assert(color==front_expected[y*256u+x]);
 }
}
'''
 C=C.replace('int main(int argc,char **argv){',probe+'\nint main(int argc,char **argv){')
 C=C.replace(' printf(', ' assert(service_calls);fprintf(stderr,"SERVICES:%u\\n",service_calls);\n printf(')
with tempfile.TemporaryDirectory(prefix='kinder-bg-stream-')as td:
 d=Path(td);source=d/'test.c';source.write_text(C);exe=d/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',*(['-DNATIVE_BG_READ_BYTES='+str(a.read_block)]if a.read_block else []),*(['-DNATIVE_BG_CACHE_BYTES='+str(a.read_cache)]if a.read_cache else []),'-I'+str(headers),'-I'+str(R/'ds/source'),str(source),'-o',str(exe)],check=True);r=subprocess.run([str(exe),str(a.fixture_dir.resolve()/'nitrofs')],capture_output=True,text=True)
 if r.returncode:print(r.stderr);raise RuntimeError('streamed asset/front proof failed')
 result=json.loads(r.stdout)
 if a.service_probe:
  import re
  result['service_calls']=int(re.search(r'SERVICES:(\d+)',r.stderr)[1])
result.update(scope=__doc__,sample_foreground=a.sample_foreground,io_profile=a.profile_io,read_block_bytes=a.read_block,read_cache_bytes=a.read_cache,sanitizers=['address','undefined'],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in headers.glob('*.h')},limits=['Host graphics/map model compares serialized independent pixel references; real GPU publication is tested separately.','Injected I/O/callback failures do not establish physical flashcart durability or timing.'])
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
