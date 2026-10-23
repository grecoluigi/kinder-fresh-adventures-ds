"""Write independently readable 1KiB LZ10/raw blocks for an immutable native pack."""
from pathlib import Path
import argparse,hashlib,json,struct
from tile_storage import lz10,unlz

def pack_blocks(blob):
 count=(len(blob)+1023)//1024;result=bytearray(32+count*16);compressed=0
 for block,at in enumerate(range(0,len(blob),1024)):
  raw=blob[at:at+1024];encoded=bytes(lz10(raw));assert unlz(encoded)==raw
  is_compressed=len(encoded)<len(raw);payload=encoded if is_compressed else raw;compressed+=is_compressed
  result.extend(b'\0'*((-len(result))%4));offset=len(result);result.extend(payload)
  struct.pack_into('<4I',result,32+block*16,offset,len(payload)|(0x80000000 if is_compressed else 0),len(raw),0)
 struct.pack_into('<4s7I',result,0,b'KZB1',1,len(blob),1024,count,32,len(result),0)
 return bytes(result),compressed

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
 source=args.input.read_bytes();packed,count=pack_blocks(source);args.output.write_bytes(packed)
 print(json.dumps({'logical_bytes':len(source),'physical_bytes':len(packed),'compressed_blocks':count,'source_sha256':hashlib.sha256(source).hexdigest(),'output_sha256':hashlib.sha256(packed).hexdigest()}))
