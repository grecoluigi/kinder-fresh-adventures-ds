"""Check threshold-packet CPU restoration against independent exact painter owners."""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from test_native_bg_hardware import decode
from build_offline_depth_packets import HEADER,ENTRY,unpack_rectangle
from tile_storage import unlz
R=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();study=R/'research/rendering/native-bg-asset-study';meta={r['map']:r for r in json.loads((study/'report.json').read_text())['maps']};cases=[];old_bad=0
 for path in sorted(study.glob('*.ntb')):
  w,h,palettes,patterns,pages=decode(path.read_bytes());width=w*8;height=h*8
  owner_bytes=path.with_suffix('.owners').read_bytes();cells={struct.unpack_from('<I',owner_bytes,i)[0]:np.frombuffer(owner_bytes,dtype='u1',count=256,offset=i+4).reshape(16,16) for i in range(0,len(owner_bytes),260)}
  mesh_path=R/'ds/nitrofs/composite'/(path.stem+'.mesh');blob=mesh_path.read_bytes();magic,mw,mh,cols,rows,sx,sy,record,count=HEADER.unpack_from(blob);assert (magic,mw,mh,sx,sy,record,count)==(b'KDM2',width,height,256,192,6,cols*rows)
  px,py=meta[path.stem]['preview_camera'];positions=[(px,py),(min(width-256,px+7),min(height-192,py+7)),(width-256,height-192),((width-256)//2,(height-192)//2)]
  for cx,cy in positions:
   colors=np.zeros((192,256),dtype='<u2');owners=np.zeros((192,256),dtype='u1')
   for yy in range(cy//8,(cy+191)//8+1):
    for xx in range(cx//8,(cx+255)//8+1):
     word=struct.unpack_from('<I',pages[(yy//16)*((w+15)//16)+xx//16],((yy%16)*16+xx%16)*4)[0];tile=palettes[word>>28,np.frombuffer(patterns[word&0xfffffff],dtype='u1')].reshape(8,8)
     x=xx*8-cx;y=yy*8-cy;l=max(0,x);r=min(256,x+8);t=max(0,y);b=min(192,y+8);colors[t:b,l:r]=tile[t-y:b-y,l-x:r-x]
   for yy in range(cy//16,(cy+191)//16+1):
    for xx in range(cx//16,(cx+255)//16+1):
     tile=cells.get(yy*(w//2)+xx)
     if tile is None:continue
     x=xx*16-cx;y=yy*16-cy;l=max(0,x);r=min(256,x+16);t=max(0,y);b=min(192,y+16);owners[t:b,l:r]=tile[t-y:b-y,l-x:r-x]
   assert np.array_equal(colors!=0,owners!=0)
   off,size,n,flags=ENTRY.unpack_from(blob,HEADER.size+(cy//192*cols+cx//256)*ENTRY.size);assert flags!=1
   raw=unlz(blob[off:off+size])if flags&2 else blob[off:off+size]
   if flags&4:raw=np.frombuffer(raw,dtype='u1').reshape(6,n).T.tobytes()
   rectangles=[unpack_rectangle(raw[i:i+6])for i in range(0,len(raw),6)];assert len(rectangles)==n
   yy,xx=np.indices(colors.shape);background=(32768|(xx%32)|((yy%32)<<5)|(7<<10)).astype('<u2');base=np.where(colors,colors,background).astype('<u2')
   ranks=np.unique(owners[owners!=0]);middle=int(ranks[len(ranks)//2])if len(ranks)else 1
   actors=[(0,0,256,192,0,32799),(57,44,188,166,middle,33760),(151,120,256,192,255,64512)]
   expected=base.copy()
   for l,t,r,b,order,color in actors:
    target=expected[t:b,l:r];mask=(owners[t:b,l:r]<=order)&((xx[t:b,l:r]+yy[t:b,l:r])%5!=0);target[mask]=color
   def restored(preserve):
    image=base.copy()
    for order in sorted(set([q[4]for q in rectangles]+[q[4]for q in actors])):
     for l,t,r,b,rank in rectangles:
      if rank!=order:continue
      l=max(0,l-cx%256);r=min(256,r-cx%256);t=max(0,t-cy%192);b=min(192,b-cy%192)
      if l>=r or t>=b:continue
      source=colors[t:b,l:r];target=image[t:b,l:r]
      if preserve:mask=source!=0;target[mask]=source[mask]
      else:target[:]=source
     for l,t,r,b,rank,color in actors:
      if rank==order:
       target=image[t:b,l:r];target[(xx[t:b,l:r]+yy[t:b,l:r])%5!=0]=color
    return image
   assert np.array_equal(restored(True),expected),(path.name,cx,cy)
   bad=int(np.sum(restored(False)!=expected));old_bad+=bad
   cases.append({'map':path.stem,'camera':[cx,cy],'pixels':49152,'corrected_mismatches':0,'old_erasing_restore_mismatches':bad,'mesh_sha256':hashlib.sha256(blob).hexdigest()})
 assert len(cases)==48 and old_bad
 report={'scope':__doc__,'cases':cases,'pixels':len(cases)*49152,'corrected_mismatches':0,'old_erasing_restore_mismatches':old_bad,'limits':['Offline order model using actual shipped KDM2 packets and converted tile colors.','C sampling/merging is checked separately under sanitizers; this does not execute gameplay callbacks or establish hardware speed.']};a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='cases'}))
if __name__=='__main__':main()
