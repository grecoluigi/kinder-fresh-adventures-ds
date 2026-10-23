"""Share byte-identical NitroFS payloads in a DS homebrew ROM.
Preserves file IDs/names, executable/banner bytes and 512-byte payload alignment.
Supports ndstool unsigned DS/DSi homebrew; rejects overlays, digest tables and encryption.
"""
from pathlib import Path
import argparse,hashlib,json,os,struct,tempfile

def crc16(data):
 value=0xffff
 for byte in data:
  value^=byte
  for _ in range(8):value=(value>>1)^ (0xa001 if value&1 else 0)
 return value

def compact(data):
 assert len(data)>=0x4000 and data[0x12] in (0,2),'Only DS/DSi-compatible homebrew supported'
 assert struct.unpack_from('<H',data,0x15e)[0]==crc16(data[:0x15e]),'Bad input header CRC'
 read=lambda at:struct.unpack_from('<I',data,at)[0]
 assert not any(read(at) for at in (0x50,0x54,0x58,0x5c)),'Overlays are not supported'
 fat,size=read(0x48),read(0x4c);assert size and size%8==0 and fat+size<=len(data)
 entries=[struct.unpack_from('<II',data,fat+i) for i in range(0,size,8)]
 assert all(0<=start<=end<=len(data) for start,end in entries)
 start=min(a for a,b in entries);end=max(b for a,b in entries)
 assert start%512==0 and fat+size<=start
 for offset,length in ((read(0x20),read(0x2c)),(read(0x30),read(0x3c)),(read(0x40),read(0x44)),(read(0x68),0x840)):
  assert offset and offset+length<=start,'Non-file ROM data follows file region'
 assert read(0x80)==(end+3)&~3,'Unexpected ROM used-size layout'
 cursor=start
 for a,b in sorted(set(entries)):
  assert a>=cursor,'Partially overlapping FAT ranges'
  assert all(byte in (0,255)for byte in data[cursor:a]),'Non-padding between assets'
  cursor=b
 tails=[]
 if data[0x12]==2:
  assert not any(read(at) for at in (*range(0x1e0,0x208,4),*range(0x220,0x230,4))), 'Digest/encrypted ROM is not supported'
  assert data[0xf80:0xf82]==b'\0\1' and data[0xfeb]==0 and data[0xfec:0x1000]==hashlib.sha1(data[:0xe00]).digest(),'Unsupported DSi signature'
  assert read(0x210)==len(data),'Unexpected DSi total size'
  for offset_at,size_at,alignment in ((0x1c0,0x1cc,1024),(0x1d0,0x1dc,512)):
   a,b=read(offset_at),read(offset_at)+read(size_at)
   assert a>=cursor and a%alignment==0 and b<=len(data)
   assert all(byte in (0,255)for byte in data[cursor:a]),'Non-padding DSi gap'
   tails.append((offset_at,a,b,alignment));cursor=b
 assert all(byte in (0,255)for byte in data[cursor:]),'Non-padding ROM trailer'
 output=bytearray(data[:start]);buckets={};new_entries=[];aliases=0;logical_duplicate_bytes=0
 for a,b in entries:
  payload=data[a:b];key=(len(payload),hashlib.sha256(payload).digest());match=None
  for previous in buckets.get(key,[]):
   x,y=previous
   if output[x:y]==payload:match=previous;break
  if match is None:
   output.extend(b'\0'*((-len(output))%512));x=len(output);output.extend(payload);match=(x,len(output));buckets.setdefault(key,[]).append(match)
  else:aliases+=1;logical_duplicate_bytes+=len(payload)
  new_entries.append(match)
 for i,(a,b) in enumerate(new_entries):struct.pack_into('<II',output,fat+8*i,a,b)
 output.extend(b'\0'*((-len(output))%4));struct.pack_into('<I',output,0x80,len(output))
 for offset_at,a,b,alignment in tails:
  output.extend(b'\0'*((-len(output))%alignment));struct.pack_into('<I',output,offset_at,len(output));output.extend(data[a:b])
 output.extend(b'\0'*((-len(output))%512))
 if tails:struct.pack_into('<I',output,0x210,len(output))
 output[0x14]=max(0,(len(output)-1).bit_length()-17)
 struct.pack_into('<H',output,0x15e,crc16(output[:0x15e]))
 if tails:output[0xfec:0x1000]=hashlib.sha1(output[:0xe00]).digest()
 assert len(output)<=len(data),'Compaction grew ROM'
 # Validate every file against the input independently of its hash bucket.
 assert all(output[x:y]==data[a:b] for (a,b),(x,y)in zip(entries,new_entries))
 return bytes(output),{'files':len(entries),'unique_payloads':sum(len(x)for x in buckets.values()),'aliased_files':aliases,'logical_duplicate_bytes':logical_duplicate_bytes,'dsi_binaries_preserved':len(tails),'before_bytes':len(data),'after_bytes':len(output),'saved_bytes':len(data)-len(output),'sha256':hashlib.sha256(output).hexdigest()}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('rom',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
 original=args.rom.read_bytes();result,report=compact(original)
 if result!=original:
  temporary=None
  try:
   with tempfile.NamedTemporaryFile(dir=args.rom.parent,prefix='.nds-pack-',delete=False)as file:
    temporary=Path(file.name);file.write(result);file.flush();os.fsync(file.fileno())
   temporary.chmod(args.rom.stat().st_mode&0o777);os.replace(temporary,args.rom);temporary=None
  finally:
   if temporary is not None:temporary.unlink(missing_ok=True)
 if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
if __name__=='__main__':main()
