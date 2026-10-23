"""Group native map packets and first-used graphics by spatial page, losslessly."""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from tile_storage import lz10,unlz
R=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-dir',type=Path,default=R/'research/rendering/native-bg-asset-study');p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False);rows=[]
 for path in sorted(a.source_dir.glob('*.ntb')):
  source=path.read_bytes();head=list(struct.unpack_from('<4s11I',source));magic,version,w,h,n,groups,m,pa,tr,pr,po,flags=head;assert magic==b'KNTB'and version==1 and groups==16 and flags==0
  tile_packets=[];tile_raw=[];pages=[]
  for i in range(n):
   at,size=struct.unpack_from('<II',source,tr+i*8);packet=source[po+at:po+at+size];raw=unlz(packet);assert len(raw)==64;tile_packets.append(packet);tile_raw.append(raw)
  for i in range(m):
   at,size=struct.unpack_from('<II',source,pr+i*8);raw=unlz(source[po+at:po+at+size]);assert len(raw)==1024;pages.append(np.frombuffer(raw,dtype='<u4'))
  assert tile_raw[0]==bytes(64)
  order=[0];seen={0};first=[]
  for page in pages:
   added=[]
   for value in page:
    old=int(value)&0x0fffffff;assert old<n
    if old not in seen:seen.add(old);order.append(old);added.append(old)
   first.append(added)
  # Preserve any valid unplaced graphics at the end rather than dropping them.
  remaining=[i for i in range(n)if i not in seen];order.extend(remaining);assert len(order)==n
  remap=np.empty(n,dtype='<u4');remap[np.array(order)]=np.arange(n,dtype='<u4');rewritten=[((page&0xf0000000)|remap[page&0x0fffffff]).astype('<u4').tobytes()for page in pages]
  payload=bytearray();tiles=[None]*n;page_records=[];page_dedup={}
  def append(packet):
   at=len(payload);payload.extend(packet);payload.extend(bytes(-len(payload)%4));return at,len(packet)
  tiles[0]=append(tile_packets[0])
  for raw,added in zip(rewritten,first):
   if raw not in page_dedup:page_dedup[raw]=append(bytes(lz10(raw)))
   page_records.append(page_dedup[raw])
   for old in added:tiles[int(remap[old])]=append(tile_packets[old])
  for old in remaining:tiles[int(remap[old])]=append(tile_packets[old])
  assert all(item is not None for item in tiles)
  blob=struct.pack('<4s11I',*head)+source[pa:pa+8192]+b''.join(struct.pack('<II',*record)for record in tiles+page_records)+payload
  assert po==48+8192+n*8+m*8
  # Decode the serialized destination and compare every map reference's exact
  # palette group and graphic bytes. Color/alpha/geometry cannot drift here.
  decoded=[]
  for at,size in tiles:decoded.append(unlz(blob[po+at:po+at+size]))
  for old,page,(at,size)in zip(pages,rewritten,page_records):
   raw=unlz(blob[po+at:po+at+size]);assert raw==page
   new=np.frombuffer(raw,dtype='<u4');assert np.array_equal(old>>28,new>>28)
   for before,after in zip(old,new):assert tile_raw[int(before)&0x0fffffff]==decoded[int(after)&0x0fffffff]
  assert blob[pa:pa+8192]==source[pa:pa+8192]
  (out/path.name).write_bytes(blob);row={'map':path.stem,'source_bytes':len(source),'repacked_bytes':len(blob),'tile_patterns':n,'map_pages':m,'map_references_exact':m*256,'palette_bytes_exact':8192,'unplaced_patterns_retained':len(remaining),'source_sha256':hashlib.sha256(source).hexdigest(),'repacked_sha256':hashlib.sha256(blob).hexdigest()};rows.append(row);print(json.dumps(row),flush=True)
 report={'scope':__doc__,'maps':rows,'source_bytes':sum(r['source_bytes']for r in rows),'repacked_bytes':sum(r['repacked_bytes']for r in rows),'limits':['Same KNTB format and exact art/palettes/alpha/map placement. Asset locality only; no runtime code or production ROM modified.','Grouping does not by itself prove fewer physical SD reads; cache replay and device measurements must establish the benefit.']};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
