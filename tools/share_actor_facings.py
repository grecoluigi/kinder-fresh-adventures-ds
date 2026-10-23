"""Share exact mirrored actor facings, preserving every source frame and colour.

KAD2 catalog references mark reverse-U in bit31. GPU texture/palette payloads
retain their native formats. Every serialized destination frame is verified
against the input before a result is returned.
"""
from pathlib import Path
import argparse,hashlib,json,struct,zlib
import numpy as np

def share_facings(b:bytes):
 head=struct.unpack_from('<4s7I',b);assert head[0]==b'KGP1'and head[1]==2
 footer=struct.unpack_from('<4s7I',b,len(b)-32);assert footer[0]==b'KGC1'and footer[1]==1;at=footer[2]
 h=struct.unpack_from('<4s7I',b,at);assert h[0]==b'KAD1'and h[1]==1 and h[4]==64
 frames=[];refs=[];decoded={}
 for i in range(h[2]):frames.append(list(struct.unpack_from('<IIHHIII',b,at+64+i*24)))
 for i in range(h[3]):refs.append(struct.unpack_from('<I4H',b,at+h[5]+i*12))
 def page(index):
  if index not in decoded:
   t,p,w,ht,bits,flags,z,n,pn,tc,pc=struct.unpack_from('<IIHHBBHIIII',b,32+index*32)
   assert zlib.crc32(b[t:t+n])==tc
   if bits==16:raw=np.frombuffer(b,dtype='<u2',count=n//2,offset=t).reshape(ht,w)
   else:
    assert zlib.crc32(b[p:p+pn])==pc
    data=np.frombuffer(b,dtype='u1',count=n,offset=t);ids=data if bits==8 else np.stack((data&15,data>>4),axis=1).ravel()
    raw=np.frombuffer(b,dtype='<u2',count=pn//2,offset=p)[ids].copy();raw[ids!=0]|=32768;raw=raw.reshape(ht,w)
   decoded[index]=raw
  return decoded[index]
 def raster(frame,entries):
  k,id,w,ht,first,count,z=frame;out=np.zeros((ht,w),dtype='<u2')
  for index,x,y,rw,rh in entries:
   assert index&0x7fffffff<head[2]and x+rw<=w and y+rh<=ht
   src=page(index&0x7fffffff)[:rh,:rw]
   if index>>31:src=src[:,::-1]
   out[y:y+rh,x:x+rw]=src
  return out
 lookup={(f[0],f[1]):i for i,f in enumerate(frames)if f[2]and f[3]};newrefs=[];rewritten=[];pairs=[0]*3;pixels=0
 for f in frames:
  k,id,w,ht,first,count,z=f;entries=refs[first:first+count]
  if w and ht and id&1 and (k,id-1)in lookup:
   other=frames[lookup[k,id-1]];original=refs[other[4]:other[4]+other[5]]
   if (w,ht)==tuple(other[2:4])and np.array_equal(raster(f,entries),raster(other,original)[:,::-1]):
    entries=[(index|0x80000000,w-x-rw,y,rw,rh)for index,x,y,rw,rh in original];pairs[k]+=1
  if w and ht:
   assert np.array_equal(raster(f,entries),raster(f,refs[first:first+count]));pixels+=w*ht
  rewritten.append([k,id,w,ht,len(newrefs),len(entries),z]);newrefs.extend(entries)
 used=sorted({r[0]&0x7fffffff for r in newrefs});remap={old:new for new,old in enumerate(used)}
 blob=bytearray(32+len(used)*32);palettes={}
 def pad(n):blob.extend(bytes(-len(blob)%n))
 for old in used:
  t,p,w,ht,bits,flags,z,n,pn,tc,pc=struct.unpack_from('<IIHHBBHIIII',b,32+old*32)
  if pn and p not in palettes:pad(16);palettes[p]=len(blob);blob.extend(b[p:p+pn])
 for i,old in enumerate(used):
  t,p,w,ht,bits,flags,z,n,pn,tc,pc=struct.unpack_from('<IIHHBBHIIII',b,32+old*32);pad(8);newt=len(blob);blob.extend(b[t:t+n]);blob[32+i*32:64+i*32]=struct.pack('<IIHHBBHIIII',newt,palettes.get(p,0),w,ht,bits,flags,z,n,pn,tc,pc)
 pad(4);catat=len(blob);cat=bytearray(b[at:at+64]);refat=64+len(frames)*24;cat[:32]=struct.pack('<4s7I',b'KAD2',1,len(frames),len(newrefs),64,refat,refat+len(newrefs)*12,0);struct.pack_into('<I',cat,56,len(used))
 cat.extend(b''.join(struct.pack('<IIHHIII',*f)for f in rewritten));cat.extend(b''.join(struct.pack('<I4H',remap[index&0x7fffffff]|(index&0x80000000),x,y,w,h)for index,x,y,w,h in newrefs));blob.extend(cat)
 size=len(blob)+32;blob[:32]=struct.pack('<4s7I',b'KGP1',2,len(used),32,32,size,0,0);blob.extend(struct.pack('<4s7I',b'KGC1',1,catat,len(cat),len(used),size,0,0))
 # Independent serialized destination read: use destination descriptor offsets,
 # not generator's old page arrays or remapping table, to check all final pixels.
 cache={}
 def finalpage(index):
  if index not in cache:
   t,p,w,ht,bits,flags,z,n,pn,tc,pc=struct.unpack_from('<IIHHBBHIIII',blob,32+index*32)
   assert zlib.crc32(blob[t:t+n])==tc
   if bits==16:raw=np.frombuffer(blob,dtype='<u2',count=n//2,offset=t).copy().reshape(ht,w)
   else:
    data=np.frombuffer(blob,dtype='u1',count=n,offset=t);ids=data if bits==8 else np.stack((data&15,data>>4),axis=1).ravel();raw=np.frombuffer(blob,dtype='<u2',count=pn//2,offset=p)[ids].copy();raw[ids!=0]|=32768;raw=raw.reshape(ht,w)
   cache[index]=raw
  return cache[index]
 verified=0
 for i,old in enumerate(frames):
  k,id,w,ht,first,count,z=struct.unpack_from('<IIHHIII',blob,catat+64+i*24)
  assert [k,id,w,ht,z]==[old[0],old[1],old[2],old[3],old[6]]
  if not w or not ht:continue
  actual=np.zeros((ht,w),dtype='<u2')
  for j in range(count):
   key,x,y,rw,rh=struct.unpack_from('<I4H',blob,catat+refat+(first+j)*12);raw=finalpage(key&0x7fffffff)[:rh,:rw];raw=raw[:,::-1]if key>>31 else raw;actual[y:y+rh,x:x+rw]=raw
  assert np.array_equal(actual,raster(old,refs[old[4]:old[4]+old[5]]));verified+=1
 report={'scope':__doc__.strip(),'source_sha256':hashlib.sha256(b).hexdigest(),'destination_sha256':hashlib.sha256(blob).hexdigest(),'source_bytes':len(b),'destination_bytes':len(blob),'saved_bytes':len(b)-len(blob),'mirrored_pairs_by_kind':pairs,'source_pages':head[2],'retained_pages':len(used),'verified_frames':verified,'verified_pixels':pixels,'all_frame_ids_dimensions_and_pixels_exact':True,'limits':['Facing alignment remains supplied by unchanged existing player/enemy/pickup metadata.','No runtime UV/clipping or GPU raster verification in this asset conversion.']}
 return bytes(blob),report

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();blob,report=share_facings(a.source.read_bytes())
 if a.output.exists():p.error('Output already exists')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(blob)
 a.output.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))

if __name__=='__main__':main()
