"""Verify GPU page storage, runtime catalogs and every source actor raster."""
from pathlib import Path
import argparse,ctypes as C,hashlib,json,struct,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
#include "native_catalog.h"
#include "sprite_codec.h"
static NativeStream stream;
static NativeCatalog catalog;
static uint32_t base;
static bool read_catalog(void *unused,uint32_t at,void *out,uint32_t n){(void)unused;return native_stream_read(&stream,base+at,out,n);}
int open_pack(const char *path){
 uint8_t footer[32];
 if(!native_stream_open(&stream,path)||stream.bytes<64||!native_stream_read(&stream,stream.bytes-32,footer,32))return 0;
 base=native_stream_u32(footer+8);unsigned bytes=native_stream_u32(footer+12);
 if(memcmp(footer,"KGC1",4)||native_stream_u32(footer+4)!=1||native_stream_u32(footer+16)!=stream.pages||native_stream_u32(footer+20)!=stream.bytes||native_stream_u32(footer+24)||native_stream_u32(footer+28)||base>stream.bytes-32||bytes!=stream.bytes-32-base)return 0;
 return native_catalog_init(&catalog,read_catalog,0,bytes,stream.pages);
}
void close_pack(void){native_stream_close(&stream);memset(&catalog,0,sizeof(catalog));}
unsigned page_count(void){return stream.pages;}
unsigned frame_count(unsigned kind){return kind<3?catalog.kind_count[kind]:0;}
int find_frame(unsigned kind,unsigned id,uint32_t *out){
 NativeCatalogFrame f;if(!native_catalog_find(&catalog,kind,id,&f))return 0;
 out[0]=f.width;out[1]=f.height;out[2]=f.count;return 1;
}
int frame_refs(unsigned kind,unsigned id,unsigned first,unsigned count,uint32_t *out){
 NativeCatalogFrame f;NativeCatalogRef refs[NATIVE_CATALOG_BATCH];
 if(!native_catalog_find(&catalog,kind,id,&f)||!native_catalog_refs(&catalog,&f,first,count,refs))return 0;
 for(unsigned i=0;i<count;i++){out[i*5]=refs[i].page;out[i*5+1]=refs[i].x;out[i*5+2]=refs[i].y;out[i*5+3]=refs[i].width;out[i*5+4]=refs[i].height;}
 return 1;
}
int read_page(unsigned index,uint16_t *out,unsigned capacity,uint32_t *meta){
 struct {uint32_t before[4];uint8_t data[4096];uint32_t after[4];} tex;
 struct {uint32_t before[4];uint8_t data[512];uint32_t after[4];} pal;
 memset(&tex,0xA5,sizeof(tex));memset(&pal,0xA5,sizeof(pal));NativeStreamPage p;
 if(!native_stream_page(&stream,index,tex.data,sizeof(tex.data),pal.data,sizeof(pal.data),&p))return 0;
 for(unsigned i=0;i<4;i++)if(tex.before[i]!=0xA5A5A5A5||tex.after[i]!=0xA5A5A5A5||pal.before[i]!=0xA5A5A5A5||pal.after[i]!=0xA5A5A5A5)return 0;
 unsigned n=p.width*p.height;if(capacity<n)return 0;
 for(unsigned i=0;i<n;i++){
  if(p.bits==16)out[i]=native_stream_u16(tex.data+i*2);
  else{unsigned value=p.bits==8?tex.data[i]:(tex.data[i/2]>>((i&1)*4))&15;out[i]=value?(native_stream_u16(pal.data+value*2)|32768):0;}
 }
 meta[0]=p.width;meta[1]=p.height;meta[2]=p.bits;return 1;
}
int decode_source(const uint8_t*p,size_t bytes,uint16_t*out,unsigned pixels){return sprite_codec_decode(p,bytes,out,pixels);}
'''

def source_rasters(players,enemies,pickups):
 for character,name in enumerate(('pinguin','milchschnitte')):
  blob=(players/(name+'.frames')).read_bytes();assert blob[:4]==b'KFP3';n=struct.unpack_from('<I',blob,4)[0]
  for frame in range(n):
   for facing in range(2):yield 0,(frame*2+character)*2+facing,blob,8+n*40,16+frame*40+facing*16
 for path,magic,stride,resource_stride,descriptor,kind in ((enemies,b'KFES',40,84,8,1),(pickups,b'KFSP',48,12,16,2)):
  blob=path.read_bytes();assert blob[:4]==magic;nr,n,total=struct.unpack_from('<HHI',blob,4);frames=12+nr*resource_stride;base=frames+n*stride;assert base+total==len(blob)
  for frame in range(n):
   for facing in range(2):yield kind,frame*2+facing,blob,base,frames+frame*stride+descriptor+facing*16

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('pack','players','enemies','pickups','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--source-dir',type=Path,default=ROOT/'ds/source',help='Runtime headers matching the pack being verified')
 a=p.parse_args();pack=a.pack.read_bytes();pages={};source_ids=set();references=pixels=0;formats={}
 with tempfile.TemporaryDirectory(prefix='kinder-gpu-pack-')as td:
  work=Path(td);source=work/'check.c';library=work/'check.dylib';source.write_text(CODE)
  subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-dynamiclib','-I'+str(a.source_dir),str(source),'-o',str(library)],check=True)
  c=C.CDLL(str(library));c.open_pack.argtypes=[C.c_char_p];c.open_pack.restype=C.c_int;c.page_count.restype=C.c_uint;c.frame_count.argtypes=[C.c_uint];c.frame_count.restype=C.c_uint
  c.read_page.argtypes=[C.c_uint,C.c_void_p,C.c_uint,C.c_void_p];c.find_frame.argtypes=[C.c_uint,C.c_uint,C.c_void_p];c.frame_refs.argtypes=[C.c_uint,C.c_uint,C.c_uint,C.c_uint,C.c_void_p];c.decode_source.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint]
  assert c.open_pack(str(a.pack).encode())
  try:
   for index in range(c.page_count()):
    guard=np.full(2048+32,0x1357,dtype='<u2');meta=(C.c_uint32*3)()
    assert c.read_page(index,guard[16:].ctypes.data,2048,meta)
    w,h,bits=meta;assert np.all(guard[:16]==0x1357)and np.all(guard[16+w*h:]==0x1357)
    pages[index]=guard[16:16+w*h].copy().reshape(h,w);formats[bits]=formats.get(bits,0)+1
   info=(C.c_uint32*3)();scratch=np.zeros(2048,dtype='<u2')
   assert not c.read_page(c.page_count(),scratch.ctypes.data,2048,info)
   assert not c.find_frame(3,0,info)and not c.find_frame(0,0xffffffff,info)
   for kind,id,blob,base,record in source_rasters(a.players,a.enemies,a.pickups):
    assert(kind,id)not in source_ids;source_ids.add((kind,id))
    offset,size,w,h,_,_=struct.unpack_from('<IIHHhh',blob,record);packet=C.create_string_buffer(blob[base+offset:base+offset+size]);guard=np.full(w*h+32,0x1357,dtype='<u2')
    assert c.decode_source(packet,size,guard[16:].ctypes.data,w*h)
    assert np.all(guard[:16]==0x1357)and np.all(guard[-16:]==0x1357)
    expected=guard[16:-16].reshape(h,w);expected=np.where(expected&32768,expected,0)
    assert c.find_frame(kind,id,info)and tuple(info[:2])==(w,h)
    count=info[2];restored=np.zeros((h,w),dtype='<u2')
    for first in range(0,count,32):
     n=min(32,count-first);refs=(C.c_uint32*(5*n))();assert c.frame_refs(kind,id,first,n,refs)
     for i in range(n):
      page,x,y,rw,rh=refs[i*5:i*5+5];image=pages[page&0x7fffffff];assert rw<=image.shape[1]and rh<=image.shape[0]
      crop=image[:rh,:rw]
      restored[y:y+rh,x:x+rw]=crop[:,::-1]if page>>31 else crop;references+=1
    assert np.array_equal(expected,restored),(kind,id)
    assert not c.frame_refs(kind,id,count,1,(C.c_uint32*5)())
    pixels+=w*h
   catalog_ids={(kind,id)for kind in range(3)for id in range(c.frame_count(kind))if c.find_frame(kind,id,info)}
   assert catalog_ids==source_ids
  finally:c.close_pack()
 report={'scope':__doc__,'pages':len(pages),'formats':formats,'source_rasters':len(source_ids),'page_references':references,'source_pixels_reconstructed_exactly':pixels,'runtime_CRC_reads_passed':True,'guards_intact':True,'missing_frames_rejected':True,'pack_bytes':len(pack),'pack_sha256':hashlib.sha256(pack).hexdigest(),'limits':['Storage, catalogs and source raster equality only; physical VRAM publication, frame timing and full gameplay remain separate.']}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
