"""Build full-resolution collision masks directly from decoded original atlas alpha."""
from pathlib import Path
import argparse, hashlib, json, struct
from PIL import Image

def build(assets,maps,output):
    output.mkdir(parents=True,exist_ok=True)
    inventory={row['source'].lower():row for row in json.loads((assets/'inventory.json').read_text())if 'frames'in row}
    manifest=[]
    for folder in sorted(maps.glob('*.W02')):
        data=json.loads((folder/'00.json').read_text());stem=folder.stem
        if stem.lower().endswith('e'):stem=stem[:-1]
        frames=inventory[('maps/'+stem+'.w01').lower()]['frames'];records=[];header=bytearray(b'KFC1')
        for frame in data['tile_bank_selection']:
            path=Path(frames[frame]['png'])
            # Existing inventories store repository-relative paths; portable
            # inventories may instead carry an absolute extraction path.
            if not path.is_absolute()and not path.exists():path=assets.parent.parent/path
            image=Image.open(path).convert('RGBA');bits=bytearray((image.width*image.height+7)//8)
            for i,rgba in enumerate(image.get_flattened_data()):
                if rgba[3]:bits[i>>3]|=1<<(i&7)
            name=hashlib.sha256(bits).hexdigest()+'.mask';(output/name).write_bytes(bits)
            header.extend(struct.pack('<HH72s',image.width,image.height,name.encode('ascii')))
            records.append(dict(file=name,width=image.width,height=image.height))
        if len(records)!=4:raise ValueError('Expected four collision banks: '+folder.name)
        (output/(folder.name+'.collision')).write_bytes(header)
        manifest.append(dict(map=folder.name,bank_masks=records,tile_bytes=(folder/'00.tiles.bin').stat().st_size))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return dict(maps=len(manifest),unique_masks=len(list(output.glob('*.mask'))))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,default=Path('generated/assets'))
    p.add_argument('--maps',type=Path,default=Path('generated/maps'));p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.assets,a.maps,a.output)))
if __name__=='__main__':main()
