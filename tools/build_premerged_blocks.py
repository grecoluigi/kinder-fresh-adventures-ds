"""Precompute exact 4x4-cell scenery blocks and native per-cell occlusion spans; research assets only."""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import argparse,collections,hashlib,json,struct
import numpy as np
from scenery_codec import records
from scenery_codec import unpack
from tile_storage import packet,lz10,unlz
R=Path(__file__).resolve().parents[1]
HEADER=struct.Struct('<4s6H4I');ENTRY=struct.Struct('<I4H');SIDE=4;PIXELS=64;MAX_PASSES=20
def merged_planes(index,atlas):
 magic,w,h,nc,npairs,_,_=struct.unpack_from('<4sHHIIHH',index)
 assert magic==b'KFLD' and len(index)==20+12*nc+4*npairs
 base,table=records(atlas);decoded={};colors=np.zeros((h*16,w*16),dtype='<u2');owners=np.zeros(colors.shape,dtype='u1');ordinal=0
 for kind,begin,count in struct.iter_unpack('<III',index[20:20+12*nc]):
  if kind:continue
  ordinal+=1;assert ordinal<=MAX_PASSES and begin+count<=npairs
  for at in range(begin,begin+count):
   cell,tile=struct.unpack_from('<HH',index,20+12*nc+4*at);assert cell<w*h and tile<len(table)
   if tile not in decoded:
    off,size=table[tile];decoded[tile]=unpack(atlas[base+off:base+off+size]).reshape(16,16)
   image=decoded[tile];opaque=(image&32768)!=0;y=cell//w*16;x=cell%w*16
   colors[y:y+16,x:x+16][opaque]=image[opaque];owners[y:y+16,x:x+16][opaque]=ordinal
 return colors,owners,ordinal
def cell_spans(owner,passes):
 groups=[[] for _ in range(passes)]
 for y in range(16):
  x=0
  while x<16:
   begin=x;order=int(owner[y,x]);x+=1
   while x<16 and owner[y,x]==order:x+=1
   if order:groups[order-1].append((y<<9)|(x<<4)|begin)
 offsets=[0]
 for group in groups:offsets.append(offsets[-1]+len(group))
 assert offsets[-1]<=256
 return offsets+[run for group in groups for run in group]
def encode_block(color,owner,passes):
 raw=color.tobytes();encoded,bits=packet(raw)
 if len(encoded)>len(raw)+4:encoded=struct.pack('<BBH',16,1,0)+raw;bits=16
 assert np.array_equal(unpack(encoded).reshape(64,64),color)
 words=[17];cells=[]
 for y in range(4):
  for x in range(4):
   values=cell_spans(owner[y*16:y*16+16,x*16:x*16+16],passes);cells.extend(values);words.append(17+len(cells))
 values=words+cells;span=struct.pack('<'+'H'*len(values),*values);packed=lz10(span)
 flags=int(len(packed)<len(span));stored=bytes(packed) if flags else span
 assert (unlz(stored) if flags else stored)==span
 return encoded,stored,len(values),flags,bits
def build(index,atlas):
 colors,owners,passes=merged_planes(index,atlas);h,w=colors.shape;cols=(w+63)//64;rows=(h+63)//64;n=cols*rows
 assert n<=8192
 payload=bytearray();directory=[];unique={};modes=collections.Counter();base=64+n*ENTRY.size;nonempty=0
 for row in range(rows):
  for col in range(cols):
   color=np.zeros((64,64),dtype='<u2');owner=np.zeros((64,64),dtype='u1');c=colors[row*64:row*64+64,col*64:col*64+64];o=owners[row*64:row*64+64,col*64:col*64+64];color[:c.shape[0],:c.shape[1]]=c;owner[:o.shape[0],:o.shape[1]]=o
   key=color.tobytes()+owner.tobytes()
   if key not in unique:
    a,b,words,flags,bits=encode_block(color,owner,passes);offset=base+len(payload);payload.extend(a);payload.extend(bytes(-len(payload)%4));payload.extend(b);payload.extend(bytes(-len(payload)%4));unique[key]=(offset,len(a),len(b),words,flags);modes[bits]+=1
   directory.append(unique[key]);nonempty+=bool(np.any(owner))
 digest=hashlib.sha256(index+atlas).digest();length=base+len(payload)
 data=HEADER.pack(b'SMC1',w//16,h//16,4,passes,cols,rows,n,ENTRY.size,base,length)+digest+b''.join(ENTRY.pack(*v) for v in directory)+payload
 assert len(data)==length
 return data,{'width_cells':w//16,'height_cells':h//16,'static_passes':passes,'blocks':n,'nonempty_blocks':nonempty,'unique_blocks':len(unique),'color_modes':dict(modes),'bytes':len(data),'original_index_atlas_bytes':len(index)+len(atlas),'source_sha256':digest.hex(),'block_pixels':64,'block_cells':4,'maximum_span_words':max(v[3] for v in directory),'maximum_color_packet':max(v[1] for v in directory),'maximum_span_packet':max(v[2] for v in directory)}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=R/'research/rendering/premerged-block-assets');a=p.parse_args();a.output_dir.mkdir(exist_ok=True,parents=True)
 rom=resolve_rom(R / 'ds');sha=hashlib.sha256(rom.read_bytes()).hexdigest();eligible={m['map'] for m in json.loads((R/'research/rendering/ds-background-feasibility.json').read_text())['maps'] if m['views']};maps=[]
 for path in sorted((R/'ds/nitrofs/composite').glob('*.index')):
  if path.stem.removesuffix('.enemy') not in eligible:continue
  blob,meta=build(path.read_bytes(),path.with_suffix('.atlas').read_bytes());target=a.output_dir/(path.stem+'.smc');target.write_bytes(blob);meta.update(map=path.stem,sha256=hashlib.sha256(blob).hexdigest());maps.append(meta);print(json.dumps(meta),flush=True)
 assert len(maps)==7 and hashlib.sha256(rom.read_bytes()).hexdigest()==sha
 report={'scope':__doc__,'maps':maps,'bytes':sum(m['bytes'] for m in maps),'original_index_atlas_bytes':sum(m['original_index_atlas_bytes'] for m in maps),'canonical_rom_unchanged':True,'rom_sha256':sha,'limits':['Research assets only; no runtime integration or speed claim.','Packs supplement existing assets during experiments; replacement/fallback and final ROM-size accounting remain.','Packed colors and spans reconstruct exact native static ownership, not gameplay geometry.']};(a.output_dir/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='maps'}))
if __name__=='__main__':main()
