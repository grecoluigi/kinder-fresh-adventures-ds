"""Compare runtime C paged/tile decoding with independently expanded serialized assets under sanitizers."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,tempfile
from tile_storage import unlz
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--prototype-dir',type=Path,default=R/'ds/source');a=p.parse_args();study=a.study_dir.resolve();header=a.prototype_dir.resolve()/'native_bg_assets.h';files=sorted(study.glob('*.ntb'))
C=r'''
#include "HEADER"
#include <assert.h>
#include <stdlib.h>
static NativeBGAssets asset;
static unsigned read_u32(FILE *f){uint8_t b[4];assert(fread(b,1,4,f)==4);return native_bg_u32(b);}
int main(int argc,char **argv){
 assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);unsigned files=read_u32(f),tiles=0,pages=0,malformed=0;
 for(unsigned file=0;file<files;file++){
  unsigned length=read_u32(f);char path[4096];assert(length<sizeof(path)&&fread(path,1,length,f)==length);path[length]=0;assert(native_bg_open(&asset,path));
  unsigned n=read_u32(f),m=read_u32(f);assert(n==asset.tiles&&m==asset.pages);
  for(unsigned i=0;i<4096;i++){unsigned lo=fgetc(f),hi=fgetc(f);assert(lo<256&&hi<256&&asset.palette[i]==(lo|(hi<<8)));}
  uint8_t tile[64],expected[1024];uint32_t page[256];
  for(unsigned i=0;i<n;i++){assert(fread(expected,1,64,f)==64);assert(native_bg_tile(&asset,i,tile)&&!memcmp(tile,expected,64));tiles++;}
  for(unsigned i=0;i<m;i++){assert(fread(expected,1,1024,f)==1024);assert(native_bg_page(&asset,i,page));for(unsigned j=0;j<256;j++)assert(page[j]==native_bg_u32(expected+j*4));pages++;}
  assert(!native_bg_tile(&asset,n,tile)&&!native_bg_page(&asset,m,page));native_bg_close(&asset);assert(!native_bg_tile(&asset,0,tile)&&!native_bg_page(&asset,0,page));
 }
 unsigned bad_count=read_u32(f);
 for(unsigned i=0;i<bad_count;i++){
  unsigned length=read_u32(f);char path[4096];assert(length<sizeof(path)&&fread(path,1,length,f)==length);path[length]=0;
  unsigned kind=read_u32(f);bool opened=native_bg_open(&asset,path);
  if(!kind)assert(!opened);else{
   assert(opened);uint8_t tile[64];uint32_t page[256];
   if(kind==1)assert(!native_bg_tile(&asset,0,tile));
   else{for(unsigned j=0;j<256;j++)page[j]=0xdeadbeef;assert(!native_bg_page(&asset,0,page));for(unsigned j=0;j<256;j++)assert(page[j]==0xdeadbeef);}
  }
  native_bg_close(&asset);malformed++;
 }
 assert(fgetc(f)==EOF);fclose(f);printf("{\"files\":%u,\"tiles\":%u,\"pages\":%u,\"malformed_cases\":%u}\n",files,tiles,pages,malformed);
}
'''.replace('HEADER',str(header))
with tempfile.TemporaryDirectory(prefix='kinder-native-bg-assets-')as td:
 d=Path(td);trace=d/'trace';bad=[]
 with trace.open('wb')as f:
  f.write(struct.pack('<I',len(files)))
  for path in files:
   blob=path.read_bytes();_,version,w,h,n,g,m,pa,tr,pr,po,flags=struct.unpack_from('<4s11I',blob);assert version==1 and not flags
   name=str(path).encode();f.write(struct.pack('<I',len(name))+name+struct.pack('<II',n,m)+blob[pa:pa+8192])
   for table,count,size in [(tr,n,64),(pr,m,1024)]:
    for i in range(count):
     off,length=struct.unpack_from('<II',blob,table+i*8);raw=unlz(blob[po+off:po+off+length]);assert len(raw)==size;f.write(raw)
  # A small valid container permits header, range, codec and semantic mutations.
  from tile_storage import lz10
  tile=bytes(lz10(bytes(64)));page=bytes(lz10(bytes(1024)));po=8256
  base=struct.pack('<4s11I',b'KNTB',1,16,16,1,16,1,48,8240,8248,po,0)+bytes(8192)+struct.pack('<4I',0,len(tile),len(tile),len(page))+tile+page
  edits=[(0,b'BAD!'),(4,struct.pack('<I',2)),(8,bytes(4)),(12,bytes(4)),(16,bytes(4)),(20,struct.pack('<I',17)),(24,struct.pack('<I',2)),(28,struct.pack('<I',0xffffffff)),(32,struct.pack('<I',48)),(36,struct.pack('<I',0xfffffffe)),(40,struct.pack('<I',0xffffffff)),(44,struct.pack('<I',1)),(48,b'\x01\x00')]
  for offset,value in edits:
   v=bytearray(base);v[offset:offset+len(value)]=value;bad.append((bytes(v),0))
  bad.extend((base[:size],0)for size in [0,1,4,47,48,8192,8255])
  v=bytearray(base);struct.pack_into('<I',v,8240,0xffffffff);bad.append((bytes(v),1))
  v=bytearray(base);struct.pack_into('<I',v,8244,1157);bad.append((bytes(v),1))
  v=bytearray(base);v[po]=0;bad.append((bytes(v),1))
  invalid_page=bytearray(1024);struct.pack_into('<I',invalid_page,0,1);packed=bytes(lz10(bytes(invalid_page)));v=base[:po+len(tile)]+packed;v=bytearray(v);struct.pack_into('<I',v,8252,len(packed));bad.append((bytes(v),2))
  f.write(struct.pack('<I',len(bad)))
  for i,(blob,kind)in enumerate(bad):
   path=d/('bad'+str(i));path.write_bytes(blob);name=str(path).encode();f.write(struct.pack('<I',len(name))+name+struct.pack('<I',kind))
 source=d/'test.c';source.write_text(C);exe=d/'test';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ds/source'),str(source),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe),str(trace)],text=True,capture_output=True)
 if r.returncode:print(r.stderr);raise RuntimeError('native BG decoder proof failed')
 result=json.loads(r.stdout)
result.update(scope=__doc__,header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),sanitizers=['address','undefined'],asset_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in files},limits=['Runtime loader on host only; no VRAM upload, actual2D hardware display, actor occlusion or performance proof.','Independent serialized decode comparison does not establish original Windows color parity; study separately measures additional quantization.'])
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='asset_sha256'}))
