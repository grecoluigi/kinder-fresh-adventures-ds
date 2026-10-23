"""Audit current quantized scenery for an exact 8bpp extended-palette tilemap.
Static only: no proposed runtime backend, no new quantization or ROM mutation.
"""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import argparse,collections,hashlib,json,random,struct
import numpy as np
from tile_storage import unlz
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--views',type=int,default=32);p.add_argument('--merge-palettes',action='store_true');a=p.parse_args();maps=[]
rng=random.Random(20261019);rom=resolve_rom(R / 'ds');before=hashlib.sha256(rom.read_bytes()).hexdigest()
for path in sorted((R/'ds/nitrofs/composite').glob('*.atlas')):
 data=path.read_bytes();magic,version,n,colors,records,paloff,payload,flags=struct.unpack_from('<4s7I',data)
 assert magic==b'KQSC'and version==2 and flags==1
 palette=np.frombuffer(data,dtype='<u2',count=colors,offset=paloff);tiles=[]
 for i in range(n):
  offset,word=struct.unpack_from('<II',data,records+8*i);ids=np.frombuffer(unlz(data[payload+offset:payload+offset+(word&65535)]),dtype='u1')
  assert ids.size==256;tiles.append(palette[(word>>16)*256+ids.astype(np.uint32)].reshape(16,16))
 index=path.with_suffix('.index').read_bytes();_,w,h,nc,npairs,_,_=struct.unpack_from('<4sHHIIHH',index)
 pairs=list(struct.iter_unpack('<HH',index[20+nc*12:]));assert len(pairs)==npairs
 final={};orders={};ordinal=0
 for kind,first,count in struct.iter_unpack('<III',index[20:20+nc*12]):
  if kind:continue
  ordinal+=1;assert ordinal<=255
  for cell,tile in pairs[first:first+count]:
   if cell not in final:final[cell]=np.zeros((16,16),dtype='<u2');orders[cell]=np.zeros((16,16),dtype='u1')
   src=tiles[tile];mask=(src&32768)!=0;final[cell][mask]=src[mask];orders[cell][mask]=ordinal
 maxx=max(0,w-17);maxy=max(0,h-13);positions=[(0,0),(maxx,0),(0,maxy),(maxx,maxy)]
 positions +=[(rng.randrange(maxx+1),rng.randrange(maxy+1))for _ in range(max(0,a.views-4))]
 cases=[]
 for tx,ty in positions:
  canvas=np.zeros((208,272),dtype='<u2');owner=np.zeros((208,272),dtype='u1')
  for y in range(13):
   for x in range(17):
    cell=(ty+y)*w+tx+x
    if tx+x<w and ty+y<h and cell in final:canvas[y*16:y*16+16,x*16:x*16+16]=final[cell];owner[y*16:y*16+16,x*16:x*16+16]=orders[cell]
  pieces=[canvas[y:y+8,x:x+8]for y in range(0,208,8)for x in range(0,272,8)]
  sets={frozenset(int(v)for v in np.unique(t)if v&32768)for t in pieces};banks=[]
  for colorset in sorted(sets,key=lambda s:(-len(s),tuple(sorted(s)))):
   if not colorset:continue
   candidates=[(len(colorset-b),-len(b),i)for i,b in enumerate(banks)if len(colorset|b)<=255]
   if candidates:banks[min(candidates)[2]]|=colorset
   else:banks.append(set(colorset))
  before_merge=len(banks)
  if a.merge_palettes:
   while True:
    candidates=[]
    for i in range(len(banks)):
     for j in range(i):
      union=banks[i]|banks[j]
      if len(union)<=255:candidates.append((-len(banks[i]&banks[j]),len(union),j,i))
    if not candidates:break
    _,_,j,i=min(candidates);banks[j]|=banks[i];del banks[i]
  # Reconstruct every selected tile from its actual bank assignment.
  bank_palettes=[np.array([0,*sorted(b)],dtype='<u2')for b in banks];lookups=[{int(v):i for i,v in enumerate(p)}for p in bank_palettes];patterns=set()
  for tile in pieces:
   colorset=frozenset(int(v)for v in np.unique(tile)if v&32768)
   if not colorset:patterns.add(bytes(64));continue
   bi=next(i for i,b in enumerate(banks)if colorset<=b)
   encoded=np.array([lookups[bi][int(v)]if v&32768 else 0 for v in tile.flat],dtype='u1').reshape(8,8)
   assert np.array_equal(bank_palettes[bi][encoded],tile);patterns.add(encoded.tobytes())
  opaque=canvas[canvas!=0];order_set=np.unique(owner[owner!=0]);mixed=sum(len(np.unique(owner[y:y+8,x:x+8][owner[y:y+8,x:x+8]!=0]))>1 for y in range(0,208,8)for x in range(0,272,8))
  cases.append({'tile_camera':[tx,ty],'opaque_colors':len(np.unique(opaque)),'greedy_palette_banks_before_merge':before_merge,'greedy_palette_banks':len(banks),'indexed_patterns':len(patterns),'fits_single_BG_palette_and_pattern_limits':len(banks)<=16 and len(patterns)<=1024,'static_painter_ordinals':[int(v)for v in order_set],'tiles_with_multiple_painter_ordinals':mixed,'exact_reconstructed_pixels':272*208})
 row={'map':path.stem,'atlas_sha256':hashlib.sha256(data).hexdigest(),'index_sha256':hashlib.sha256(index).hexdigest(),'views':cases,'max_banks':max(c['greedy_palette_banks']for c in cases),'max_patterns':max(c['indexed_patterns']for c in cases),'fitting_views':sum(c['fits_single_BG_palette_and_pattern_limits']for c in cases)};maps.append(row);print(json.dumps({k:v for k,v in row.items()if k not in('views','atlas_sha256','index_sha256')}),flush=True)
assert hashlib.sha256(rom.read_bytes()).hexdigest()==before
result={'scope':__doc__,'rom_sha256':before,'palette_merge':a.merge_palettes,'maps':maps,'total_views':sum(len(m['views'])for m in maps),'fitting_views':sum(m['fitting_views']for m in maps),'limits':['Only sampled272x208static scenery windows; dynamic actors and parallax excluded.','Greedy packing failure does not prove an optimal16-bank assignment impossible.','Capacity fit is necessary but does not solve original painter ordering, streaming or shared VRAM ownership.','Transparent index0 and all current quantized RGB555 colors retained exactly; no further image-quality changes.']};a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'total_views':result['total_views'],'fitting_views':result['fitting_views']}))
