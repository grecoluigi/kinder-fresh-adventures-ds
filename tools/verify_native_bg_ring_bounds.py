"""Exhaust ordinary-scroll visible-cell bounds for the proposed hardware BG ring.
This proves capacity/address arithmetic, not a cache implementation or deadline.
"""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();count=0;max_visible=max_union=max_box=0;worst=None
for x in range(8):
 for y in range(8):
  for dx in range(-16,17):
   for dy in range(-16,17):
    old=(x//8,y//8,(x+255)//8,(y+191)//8);new=((x+dx)//8,(y+dy)//8,(x+dx+255)//8,(y+dy+191)//8)
    def area(r):return (r[2]-r[0]+1)*(r[3]-r[1]+1)
    overlap=max(0,min(old[2],new[2])-max(old[0],new[0])+1)*max(0,min(old[3],new[3])-max(old[1],new[1])+1)
    union=area(old)+area(new)-overlap;bw=max(old[2],new[2])-min(old[0],new[0])+1;bh=max(old[3],new[3])-min(old[1],new[1])+1
    assert bw<64 and bh<32 # Modulo64×32 is injective inside this bounding box.
    assert union+1<=960 # Reserve a permanent transparent graphic slot.
    max_visible=max(max_visible,area(old),area(new));max_box=max(max_box,bw*bh)
    if union>max_union:max_union=union;worst={'phase':[x,y],'delta':[dx,dy],'bounding_dimensions':[bw,bh]}
    count+=1
result={'scope':__doc__,'cases':count,'maximum_visible_cells':max_visible,'maximum_old_new_union_cells':max_union,'maximum_bounding_cells':max_box,'permanent_blank_slots':1,'available_graphic_slots':960,'maximum_required_slots_including_blank':max_union+1,'minimum_spare_slots':960-max_union-1,'ring_columns':64,'ring_rows':32,'tile_graphic_bytes':960*64,'map_bytes':64*32*2,'total_bytes':960*64+64*32*2,'worst_case':worst,'limits':['Camera steps beyond16DS pixels per axis require separate admission or a controlled transition.','Distinct cell count bounds distinct graphics conservatively; alpha/repetition can reduce actual use.','Does not prove pinning/eviction, staging, scroll publication, flash read locality or presentation deadlines.']};assert result['total_bytes']==65536;a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
