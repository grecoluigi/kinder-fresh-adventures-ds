"""Compile the runtime GPU actor bundle from complete regenerated actor banks.

Uses exact 4/8-bit palettes or RGB555 pages, a dense frame catalog, and the
current uncompressed texture/palette-bank layout. No route observations needed.
"""
from pathlib import Path
import argparse,ctypes,hashlib,json,struct,subprocess,tempfile
import numpy as np
from native_page_encoder import NativePageEncoder,sha
from pack_native_actor_pages import build as pack_pages
from native_catalog_index import dense_index
from share_actor_facings import share_facings

R=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--players',type=Path,required=True)
 parser.add_argument('--enemies',type=Path,required=True,help='Regenerated enemies.frames')
 parser.add_argument('--pickups',type=Path,required=True,help='Regenerated pickups.frames')
 parser.add_argument('--output-dir',type=Path,required=True)
 parser.add_argument('--keep-loose-pages',action='store_true')
 args=parser.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
 encoder=NativePageEncoder(out,strip_height=32,local_palettes=True)
 bindings={};sources=[];counts={};pixels=0

 with tempfile.TemporaryDirectory(prefix='kinder-native-catalog-') as directory:
  t=Path(directory);src=t/'decode.c';lib=t/'decode.dylib'
  src.write_text('#include "sprite_codec.h"\nint decode(const uint8_t*p,size_t n,uint16_t*d,unsigned count){return sprite_codec_decode(p,n,d,count);}\n')
  subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'ds/source'),str(src),'-o',str(lib)],check=True)
  codec=ctypes.CDLL(str(lib));codec.decode.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_uint]

  def convert(blob,base,record,kind,frame_id):
   nonlocal pixels
   offset,size,w,h,x,y=struct.unpack_from('<IIHHhh',blob,record)
   assert w and h and base+offset+size<=len(blob) and size>=4
   packet=ctypes.create_string_buffer(blob[base+offset:base+offset+size])
   guard=np.full(w*h+32,0x1234,dtype='<u2')
   assert codec.decode(packet,size,guard[16:].ctypes.data,w*h),(kind,frame_id)
   assert np.all(guard[:16]==0x1234) and np.all(guard[-16:]==0x1234)
   image=guard[16:-16].reshape(h,w);normalized=np.where(image&32768,image,0).astype('<u2')
   pages=encoder.encode(image)
   # Reconstruct the entire source raster, including transparent gaps and edges.
   reconstructed=np.zeros_like(normalized)
   for p in pages:
    if p.bits==16:decoded=np.frombuffer(p.texels,dtype='<u2').reshape(p.texture_height,p.width)
    else:
     raw=np.frombuffer(p.texels,dtype=np.uint8)
     indices=raw if p.bits==8 else np.stack((raw&15,raw>>4),axis=1).ravel()
     decoded=np.frombuffer(p.palette,dtype='<u2')[indices].copy()
     decoded[indices!=0]|=32768;decoded=decoded.reshape(p.texture_height,p.width)
    reconstructed[p.source_y:p.source_y+p.height,p.source_x:p.source_x+p.draw_width]=decoded[:p.height,:p.draw_width]
   assert np.array_equal(reconstructed,normalized),(kind,frame_id,'reconstruction')
   binding={'kind':kind,'frame_id':frame_id,'width':w,'height':h,'source_normalized_sha256':sha(normalized.tobytes()),'pages':[{'key':p.key,'source_x':p.source_x,'source_y':p.source_y,'draw_width':p.draw_width,'draw_height':p.height}for p in pages]}
   key=f'{kind}:{frame_id}';assert key not in bindings;bindings[key]=binding
   counts[kind]=counts.get(kind,0)+1;pixels+=w*h

  for character,name in enumerate(('pinguin','milchschnitte')):
   path=args.players/f'{name}.frames';blob=path.read_bytes()
   assert blob[:4]==b'KFP3';n=struct.unpack_from('<I',blob,4)[0];base=8+n*40
   sources.append({'file':str(path.resolve()),'sha256':sha(blob),'bytes':len(blob)})
   for frame in range(n):
    for facing in range(2):convert(blob,base,8+frame*40+8+facing*16,0,(frame*2+character)*2+facing)
  for name,magic,stride,resource_stride,raster_offset,kind in (
   ('enemies',b'KFES',40,84,8,1),('pickups',b'KFSP',48,12,16,2)):
   path=args.enemies if name=='enemies' else args.pickups;blob=path.read_bytes();assert blob[:4]==magic
   resources,n,payload=struct.unpack_from('<HHI',blob,4);frames=12+resources*resource_stride;base=frames+n*stride
   assert base+payload==len(blob)
   sources.append({'file':str(path.resolve()),'sha256':sha(blob),'bytes':len(blob)})
   for frame in range(n):
    for facing in range(2):convert(blob,base,frames+frame*stride+raster_offset+facing*16,kind,frame*2+facing)

 manifest={'scope':__doc__,'bindings':{'global':bindings},'pages':list(encoder.artifacts.values()),'sources':sources,'raster_counts':counts,'pixels_checked':pixels,'strip_height':32,'trim_rows':False,'adaptive_orientation':False,'local_palettes':True,'limits':['Four complete actor banks; transient projectiles/effects and scenery use separate runtime paths.','Asset compilation only; GPU presentation and physical performance require separate checks.']}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 pack_pages(out,out/'pack.json')
 blob=bytearray((out/'pages.gpu').read_bytes());blob.extend(bytes(-len(blob)%32))
 index=dense_index((out/'global.gpi').read_bytes(),len(encoder.artifacts));index_at=len(blob);blob.extend(index)
 total=len(blob)+32;blob.extend(struct.pack('<4s7I',b'KGC1',1,index_at,len(index),len(encoder.artifacts),total,0,0));struct.pack_into('<I',blob,20,total)
 final,sharing=share_facings(bytes(blob))
 storage={'palette_bank':True,'compress_textures':False,'texture_payloads_deduplicated':False,'mirrored_facing_pages_shared':True}
 (out/'pages.gpu').write_bytes(final)
 (out/'global.gpi').unlink()
 manifest['runtime_pack']={'bytes':len(final),'sha256':sha(final),'storage':storage,'facing_sharing':sharing}
 if not args.keep_loose_pages:
  # Packed records retain every texture/palette byte and CRC. Removing only the
  # content-addressed intermediates produced above avoids thousands of tiny
  # filesystem allocations; rerun this converter to regenerate loose pages.
  for filename in {name for page in encoder.artifacts.values() for name in (page['texels'],page['palette']) if name}:
   path=out/filename
   assert path.parent==out and len(path.stem)==64 and path.suffix in ('.tex','.pal')
   path.unlink()
  manifest['payload_storage']='pages.gpu; loose texel/palette intermediates omitted'
  (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 # Final manifest and report describe the runtime bundle, not its temporary
 # page-only predecessor. Loose intermediates are optional build artifacts.
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 report=json.loads((out/'pack.json').read_text());report['source_manifest_sha256']=sha((out/'manifest.json').read_bytes())
 report['page_only_pack_bytes']=report['pack_bytes'];report['pack_bytes']=len(final);report['pack_sha256']=sha(final);report['unshared_page_records']=report['page_records'];report['page_records']=sharing['retained_pages'];report['facing_sharing']=sharing
 report['limits']=['Complete regenerated player/enemy/pickup banks only; dynamic scenery/effects use separate paths.','Exact GPU texture formats; no visual or physical performance claim from asset compilation.']
 (out/'pack.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'rasters':counts,'pages':len(encoder.artifacts),'pixels_checked':pixels,'output':str(out)}))

if __name__=='__main__':main()
