"""Audit serialized QSC palettes/packets against canonical scenery IDs and alpha.
RGB changes are measured, not treated as exact. No DS runtime is exercised.
"""
from pathlib import Path
import argparse,hashlib,json,math,struct
import numpy as np
from scenery_codec import unpack
from tile_storage import unlz
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study-dir',type=Path,required=True);a=p.parse_args();root=a.study_dir.resolve();manifest=json.loads((root/'report.json').read_text());rows=[]
def rgb(v):
 c=np.stack((v&31,(v>>5)&31,(v>>10)&31),axis=-1).astype(np.int32);return (c<<3)|(c>>2)
for expected in manifest['maps']:
 name=expected['map'];path=root/'assets'/(name+'.qsc');blob=path.read_bytes()
 magic,version,count,colors,table,paloff,dataoff,flags=struct.unpack_from('<4s7I',blob)
 assert magic==b'KQSC'and version in(1,2)and table==32 and count>0 and count<=65536
 assert paloff==32+count*8 and paloff+colors*2<=dataoff<=len(blob)and dataoff%4==0
 assert colors<=32768 and ((version==1 and flags==0 and colors<=256)or(version==2 and flags==1 and colors%256==0))
 palette=np.frombuffer(blob,dtype='<u2',count=colors,offset=paloff)
 source=(R/'ds/nitrofs/composite'/(name+'.atlas')).read_bytes();assert source[:4]==b'KFC5'and struct.unpack_from('<I',source,4)[0]==count
 assert hashlib.sha256(source).hexdigest()==expected['source_sha256']
 assert hashlib.sha256(blob).hexdigest()==expected['candidate_sha256']
 assert (root/'assets'/(name+'.index')).read_bytes()==(R/'ds/nitrofs/composite'/(name+'.index')).read_bytes()
 opaque=error_sum=max_error=0;changed=0;digest=hashlib.sha256()
 for tile in range(count):
  offset,word=struct.unpack_from('<II',blob,32+tile*8);group=word>>16 if version==2 else 0;size=word&65535 if version==2 else word
  assert size>0 and dataoff+offset+size<=len(blob)and offset%4==0 and group*256<colors and palette[group*256]==0
  raw=unlz(blob[dataoff+offset:dataoff+offset+size]);assert len(raw)==256
  index=np.frombuffer(raw,dtype='u1');assert group*256+int(index.max())<colors
  actual=palette[group*256+index.astype(np.uint32)]
  oldoffset,oldsize=struct.unpack_from('<II',source,8+tile*8);start=8+count*8+(oldoffset&0x1fffff);original=unpack(source[start:start+(oldsize&1023)])
  assert len(original)==256 and np.array_equal(actual&32768,original&32768)
  mask=(original&32768)!=0;delta=rgb(actual[mask])-rgb(original[mask]);errors=np.sum(delta*delta,axis=-1)
  if errors.size:max_error=max(max_error,int(errors.max()))
  opaque+=int(mask.sum());error_sum+=int(errors.sum());changed+=int(np.count_nonzero(actual[mask]!=original[mask]));digest.update(actual.astype('<u2').tobytes())
 mse=error_sum/(opaque*3);rmse=math.sqrt(mse);psnr=None if not mse else 10*math.log10(255*255/mse)
 assert abs(rmse-expected['opaque_pixel_rgb8_rmse'])<.001
 if psnr is not None:assert abs(psnr-expected['opaque_pixel_rgb8_psnr_db'])<.001
 row=dict(map=name,tiles=count,alpha_exact=True,index_bytes_exact=True,palette_bytes=colors*2,RGB_changed_opaque_pixels=changed,opaque_pixels=opaque,rgb8_rmse=round(rmse,3),rgb8_psnr_db=None if psnr is None else round(psnr,3),max_pixel_rgb8_error=round(math.sqrt(max_error),3),decoded_sha256=digest.hexdigest());rows.append(row)
report=dict(scope=__doc__,maps=rows,tiles_verified=sum(v['tiles']for v in rows),pixels_verified=sum(v['tiles']*256 for v in rows),palette_budget_bytes=65536,maximum_palette_bytes=max(v['palette_bytes']for v in rows),alpha_and_index_exact=True,limits=['Quantized RGB differs from original; this does not establish acceptable visual quality.','File/codec audit only, no CPU fallback/GPU integration or frame-rate evidence.'])
(root/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='maps'}))
