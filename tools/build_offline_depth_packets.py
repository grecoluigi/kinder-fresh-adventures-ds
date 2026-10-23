"""Precompute immutable scenery depth into compressed, bounded camera-region packets.
Consumes explicit immutable conversion inputs; no research assets are needed.
"""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from scenery_codec import unpack
from scenery_codec import records
from threshold_depth_mesh import threshold_mesh
from tile_storage import lz10,unlz
R=Path(__file__).resolve().parents[1]
HEADER=struct.Struct('<4s6H2I');ENTRY=struct.Struct('<IIHH');RECORD_BYTES=6
STEP_X,STEP_Y=256,192
REGION_W,REGION_H=512,384
CAPACITY=1536

def pack_rectangle(q):
 left,top,right,bottom,ordinal=q
 assert 0<=left<right<=512 and 0<=top<bottom<=384 and 0<ordinal<=255
 value=left|(top<<9)|((right-1)<<18)|((bottom-1)<<27)|(ordinal<<36)
 return value.to_bytes(RECORD_BYTES,'little')

def unpack_rectangle(data):
 assert len(data)==RECORD_BYTES
 v=int.from_bytes(data,'little');assert not v>>44
 return (v&511,(v>>9)&511,((v>>18)&511)+1,((v>>27)&511)+1,(v>>36)&255)

def ownership(index,atlas):
 magic,w,h,nc,npairs,_,_=struct.unpack_from('<4sHHIIHH',index)
 assert magic==b'KFLD' and len(index)==20+nc*12+npairs*4
 shared=atlas[:4]==b'KQSC'
 if shared:
  _,version,n,colors,record_offset,palette_offset,base,flags=struct.unpack_from('<4s7I',atlas)
  assert version==2 and flags==1 and record_offset==32 and colors%256==0
  table=[(off,word&65535)for off,word in struct.iter_unpack('<II',atlas[32:32+n*8])]
 else:base,table=records(atlas)
 decoded={};owner=np.zeros((h*16,w*16),dtype=np.uint8);ordinal=0
 for kind,begin,count in struct.iter_unpack('<III',index[20:20+nc*12]):
  if kind:continue
  ordinal+=1;assert ordinal<=255 and begin+count<=npairs
  for at in range(begin,begin+count):
   cell,tile=struct.unpack_from('<HH',index,20+nc*12+at*4);assert cell<w*h and tile<len(table)
   if tile not in decoded:
    off,size=table[tile]
    if shared:
     indices=np.frombuffer(unlz(atlas[base+off:base+off+size]),dtype=np.uint8);assert len(indices)==256
     decoded[tile]=indices.reshape(16,16)!=0
    else:decoded[tile]=(unpack(atlas[base+off:base+off+size]).reshape(16,16)&32768)!=0
   x=cell%w*16;y=cell//w*16;owner[y:y+16,x:x+16][decoded[tile]]=ordinal
 return owner

def packet_rectangles(rectangles,x,y):
 result=[]
 for left,top,right,bottom,ordinal in rectangles:
  left=max(0,left-x);right=min(REGION_W,right-x);top=max(0,top-y);bottom=min(REGION_H,bottom-y)
  if left<right and top<bottom:result.append((left,top,right,bottom,ordinal))
 return result

def verify_packet(rectangles,owner,x,y):
 reference=np.zeros((REGION_H,REGION_W),dtype=np.uint8);part=owner[y:y+REGION_H,x:x+REGION_W];reference[:part.shape[0],:part.shape[1]]=part
 restored=np.zeros_like(reference)
 for left,top,right,bottom,ordinal in rectangles:
  region=reference[top:bottom,left:right];target=restored[top:bottom,left:right]
  assert np.all((region==0)|(region>=ordinal))
  np.maximum(target,np.where(region!=0,ordinal,0).astype(reference.dtype),out=target)
 assert np.array_equal(restored,reference)

def build(index,atlas):
 owner=ownership(index,atlas);height,width=owner.shape;rectangles=threshold_mesh(owner)
 columns=(width+STEP_X-1)//STEP_X;rows=(height+STEP_Y-1)//STEP_Y;n=columns*rows
 payload=bytearray();entries=[];unique={};samples=[];base=HEADER.size+n*ENTRY.size
 for row in range(rows):
  for col in range(columns):
   x=col*STEP_X;y=row*STEP_Y;part=packet_rectangles(rectangles,x,y);verify_packet(part,owner,x,y)
   if len(part)>CAPACITY:
    entries.append((0,0,0,1));samples.append({'x':x,'y':y,'rectangles':len(part),'fallback':True});continue
   raw=b''.join(pack_rectangle(q) for q in part)
   assert [unpack_rectangle(raw[i:i+RECORD_BYTES]) for i in range(0,len(raw),RECORD_BYTES)]==part
   compressed=lz10(raw) if raw else b''
   flags=2 if len(compressed)<len(raw) else 0;stored=bytes(compressed) if flags else raw
   # Like-byte planes expose repeated coordinate/depth bits to LZ10. Keep the
   # interleaved/raw path when it is smaller; no extra precision is discarded.
   if raw:
    planar=np.frombuffer(raw,dtype=np.uint8).reshape(-1,RECORD_BYTES).T.tobytes();packed_planar=bytes(lz10(planar))
    if len(packed_planar)<len(stored):stored=packed_planar;flags=6
   expanded=unlz(stored) if flags&2 else stored
   if flags&4:expanded=np.frombuffer(expanded,dtype=np.uint8).reshape(RECORD_BYTES,-1).T.tobytes()
   assert expanded==raw
   key=(flags,len(part),stored)
   if key not in unique:
    unique[key]=base+len(payload);payload.extend(stored);payload.extend(bytes(-len(payload)%4))
   entries.append((unique[key],len(stored),len(part),flags));samples.append({'x':x,'y':y,'rectangles':len(part),'raw_bytes':len(raw),'stored_bytes':len(stored),'lz10':bool(flags&2),'planar':bool(flags&4),'fallback':False})
 blob=HEADER.pack(b'KDM2',width,height,columns,rows,STEP_X,STEP_Y,RECORD_BYTES,n)+b''.join(ENTRY.pack(*e) for e in entries)+payload
 metadata={'width':width,'height':height,'global_rectangles':len(rectangles),'packets':n,'unique_packet_payloads':len(unique),'fallback_packets':sum(s['fallback'] for s in samples),'packet_rectangles_max':max(s['rectangles'] for s in samples),'bytes':len(blob),'raw_packet_bytes':sum(s.get('raw_bytes',0) for s in samples),'stored_packet_bytes_before_dedup':sum(s.get('stored_bytes',0) for s in samples),'packets_depth_exact':True,'samples':samples}
 return blob,metadata

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=False);rows=[]
 for path in sorted(a.source_dir.glob('*.index')):
  atlas=path.with_suffix('.atlas').read_bytes();index=path.read_bytes();blob,meta=build(index,atlas)
  assert meta['fallback_packets']==0,'Depth capacity exceeded; runtime has no software scenery fallback'
  (a.output_dir/(path.stem+'.mesh')).write_bytes(blob);meta.update(map=path.stem,mesh_sha256=hashlib.sha256(blob).hexdigest());rows.append(meta)
  print(json.dumps({k:v for k,v in meta.items()if k!='samples'}),flush=True)
 if not rows:p.error('No ordered scenery inputs')
 (a.output_dir/'manifest.json').write_text(json.dumps({'scope':__doc__,'maps':rows,'total_bytes':sum(r['bytes']for r in rows)},indent=2)+'\n')
if __name__=='__main__':main()
