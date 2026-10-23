"""Decode staged DS FIFO commands independently and verify vertices/state/capacity under sanitizers."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();header=a.candidate_dir.resolve()/'geometry_batch.h'
source=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "HEADER"
static uint32_t seed=2001;
static unsigned random_u(void){seed=seed*1664525u+1013904223u;return seed;}
typedef struct {uint32_t format,palette;int16_t x[4],y[4],z;uint32_t uv[4];} Expected;
static Expected expected[768];static uint32_t data[1+15*768+2];
static unsigned decode(const uint32_t *list){
 unsigned end=list[0]+1,at=1,draw=0,vertex=0;uint32_t format=0,palette=0,uv=0;int16_t z=0;bool begun=false;
 while(at<end){uint32_t commands=list[at++];for(unsigned slot=0;slot<4;slot++){
  unsigned op=(commands>>(8*slot))&255,params;
  switch(op){case 0:params=0;break;case 0x2a:case 0x2b:case 0x40:case 0x22:case 0x25:params=1;break;case 0x23:params=2;break;case 0x41:params=0;break;default:abort();}
  assert(at+params<=end);uint32_t value=params?list[at]:0;
  if(op==0x2a)format=value;
  if(op==0x2b)palette=value;
  if(op==0x40){assert(!begun&&value==1);begun=true;vertex=0;}
  if(op==0x22)uv=value;
  if(op==0x23||op==0x25){
   assert(begun&&vertex<4&&draw<768);if(op==0x23)z=(int16_t)list[at+1];Expected *e=expected+draw;
   assert(format==e->format&&palette==e->palette&&z==e->z);
   assert((int16_t)value==e->x[vertex]&&(int16_t)(value>>16)==e->y[vertex]&&uv==e->uv[vertex]);vertex++;
  }
  if(op==0x41){assert(begun&&vertex==4);begun=false;draw++;}
  at+=params;
 }}assert(at==end&&!begun);return draw;
}
int main(void){
 unsigned total=0;GeometryBatch b;assert(!geometry_batch_begin(NULL,data,1));assert(!geometry_batch_begin(&b,NULL,1));assert(!geometry_batch_begin(&b,data,0));assert(!geometry_batch_quad(&b,0,0,0,0,0,0,0,0,0,0,0));
 for(unsigned round=0;round<256;round++){
  unsigned count=round==255?768:random_u()%769,capacity=1+count*15;
  for(unsigned i=0;i<sizeof(data)/sizeof(*data);i++)data[i]=0xdeadbeef;
  assert(geometry_batch_begin(&b,data+1,capacity));
  for(unsigned i=0;i<count;i++){
   int l=(int16_t)random_u(),r=(int16_t)random_u(),t=(int16_t)random_u(),bottom=(int16_t)random_u(),z=(int16_t)random_u();
   unsigned u=random_u()%257,v=random_u()%257,ur=random_u()%257,vb=random_u()%257;
   Expected *e=expected+i;e->format=random_u();e->palette=random_u();e->z=(int16_t)z;
   int xx[4]={l,l,r,r},yy[4]={t,bottom,bottom,t};unsigned uu[4]={u,u,ur,ur},vv[4]={v,vb,vb,v};
   for(unsigned j=0;j<4;j++){e->x[j]=(int16_t)xx[j];e->y[j]=(int16_t)yy[j];e->uv[j]=(uu[j]*16u&65535u)|(vv[j]*1048576u);}
   assert(geometry_batch_quad(&b,e->format,e->palette,l,t,r,bottom,z,u,v,ur,vb));
  }
  assert(!geometry_batch_quad(&b,0,0,0,0,0,0,0,0,0,0,0));assert(data[0]==0xdeadbeef&&data[capacity+1]==0xdeadbeef);
  assert(b.used==capacity&&decode(data+1)==count);total+=count;
 }
 printf("{\"batches\":256,\"quads\":%u,\"vertices\":%u,\"capacity_and_canaries\":true}\n",total,total*4);
}
'''.replace('HEADER',str(header))
with tempfile.TemporaryDirectory(prefix='kinder-geometry-proof-') as td:
 d=Path(td);(d/'proof.c').write_text(source);subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(d/'proof.c'),'-o',str(d/'proof')],check=True);r=subprocess.run([str(d/'proof')],capture_output=True,text=True,check=True);result=json.loads(r.stdout)
result.update(scope=__doc__,header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),sanitizers=['address','undefined'],limits=['Command interpretation/state equality only; actual DS GPU raster/VRAM/palette recovery and frame timing require integrated tests.'])
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
