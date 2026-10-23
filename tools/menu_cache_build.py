"""Encode an exact RGB555 menu base and lossless focus patches."""
import hashlib
import struct
from tile_storage import lz10, unlz

PIXELS = 256*192

def encode_menu(screens):
    if len(screens) != 7 or any(len(raw) != PIXELS*2 for raw in screens):
        raise ValueError('Expected seven complete 256x192 RGB555 screens')
    base = screens[0]
    pixels = struct.unpack('<49152H', base)
    encoded = bytes(lz10(base))
    assert unlz(encoded) == base
    files = {'menu_normal_lz.bin':encoded}
    rows = []
    for focus, raw in enumerate(screens[1:]):
        target = struct.unpack('<49152H', raw)
        records, rebuilt = [], bytearray(base)
        i = 0
        while i < PIXELS:
            if target[i] == pixels[i]:
                i += 1
                continue
            first = i
            while i < PIXELS and target[i] != pixels[i]:
                i += 1
            data = raw[first*2:i*2]
            records.append(struct.pack('<HH', first, i-first)+data)
            rebuilt[first*2:i*2] = data
        patch = struct.pack('<4sI', b'KFMP', len(records))+b''.join(records)
        assert bytes(rebuilt) == raw
        files[f'menu_focus_{focus}_patch.bin'] = patch
        rows.append({'focus':focus,'patch_bytes':len(patch),'spans':len(records),
                     'original_sha256':hashlib.sha256(raw).hexdigest()})
    return files, rows
