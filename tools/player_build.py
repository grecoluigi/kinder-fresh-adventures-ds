"""Native player packing entry point; shared LZ10 encoder for asset converters."""
from collections import defaultdict, deque

def lz10(raw):
 out=bytearray(b'\x10'+len(raw).to_bytes(3,'little'));history=defaultdict(deque);pos=0
 while pos<len(raw):
  flagpos=len(out);out.append(0);flags=0
  for bit in range(8):
   if pos>=len(raw):break
   key=raw[pos:pos+3];candidates=history[key]
   while candidates and pos-candidates[0]>4096:candidates.popleft()
   bestlen=0;bestdistance=0
   for old in list(candidates)[-64:][::-1]:
    length=3
    while length<18 and pos+length<len(raw) and raw[old+length]==raw[pos+length]:length+=1
    if length>bestlen:bestlen=length;bestdistance=pos-old
    if length==18:break
   length=bestlen if bestlen>=3 else 1
   if length>=3:
    flags|=128>>bit;word=((length-3)<<12)|(bestdistance-1);out.extend(word.to_bytes(2,'big'))
   else:out.append(raw[pos])
   for index in range(pos,pos+length):history[raw[index:index+3]].append(index)
   pos+=length
  out[flagpos]=flags
 return out

if __name__=='__main__':
 from player_scaled_build import main
 main()
