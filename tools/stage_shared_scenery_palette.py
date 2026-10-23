"""Compile the current clustered scenery palettes from ordered RGB555 tile inputs.

The fixed 32-group / 64-outlier policy preserves alpha, tile identities and
callback order. Color quantization matches the current DS adaptation.
"""
from pathlib import Path
import argparse,hashlib,json,math,struct
import numpy as np
from PIL import Image
from scenery_codec import unpack
from scenery_codec import records
from tile_storage import lz10,unlz

def rgb(values):
 values=np.asarray(values,dtype=np.uint16);c=np.stack((values&31,(values>>5)&31,(values>>10)&31),axis=-1)
 return ((c<<3)|(c>>2)).astype('u1')
def convert(original,index,groups_requested=32,reserve_outliers=64):
 base,table=records(original);n=len(table)
 tiles=[unpack(original[base+off:base+off+size])for off,size in table]
 pixels=np.stack(tiles);opaque=(pixels&32768)!=0
 # Cluster normalized coarse color histograms; no spatial filtering/dither.
 groups=min(groups_requested,int(np.count_nonzero(np.any(opaque,axis=1))))
 assignment=np.zeros(n,dtype=np.uint16)
 if groups>1:
  from scipy.cluster.vq import kmeans2
  coarse=((pixels&31)>>3)+((((pixels>>5)&31)>>3)<<2)+((((pixels>>10)&31)>>3)<<4)
  features=np.zeros((n,64),dtype=np.float32)
  for i in range(n):
   if np.any(opaque[i]):features[i]=np.sqrt(np.bincount(coarse[i,opaque[i]],minlength=64)/int(opaque[i].sum()))
  present=np.flatnonzero(np.any(opaque,axis=1))
  _,labels=kmeans2(features[present],groups,iter=30,minit='++',seed=22050)
  assignment[present]=labels
 palettes=np.zeros((groups,256),dtype='<u2');indices=np.zeros((n,256),dtype='u1')
 for group in range(groups):
  selected=np.flatnonzero(assignment==group);subset=pixels[selected];mask=opaque[selected];values=subset[mask]&32767
  if not len(values):continue
  image=rgb(values);padding=(-len(image))%256
  if padding:image=np.concatenate((image,np.repeat(image[-1:],padding,axis=0)))
  quant=Image.fromarray(image.reshape(-1,256,3)).quantize(colors=255-reserve_outliers,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
  colors=np.asarray(quant.getpalette(),dtype=np.uint16).reshape(-1,3)[:255-reserve_outliers]
  colors=(colors*31+127)//255;packed=np.unique((colors[:,0]|colors[:,1]<<5|colors[:,2]<<10).astype('<u2'))
  unique=np.unique(values);original_rgb=rgb(unique).astype(np.int32)
  if reserve_outliers:
   if len(unique)<=255:packed=unique.copy()
   else:
    target_rgb=rgb(packed).astype(np.int32);minimum=np.empty(len(unique),dtype=np.int32)
    for start in range(0,len(unique),512):
     delta=original_rgb[start:start+512,None,:]-target_rgb[None,:,:];minimum[start:start+512]=np.sum(delta*delta,axis=-1).min(axis=1)
    # Reserve exact rare colors using farthest-point coverage. Dense median-cut
    # colors remain intact, so bright accents cannot simply disappear.
    while len(packed)<255 and int(minimum.max()):
     farthest=int(np.argmax(minimum));packed=np.append(packed,unique[farthest]);delta=original_rgb-original_rgb[farthest];minimum=np.minimum(minimum,np.sum(delta*delta,axis=1))
  palettes[group,1:1+len(packed)]=packed|32768
  target_rgb=rgb(packed).astype(np.int32);lut=np.zeros(32768,dtype='u1')
  for start in range(0,len(unique),512):
   diff=original_rgb[start:start+512,None,:]-target_rgb[None,:,:];distance=np.sum(diff*diff,axis=-1);nearest=np.argmin(distance,axis=1)
   lut[unique[start:start+512]]=nearest+1
  indices[selected]=np.where(mask,lut[subset&32767],0).astype('u1')
 palette=palettes.reshape(-1);converted=palettes[assignment[:,None],indices]
 assert np.array_equal((converted&32768)!=0,opaque)
 diff=rgb(pixels[opaque]).astype(np.int32)-rgb(converted[opaque]).astype(np.int32);error=np.sum(diff*diff,axis=-1).astype(np.float64);mse=float(error.sum()/(len(error)*3));psnr=math.inf if not mse else 10*math.log10(255*255/mse)
 payload=bytearray();table=[];dedup={}
 for tile_id,row in enumerate(indices):
  raw=row.tobytes()
  if raw not in dedup:
   packet=bytes(lz10(raw));assert unlz(packet)==raw;dedup[raw]=(len(payload),len(packet));payload.extend(packet);payload.extend(bytes(-len(payload)%4))
  offset,size=dedup[raw];assert size<65536
  table.append((offset,size|(int(assignment[tile_id])<<16)))
 paloff=32+n*8;dataoff=(paloff+len(palette)*2+3)&~3
 data=struct.pack('<4s7I',b'KQSC',2,n,len(palette),32,paloff,dataoff,1)+b''.join(struct.pack('<II',*r)for r in table)+palette.tobytes()+bytes(dataoff-paloff-len(palette)*2)+payload
 return data,{'tiles':n,'groups':groups,'palette_bytes':len(palette)*2,'bytes':len(data),'alpha_exact':True,'opaque_pixel_rgb8_rmse':round(math.sqrt(mse),3),'sha256':hashlib.sha256(data).hexdigest()}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=False);rows=[]
 for path in sorted(a.source_dir.glob('*.atlas')):
  index=path.with_suffix('.index').read_bytes();data,row=convert(path.read_bytes(),index)
  (a.output_dir/(path.stem+'.qsc')).write_bytes(data);(a.output_dir/(path.stem+'.index')).write_bytes(index);row['map']=path.stem;rows.append(row);print(json.dumps(row),flush=True)
 if not rows:p.error('No ordered scenery inputs')
 (a.output_dir/'report.json').write_text(json.dumps({'scope':__doc__,'maps':rows},indent=2)+'\n')

if __name__=='__main__':main()
