"""Check regenerated character/projectile data against original decoded artwork.

Player packets are expanded by the runtime C codec. Sprite alignment and raster
bounds are derived independently from the original coordinate lattice; expected
pixels come from the shared offline Lanczos raster filter. No software scene
renderer or rendered framebuffer reference is used.
"""
from pathlib import Path
import argparse
import ctypes as C
import hashlib
import json
import struct
import subprocess
import tempfile
import numpy as np
from decoded_assets import DecodedAssets
from player_scaled_build import raster

ROOT=Path(__file__).resolve().parents[1]

def rgb555(assets,frame):
    rgba=np.asarray(assets.image(frame),dtype=np.uint16)
    return np.where(rgba[:,:,3],0x8000|(rgba[:,:,0]>>3)|((rgba[:,:,1]>>3)<<5)|((rgba[:,:,2]>>3)<<10),0).astype('<u2')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--decoded-assets',type=Path,required=True)
    p.add_argument('--players',type=Path,required=True)
    p.add_argument('--projectiles',type=Path,required=True)
    p.add_argument('--enemy-shots',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();assets=DecodedAssets(a.decoded_assets)
    frames=variants=pixels=0
    with tempfile.TemporaryDirectory(prefix='kinder-character-assets-')as td:
        root=Path(td);source=root/'decode.c';library=root/'decode.dylib'
        source.write_text('#include "sprite_codec.h"\nint decode(const uint8_t*p,size_t n,uint16_t*d,unsigned count){return sprite_codec_decode(p,n,d,count);}\n')
        subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-dynamiclib','-I'+str(ROOT/'ds/source'),str(source),'-o',str(library)],check=True)
        codec=C.CDLL(str(library));codec.decode.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint];codec.decode.restype=C.c_int
        # Source-coordinate centers on an independent, generously bounded
        # lattice. Locate geometry intervals instead of using packer offsets.
        lattice=np.arange(-1024,1024);centers=np.floor((lattice+.5)*25/8).astype(int)
        for name in ('PINGUIN','MILCHSCHNITTE'):
            original=assets.inventory['animation/'+name.lower()+'.w01']['frames']
            pack=(a.players/(name.lower()+'.frames')).read_bytes()
            assert pack[:4]==b'KFP3' and struct.unpack_from('<I',pack,4)[0]==len(original)
            payload=8+40*len(original)
            for index,frame in enumerate(original):
                image=rgb555(assets,frame);h,w=image.shape
                assert struct.unpack_from('<HHhh',pack,8+40*index)==(w,h,frame['x'],frame['y'])
                frames+=1
                for facing in (0,1):
                    offset,size,pw,ph,px,py=struct.unpack_from('<IIHHhh',pack,16+40*index+facing*16)
                    assert 0<size and payload+offset+size<=len(pack)
                    left=frame['x'] if facing else -frame['x']-w
                    ix=np.flatnonzero((centers>=left)&(centers<left+w))
                    iy=np.flatnonzero((centers>=frame['y'])&(centers<frame['y']+h))
                    if not len(ix):ix=np.array([np.searchsorted(centers,left)])
                    if not len(iy):iy=np.array([np.searchsorted(centers,frame['y'])])
                    assert (pw,ph,px,py)==(len(ix),len(iy),lattice[ix[0]],lattice[iy[0]])
                    expected=raster(image,frame['x'],frame['y'],facing)[0]
                    packet=C.create_string_buffer(pack[payload+offset:payload+offset+size])
                    guard=np.full(pw*ph+32,0x1357,dtype='<u2')
                    assert codec.decode(packet,size,guard[16:].ctypes.data,pw*ph)
                    assert np.all(guard[:16]==0x1357) and np.all(guard[-16:]==0x1357)
                    assert np.array_equal(guard[16:-16].reshape(ph,pw),expected),(name,index,facing)
                    variants+=1;pixels+=pw*ph
    shots=(a.projectiles/'shots.bin').read_bytes();assert shots[:4]==b'KFS1';at=4
    for index in (261,232):
        frame=assets.inventory['animation/pinguin.w01']['frames'][index];expected=rgb555(assets,frame)
        h,w=expected.shape
        assert struct.unpack_from('<HHhh',shots,at)==(w,h,frame['x'],frame['y']);at+=8
        assert shots[at:at+expected.nbytes]==expected.tobytes();at+=expected.nbytes
    assert at==len(shots)
    enemy_frames=(('kong','kong02',16),('yeti','kleiner_yeti',25),('snowman','schneemann',54),
                  ('egg','eier_roboter',23),('gorilla','gorilla',87),('factory','roboter',188),
                  ('bear','b_r',53),('octopus','krake',50))
    for name,resource,index in enemy_frames:
        frame=assets.inventory['animation/'+resource+'.w01']['frames'][index];expected=rgb555(assets,frame)
        blob=(a.enemy_shots/(name+'.bin')).read_bytes()
        assert struct.unpack_from('<4sHH',blob)==(b'KFE1',expected.shape[1],expected.shape[0])
        assert blob[8:]==expected.tobytes(),name
    report={'scope':__doc__,'player_frames':frames,'facing_variants':variants,'decoded_pixels_equal':pixels,
            'decoder_guards_intact':True,'native_metadata_exact':True,'player_projectiles':2,
            'enemy_projectiles':len(enemy_frames),'runtime_codec_sha256':hashlib.sha256((ROOT/'ds/source/sprite_codec.h').read_bytes()).hexdigest(),
            'limits':['Asset decoding and original pixel/alignment equality; no GPU presentation or physical FPS claim.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
