"""Evaluate block-based DS IMA ADPCM against regenerated adapted PCM.

Offline evaluation only. KFA1 is an experimental container; the playable game
still uses its existing audio format. No CPU or hardware-audio gain is claimed.
"""
from pathlib import Path
import argparse
import ctypes as C
import hashlib
import json
import math
import struct
import subprocess
import tempfile
import wave
import numpy as np
from tile_storage import unlz

# Protocol arithmetic is implemented here for offline measurement. The DS uses
# a -32767 clamp and separately truncated bit contributions to the delta.
CODEC = r'''
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
static const int steps[89]={7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767};
static const int changes[8]={-1,-1,-1,-1,2,4,6,8};
static int clamp(int x,int lo,int hi){return x<lo?lo:x>hi?hi:x;}
static int advance(unsigned nibble,int *value,int *index){
 int step=steps[*index],difference=step>>3;
 if(nibble&1)difference+=step>>2;
 if(nibble&2)difference+=step>>1;
 if(nibble&4)difference+=step;
 *value=clamp(*value+((nibble&8)?-difference:difference),-32767,32767);
 *index=clamp(*index+changes[nibble&7],0,88);
 return *value;
}
static unsigned choose(int target,int value,int index){
 int difference=target-value,step=steps[index];unsigned nibble=0;
 if(difference<0){nibble=8;difference=-difference;}
 if(difference>=step){nibble|=4;difference-=step;}
 if(difference>=(step>>1)){nibble|=2;difference-=step>>1;}
 if(difference>=(step>>2))nibble|=1;
 return nibble;
}
size_t encode(const int16_t *input,unsigned n,uint8_t *out,size_t capacity){
 if(!input||!out||!n||n>2048||capacity<4+(n+1)/2)return 0;
 int initial=clamp(input[0],-32767,32767),best_index=0;
 int64_t best=INT64_MAX;
 /* Select initial step by measuring the first 32 samples. This does not
    alter the format or predictor rules used by the DS. */
 for(int candidate=0;candidate<89;candidate++){
  int value=initial,index=candidate;int64_t error=0;
  for(unsigned i=0;i<n&&i<32;i++){
   unsigned nibble=choose(input[i],value,index);
   int delta=advance(nibble,&value,&index)-(int)input[i];
   error+=(int64_t)delta*delta;
  }
  if(error<best){best=error;best_index=candidate;}
 }
 out[0]=(uint16_t)initial;out[1]=(uint16_t)initial>>8;out[2]=best_index;out[3]=0;
 int value=initial,index=best_index;
 for(unsigned i=0;i<n;i++){
  unsigned nibble=choose(input[i],value,index);advance(nibble,&value,&index);
  if(i&1)out[4+i/2]|=nibble<<4;else out[4+i/2]=nibble;
 }
 return 4+(n+1)/2;
}
int decode(const uint8_t *packet,size_t bytes,unsigned n,int16_t *out){
 if(!packet||!out||!n||n>2048||bytes!=4+(n+1)/2||packet[2]>88||packet[3])return 0;
 int value=(int16_t)((unsigned)packet[0]|(unsigned)packet[1]<<8),index=packet[2];
 for(unsigned i=0;i<n;i++){
  unsigned nibble=(packet[4+i/2]>>((i&1)*4))&15;
  out[i]=advance(nibble,&value,&index);
 }
 return 1;
}
'''

def effect_pcm(pack, asset):
    at, left = asset['packed_offset'], asset['frames']
    result = bytearray()
    while left:
        n, flags = struct.unpack_from('<HH', pack, at)
        assert 0 < n <= min(left, 2048)
        size = flags & 32767
        payload = pack[at+4:at+4+size]
        if flags & 32768:
            assert len(payload) == n*2
            block = payload
        else:
            planes = unlz(payload)
            assert len(planes) == n*2
            delta = np.frombuffer(planes[:n], dtype='u1').astype(np.uint16) | (np.frombuffer(planes[n:], dtype='u1').astype(np.uint16) << 8)
            block = (np.cumsum(delta, dtype=np.uint64) & 65535).astype('<u2').tobytes()
        result.extend(block)
        left -= n
        at = (at+4+size+3) & ~3
    assert at == asset['packed_offset']+asset['stored_bytes']
    assert hashlib.sha256(result).hexdigest() == asset['pcm_sha256']
    return np.frombuffer(result, dtype='<i2')

def write_wave(path, samples):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, 22050, len(samples), 'NONE', 'not compressed'))
        stream.writeframes(samples.astype('<i2').tobytes())

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True, help='Regenerated directory containing audio/ and sounds/')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previews', action='store_true', help='Write before/after WAVs for music and the three lowest-SNR voices/effects')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must not already exist')
    args.output.mkdir(parents=True)
    manifest = json.loads((args.assets/'sounds/effects-manifest.json').read_text())
    pack = (args.assets/'sounds/samples.pcm').read_bytes()
    assert hashlib.sha256(pack).hexdigest() == manifest['pack_sha256']
    rows, previews = [], {}
    with tempfile.TemporaryDirectory(prefix='kinder-adpcm-') as temporary:
        root = Path(temporary)
        source = root/'codec.c';source.write_text(CODEC)
        library = root/'codec.dylib'
        subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror', '-dynamiclib', str(source), '-o', str(library)], check=True)
        codec = C.CDLL(str(library))
        codec.encode.argtypes = [C.c_void_p,C.c_uint,C.c_void_p,C.c_size_t];codec.encode.restype = C.c_size_t
        codec.decode.argtypes = [C.c_void_p,C.c_size_t,C.c_uint,C.c_void_p];codec.decode.restype = C.c_int
        # Fixed protocol vector exercises both nibbles, sign and index changes.
        vector = b'\0\0\0\0\x70\xff'
        buffer = C.create_string_buffer(vector);out = (C.c_int16*4)()
        assert codec.decode(buffer,len(vector),4,out) and list(out)==[0,11,-19,-82]
        for payload,n in [(b'',1),(vector,0),(vector,2049),(vector[:4]+b'\0',4),(b'\0\0\x59\0\0',1),(b'\0\0\0\1\0',1)]:
            assert not codec.decode(C.create_string_buffer(payload),len(payload),n,out)
        def convert(name, group, samples, current_bytes):
            pieces, decoded = [], np.empty(len(samples), dtype='<i2')
            for at in range(0,len(samples),2048):
                part = np.ascontiguousarray(samples[at:at+2048]);n = len(part)
                storage = (C.c_uint8*1044)(*([0xA5]*1044))
                size = codec.encode(part.ctypes.data,n,C.byref(storage,8),1028)
                assert size == 4+(n+1)//2
                assert bytes(storage)[:8] == b'\xa5'*8 and bytes(storage)[8+size:] == b'\xa5'*(1044-8-size)
                encoded = bytes(storage)[8:8+size]
                guard = (C.c_int16*(n+8))(*([0x1357]*(n+8)))
                assert codec.decode(C.create_string_buffer(encoded),len(encoded),n,C.byref(guard,8))
                assert list(guard)[:4] == [0x1357]*4 and list(guard)[-4:] == [0x1357]*4
                decoded[at:at+n] = np.frombuffer(bytes(guard)[8:8+n*2],dtype='<i2')
                pieces.append(encoded)
            payload = bytearray();records = []
            for piece in pieces:
                records.append((len(payload),len(piece)));payload.extend(piece);payload.extend(bytes(-len(payload)%4))
            blob = struct.pack('<4s5I',b'KFA1',1,22050,len(samples),2048,len(pieces))
            blob += b''.join(struct.pack('<II',*record) for record in records)+payload
            target = args.output/(name+'.adp')
            target.write_bytes(blob)
            # Validate the serialized file, including block lookup and the last
            # partial block; an in-memory encode/decode round trip is not enough.
            serialized = target.read_bytes()
            magic,version,rate,count,block_size,block_count = struct.unpack_from('<4s5I',serialized)
            assert (magic,version,rate,count,block_size,block_count) == (b'KFA1',1,22050,len(samples),2048,len(pieces))
            payload_at = 24+block_count*8
            previous_end = 0
            for i in range(block_count):
                offset,length = struct.unpack_from('<II',serialized,24+i*8)
                n = min(2048,count-i*2048)
                assert offset == previous_end and length == 4+(n+1)//2
                packet = serialized[payload_at+offset:payload_at+offset+length]
                restored = (C.c_int16*n)()
                assert codec.decode(C.create_string_buffer(packet),len(packet),n,restored)
                assert np.array_equal(np.frombuffer(bytes(restored),dtype='<i2'),decoded[i*2048:i*2048+n])
                previous_end = (offset+length+3)&~3
            assert payload_at+previous_end == len(serialized)
            error = samples.astype(np.float64)-decoded.astype(np.float64)
            energy = float(np.sum(samples.astype(np.float64)**2));noise = float(np.sum(error**2))
            row = {'name':name,'group':group,'frames':len(samples),'blocks':len(pieces),
                   'current_bytes':current_bytes,'pcm_bytes':samples.nbytes,'adpcm_bytes':len(blob),
                   'snr_db':round(10*math.log10(energy/noise),2) if energy and noise else None,
                   'rms_error':round(float(np.sqrt(np.mean(error**2))),2),
                   'max_error':int(np.max(np.abs(error))),
                   'pcm_sha256':hashlib.sha256(samples.tobytes()).hexdigest(),
                   'adpcm_sha256':hashlib.sha256(blob).hexdigest()}
            rows.append(row)
            if args.previews:previews[name]=(samples.copy(),decoded)
        for path in sorted((args.assets/'audio').glob('*.wav')):
            with wave.open(str(path)) as stream:
                assert stream.getparams()[:3] == (1,2,22050)
                samples = np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2')
            convert(path.stem,'music',samples,path.stat().st_size)
        for asset in manifest['assets']:
            group = 'voice' if 'voices' in asset['path'].lower() else 'effect'
            name = group+'_'+format(asset['va'],'x')
            convert(name,group,effect_pcm(pack,asset),asset['stored_bytes'])
    source_names = {group+'_'+format(asset['va'],'x'):asset['path'] for asset in manifest['assets']
                    for group in ['voice' if 'voices' in asset['path'].lower() else 'effect']}
    for row in rows:
        row['source'] = source_names.get(row['name'], row['name']+'.wav')
    groups = {}
    for group in ('music','voice','effect'):
        group_rows = [r for r in rows if r['group']==group]
        current = sum(r['current_bytes'] for r in group_rows)
        size = sum(r['adpcm_bytes'] for r in group_rows)
        groups[group] = {'assets':len(group_rows),'current_bytes':current,'adpcm_bytes':size,
                         'reduction_percent':round((1-size/current)*100,2),
                         'lowest_snr_db':min((r['snr_db'] for r in group_rows if r['snr_db'] is not None),default=None)}
    if args.previews:
        selected = [r for r in rows if r['group']=='music']
        for group in ('voice','effect'):
            selected += sorted((r for r in rows if r['group']==group),key=lambda r:r['snr_db'] if r['snr_db'] is not None else float('inf'))[:3]
        for row in selected:
            before,after = previews[row['name']]
            write_wave(args.output/(row['name']+'_before.wav'),before)
            write_wave(args.output/(row['name']+'_after.wav'),after)
    current = sum(r['current_bytes'] for r in rows)+8  # KFS1 global header
    size = sum(r['adpcm_bytes'] for r in rows)
    report = {'scope':__doc__,'groups':groups,'current_audio_bytes':current,'adpcm_audio_bytes':size,
              'potential_payload_saving_bytes':current-size,'assets':rows,
              'codec_sha256':hashlib.sha256(CODEC.encode()).hexdigest(),
              'fixed_vector_passed':True,'guard_checks_passed':True,'serialized_blocks_verified':True,'malformed_cases':6,
              'limits':['Offline quality metrics and size only; listening and DS timing unverified.',
                        'KFA1 is not a format accepted by the current runtime.',
                        'DS hardware ADPCM cannot directly replace the current PCM ring stream.',
                        'Per-block headers and record tables are included; projected ROM size is not measured.']}
    if args.previews:
        lines = ['Offline ADPCM listening comparisons; unchanged 22050 Hz mono sample rate.',
                 'Each *_before.wav is adapted PCM; *_after.wav is ADPCM decoded back to PCM.',
                 'Metrics alone do not prove audible quality. No runtime changes have been made.', '']
        lines += [r['name']+' | '+r['source']+' | SNR '+str(r['snr_db'])+' dB' for r in selected]
        (args.output/'listening.txt').write_text('\n'.join(lines)+'\n')
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('scope','assets')},indent=2))

if __name__ == '__main__':
    main()
