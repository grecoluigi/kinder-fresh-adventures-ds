"""Build a direct-address KAD1 index from a validated sorted KAF1 catalog."""
import struct

def dense_index(source,pages):
 magic,version,frames,refs,frame_offset,ref_offset,total,reserved=struct.unpack_from('<4s7I',source)
 assert (magic,version,frame_offset,total,reserved)==(b'KAF1',1,32,len(source),0)
 assert ref_offset==32+frames*24 and ref_offset+refs*12==total
 groups=[{} for _ in range(3)]
 for i in range(frames):
  record=source[32+i*24:56+i*24];kind,frame_id=struct.unpack_from('<II',record)
  assert kind<3 and frame_id<65536 and frame_id not in groups[kind]
  groups[kind][frame_id]=record
 counts=[max(g,default=-1)+1 for g in groups];bases=[0,counts[0],counts[0]+counts[1]];slots=sum(counts)
 records=bytearray()
 for kind,group in enumerate(groups):
  for frame_id in range(counts[kind]):records.extend(group.get(frame_id,struct.pack('<IIHHIII',kind,frame_id,0,0,0,0,0)))
 assert len(records)==slots*24
 new_ref_offset=64+len(records);size=new_ref_offset+refs*12
 return struct.pack('<4s7I',b'KAD1',1,slots,refs,64,new_ref_offset,size,0)+struct.pack('<8I',*bases,*counts,pages,0)+records+source[ref_offset:]
