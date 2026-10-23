"""Build temporary expanded RGB555 references for a verified QSC study."""
import hashlib,json,struct
from pathlib import Path
import numpy as np
from tile_storage import unlz

def stage_reference(study,assets,reference):
 study=Path(study);assets.mkdir();reference.mkdir()
 for row in json.loads((study/'verification.json').read_text())['maps']:
  name=row['map'];source=study/'assets'/(name+'.qsc');blob=source.read_bytes();_,version,n,colors,rec,paloff,dataoff,flags=struct.unpack_from('<4s7I',blob);assert version==2 and flags==1
  palette=np.frombuffer(blob,dtype='<u2',count=colors,offset=paloff);payload=bytearray();records=[];digest=hashlib.sha256()
  for i in range(n):
   offset,word=struct.unpack_from('<II',blob,rec+i*8);length=word&65535;group=word>>16
   indices=np.frombuffer(unlz(blob[dataoff+offset:dataoff+offset+length]),dtype='u1');assert len(indices)==256
   raw=palette[group*256+indices.astype(np.uint32)].astype('<u2').tobytes();digest.update(raw)
   packet=struct.pack('<BBH',16,1,0)+raw;records.append((len(payload),len(packet)));payload.extend(packet)
  assert digest.hexdigest()==row['decoded_sha256']
  (reference/(name+'.atlas')).write_bytes(struct.pack('<4sI',b'KFC4',n)+b''.join(struct.pack('<II',*r)for r in records)+payload)
  (assets/(name+'.atlas')).symlink_to(source.resolve())
  index=(study/'assets'/(name+'.index')).read_bytes()
  for root in (assets,reference):(root/(name+'.index')).write_bytes(index)
