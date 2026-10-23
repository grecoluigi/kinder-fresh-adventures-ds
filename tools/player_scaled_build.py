"""Offline uniform8/25 player rasters anchored at the original animation/body origin."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import struct
import numpy as np
from PIL import Image
from tile_storage import packet
from decoded_assets import DecodedAssets

def ceil_div(a,b):return -((-a)//b)

def raster(rgb,fx,fy,facing):
    h,w=rgb.shape;left=fx if facing else -fx-w
    source=rgb if facing else rgb[:,::-1]
    x=ceil_div(16*left-25,50);y=ceil_div(16*fy-25,50)
    width=max(1,ceil_div(16*(left+w)-25,50)-x)
    height=max(1,ceil_div(16*(fy+h)-25,50)-y)
    # Same 8/25 lattice as centered sampling; premultiplied Lanczos replaces the
    # single source tap and the 1-bit alpha is restored at half coverage.
    pad=12;rgba=np.zeros((h+2*pad,w+2*pad,4),dtype=np.uint8);inner=rgba[pad:pad+h,pad:pad+w]
    for channel,shift in enumerate((0,5,10)):inner[...,channel]=((source>>shift)&31)*255//31
    inner[...,3]=np.where(source&0x8000,255,0)
    box=((x*25/8)-left+pad,(y*25/8)-fy+pad,((x+width)*25/8)-left+pad,((y+height)*25/8)-fy+pad)
    a=np.asarray(Image.fromarray(rgba,'RGBA').convert('RGBa').resize((width,height),Image.Resampling.LANCZOS,box=box),dtype=np.float64)
    c=np.clip(np.rint(a[...,:3]*31/np.maximum(a[...,3:],1)),0,31).astype(np.uint16)
    pixels=np.where(a[...,3]>=128,c[...,0]|(c[...,1]<<5)|(c[...,2]<<10)|0x8000,0).astype('<u2')
    # Filtering adds edge colors. Keep the frame (or, for direct-color frames,
    # each 32-row GPU strip) within the 4/8-bit palette class its
    # centered-sample raster had, so page formats never grow.
    xs=((2*(x+np.arange(width))+1)*25)//16-left
    ys=((2*(y+np.arange(height))+1)*25)//16-fy
    valid=(ys[:,None]>=0)&(ys[:,None]<h)&(xs[None,:]>=0)&(xs[None,:]<w)
    nearest=np.where(valid,source[np.clip(ys,0,h-1)[:,None],np.clip(xs,0,w-1)[None,:]],0)
    bands=[(0,height)] if len(np.unique(nearest[nearest!=0]))<=255 else [(top,top+32) for top in range(0,height,32)]
    for top,end in bands:
        band=pixels[top:end];before=len(np.unique(nearest[top:end][nearest[top:end]!=0]))
        limit=15 if before<=15 else 255 if before<=255 else None
        if limit and len(np.unique(band[band!=0]))>limit:band[band!=0]=quantize555(band[band!=0],limit)
    return pixels,x,y

def quantize555(words,count):
    rgb=np.stack([((words>>shift)&31)*255//31 for shift in (0,5,10)],axis=-1).astype(np.uint8)
    q=Image.fromarray(rgb.reshape(-1,1,3),'RGB').quantize(colors=count,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    c=(np.asarray(q.convert('RGB'),dtype=np.uint16).reshape(-1,3)*31+127)//255
    return c[:,0]|(c[:,1]<<5)|(c[:,2]<<10)|0x8000

def build(decoded,out):
    out.mkdir(parents=True,exist_ok=False)
    assets=DecodedAssets(decoded);inventory=list(assets.inventory.values());manifest=[]
    for name in ('PINGUIN','MILCHSCHNITTE'):
        asset=next(a for a in inventory if a['source']=='Animation/'+name+'.W01')
        records=[];payload=bytearray();lookup={};modes=Counter();max_pixels=0;source_pixels=0
        for f in asset['frames']:
            rgba=np.array(assets.image(f),dtype=np.uint16)
            rgb=np.where(rgba[:,:,3],(rgba[:,:,0]>>3)|((rgba[:,:,1]>>3)<<5)|((rgba[:,:,2]>>3)<<10)|0x8000,0).astype('<u2')
            h,w=rgb.shape;source_pixels+=w*h
            record=bytearray(struct.pack('<HHhh',w,h,f['x'],f['y']))
            for facing in (0,1):
                pixels,x,y=raster(rgb,f['x'],f['y'],facing);raw=pixels.tobytes();key=raw
                if key not in lookup:
                    packed,bits=packet(raw);lookup[key]=(len(payload),len(packed));modes[bits]+=1
                    payload.extend(packed);payload.extend(bytes(-len(payload)%4))
                offset,size=lookup[key];height,width=pixels.shape
                record.extend(struct.pack('<IIHHhh',offset,size,width,height,x,y));max_pixels=max(max_pixels,pixels.size)
            assert len(record)==40;records.append(record)
        data=b'KFP3'+struct.pack('<I',len(records))+b''.join(records)+payload
        path=out/(name.lower()+'.frames');path.write_bytes(data)
        manifest.append({'character':name,'format':'KFP3','frames':len(records),'facing_variants':2,
                         'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                         'max_frame_bytes':max_pixels*2,'source_pixels':source_pixels,
                         'stored_packets':len(lookup),'packet_modes':dict(modes),
                         'scaling':'Uniform8/25 premultiplied Lanczos around animation origin, 1-bit alpha at half coverage; both facings baked',
                         'color':'Adaptive4/8-bit exact palettes or RGB555; no color quantization'})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.assets,a.output)

if __name__=='__main__':main()
