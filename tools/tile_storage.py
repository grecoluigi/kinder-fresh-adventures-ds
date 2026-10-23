"""Lossless adaptive4/8/16-bit indexed32x32 tile banks, with exact tile deduplication."""
from pathlib import Path
import ast
import argparse
import hashlib
import json
import struct
from collections import defaultdict,deque
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
tree=ast.parse((ROOT/'tools/player_build.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='lz10'],type_ignores=[]),'lz10','exec'))

def packet(raw):
    values=np.frombuffer(raw,dtype='<u2')
    palette,inverse=np.unique(values,return_inverse=True)
    bits=4 if len(palette)<=16 else 8 if len(palette)<=256 else 16
    direct=struct.pack('<BBH',16,0,0)+lz10(raw)
    if bits==16:return direct,16
    indices=inverse.astype('u1')
    if bits==4:
        if len(indices)&1:indices=np.concatenate((indices,np.zeros(1,dtype='u1')))
        indices=indices[::2]|indices[1::2]<<4
    colors=palette.astype('<u2').tobytes()
    encoded=struct.pack('<BBH',bits,0,len(palette))+colors+bytes(-len(colors)%4)+lz10(indices.tobytes())
    # Palette overhead can exceed the saving on a very simple RGB555 tile.
    return (encoded,bits) if len(encoded)<len(direct) else (direct,16)

def pack_bank(raw):
    assert len(raw)==512*2048
    lookup={};records=[];payload=bytearray();modes={4:0,8:0,16:0}
    for i in range(512):
        tile=raw[i*2048:(i+1)*2048]
        if tile not in lookup:
            encoded,bits=packet(tile);modes[bits]+=1
            lookup[tile]=(len(payload),len(encoded));payload.extend(encoded);payload.extend(bytes(-len(payload)%4))
        records.append(lookup[tile])
    data=b'KFT1'+struct.pack('<I',512)+b''.join(struct.pack('<II',*r)for r in records)+payload
    return data,{'unique_tiles':len(lookup),'stored_modes':modes,'raw_bytes':len(raw),'bytes':len(data),'original_rgb555_sha256':hashlib.sha256(raw).hexdigest()}

def unlz(data):
    assert data[0]==16
    size=int.from_bytes(data[1:4],'little');result=bytearray();i=4
    while len(result)<size:
        flags=data[i];i+=1
        for bit in (128,64,32,16,8,4,2,1):
            if len(result)==size:break
            if flags&bit:
                word=int.from_bytes(data[i:i+2],'big');i+=2
                for _ in range((word>>12)+3):result.append(result[-((word&4095)+1)])
            else:result.append(data[i]);i+=1
    assert len(result)==size and i==len(data)
    return bytes(result)

def unpack_packet(encoded):
    bits,unused,colors=struct.unpack_from('<BBH',encoded);assert unused==0
    if bits==16:
        assert colors==0;raw=unlz(encoded[4:]);assert len(raw)==2048;return raw
    assert bits in (4,8)and 0<colors<=1<<bits
    prefix=4+((colors*2+3)&~3)
    palette=np.frombuffer(encoded,dtype='<u2',count=colors,offset=4)
    indices=np.frombuffer(unlz(encoded[prefix:]),dtype='u1')
    if bits==4:indices=np.stack((indices&15,indices>>4),axis=1).reshape(1024)
    assert len(indices)==1024
    return palette[indices].astype('<u2').tobytes()

def unpack_bank(data):
    assert data[:4]==b'KFT1'and struct.unpack_from('<I',data,4)[0]==512
    tiles=[]
    for i in range(512):
        offset,size=struct.unpack_from('<II',data,8+i*8)
        tiles.append(unpack_packet(data[4104+offset:4104+offset+size]))
    return b''.join(tiles)

def convert_atlases():
    backup=Path('/tmp/kinder-atlases-before-indexed');backup.mkdir(exist_ok=True);rows=[]
    for path in sorted((ROOT/'ds/nitrofs/composite').glob('*.atlas')):
        before=path.read_bytes()
        if before[:4]==b'KFC3':
            if (backup/path.name).exists():before=(backup/path.name).read_bytes()
            else:
                count=struct.unpack_from('<I',before,4)[0];base=8+count*8;records=[];payload=bytearray()
                for tile in range(count):
                    offset,size=struct.unpack_from('<II',before,8+tile*8)
                    packed=lz10(unpack_packet(before[base+offset:base+offset+size]))
                    records.append((len(payload),len(packed)));payload.extend(packed)
                before=b'KFC2'+struct.pack('<I',count)+b''.join(struct.pack('<II',*r)for r in records)+payload
                (backup/path.name).write_bytes(before)
        else:(backup/path.name).write_bytes(before)
        assert before[:4]==b'KFC2';count=struct.unpack_from('<I',before,4)[0]
        start=8+count*8;records=[];payload=bytearray();modes={4:0,8:0,16:0}
        for tile in range(count):
            offset,size=struct.unpack_from('<II',before,8+tile*8)
            raw=unlz(before[start+offset:start+offset+size]);assert len(raw)==2048
            encoded,bits=packet(raw);modes[bits]+=1
            records.append((len(payload),len(encoded)));payload.extend(encoded)
        data=b'KFC3'+struct.pack('<I',count)+b''.join(struct.pack('<II',*r)for r in records)+payload
        path.write_bytes(data);rows.append({'file':path.name,'tiles':count,'before_bytes':len(before),'bytes':len(data),'stored_modes':modes,'original_pack_sha256':hashlib.sha256(before).hexdigest()})
    result={'method':__doc__,'atlases':rows,'before_bytes':sum(r['before_bytes']for r in rows),'after_bytes':sum(r['bytes']for r in rows)}
    (ROOT/'research/rendering/atlas-storage-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='atlases'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--atlases-only',action='store_true');args=parser.parse_args()
    if args.atlases_only:convert_atlases();raise SystemExit
    backup=Path('/tmp/kinder-tiles-before-indexed');backup.mkdir(exist_ok=True)
    rows=[]
    for path in sorted((ROOT/'ds/nitrofs/scenes').glob('*.tiles')):
        raw=path.read_bytes()
        if raw[:4]==b'KFT1':
            raw=(backup/path.name).read_bytes()if (backup/path.name).exists()else unpack_bank(raw)
            (backup/path.name).write_bytes(raw)
        else:(backup/path.name).write_bytes(raw)
        data,stats=pack_bank(raw);path.write_bytes(data);rows.append({'file':path.name,**stats})
    result={'method':__doc__,'banks':rows,'before_bytes':sum(r['raw_bytes']for r in rows),'after_bytes':sum(r['bytes']for r in rows)}
    (ROOT/'research/rendering/tile-storage-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k!='banks'}))
