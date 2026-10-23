"""Compile fixed-palette 8x8 DS scenery pages from offline shared-palette inputs.
Additional color quantization is measured; alpha, cell layout and painter-owner
metadata are retained. No runtime renderer or private workspace assets are used.
"""
from pathlib import Path
import argparse,hashlib,json,math,struct
import numpy as np
from PIL import Image
from scipy.cluster.vq import kmeans2
from tile_storage import unlz,lz10
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--map',action='append');a=p.parse_args();out=a.output_dir.resolve();out.mkdir(exist_ok=False);rows=[]
def rgb(v):
 c=np.stack((v&31,(v>>5)&31,(v>>10)&31),axis=-1);return ((c<<3)|(c>>2)).astype('u1')
def rgba(v):return np.concatenate((rgb(v),np.where(v[...,None]&32768,255,0).astype('u1')),axis=-1)
for path in sorted(a.source_dir.glob('*.qsc')):
 if a.map and path.stem not in a.map:continue
 data=path.read_bytes();magic,version,n,colors,records,paloff,payload,flags=struct.unpack_from('<4s7I',data);assert magic==b'KQSC'and version==2 and flags==1
 palette=np.frombuffer(data,dtype='<u2',count=colors,offset=paloff);tiles=[]
 for i in range(n):
  offset,word=struct.unpack_from('<II',data,records+8*i);ids=np.frombuffer(unlz(data[payload+offset:payload+offset+(word&65535)]),dtype='u1');assert len(ids)==256;tiles.append(palette[(word>>16)*256+ids.astype(np.uint32)].reshape(16,16))
 index=path.with_suffix('.index').read_bytes();_,w,h,nc,npairs,_,_=struct.unpack_from('<4sHHIIHH',index);pairs=list(struct.iter_unpack('<HH',index[20+nc*12:]));assert len(pairs)==npairs
 final={};owners={};ordinal=0
 for kind,first,count in struct.iter_unpack('<III',index[20:20+nc*12]):
  if kind:continue
  ordinal+=1;assert ordinal<256
  for cell,tile in pairs[first:first+count]:
   assert cell<w*h
   if cell not in final:final[cell]=np.zeros((16,16),dtype='<u2');owners[cell]=np.zeros((16,16),dtype='u1')
   mask=(tiles[tile]&32768)!=0;final[cell][mask]=tiles[tile][mask];owners[cell][mask]=ordinal
 # Build unique final8x8 rasters, separately preserving each cell's owner mask.
 unique={bytes(128):0};original=[np.zeros(64,dtype='<u2')];cells={}
 for cell,image in sorted(final.items()):
  ids=[]
  for y,x in [(0,0),(0,8),(8,0),(8,8)]:
   raw=image[y:y+8,x:x+8].tobytes()
   if raw not in unique:unique[raw]=len(original);original.append(np.frombuffer(raw,dtype='<u2'))
   ids.append(unique[raw])
  cells[cell]=ids
 pixels=np.stack(original);opaque=(pixels&32768)!=0;present=np.flatnonzero(np.any(opaque,axis=1));groups=min(16,len(present));assert groups
 assignment=np.zeros(len(pixels),dtype='u1');coarse=((pixels&31)>>3)+((((pixels>>5)&31)>>3)<<2)+((((pixels>>10)&31)>>3)<<4)
 features=np.zeros((len(pixels),64),dtype=np.float32)
 for i in present:features[i]=np.sqrt(np.bincount(coarse[i,opaque[i]],minlength=64)/int(opaque[i].sum()))
 if groups>1:_,labels=kmeans2(features[present],groups,iter=30,minit='++',seed=22050);assignment[present]=labels
 palettes=np.zeros((16,256),dtype='<u2');encoded=np.zeros((len(pixels),64),dtype='u1')
 for group in range(groups):
  selected=np.flatnonzero(assignment==group);subset=pixels[selected];mask=opaque[selected];values=subset[mask]&32767
  if not values.size:continue
  values_unique=np.unique(values);source_rgb=rgb(values_unique).astype(np.int32)
  if len(values_unique)<=255:packed=values_unique.copy()
  else:
   image=rgb(values);padding=(-len(image))%256
   if padding:image=np.concatenate((image,np.repeat(image[-1:],padding,axis=0)))
   quant=Image.fromarray(image.reshape(-1,256,3)).quantize(colors=191,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
   colors=(np.asarray(quant.getpalette(),dtype=np.uint16).reshape(-1,3)[:191]*31+127)//255
   packed=np.unique((colors[:,0]|colors[:,1]<<5|colors[:,2]<<10).astype('<u2'))
   delta=source_rgb[:,None,:]-rgb(packed)[None,:,:].astype(np.int32);minimum=np.sum(delta*delta,axis=-1).min(axis=1)
   while len(packed)<255 and int(minimum.max()):
    far=int(np.argmax(minimum));packed=np.append(packed,values_unique[far]);delta=source_rgb-source_rgb[far];minimum=np.minimum(minimum,np.sum(delta*delta,axis=1))
  palettes[group,1:1+len(packed)]=packed|32768;target=rgb(packed).astype(np.int32);lut=np.zeros(32768,dtype='u1')
  for start in range(0,len(values_unique),512):
   delta=source_rgb[start:start+512,None,:]-target[None,:,:];lut[values_unique[start:start+512]]=np.argmin(np.sum(delta*delta,axis=-1),axis=1)+1
  encoded[selected]=np.where(mask,lut[subset&32767],0)
 converted=palettes[assignment[:,None],encoded];assert np.array_equal(converted&32768,pixels&32768)
 patterns=[bytes(64)];pattern_lookup={patterns[0]:0};references=[]
 for i,tile in enumerate(encoded):
  raw=tile.tobytes()
  if raw not in pattern_lookup:pattern_lookup[raw]=len(patterns);patterns.append(raw)
  references.append(pattern_lookup[raw]|(int(assignment[i])<<28)if np.any(tile)else 0)
 page_width=(w*2+15)//16;page_height=(h*2+15)//16;pages=np.zeros((page_height,page_width,16,16),dtype='<u4')
 for cell,ids in cells.items():
  x=(cell%w)*2;y=(cell//w)*2
  for k,tile in enumerate(ids):
   xx=x+(k&1);yy=y+(k>>1);pages[yy//16,xx//16,yy%16,xx%16]=references[tile]
 payload_data=bytearray();tile_records=[];page_records=[];dedup={}
 for chunks,table in [(patterns,tile_records),([page.tobytes()for page in pages.reshape(-1,16,16)],page_records)]:
  for raw in chunks:
   key=(len(raw),raw)
   if key not in dedup:
    packet=bytes(lz10(raw));assert unlz(packet)==raw;dedup[key]=(len(payload_data),len(packet));payload_data.extend(packet);payload_data.extend(bytes(-len(payload_data)%4))
   table.append(dedup[key])
 paloff=48;tilerec=paloff+8192;pagerec=tilerec+len(patterns)*8;payloff=pagerec+len(page_records)*8
 header=struct.pack('<4s11I',b'KNTB',1,w*2,h*2,len(patterns),16,len(page_records),paloff,tilerec,pagerec,payloff,0)
 result=header+palettes.tobytes()+b''.join(struct.pack('<II',*v)for v in tile_records+page_records)+payload_data
 dest=out/(path.stem+'.ntb');dest.write_bytes(result)
 # Decode serialized records and page placement independently of builder refs.
 blob=dest.read_bytes();magic,version,ww,hh,nt,ng,npg,pa,tr,pr,po,flags=struct.unpack_from('<4s11I',blob);assert magic==b'KNTB'and version==1 and (ww,hh)==(w*2,h*2)and ng==16 and not flags
 decoded_palette=np.frombuffer(blob,dtype='<u2',count=4096,offset=pa).reshape(16,256);decoded_tiles=[];decoded_pages=[]
 for at,count,target,size in [(tr,nt,decoded_tiles,64),(pr,npg,decoded_pages,1024)]:
  for i in range(count):
   off,length=struct.unpack_from('<II',blob,at+i*8);raw=unlz(blob[po+off:po+off+length]);assert len(raw)==size;target.append(raw)
 checks=0
 for cell,ids in cells.items():
  x=(cell%w)*2;y=(cell//w)*2
  for k,tile in enumerate(ids):
   xx=x+(k&1);yy=y+(k>>1);page=decoded_pages[(yy//16)*page_width+xx//16];word=struct.unpack_from('<I',page,((yy%16)*16+xx%16)*4)[0];bank=word>>28;pattern=word&0x0fffffff;assert pattern<nt
   actual=decoded_palette[bank,np.frombuffer(decoded_tiles[pattern],dtype='u1')];assert np.array_equal(actual,converted[tile]);assert np.array_equal(actual&32768,pixels[tile]&32768);checks+=64
 owner_blob=b''.join(struct.pack('<I',cell)+owners[cell].tobytes()for cell in sorted(owners));(out/(path.stem+'.owners')).write_bytes(owner_blob)
 for i,cell in enumerate(sorted(owners)):assert owner_blob[i*260+4:(i+1)*260]==owners[cell].tobytes()
 difference=rgb(pixels[opaque]).astype(np.int32)-rgb(converted[opaque]).astype(np.int32);errors=np.sum(difference*difference,axis=-1);mse=float(errors.sum()/(len(errors)*3))
 # Select a useful occupied region for comparison, with no parallax/actors.
 cx=min(max(0,w*16-256),(min(cells)%w)*16);cy=min(max(0,h*16-192),(min(cells)//w)*16)
 previews=[]
 for collection in [pixels,converted]:
  canvas=np.zeros((192,256),dtype='<u2')
  for cell,ids in cells.items():
   x=(cell%w)*16-cx;y=(cell//w)*16-cy
   for k,tile in enumerate(ids):
    xx=x+(k&1)*8;yy=y+(k>>1)*8;l=max(0,xx);r=min(256,xx+8);t=max(0,yy);b=min(192,yy+8)
    if l<r and t<b:canvas[t:b,l:r]=collection[tile].reshape(8,8)[t-yy:b-yy,l-xx:r-xx]
  previews.append(canvas)
 Image.fromarray(rgba(previews[0])).save(out/(path.stem+'-current.png'));Image.fromarray(rgba(previews[1])).save(out/(path.stem+'-native.png'))
 row={'map':path.stem,'native_file_bytes':len(result),'palette_bytes':8192,'pattern_count':nt,'page_count':npg,'original_unique_final_tiles':len(pixels),'source_atlas_bytes':len(data),'source_index_bytes':len(index),'source_atlas_sha256':hashlib.sha256(data).hexdigest(),'native_sha256':hashlib.sha256(result).hexdigest(),'alpha_exact':True,'painter_owners_exact':True,'serialized_placement_pixels_checked':checks,'additional_rgb8_psnr_db':None if not mse else round(10*math.log10(255*255/mse),3),'additional_rgb8_rmse':round(math.sqrt(mse),3),'additional_max_pixel_error':round(math.sqrt(int(errors.max())),3),'preview_camera':[cx,cy]};rows.append(row);print(json.dumps(row),flush=True)
report={'scope':__doc__,'maps':rows,'limits':['Color-changing study relative to already quantized current assets, not original Windows art.','Error weights unique final8x8rasters once; placement alpha/color reconstruction is verified separately.','Fixed16palettes/map avoid per-view palette repacking; global pattern IDs require a bounded VRAM tile cache.','16x16tile-map pages decode to1024bytes and graphics packets to64bytes; full-map decompression is unnecessary.','Painter masks are exact sidecar metadata for prototyping, not a solution to hardware priority/occlusion by themselves.','No runtime renderer, VRAM ownership changes, gameplay integration or hardware speed claim.']};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
