"""Lossless indexed/direct-color DS GPU texture-page encoding."""
from dataclasses import dataclass
import hashlib
import numpy as np

def sha(data):return hashlib.sha256(data).hexdigest()

def page_regions(image,chunk_width,strip_height,trim_rows):
 h,w=image.shape;regions=[]
 for sy in range(0,h,strip_height):
  sh=min(strip_height,h-sy)
  for chunk_x in range(0,w,chunk_width):
   block=image[sy:sy+sh,chunk_x:min(w,chunk_x+chunk_width)]
   rows=np.flatnonzero(np.any(block&32768,axis=1))
   if not len(rows):continue
   columns=np.flatnonzero(np.any(block&32768,axis=0))
   first_row=int(rows[0]) if trim_rows else 0
   last_row=int(rows[-1])+1 if trim_rows else sh
   page_sh=last_row-first_row;page_ph=8
   while page_ph<page_sh:page_ph*=2
   sx=chunk_x+int(columns[0]);sw=int(columns[-1]-columns[0]+1);pw=8
   while pw<sw:pw*=2
   assert pw*page_ph<=2048
   regions.append((sx,sy+first_row,sw,page_sh,pw,page_ph))
 return regions

@dataclass
class Page:
 key: str
 texels: bytes
 palette: bytes
 width: int
 height: int
 bits: int
 source_x: int
 source_y: int
 draw_width: int
 opaque: bool
 texture_height: int = 8

class NativePageEncoder:
 def __init__(self,output,strip_height=32,trim_rows=False,adaptive_orientation=False,local_palettes=True):
  assert strip_height in (8,16,32)
  assert not adaptive_orientation or strip_height==32
  self.output=output;self.strip_height=strip_height;self.trim_rows=trim_rows
  self.adaptive_orientation=adaptive_orientation;self.local_palettes=local_palettes
  self.vertical_frames=0;self.artifacts={}
 def encode(self,image,transient=False):
  h,w=image.shape
  normalized=np.where(image&32768,image,0).astype('<u2')
  fullcolors=np.unique(normalized[normalized!=0])
  # A frame-wide palette can be shared by every strip. High-color frames
  # use direct-color strips rather than introducing a lossy reduction.
  bits=4 if len(fullcolors)<=15 else 8 if len(fullcolors)<=255 else 16
  if transient:bits=16
  palette=np.zeros(1<<bits,dtype='<u2') if bits<16 else np.zeros(0,dtype='<u2')
  if bits<16:palette[1:len(fullcolors)+1]=fullcolors&32767
  frame_bits=bits;frame_palette=palette
  pages=[]
  regions=page_regions(normalized,64,self.strip_height,self.trim_rows)
  if self.adaptive_orientation and not transient:
   vertical=page_regions(normalized,32,64,self.trim_rows)
   score=lambda rr:(sum(r[4]*r[5] for r in rr),len(rr))
   if score(vertical)<score(regions):regions=vertical;self.vertical_frames+=1
  for sx,page_sy,sw,page_sh,pw,page_ph in regions:
    pixels=np.zeros((page_ph,pw),dtype='<u2');pixels[:page_sh,:sw]=normalized[page_sy:page_sy+page_sh,sx:sx+sw]
    bits=frame_bits;palette=frame_palette;colors=fullcolors
    if self.local_palettes and not transient and frame_bits==16:
     local=np.unique(pixels[pixels!=0]);local_bits=4 if len(local)<=15 else 8 if len(local)<=255 else 16
     if local_bits<16 and pw*page_ph*local_bits//8+(2<<local_bits)<pw*page_ph*2:
      bits=local_bits;colors=local;palette=np.zeros(1<<bits,dtype='<u2');palette[1:len(colors)+1]=colors&32767
    opaque=True
    if bits==16:texels=pixels.tobytes()
    else:
     flat=pixels.ravel();indices=np.zeros(len(flat),dtype=np.uint8);mask=flat!=0
     indices[mask]=np.searchsorted(colors,flat[mask])+1
     texels=indices.tobytes() if bits==8 else (indices[::2]|(indices[1::2]<<4)).tobytes()
    pbytes=palette.tobytes();key=sha(bytes([bits])+pw.to_bytes(2,'little')+texels+pbytes)
    page=Page(key,texels,pbytes,pw,page_sh,bits,sx,page_sy,sw,opaque,page_ph);pages.append(page)
    if not transient and key not in self.artifacts:
     (self.output/(key+'.tex')).write_bytes(texels)
     if pbytes:(self.output/(sha(pbytes)+'.pal')).write_bytes(pbytes)
     self.artifacts[key]={'key':key,'width':pw,'height':page_ph,'bits':bits,'texel_bytes':len(texels),'palette_bytes':len(pbytes),'texels':key+'.tex','palette':sha(pbytes)+'.pal' if pbytes else None,'decoded_normalized_sha256':sha(pixels.tobytes()),'opaque':opaque}
    # Independent expected source normalization; C decoder verified separately.
    if bits<16:
     raw=np.frombuffer(texels,dtype=np.uint8)
     idx=raw if bits==8 else np.stack((raw&15,raw>>4),axis=1).ravel()
     decoded=palette[idx].copy();decoded[idx!=0]|=32768
     assert decoded.tobytes()==pixels.tobytes()
  return pages
