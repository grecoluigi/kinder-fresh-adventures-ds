"""Small private FAT16 image for emulator integration tests; no host mounts."""
from pathlib import Path
import struct

def create(path,empty_save=False):
 """Create a sparse256MiB FAT16 superfloppy, compatible with libfat."""
 path=Path(path);boot=bytearray(512);boot[:3]=b'\xeb\x3c\x90';boot[3:11]=b'KFTEST  '
 struct.pack_into('<HBHBHHBHHHII',boot,11,512,8,1,2,512,0,0xf8,256,32,64,0,524288)
 boot[36]=0x80;boot[38]=0x29;struct.pack_into('<I',boot,39,2001)
 boot[43:54]=b'KINDER TEST';boot[54:62]=b'FAT16   ';boot[510:512]=b'\x55\xaa'
 with path.open('xb')as f:
  f.truncate(256*1024*1024);f.seek(0);f.write(boot)
  for sector in (1,257):f.seek(sector*512);f.write(b'\xf8\xff\xff\xff')
  if empty_save:
   short=b'KINDER~1SAV';checksum=0
   for value in short:checksum=(((checksum&1)<<7)+(checksum>>1)+value)&255
   units=list('kinder_fresh.sav'.encode('utf-16le'))+[0,0]
   units+=list(b'\xff\xff')*((52-len(units))//2)
   records=[]
   for ordinal in (2,1):
    record=bytearray(32);record[0]=ordinal|(64 if ordinal==2 else 0);record[11]=15;record[13]=checksum
    chars=bytes(units[(ordinal-1)*26:ordinal*26]);record[1:11]=chars[:10];record[14:26]=chars[10:22];record[28:32]=chars[22:26];records.append(record)
   entry=bytearray(32);entry[:11]=short;entry[11]=32;records.append(entry)
   f.seek(513*512);f.write(b''.join(records))

def files(path):
 """Read root files and long names without modifying the image."""
 with Path(path).open('rb')as f:
  b=f.read(512);assert b[510:]==b'\x55\xaa'
  ss,spc,res,fats,entries,total,media,spf=struct.unpack_from('<HBHBHHBH',b,11)
  total=total or struct.unpack_from('<I',b,32)[0]
  assert ss==512 and spc and spf and entries and total
  root=res+fats*spf;data=root+(entries*32+ss-1)//ss
  f.seek(res*ss);fat=f.read(spf*ss);f.seek(root*ss);directory=f.read(entries*32)
  names={};result={}
  for at in range(0,len(directory),32):
   e=directory[at:at+32]
   if e[0]==0:break
   if e[0]==0xe5:names={};continue
   if e[11]==15:
    raw=e[1:11]+e[14:26]+e[28:32];names[e[0]&31]=raw.decode('utf-16le').split('\0')[0].rstrip('\uffff');continue
   name=''.join(names[k]for k in sorted(names))if names else e[:8].decode('ascii').rstrip()+('.'+e[8:11].decode('ascii').rstrip()if e[8:11].strip()else'');names={}
   if e[11]&24:continue
   cluster=struct.unpack_from('<H',e,26)[0];size=struct.unpack_from('<I',e,28)[0];content=bytearray();seen=set()
   while len(content)<size:
    assert 2<=cluster<0xfff8 and cluster not in seen and cluster*2+2<=len(fat)
    seen.add(cluster);f.seek((data+(cluster-2)*spc)*ss);content.extend(f.read(spc*ss));cluster=struct.unpack_from('<H',fat,cluster*2)[0]
   result[name]=bytes(content[:size])
  return result

def root_names(path):
 """Every root directory entry name, including directories (volume label excluded)."""
 with Path(path).open('rb')as f:
  b=f.read(512);ss,spc,res,fats,entries,total,media,spf=struct.unpack_from('<HBHBHHBH',b,11)
  f.seek((res+fats*spf)*ss);directory=f.read(entries*32)
 names=[];long={}
 for at in range(0,len(directory),32):
  e=directory[at:at+32]
  if e[0]==0:break
  if e[0]==0xe5:long={};continue
  if e[11]==15:long[e[0]&31]=(e[1:11]+e[14:26]+e[28:32]).decode('utf-16le').split('\0')[0].rstrip('\uffff');continue
  if e[11]&8:long={};continue
  names.append(''.join(long[k]for k in sorted(long))if long else e[:8].decode('ascii').rstrip()+('.'+e[8:11].decode('ascii').rstrip()if e[8:11].strip()else''));long={}
 return names
