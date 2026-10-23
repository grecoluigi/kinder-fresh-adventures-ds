"""Verify compiled scene records, original tile layers, background rows and collision alpha."""
from pathlib import Path
import argparse,ctypes as C,hashlib,json,struct,subprocess,tempfile
import numpy as np
from PIL import Image
from decoded_assets import DecodedAssets
from native_resources import asset_source

ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('decoded-assets','maps','scenes','backgrounds','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();assets=DecodedAssets(a.decoded_assets);scripts={s['ObjNr']:s for s in json.loads((a.maps/'scripts.json').read_text()).values()if 'ObjNr' in s}
 identities={};records_checked=tile_bytes=mask_pixels=0;keys=set();maps=json.loads((a.maps/'inventory.json').read_text())
 for item in maps:
  name=item['file'];original=json.loads((a.maps/name/'00.json').read_text());blob=(a.scenes/(name+'.scene')).read_bytes()
  magic,w,h,layers,tw,th,n,flags,sx,sy,offset,size,keybytes=struct.unpack_from('<4s7H2i2I28s2x',blob)
  assert magic==b'KFS1'and not flags and(w,h,layers,tw,th)==tuple(original[k]for k in ('width_cells','height_cells','layers','tile_width','tile_height'))
  assert offset==64+n*20 and len(blob)==offset+size
  assert blob[offset:]==(a.maps/name/'00.tiles.bin').read_bytes();tile_bytes+=size
  spawn=next((o for o in original['objects']if o['obj_nr']==1000),{'x_px':400,'y_px':300})
  assert(sx,sy)==(spawn['x_px'],spawn['y_px'])
  stem=Path(name).stem.lower();stem=stem[:-1]if stem.endswith('e')else stem
  assert keybytes.split(b'\0')[0].decode()==stem;keys.add(stem)
  records=list(struct.iter_unpack('<HBBiiIHH',blob[64:offset]));next_record=0
  for obj in original['objects']:
   raw=bytes.fromhex(obj['raw_hex']);script=scripts.get(obj['obj_nr'])
   if not script or not script.get('FileName'):continue
   asset=assets.inventory.get(asset_source(script))
   if not asset:continue
   frame=asset['frames'][script.get('StartAnimLeft',script.get('FileAnimStart',0))]
   zero=asset['frames'][0]if script.get('CorrectAlignToNull')else {'x':0,'y':0}
   x=C.c_int16(frame['x']-zero['x']).value;y=C.c_int16(frame['y']-zero['y']).value
   if raw[43]:x=C.c_int16(script.get('ReferenceSprWidth',0)-frame['width']-x).value
   identity=(frame['png'],bool(raw[43]))
   if identity not in identities:identities[identity]=len(identities)
   assert records[next_record]==(obj['obj_nr'],raw[25],raw[23],obj['x_px']+x,obj['y_px']+y,identities[identity],frame['width'],frame['height'])
   next_record+=1;records_checked+=1
  assert next_record==n
  collision=(a.scenes/(name+'.collision')).read_bytes();assert collision[:4]==b'KFC1'and len(collision)==308
  sheet=assets.inventory['maps/'+stem+'.w01']['frames']
  for bank,index in enumerate(original['tile_bank_selection']):
   width,height,filename=struct.unpack_from('<HH72s',collision,4+bank*76);filename=filename.split(b'\0')[0].decode()
   alpha=np.asarray(assets.image(sheet[index]))[:,:,3];assert alpha.shape==(height,width)
   bits=np.packbits((alpha!=0).reshape(-1),bitorder='little').tobytes()
   assert filename==hashlib.sha256(bits).hexdigest()+'.mask'
   assert(a.scenes/filename).read_bytes()==bits;mask_pixels+=width*height
 background_pixels=0
 with tempfile.TemporaryDirectory(prefix='kinder-scene-assets-')as td:
  work=Path(td);source=work/'decode.c';library=work/'decode.dylib'
  source.write_text('#include "tile_codec.h"\nint decode(const uint8_t*p,size_t n,uint8_t*d,unsigned count){return tile_decode_lz(p,n,d,count);}\n')
  subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'ds/source'),str(source),'-o',str(library)],check=True)
  codec=C.CDLL(str(library));codec.decode.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint];codec.decode.restype=C.c_int
  for key in sorted(keys):
   image=np.asarray(assets.image(assets.inventory['maps/'+key+'.w01']['frames'][4]));assert np.all(image[:600,:,3]==255)
   sampled=np.asarray(Image.fromarray(image[:600]).resize((256,192),Image.Resampling.LANCZOS),dtype=np.uint16)
   expected=(0x8000|(sampled[:,:,0]>>3)|((sampled[:,:,1]>>3)<<5)|((sampled[:,:,2]>>3)<<10)).astype('<u2')
   assert(a.scenes/(key+'.bg')).read_bytes()==expected.tobytes()
   blob=(a.backgrounds/(key+'.par')).read_bytes();assert struct.unpack_from('<4sHH',blob)==(b'KFB4',256,192)
   for y in range(192):
    offset,size=struct.unpack_from('<II',blob,8+y*8);assert offset%4==0 and size>=4 and 1544+offset+size<=len(blob)
    packet=C.create_string_buffer(blob[1544+offset:1544+offset+size]);guard=np.full(256+16,0x1357,dtype='<u2')
    assert codec.decode(packet,size,guard[8:].ctypes.data,512)
    assert np.array_equal(guard[8:-8],expected[y])and np.all(guard[:8]==0x1357)and np.all(guard[-8:]==0x1357)
    background_pixels+=256
 report={'scope':__doc__,'maps':len(maps),'static_metadata_records':records_checked,'stable_metadata_ids':len(identities),'tile_layer_bytes_equal':tile_bytes,'collision_alpha_pixels_equal':mask_pixels,'backgrounds':len(keys),'C_decoded_background_pixels_equal':background_pixels,'decoder_guards_intact':True,'runtime_codec_sha256':hashlib.sha256((ROOT/'ds/source/tile_codec.h').read_bytes()).hexdigest(),'limits':['Asset metadata/pixels only; no full scene framebuffer reference, DS display proof or hardware FPS measurement.']}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
