"""C geometry loader vs independent packed records; ASan/UBSan and malformed input stress."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,tempfile
from tile_storage import unlz
from build_offline_depth_packets import HEADER,ENTRY,unpack_rectangle
import numpy as np
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets-dir',type=Path,default=R/'research/rendering/offline-depth-assets');p.add_argument('--output',type=Path,default=R/'research/rendering/offline-depth-loader-verification.json');a=p.parse_args();assets=a.assets_dir.resolve()
manifest=json.loads((assets/'manifest.json').read_text())
with tempfile.TemporaryDirectory(prefix='kinder-depth-loader-') as td:
 t=Path(td);src=t/'verify.c'
 src.write_text('#include "'+str(R/'ds/source/depth_packets.h')+'"\n'+r'''
#include <assert.h>
#include <stdlib.h>
static struct {uint32_t before[8];DepthPackets packet;uint32_t after[8];} guarded;
static DepthRect expected[DEPTH_PACKET_CAPACITY];
static void guard(void){for(unsigned i=0;i<8;i++)assert(guarded.before[i]==0x12345678u&&guarded.after[i]==0x12345678u);}
int main(int argc,char **argv){
 assert(argc==6);DepthPackets *p=&guarded.packet;
 for(unsigned i=0;i<8;i++)guarded.before[i]=guarded.after[i]=0x12345678u;
 unsigned width=(unsigned)atoi(argv[2]),height=(unsigned)atoi(argv[3]);
 assert(!depth_packets_open(p,argv[1],width+1,height));
 assert(depth_packets_open(p,argv[1],width,height));FILE *reference=fopen(argv[4],"rb");assert(reference);
 unsigned packets=0,reads=0;
 for(unsigned row=0;row<p->rows;row++)for(unsigned col=0;col<p->columns;col++){
  uint32_t count;assert(fread(&count,4,1,reference)==1);int dx,dy;
  bool ok=depth_packets_load(p,(int)(col*256),(int)(row*192),&dx,&dy);assert(dx==0&&dy==0);
  if(count==UINT32_MAX){assert(!ok);continue;}
  assert(ok&&count==p->count&&count<=DEPTH_PACKET_CAPACITY);
  assert(fread(expected,sizeof(DepthRect),count,reference)==count);
  assert(!memcmp(expected,p->rectangles,count*sizeof(DepthRect)));
  unsigned before=p->read_calls;
  assert(depth_packets_load(p,(int)(col*256+255),(int)(row*192+191),&dx,&dy));assert(dx==255&&dy==191&&before==p->read_calls);
  assert(!memcmp(expected,p->rectangles,count*sizeof(DepthRect)));guard();packets++;
 }
 assert(fgetc(reference)==EOF);fclose(reference);reads=p->read_calls;
 int dx,dy;assert(!depth_packets_load(p,-1,0,&dx,&dy));assert(!depth_packets_load(p,(int)p->columns*256,0,&dx,&dy));
 depth_packets_close(p);guard();
 /* Mutate complete file bytes, preserving buffer guards on all success/error
  * paths. Some mutations are valid data; rejection is not assumed for those. */
 FILE *original=fopen(argv[1],"rb");assert(original);assert(!fseek(original,0,SEEK_END));long size=ftell(original);assert(size>0);rewind(original);
 uint8_t *saved=malloc((size_t)size),*changed=malloc((size_t)size);assert(saved&&changed);assert(fread(saved,1,(size_t)size,original)==(size_t)size);fclose(original);
 uint32_t seed=2001;unsigned opened=0,loaded=0;
 for(unsigned n=0;n<120;n++){
  memcpy(changed,saved,(size_t)size);
  for(unsigned k=0;k<1+n%8;k++){seed=seed*1664525u+1013904223u;unsigned at=seed%(unsigned)size;changed[at]^=(uint8_t)(1u<<(seed%8));}
  size_t bytes=(size_t)size;
  if(n%4==0){seed=seed*1664525u+1013904223u;bytes=seed%(unsigned)size;}
  FILE *f=fopen(argv[5],"wb");assert(f);assert(fwrite(changed,1,bytes,f)==bytes);assert(!fclose(f));
  if(depth_packets_open(p,argv[5],width,height)){
   opened++;
   for(unsigned row=0;row<p->rows;row++)for(unsigned col=0;col<p->columns;col++){
    bool ok=depth_packets_load(p,(int)(col*256),(int)(row*192),&dx,&dy);
    assert(p->count<=DEPTH_PACKET_CAPACITY);
    if(ok){loaded++;assert(p->available);for(unsigned i=0;i<p->count;i++){DepthRect q=p->rectangles[i];assert(q.left<q.right&&q.right<=512&&q.top<q.bottom&&q.bottom<=384&&q.order&&q.order<=255);}}
    else assert(!p->available);
   }
  }
  depth_packets_close(p);guard();
 }
 free(saved);free(changed);
 printf("{\"packets_exact\":%u,\"file_reads\":%u,\"loader_bytes\":%zu,\"mutated_files\":120,\"mutations_with_valid_headers\":%u,\"valid_mutated_packet_loads\":%u}\n",packets,reads,sizeof(*p),opened,loaded);return 0;
}
''')
 exe=t/'verify';subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(src),'-o',str(exe)],check=True)
 cases=[]
 for m in manifest['maps']:
  path=assets/(m['map']+'.mesh');blob=path.read_bytes();header=HEADER.unpack_from(blob);n=header[-1];expected=bytearray()
  for i in range(n):
   offset,size,count,flags=ENTRY.unpack_from(blob,HEADER.size+i*ENTRY.size)
   if flags==1:expected.extend(struct.pack('<I',0xffffffff));continue
   raw=unlz(blob[offset:offset+size]) if flags&2 else blob[offset:offset+size]
   if flags&4:raw=np.frombuffer(raw,dtype=np.uint8).reshape(6,count).T.tobytes()
   assert len(raw)==count*6
   expected.extend(struct.pack('<I',count))
   for at in range(0,len(raw),6):expected.extend(struct.pack('<5H',*unpack_rectangle(raw[at:at+6])))
  reference=t/'reference.bin';reference.write_bytes(expected)
  result=json.loads(subprocess.check_output([str(exe),str(path),str(m['width']),str(m['height']),str(reference),str(t/'mutated.mesh')],text=True))
  result['map']=m['map'];cases.append(result);print(json.dumps(result),flush=True)
 report={'scope':__doc__,'maps':cases,'packets_exact':sum(m['packets_exact'] for m in cases),'mutated_files':sum(m['mutated_files'] for m in cases),'sanitizers':['address','undefined'],'loader_header_sha256':hashlib.sha256((R/'ds/source/depth_packets.h').read_bytes()).hexdigest(),'asset_manifest_sha256':hashlib.sha256((assets/'manifest.json').read_bytes()).hexdigest(),'limits':['Host file I/O/decoder/coordinate expansion/cache behavior only; actual runtime scenery ownership and DS GPU tests remain.','Valid mutations are accepted only within structural/coordinate bounds; this is not a cryptographic integrity format.']}
 a.output.write_text(json.dumps(report,indent=2)+'\n')
