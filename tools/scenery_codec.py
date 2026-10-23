"""Decode immutable offline RGB555/indexed scenery packets without workspace state."""
import struct
import numpy as np
from tile_storage import unlz

def unpack(blob):
 bits,mode,colors=struct.unpack_from('<BBH',blob)
 if mode:
  assert mode==1 and bits==16 and colors==0 and len(blob)%2==0
  return np.frombuffer(blob[4:],dtype='<u2').copy()
 start=4+((colors*2+3)&~3)
 values=np.frombuffer(unlz(blob[start:]),dtype='u1')
 if bits==16:return np.frombuffer(values.tobytes(),dtype='<u2').copy()
 if bits==4:values=np.stack((values&15,values>>4),axis=1).reshape(-1)
 palette=np.frombuffer(blob[4:4+colors*2],dtype='<u2');return palette[values].copy()

def records(blob):
    if blob[:4] not in (b'KFC4',b'KFC5'):raise ValueError('Expected scaled atlas')
    n=struct.unpack_from('<I',blob,4)[0];base=8+n*8
    if not n or n>65536 or base>len(blob):raise ValueError('Invalid tile table')
    table=list(struct.iter_unpack('<II',blob[8:base]))
    if blob[:4]==b'KFC5':table=[(a&0x1fffff,b&1023)for a,b in table]
    if any(off%4 or not size or size>2320 or off+size>len(blob)-base for off,size in table):raise ValueError('Invalid packet range')
    return base,table
