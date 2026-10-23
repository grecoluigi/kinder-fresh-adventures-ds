"""Compact complete scaled enemy/pickup banks for the native GPU runtime.

KFE4/KFU4: magic, u16 resource count, u16 frame count, u32 total bytes;
unchanged resource records (84/12 bytes), then 24-byte frame records:
original HHhh geometry followed by HHhh geometry for each scaled facing.
All frames are retained, including those outside declared animation ranges.
Full KFES/KFSP banks remain pixel conversion/verification intermediates.
"""
import struct


def scene_actor_metadata(blob, enemies):
    magic, output_magic, stride, resource_stride, original, raster = (
        (b'KFES', b'KFE4', 40, 84, 0, 8) if enemies else
        (b'KFSP', b'KFU4', 48, 12, 8, 16))
    if len(blob) < 12 or blob[:4] != magic:
        raise ValueError('Expected a complete scaled actor bank')
    resources, frames, payload = struct.unpack_from('<HHI', blob, 4)
    if (not resources or resources > (64 if enemies else 11) or
            not frames or frames > (2048 if enemies else 256) or
            not enemies and resources != 11):
        raise ValueError('Invalid actor counts')
    frame_start = 12 + resources * resource_stride
    base = frame_start + frames * stride
    if base + payload != len(blob):
        raise ValueError('Invalid actor payload extent')
    seen = set()
    for index in range(resources):
        at = 12 + index * resource_stride
        ident, first, count = struct.unpack_from('<HHH', blob, at)
        if ident >= 1024 or ident in seen or not count or first + count > frames:
            raise ValueError('Invalid actor resource range')
        if not enemies and (not 48 <= ident <= 58 or
                            max(struct.unpack_from('<HH', blob, at+6)) >= count):
            raise ValueError('Invalid pickup resource')
        seen.add(ident)
    size = frame_start + frames * 24
    out = bytearray(struct.pack('<4sHHI', output_magic, resources, frames, size))
    out.extend(blob[12:frame_start])
    for index in range(frames):
        at = frame_start + index * stride
        w, h, _, _ = struct.unpack_from('<HHhh', blob, at+original)
        if not w or not h or w > 32767 or h > 32767:
            raise ValueError('Invalid original actor geometry')
        out.extend(blob[at+original:at+original+8])
        for facing in range(2):
            record = at + raster + facing * 16
            offset, length, w, h, x, y = struct.unpack_from('<IIHHhh', blob, record)
            if (not w or not h or offset % 4 or length < 8 or
                    offset > payload or length > payload-offset or
                    x+w > 32767 or y+h > 32767 or
                    (enemies and (w > 256 or h > 192)) or
                    (not enemies and w*h > 8192)):
                raise ValueError('Invalid scaled actor geometry/payload')
            out.extend(blob[record+8:record+16])
    return bytes(out)
