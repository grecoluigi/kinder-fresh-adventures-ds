"""Validate every production atlas tile and live-object row used by DS BIOS LZ10."""
import json,struct
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def decode(packet,size):
 assert len(packet)>=4 and packet[0]==16
 assert int.from_bytes(packet[1:4],'little')==size
 out=bytearray();at=4
 while len(out)<size:
  flags=packet[at];at+=1
  for mask in (128,64,32,16,8,4,2,1):
   if len(out)==size:break
   if flags&mask:
    value=int.from_bytes(packet[at:at+2],'big');at+=2
    length=(value>>12)+3;distance=(value&4095)+1
    assert distance<=len(out) and len(out)+length<=size
    for _ in range(length):out.append(out[-distance])
   else:out.append(packet[at]);at+=1
 assert at==len(packet)
 return out
tiles=rows=0
for file in (R/'ds/nitrofs/composite').glob('*.atlas'):
 data=file.read_bytes();assert data[:4]==b'KFC2'
 count=struct.unpack_from('<I',data,4)[0];base=8+count*8
 for i in range(count):
  offset,size=struct.unpack_from('<II',data,8+i*8)
  assert size<=2312 and base+offset+size<=len(data)
  decode(data[base+offset:base+offset+size],2048);tiles+=1
data=(R/'ds/nitrofs/scenes/enemies.frames').read_bytes()
assert data[:4]==b'KFEN'
resources,frames=struct.unpack_from('<HH',data,4);records=12+resources*84;base=records+frames*16
for i in range(frames):
 offset,size,width,height=struct.unpack_from('<IIHH',data,records+i*16)
 frame=data[base+offset:base+offset+size];assert len(frame)==size
 for y in range(height):
  start,length=struct.unpack_from('<II',frame,y*8);start+=height*8
  assert length<=1804 and start+length<=size
  decode(frame[start:start+length],width*2);rows+=1
result={'scope':__doc__,'atlas_tiles':tiles,'live_rows':rows,'all_packets_bounded_and_complete':True,
 'limits':['Checks generated packet structure; DS BIOS execution and hardware frame timing still require device verification.']}
(R/'research/rendering/graphics-packets-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
