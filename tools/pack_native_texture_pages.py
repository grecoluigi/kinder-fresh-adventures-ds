"""Repack a native bundle with independently compressed textures and exact byte deduplication."""
from pathlib import Path
import argparse,hashlib,json,struct,zlib
from tile_storage import lz10,unlz

def pack_textures(source, palette_bank=False, compress_textures=True):
 magic,version,count,stride,records,total,r0,r1=struct.unpack_from('<4s7I',source)
 assert (magic,version,stride,records,total,r0,r1)==(b'KGP1',2,32,32,len(source),0,0)
 fm,fv,index_at,index_bytes,fp,ft,f0,f1=struct.unpack_from('<4s7I',source,len(source)-32)
 assert (fm,fv,fp,ft,f0,f1)==(b'KGC1',1,count,len(source),0,0) and index_at+index_bytes==len(source)-32
 lookup=source[index_at:index_at+index_bytes];blob=bytearray(32+count*32);palettes={};payloads={};compressed=0
 # Keep frequently reused palettes together so one cached file block can
 # cover neighboring animation frames rather than unrelated texture packets.
 if palette_bank:
  for i in range(count):
   pal=struct.unpack_from('<I',source,32+i*32+4)[0]
   pn=struct.unpack_from('<I',source,32+i*32+20)[0]
   palette=source[pal:pal+pn]if pn else b''
   if palette and palette not in palettes:
    blob.extend(b'\0'*((-len(blob))%16));palettes[palette]=len(blob);blob.extend(palette)
 for i in range(count):
  tex,pal,w,h,bits,flags,reserved,n,pn,tcrc,pcrc=struct.unpack_from('<IIHHBBHIIII',source,32+i*32)
  assert reserved==0 and n==w*h*bits//8 and w*h<=2048
  raw=source[tex:tex+n];palette=source[pal:pal+pn]if pn else b''
  assert len(raw)==n and zlib.crc32(raw)==tcrc and zlib.crc32(palette)==pcrc
  pal_at=0
  if palette:
   if palette not in palettes:blob.extend(b'\0'*((-len(blob))%16));palettes[palette]=len(blob);blob.extend(palette)
   pal_at=palettes[palette]
  encoded=bytes(lz10(raw))if compress_textures else raw
  if compress_textures:assert unlz(encoded)==raw
  use_compressed=compress_textures and len(encoded)<n;payload=encoded if use_compressed else raw;compressed+=use_compressed
  key=(use_compressed,payload)
  if key not in payloads:blob.extend(b'\0'*((-len(blob))%8));payloads[key]=len(blob);blob.extend(payload)
  struct.pack_into('<IIHHBBHIIII',blob,32+i*32,payloads[key],pal_at,w,h,bits,flags,len(payload)if use_compressed else 0,n,pn,tcrc,pcrc)
 blob.extend(b'\0'*((-len(blob))%32));new_index=len(blob);blob.extend(lookup);total=len(blob)+32
 blob.extend(struct.pack('<4s7I',b'KGC1',1,new_index,len(lookup),count,total,0,0))
 struct.pack_into('<4s7I',blob,0,b'KGP1',3 if compress_textures else 2,count,32,32,total,0,0)
 return bytes(blob),{'pages':count,'compressed_pages':compressed,'unique_texture_payloads':len(payloads),'logical_source_bytes':len(source),'stored_bytes':len(blob),'index_bytes':len(lookup),'palette_bank':palette_bank,'compress_textures':compress_textures,'unique_palettes':len(palettes),'every_texture_roundtrip_exact':True}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
 source=args.input.read_bytes();packed,report=pack_textures(source);args.output.write_bytes(packed);report.update(source_sha256=hashlib.sha256(source).hexdigest(),output_sha256=hashlib.sha256(packed).hexdigest());print(json.dumps(report))
