"""Join generated native tiles/depth data with native scene definitions."""
from pathlib import Path
import argparse,hashlib,json,shutil,struct

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('tiles','depth','definitions'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();tiles={f.stem:f for f in a.tiles.glob('*.ntb')};depth={f.stem:f for f in a.depth.glob('*.mesh')};definitions={f.stem:f for f in a.definitions.glob('*.nsc')}
 assert tiles and tiles.keys()==depth.keys()==definitions.keys()
 assert all(f.suffix in('.nsc',)or f.name=='scene-definitions.json'for f in a.definitions.iterdir()),'Destination already contains compiled scenery'
 rows=[]
 for name in sorted(tiles):
  tile=tiles[name].read_bytes();mesh=depth[name].read_bytes();definition=definitions[name].read_bytes()
  magic,version,w,h,*_=struct.unpack_from('<4s11I',tile);assert magic==b'KNTB'and version==1
  mm,mw,mh,cols,rows_,sx,sy,stride,count=struct.unpack_from('<4s6H2I',mesh)
  assert mm==b'KDM2'and(mw,mh)==(w*8,h*8)and(cols*rows_==count)and(sx,sy,stride)==(256,192,6)
  assert not any(flags&1 for off,size,n,flags in struct.iter_unpack('<IIHH',mesh[24:24+count*12]))
  dm,nw,nh,dw,dh,orders,events,reserved=struct.unpack_from('<4s7I',definition)
  assert dm==b'KNS1'and(dw,dh)==(mw,mh)and not reserved
  rows.append({'map':name,'sha256':{path.name:hashlib.sha256(data).hexdigest()for path,data in ((tiles[name],tile),(depth[name],mesh),(definitions[name],definition))}})
 for name in tiles:
  shutil.copyfile(tiles[name],a.definitions/tiles[name].name);shutil.copyfile(depth[name],a.definitions/depth[name].name)
 (a.definitions/'native-scenery-manifest.json').write_text(json.dumps({'scope':__doc__,'maps':rows,'runtime_files':len(rows)*3},indent=2)+'\n')
 print(json.dumps({'maps':len(rows),'runtime_files':len(rows)*3}))

if __name__=='__main__':main()
