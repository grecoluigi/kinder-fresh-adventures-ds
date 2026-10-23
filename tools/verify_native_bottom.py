"""Verify bounded native bottom loader, HUD semantics, pixel output and rejected loads."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,tempfile
import numpy as np
from stage_native_bottom_assets import decode_patches
from tile_storage import unlz,lz10
R=Path(__file__).resolve().parents[1]
C=r'''
#include "native_bottom.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static NativeBottom hud;
static unsigned char expected[49152],guarded[49184];
static unsigned hash(const unsigned char *p){unsigned h=2166136261u;for(unsigned i=0;i<49152;i++)h=(h^p[i])*16777619u;return h;}
int main(int argc,char **argv){
 assert(argc==4);assert(native_bottom_open(&hud,argv[1]));FILE *f=fopen(argv[2],"rb");assert(f);unsigned n;
 assert(fread(&n,4,1,f)==1);unsigned previous=99;
 for(unsigned i=0;i<n;i++){
  HudState state;assert(fread(&state,1,44,f)==44&&fread(expected,1,49152,f)==49152);
  unsigned world=(unsigned)state.world%4;
  if(world!=previous){char path[512];snprintf(path,sizeof(path),"%s/%u.nbh",argv[3],world);assert(native_bottom_background(&hud,path,world));previous=world;}
  memset(guarded,0x69,sizeof(guarded));assert(native_bottom_draw(&hud,guarded+16,49152,&state));
  assert(!memcmp(guarded+16,expected,49152));
  for(unsigned j=0;j<16;j++)assert(guarded[j]==0x69&&guarded[49168+j]==0x69);
  unsigned before=hash(guarded+16);assert(!native_bottom_draw(&hud,guarded+16,49151,&state));assert(hash(guarded+16)==before);
 }
 assert(fgetc(f)==EOF);fclose(f);
 unsigned touch=0;
 for(int y=-1;y<=192;y++)for(int x=-1;x<=256;x++){
  bool expected_hit=false;
  if(x>=0&&x<256&&y>=0&&y<192)for(unsigned i=0;i<hud.count;i++){
   NativeBottomPatch p=hud.patches[i];if(p.resource==11&&x>=p.x&&y>=p.y&&x<p.x+p.width&&y<p.y+p.height)expected_hit=true;
  }
  assert(native_bottom_switch_hit(&hud,x,y)==expected_hit);touch++;
 }
 char path[512];snprintf(path,sizeof(path),"%s/bad_counts.bin",argv[3]);f=fopen(path,"rb");assert(f);unsigned bad[2];assert(fread(bad,4,2,f)==2);fclose(f);
 HudState state={.score=1234,.health=100,.ammo=3,.world=3};assert(native_bottom_draw(&hud,guarded+16,49152,&state));unsigned baseline=hash(guarded+16);
 unsigned char *data=hud.data,*background=hud.background;uint16_t pal[256];memcpy(pal,hud.palette,512);
 for(unsigned kind=0;kind<2;kind++)for(unsigned i=0;i<bad[kind];i++){
  snprintf(path,sizeof(path),"%s/bad-%u-%u.bin",argv[3],kind,i);
  bool accepted=kind?native_bottom_background(&hud,path,3):native_bottom_open(&hud,path);if(accepted)fprintf(stderr,"Accepted invalid %u/%u\n",kind,i);assert(!accepted);
  assert(hud.data==data&&hud.background==background&&!memcmp(pal,hud.palette,512));
  assert(native_bottom_draw(&hud,guarded+16,49152,&state));assert(hash(guarded+16)==baseline);
 }
 state.world=2;assert(!native_bottom_draw(&hud,guarded+16,49152,&state));assert(hash(guarded+16)==baseline);
 native_bottom_close(&hud);native_bottom_close(&hud);assert(!native_bottom_draw(&hud,guarded+16,49152,&state));
 printf("{\"cases\":%u,\"pixel_checks\":%u,\"touch_checks\":%u,\"bad_hud\":%u,\"bad_background\":%u,\"state_preserved_after_rejections\":true}\n",n,n*49152,touch,bad[0],bad[1]);
}
'''
def compose(items,back,state):
 score,health,ammo,actor,shot,boss,energy,world,*letters=state
 out=back.copy();lookup={(r,f):(a,x,y)for a,x,y,r,f in items}
 def patch(resource,frame,x=None,y=None):
  p=lookup.get((resource,frame))
  if p is None:return
  a,px,py=p;x=px if x is None else x;y=py if y is None else y
  left=max(0,x);right=min(256,x+a.shape[1]);top=max(0,y);bottom=min(192,y+a.shape[0])
  if left>=right or top>=bottom:return
  src=a[top-y:bottom-y,left-x:right-x];dst=out[top:bottom,left:right];mask=src!=0;dst[mask]=src[mask]
 patch(15,0);patch(0,0)
 text=[int(d)for d in str(score)if d.isdigit()]
 resource=next(r for r in(17,16,14)if sum(lookup[(r,d)][0].shape[1]for d in text)<=128)
 x=124
 for d in text:patch(resource,d,x,33);x+=lookup[(resource,d)][0].shape[1]
 if boss>0:
  patch(1,0)
  if energy>=0:patch(12,energy)
  patch(13,world%4)
 else:
  for i,value in enumerate(letters):patch(2+i,int(value>0))
 if health>0:patch(8,min(4,(health-1)//20))
 if ammo>0:patch(10 if shot>0 else 9,ammo-1)
 patch(11,actor)
 return out

def replace(blob,at,fmt,value):
 b=bytearray(blob);struct.pack_into(fmt,b,at,value);return bytes(b)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--prototype-dir',type=Path,default=R/'ds/source');p.add_argument('--assets-dir',type=Path,required=True);a=p.parse_args();items=decode_patches((a.assets_dir/'hud.nhp').read_bytes())
 with tempfile.TemporaryDirectory(prefix='kinder-indexed-hud-')as td:
  t=Path(td);rows=[]
  for world,name in enumerate(('jungle','ice','factory','fantasy')):
   blob=(a.assets_dir/(name+'.nbh')).read_bytes();(t/(str(world)+'.nbh')).write_bytes(blob);back=np.frombuffer(unlz(blob[524:]),dtype='u1').reshape(192,256)
   for arena in(0,4):
    for i,score in enumerate((0,1,99999,888888,111111,88888888,1234567890,2147483647,-2147483648)):
     for boss in(0,1):
      state=(score,i*13,i+1,i%2,i%2,boss,i-1,world+arena,*[int(j%2==i%2)for j in range(6)])
      rows.append((state,compose(items,back,state)))
  with(t/'cases.bin').open('wb')as f:
   f.write(struct.pack('<I',len(rows)))
   for state,expected in rows:f.write(struct.pack('<8i6h',*state)+expected.tobytes())
  hud=(a.assets_dir/'hud.nhp').read_bytes();base=16+len(items)*16
  bad_hud=[b'',hud[:15],hud[:-1],hud+b'x',b'BAD!'+hud[4:],replace(hud,4,'<I',2),replace(hud,8,'<I',129),replace(hud,12,'<I',131073),replace(hud,16,'<I',1),replace(hud,20,'<H',0),replace(hud,20,'<H',257),replace(hud,base+2,'<H',65535)]
  # Locate actual payload indices/terminators rather than guessing run offsets.
  off=base
  while struct.unpack_from('<H',hud,off+2)[0]==0:off+=4
  bad_hud +=[replace(hud,off+4,'<B',0),replace(hud,off+4,'<B',128)]
  at=base
  while True:
   run=struct.unpack_from('<H',hud,at+2)[0]
   if not run:break
   at+=4+run
  bad_hud.append(replace(hud,at,'<H',1))
  b=(t/'3.nbh').read_bytes()
  bad_bg=[b'',b[:523],b[:-1],b+b'x',b'BAD!'+b[4:],replace(b,4,'<H',255),replace(b,8,'<I',65537),replace(b,12,'<H',32768),replace(b,12+128*2,'<H',0),replace(b,12+2,'<H',0),replace(b,524,'<B',0),replace(b,525,'<B',1)]
  for packed in[bytes(lz10(bytes(49152))),bytes.fromhex('1000c000800000')]:bad_bg.append(b[:8]+struct.pack('<I',len(packed))+b[12:524]+packed)
  assert all(v!=hud for v in bad_hud)and all(v!=b for v in bad_bg)
  for kind,values in enumerate((bad_hud,bad_bg)):
   for i,value in enumerate(values):(t/f'bad-{kind}-{i}.bin').write_bytes(value)
  (t/'bad_counts.bin').write_bytes(struct.pack('<II',len(bad_hud),len(bad_bg)));(t/'test.c').write_text(C)
  cmd=['cc','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Wall','-Wextra','-Werror','-I'+str(a.prototype_dir),'-I'+str(R/'ds/source'),str(a.prototype_dir/'native_bottom.c'),str(R/'ds/source/hud.c'),str(t/'test.c'),'-o',str(t/'test')]
  subprocess.run(cmd,check=True)
  result=json.loads(subprocess.check_output([str(t/'test'),str(a.assets_dir/'hud.nhp'),str(t/'cases.bin'),str(t)],text=True))
 result.update(scope=__doc__,sanitizers=['address','undefined'],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in a.prototype_dir.glob('native_bottom.*')},limits=['Host tests, not DS visible output or VRAM publication.','Expected indexed colors come from staged assets; quantization quality audited separately.'])
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
