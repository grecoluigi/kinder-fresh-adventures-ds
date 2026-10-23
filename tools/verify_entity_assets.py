"""Verify enemy/pickup packets, AOM animation ranges, geometry and map records.

Raster bounds are derived independently from the original lattice; expected
pixels come from the shared offline Lanczos raster filter.
"""
from pathlib import Path
import argparse,ctypes as C,hashlib,json,struct,subprocess,tempfile
import numpy as np
from decoded_assets import DecodedAssets
from native_resources import asset_source
from player_scaled_build import raster

ROOT=Path(__file__).resolve().parents[1]
RANGES=('Left','Right','Up','Do','LeftUp','LeftDo','RightUp','RightDo','IdleLeft','IdleRight','IdleUp','IdleDo','IdleLeftUp','IdleLeftDo','IdleRightUp','IdleRightDo','Attack','Freeze','KO')
EXPECTED_ENEMY_IDS={3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,59,200,201,202,210,220,230,231,232,233,76,77,78,83,86,87,60,75,79,80,82,84,85,88,89,265,352,354,355,356,414}

def alignment(script,asset,index):
    frame=asset['frames'][index];zero=asset['frames'][0] if script.get('CorrectAlignToNull') else {'x':0,'y':0}
    return tuple(int(C.c_int16(frame[k]-zero[k]).value) for k in ('x','y'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('decoded-assets','maps','enemies','entities','geometry','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();assets=DecodedAssets(a.decoded_assets)
    scripts={s['ObjNr']:s for s in json.loads((a.maps/'scripts.json').read_text()).values() if 'ObjNr' in s}
    total_frames=variants=checked_pixels=ranges_checked=0
    lattice=np.arange(-16384,16384);centers=np.floor((lattice+.5)*25/8).astype(int)
    with tempfile.TemporaryDirectory(prefix='kinder-entity-assets-')as td:
        work=Path(td);source=work/'codec.c';library=work/'codec.dylib'
        source.write_text('#include "sprite_codec.h"\nint decode(const uint8_t*p,size_t n,uint16_t*d,unsigned count){return sprite_codec_decode(p,n,d,count);}\n')
        subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-dynamiclib','-I'+str(ROOT/'ds/source'),str(source),'-o',str(library)],check=True)
        codec=C.CDLL(str(library));codec.decode.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint];codec.decode.restype=C.c_int
        for kind,path in [('enemies',a.enemies/'enemies.frames'),('pickups',a.entities/'pickups.frames')]:
            data=path.read_bytes();nr,nf,size=struct.unpack_from('<HHI',data,4)
            resource_stride,frame_stride,descriptor=(84,40,8) if kind=='enemies' else (12,48,16)
            assert data[:4]==(b'KFES' if kind=='enemies' else b'KFSP')
            base=12+resource_stride*nr+frame_stride*nf;assert len(data)==base+size
            seen=set();next_frame=0
            for ri in range(nr):
                values=struct.unpack_from('<4H' if kind=='enemies' else '<6H',data,12+ri*resource_stride)
                if kind=='enemies':id,start,n,reference=values
                else:id,start,n,first,last,reference=values
                assert id not in seen;seen.add(id);script=scripts[id];asset=assets.inventory[asset_source(script)]
                assert start==next_frame and n==len(asset['frames']) and reference==script.get('ReferenceSprWidth',0)
                if kind=='enemies':
                    expected=tuple(value for key in RANGES for value in (script.get('StartAnim'+key,0),script.get('EndAnim'+key,0)))
                    assert struct.unpack_from('<38h',data,12+ri*resource_stride+8)==expected
                    ranges_checked+=19
                else:assert(first,last)==(script['StartAnimLeft'],script['EndAnimLeft'])
                for i,frame in enumerate(asset['frames']):
                    rgba=np.asarray(assets.image(frame),dtype=np.uint16)
                    rgb=np.where(rgba[:,:,3],0x8000|(rgba[:,:,0]>>3)|((rgba[:,:,1]>>3)<<5)|((rgba[:,:,2]>>3)<<10),0).astype('<u2')
                    h,w=rgb.shape;fx,fy=alignment(script,asset,i)
                    at=12+resource_stride*nr+(start+i)*frame_stride
                    assert struct.unpack_from('<HHhh',data,at+(0 if kind=='enemies' else 8))==(w,h,fx,fy)
                    for mirror in (0,1):
                        off,bytes_,pw,ph,px,py=struct.unpack_from('<IIHHhh',data,at+descriptor+mirror*16)
                        assert pw and ph and bytes_ and base+off+bytes_<=len(data)
                        left=reference-fx-w if mirror else fx
                        ix=np.flatnonzero((centers>=left)&(centers<left+w));iy=np.flatnonzero((centers>=fy)&(centers<fy+h))
                        if not len(ix):ix=np.array([np.searchsorted(centers,left)])
                        if not len(iy):iy=np.array([np.searchsorted(centers,fy)])
                        assert(pw,ph,px,py)==(len(ix),len(iy),lattice[ix[0]],lattice[iy[0]])
                        expected=raster(rgb,fx-reference if mirror else fx,fy,not mirror)[0]
                        buffer=C.create_string_buffer(data[base+off:base+off+bytes_]);guard=np.full(pw*ph+32,0x1357,dtype='<u2')
                        assert codec.decode(buffer,bytes_,guard[16:].ctypes.data,pw*ph)
                        assert np.all(guard[:16]==0x1357)and np.all(guard[-16:]==0x1357)
                        assert np.array_equal(guard[16:-16].reshape(ph,pw),expected),(kind,id,i,mirror)
                        checked_pixels+=pw*ph;variants+=1
                    total_frames+=1
                next_frame+=n
            assert next_frame==nf and seen==(EXPECTED_ENEMY_IDS if kind=='enemies' else set(range(48,59)))
    geometry=(a.geometry/'objects.geometry').read_bytes();magic,nr,nf=struct.unpack_from('<4sHH',geometry);assert magic==b'KFOG'and len(geometry)==8+nr*8+nf*8
    expected_ids=[id for id,s in sorted(scripts.items())if s.get('FileName')and assets.inventory.get(asset_source(s),{}).get('frames')]
    assert nr==len(expected_ids);next_frame=0
    for ri,id in enumerate(expected_ids):
        script=scripts[id];asset=assets.inventory[asset_source(script)]
        assert struct.unpack_from('<4H',geometry,8+ri*8)==(id,next_frame,len(asset['frames']),script.get('ReferenceSprWidth',0))
        for i,frame in enumerate(asset['frames']):
            assert struct.unpack_from('<HHhh',geometry,8+nr*8+(next_frame+i)*8)==(frame['width'],frame['height'],*alignment(script,asset,i))
        next_frame+=len(asset['frames'])
    assert next_frame==nf;objects=0;inventory=json.loads((a.maps/'inventory.json').read_text())
    for item in inventory:
        name=item['file'];metadata=json.loads((a.maps/name/'00.json').read_text());blob=(a.entities/(name+'.entities')).read_bytes()
        assert struct.unpack_from('<4sI',blob)==(b'KFE1',len(metadata['objects']))
        assert blob[8:]==b''.join(bytes.fromhex(o['raw_hex'])for o in metadata['objects']);objects+=len(metadata['objects'])
    report={'scope':__doc__,'enemy_resources':47,'pickup_resources':11,'frames':total_frames,'facing_variants':variants,
            'decoded_pixels_equal':checked_pixels,'animation_ranges_checked':ranges_checked,'decoder_guards_intact':True,
            'geometry_resources':nr,'geometry_frames':nf,'maps':len(inventory),'objects':objects,
            'runtime_codec_sha256':hashlib.sha256((ROOT/'ds/source/sprite_codec.h').read_bytes()).hexdigest(),
            'limits':['Source metadata and decoded assets only; GPU presentation, complete gameplay and physical FPS require separate verification.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
