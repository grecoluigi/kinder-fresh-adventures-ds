#!/usr/bin/env python3
"""Losslessly decode WESTKA W01 RGB565 RLE; source files remain untouched."""
from pathlib import Path
import argparse, hashlib, json, struct, wave
from collections import Counter
from PIL import Image, ImageDraw

def decode_w01(data):
    assert data[4:40].startswith(b'WESTKA Animation/Sprite File V 1.0')
    assert struct.unpack_from('<I',data,0)[0]==277
    assert struct.unpack_from('<H',data,277)[0]==16
    count=struct.unpack_from('<H',data,279)[0]
    first,compression=struct.unpack_from('<II',data,1053)
    assert compression==2
    key=struct.unpack_from('<H',data,1061)[0]
    offset=first
    offsets=[]
    for index in range(count):
        offsets.append(offset)
        kind,w,h,end,p=struct.unpack_from('<HHHII',data,offset)
        assert kind==2 and p==offset+23 and w>0 and h>0
        metadata=data[offset+14:offset+23]
        pixels=[]
        while len(pixels)<w*h:
            n=struct.unpack_from('<h',data,p)[0];p+=2
            assert n!=0
            if n>0:
                pixels.extend([struct.unpack_from('<H',data,p)[0]]*n);p+=2
            else:
                pixels.extend(struct.unpack_from('<'+'H'*(-n),data,p));p+=(-n)*2
        assert len(pixels)==w*h and p==end
        rgba=bytearray()
        for color in pixels:
            r=(color>>11)&31;g=(color>>5)&63;b=color&31
            rgba.extend(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2),0 if color==key else 255))
        image=Image.frombytes('RGBA',(w,h),bytes(rgba))
        yield image,dict(index=index,width=w,height=h,frame_offset=offset,data_end=end,metadata_hex=metadata.hex(),color_key_rgb565=key,x=struct.unpack_from('<hh',data,len(data)-count*8+index*4)[0],y=struct.unpack_from('<hh',data,len(data)-count*8+index*4)[1])
        offset=end
    assert offset==len(data)-count*8
    assert list(struct.unpack_from('<'+'I'*count,data,len(data)-count*4))==offsets
    # Tail contains signed16 x/y pairs then u32 frame offsets.

def contact(items,path,columns=8):
    cellw,cellh=160,150
    out=Image.new('RGB',(columns*cellw,((len(items)+columns-1)//columns)*cellh),'#cccccc')
    draw=ImageDraw.Draw(out)
    for i,(label,image) in enumerate(items):
        x=(i%columns)*cellw;y=(i//columns)*cellh
        im=image.copy();im.thumbnail((150,115))
        out.paste(im,(x+(cellw-im.width)//2,y),im if im.mode=='RGBA' else None)
        draw.text((x+4,y+117),label[:25],fill='black')
        draw.text((x+4,y+132),f'{image.width} x {image.height}',fill='black')
    out.save(path)

def main():
    args=argparse.ArgumentParser();args.add_argument('--source',default='original/extracted/ausf_hrende_Dateien/GData');args.add_argument('--out',default='generated/assets');a=args.parse_args()
    root=Path(a.source);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    inventory=[];firsts=[];menus=[]
    for source in sorted(root.rglob('*')):
        if not source.is_file():continue
        rel=source.relative_to(root);data=source.read_bytes()
        item=dict(source=str(rel),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        if source.suffix.lower()=='.w01':
            item['format']='WESTKA W01 RGB565 signed-count RLE';item['frames']=[]
            for image,meta in decode_w01(data):
                target=out/'frames'/rel.with_suffix('')/f'{meta["index"]:03}.png';target.parent.mkdir(parents=True,exist_ok=True);image.save(target)
                meta['png']=str(target);item['frames'].append(meta)
                if meta['index']==0:
                    firsts.append((source.stem,image))
                    if 'Interface' in rel.parts:menus.append((source.stem,image))
        elif source.suffix.lower() in ['.bmp','.gif','.ddf']:
            with Image.open(source) as im:
                image=im.convert('RGBA');target=out/'pictures'/rel.with_suffix('.png');target.parent.mkdir(parents=True,exist_ok=True);image.save(target)
                item.update(format=im.format,width=im.width,height=im.height,png=str(target))
                menus.append((source.stem,image))
        elif source.suffix.lower()=='.wav':
            with wave.open(str(source)) as w:
                item.update(format='WAVE '+w.getcomptype(),channels=w.getnchannels(),bits=w.getsampwidth()*8,sample_rate=w.getframerate(),samples=w.getnframes(),duration_seconds=w.getnframes()/w.getframerate())
        inventory.append(item)
    (out/'inventory.json').write_text(json.dumps(inventory,indent=2))
    contact(firsts,out/'sprites_contact.png');contact(menus,out/'menu_contact.png',5)
    print(json.dumps(dict(files=len(inventory),sprites=len(firsts),frames=sum(len(i.get('frames',[])) for i in inventory),wav=sum(i.get('format','').startswith('WAVE') for i in inventory)),indent=2))
if __name__=='__main__':main()
