"""Inventory the actual shipped assets, physical ROM size and encoding choices."""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
from collections import Counter,defaultdict
import hashlib
import json
import wave
import struct

R=Path(__file__).resolve().parents[1];root=R/'ds/nitrofs'
groups=defaultdict(lambda:{'bytes':0,'files':0});hashes=defaultdict(list);files=[]
for path in root.rglob('*'):
    if not path.is_file():continue
    raw=path.read_bytes();rel=str(path.relative_to(root));name=rel.split('/')[0]
    groups[name]['bytes']+=len(raw);groups[name]['files']+=1
    hashes[hashlib.sha256(raw).hexdigest()].append(rel);files.append({'file':rel,'bytes':len(raw)})
duplicates=[{'files':names,'bytes_each':(root/names[0]).stat().st_size}for names in hashes.values()if len(names)>1]
music=[]
for path in sorted((root/'audio').glob('*.wav')):
    with wave.open(str(path))as w:
        music.append({'file':path.name,'rate':w.getframerate(),'bits':w.getsampwidth()*8,'channels':w.getnchannels(),
                      'seconds':round(w.getnframes()/w.getframerate(),3),'bytes':path.stat().st_size})
effects=json.loads((R/'research/audio/effects_manifest.json').read_text())['assets']
rom=(resolve_rom(R / 'ds')).read_bytes();fat,size=struct.unpack_from('<II',rom,0x48);ranges=[struct.unpack_from('<II',rom,fat+i)for i in range(0,size,8)]
result={'scope':__doc__,'rom_bytes':(resolve_rom(R / 'ds')).stat().st_size,
        'rom_sha256':hashlib.sha256((resolve_rom(R / 'ds')).read_bytes()).hexdigest(),
        'nitrofs_bytes':sum(v['bytes']for v in groups.values()),'nitrofs_physical_payload_bytes':sum(b-a for a,b in set(ranges)),'nitrofs_aliased_files':len(ranges)-len(set(ranges)),'groups':dict(groups),
        'largest_files':sorted(files,key=lambda x:-x['bytes'])[:30],
        'exact_duplicate_files':duplicates,'duplicate_bytes':sum((len(x['files'])-1)*x['bytes_each']for x in duplicates),
        'music':music,'effects':{'assets':len(effects),'decoded_rate':22050,'decoded_bits':16,'decoded_channels':1,'storage':'KFS1 lossless block deltas/LZ10 with raw fallback',
                              'source_rates':dict(Counter(x['source_rate']for x in effects)),
                              'source_bits':dict(Counter(x['source_bits']for x in effects)),
                              'upsampled_assets':sum(x['source_rate']<22050 for x in effects)},
        'graphics':{'gameplay_scale':'256/800 =192/600 =0.32, centered nearest sampling',
                    'source_resolution_retained':['collision geometry','player frame geometry','enemy/NPC frame geometry','pickup frame geometry'],
                    'storage':'KFC5 DS-size scenery with precomputed row masks packed in existing records, KFP3 players and KFES entities and KFSP pickups: exact4/8-bit palettes or RGB555 plus LZ10, with exact raw fallback for oversized scenery packets; KFB4 DS-size backgrounds',
                    'runtime':'Hardware parallax and eligible merged static passes; ordered software dynamic actors, bounded decoded-image caches and incremental static overlap masks',
                    'pending':['Reduced audio storage','Further hardware sprite/dynamic rendering'],'cross_file_storage':'Byte-identical files alias shared FAT payloads; logical source file sizes include aliases'}}
(R/'research/rendering/rom-asset-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'rom_bytes':result['rom_bytes'],'nitrofs_bytes':result['nitrofs_bytes'],'duplicate_bytes':result['duplicate_bytes'],'groups':dict(groups)}))
