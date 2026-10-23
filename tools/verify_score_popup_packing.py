"""Independent full original POINTS PNG -> packed-tile pixel comparison."""
from pathlib import Path
import struct,json
from PIL import Image
R=Path(__file__).resolve().parents[1];data=(R/'ds/nitrofs/enemy_shots/points.bin').read_bytes();tile,frames,tiles,count=struct.unpack_from('<4H',data,4);assert data[:4]==b'KFP2'and(tile,frames,tiles,count)==(4,3,371,1001)
assert len(data)==36+count*2+tiles*16*2
indices=struct.unpack_from('<1001H',data,36);atlas=struct.unpack_from('<5936H',data,36+2002);checked=0
for frame in range(3):
 width,height,offset=struct.unpack_from('<HHI',data,12+frame*8);im=Image.open(R/f'generated/assets/frames/Animation/POINTS/{frame:03}.png').convert('RGBA');assert im.size==(width,height)
 cols=(width+3)//4
 for y in range(height):
  for x in range(width):
   tile=indices[offset+(y//4)*cols+x//4];actual=atlas[tile*16+(y%4)*4+x%4];r,g,b,a=im.getpixel((x,y));expected=(r>>3)|((g>>3)<<5)|((b>>3)<<10)|0x8000 if a else 0
   assert actual==expected,(frame,x,y,actual,expected);checked+=1
result={'scope':__doc__,'original_pixels':checked,'resident_bytes_before':29684,'resident_bytes_after':13874,'saved_bytes':15810,'color_quantization':'Original RGB555 conversion only; no palette reduction or resampling.'}
(R/'research/rendering/score-popup-packing-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
