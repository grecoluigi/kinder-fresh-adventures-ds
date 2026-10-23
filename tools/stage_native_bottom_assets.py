"""Pack a shared indexed HUD and four 8-bit bottom backdrops from offline intermediates."""
from pathlib import Path
import argparse,hashlib,json,math,struct
import numpy as np
from PIL import Image
from tile_storage import unlz,lz10
R=Path(__file__).resolve().parents[1]
def rgb(words):
 a=np.asarray(words,dtype=np.uint16)
 return np.stack((a&31,(a>>5)&31,(a>>10)&31),axis=-1).astype(np.uint8)*8

def quantize(words,count):
 # Palette construction may change colors; mapping and error are audited below.
 image=Image.fromarray(rgb(words).reshape(-1,1,3))
 q=image.quantize(colors=count,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
 values=np.asarray(q.convert('RGB'),dtype=np.uint16).reshape(-1,3)>>3
 return np.unique((values[:,0]|values[:,1]<<5|values[:,2]<<10)|32768)

def nearest(words,palette,start):
 lut=np.zeros(32768,dtype='u1');targets=rgb(palette).astype(np.int32)
 for first in range(0,32768,512):
  src=rgb(np.arange(first,min(32768,first+512))).astype(np.int32)
  distance=((src[:,None,:]-targets[None,:,:])**2).sum(axis=2)
  lut[first:first+len(src)]=(distance.argmin(axis=1)+start).astype('u1')
 return lut

def decode_background(path):
 b=path.read_bytes();magic,w,h,n=struct.unpack_from('<4sHHI',b);assert magic==b'KHB1'and(w,h)==(256,192)and n==len(b)-12
 packet=b[12:];bits,mode,n=struct.unpack_from('<BBH',packet)
 if mode:assert mode==1 and bits==16 and n==0;raw=packet[4:]
 elif bits==16:assert n==0;raw=unlz(packet[4:])
 else:
  assert bits in(4,8)and n<=1<<bits
  pal=np.frombuffer(packet,dtype='<u2',count=n,offset=4);indices=np.frombuffer(unlz(packet[4+((n*2+3)&~3):]),dtype='u1')
  if bits==4:indices=np.stack((indices&15,indices>>4),axis=1).reshape(-1)
  raw=pal[indices].astype('<u2').tobytes()
 a=np.frombuffer(raw,dtype='<u2');assert len(a)==49152 and np.all(a&32768)
 return a.reshape(192,256)

def patches(path):
 b=path.read_bytes();magic,n,words=struct.unpack_from('<4sII',b);assert magic==b'KFH2'and len(b)==12+n*16+words*2
 data=np.frombuffer(b,dtype='<u2',offset=12+n*16);result=[]
 for i in range(n):
  off,w,h,x,y,r,f=struct.unpack_from('<IHHhhHH',b,12+i*16);a=np.zeros((h,w),dtype='<u2');at=off
  for row in range(h):
   col=0
   while True:
    skip,run=map(int,data[at:at+2]);at+=2
    if not run:break
    col+=skip;assert col+run<=w and at+run<=len(data)
    a[row,col:col+run]=data[at:at+run];assert np.all(a[row,col:col+run]&32768)
    col+=run;at+=run
  result.append((a,x,y,r,f))
 return result

def encode_patches(items,lut):
 records=[];data=bytearray()
 for a,x,y,r,f in items:
  records.append(struct.pack('<IHHhhHH',len(data),a.shape[1],a.shape[0],x,y,r,f))
  for row in a:
   col=cursor=0
   while col<len(row):
    if not row[col]&32768:col+=1;continue
    first=col
    while col<len(row)and row[col]&32768:col+=1
    data.extend(struct.pack('<HH',first-cursor,col-first));data.extend(lut[row[first:col]&32767].tobytes());cursor=col
   data.extend(bytes(4))
 return struct.pack('<4sIII',b'KHU8',1,len(records),len(data))+b''.join(records)+data

def decode_patches(blob):
 magic,v,n,size=struct.unpack_from('<4sIII',blob);assert magic==b'KHU8'and v==1 and len(blob)==16+n*16+size
 result=[];base=16+n*16
 for i in range(n):
  off,w,h,x,y,r,f=struct.unpack_from('<IHHhhHH',blob,16+i*16);a=np.zeros((h,w),dtype='u1');at=base+off
  for row in range(h):
   col=0
   while True:
    skip,run=struct.unpack_from('<HH',blob,at);at+=4
    if not run:break
    col+=skip;assert col+run<=w and at+run<=len(blob)
    a[row,col:col+run]=np.frombuffer(blob,dtype='u1',count=run,offset=at);assert np.all(a[row,col:col+run])
    col+=run;at+=run
  result.append((a,x,y,r,f))
 return result

def error(source,decoded):
 delta=rgb(source).astype(np.float64)-rgb(decoded).astype(np.float64);mse=float(np.mean(delta*delta))
 return {'psnr_db':None if not mse else round(10*math.log10(255**2/mse),3),'rmse_rgb8':round(math.sqrt(mse),3),'pixels':int(np.size(source))}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir;out.mkdir(parents=True,exist_ok=False)
 source=a.source_dir
 items=patches(source/'hud_bottom.bin');font=np.unique(np.concatenate([a[a&32768!=0]for a,x,y,r,f in items if r in(14,16,17)]));assert len(font)<128
 opaque=np.concatenate([a[a&32768!=0]for a,x,y,r,f in items]);other=quantize(opaque,127-len(font));pal=np.zeros(256,dtype='<u2');hud=np.concatenate((font,np.setdiff1d(other,font)));assert len(hud)<=127;pal[1:1+len(hud)]=hud
 lut=nearest(opaque,hud,1);packet=encode_patches(items,lut);(out/'hud.nhp').write_bytes(packet);decoded=decode_patches((out/'hud.nhp').read_bytes());allbefore=[];allafter=[];font_pixels=0
 for (orig,x,y,r,f),(ids,xx,yy,rr,ff)in zip(items,decoded):
  assert(x,y,r,f)==(xx,yy,rr,ff)and orig.shape==ids.shape
  mask=(orig&32768)!=0;assert np.array_equal(mask,ids!=0);assert np.all(ids[mask]<128)
  sampled=pal[ids];assert np.array_equal(ids[mask],lut[orig[mask]&32767])
  if r in(14,16,17):assert np.array_equal(orig,sampled);font_pixels+=int(mask.sum())
  allbefore.append(orig[mask]);allafter.append(sampled[mask])
 hud_quality=error(np.concatenate(allbefore),np.concatenate(allafter));rows=[]
 for name in('jungle','ice','factory','fantasy'):
  path=source/'hud_backgrounds'/(name+'.bin');original=decode_background(path);colors=quantize(original,128);palette=pal.copy();palette[128:128+len(colors)]=colors
  backlut=nearest(original,colors,128);indices=backlut[original&32767];assert np.all(indices>=128)
  encoded=bytes(lz10(indices.tobytes()));blob=struct.pack('<4sHHI',b'KHB8',256,192,len(encoded))+palette.tobytes()+encoded;dest=out/(name+'.nbh');dest.write_bytes(blob)
  saved=dest.read_bytes();magic,w,h,n=struct.unpack_from('<4sHHI',saved);assert magic==b'KHB8'and(w,h)==(256,192)and n==len(saved)-524
  savedpal=np.frombuffer(saved,dtype='<u2',count=256,offset=12);savedids=np.frombuffer(unlz(saved[524:]),dtype='u1').reshape(192,256);assert np.array_equal(savedids,indices);assert np.array_equal(savedpal[:128],pal[:128])
  recovered=savedpal[savedids];preview=recovered.copy()
  # Representative composition only; runtime state/layout remains in hud.c.
  selected={(0,0),(15,0),(11,0),(8,4),(9,2)}|{(r,0)for r in range(2,8)}
  for ids,x,y,r,f in decoded:
   if(r,f)not in selected:continue
   l=max(0,x);t=max(0,y);right=min(256,x+ids.shape[1]);bottom=min(192,y+ids.shape[0])
   if l>=right or t>=bottom:continue
   region=ids[t-y:bottom-y,l-x:right-x];target=preview[t:bottom,l:right];mask=region!=0;target[mask]=savedpal[region[mask]]
  x=124
  for digit in(1,2,3,4):
   ids=next(row[0]for row in decoded if row[3:]==(17,digit));right=min(256,x+ids.shape[1]);part=ids[:,:right-x];target=preview[33:33+ids.shape[0],x:right];mask=part!=0;target[mask]=savedpal[part[mask]];x=right
  Image.fromarray(rgb(preview)).save(out/(name+'-preview.png'))
  rows.append({'world':name,'source_bytes':path.stat().st_size,'bytes':len(blob),'background_colors':len(colors),'quality':error(original,recovered),'sha256':hashlib.sha256(blob).hexdigest()})
 report={'scope':__doc__,'patches':len(items),'hud_colors':len(hud),'font_colors_exact':len(font),'font_pixels_exact':font_pixels,'alpha_exact':True,'hud_quality':hud_quality,'hud_source_bytes':(source/'hud_bottom.bin').stat().st_size,'hud_bytes':len(packet),'backgrounds':rows,'visible_framebuffer_bytes':49152,'prior_rgb555_framebuffer_bytes':98304,'limits':['Asset compilation only; runtime presentation and hardware behavior are checked separately.','HUD and background colors are quantized separately, fonts remain exact.','Preview is a representative composition, not complete runtime layout acceptance.']}
 report['source_total_bytes']=report['hud_source_bytes']+sum(r['source_bytes']for r in rows);report['staged_total_bytes']=len(packet)+sum(r['bytes']for r in rows)
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
