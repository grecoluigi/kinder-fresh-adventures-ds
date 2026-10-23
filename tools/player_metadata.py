"""Build metadata-only runtime player banks from verified scaled intermediates.

KFP4 contains a count followed by 24-byte records: original geometry (HHhh),
then each facing's scaled geometry (HHhh). Pixel payloads live in pages.gpu.
The complete KFP3 banks remain conversion/verification intermediates.
"""
import struct


def player_metadata(blob):
    if len(blob) < 8 or blob[:4] != b'KFP3':
        raise ValueError('Expected a complete KFP3 player bank')
    count, = struct.unpack_from('<I', blob, 4)
    base = 8 + count * 40
    if not 0 < count <= 512 or base > len(blob):
        raise ValueError('Invalid player frame count')
    output = bytearray(struct.pack('<4sI', b'KFP4', count))
    for frame in range(count):
        at = 8 + frame * 40
        w, h, _, _ = struct.unpack_from('<HHhh', blob, at)
        if not w or not h or w * h > 512 * 512:
            raise ValueError('Invalid original player geometry')
        output.extend(blob[at:at + 8])
        for facing in range(2):
            raster = at + 8 + facing * 16
            offset, size, w, h, _, _ = struct.unpack_from('<IIHHhh', blob, raster)
            if (not w or not h or w * h > 512 * 512 or size < 4 or
                    offset > len(blob) - base or size > len(blob) - base - offset):
                raise ValueError('Invalid player raster')
            output.extend(blob[raster + 8:raster + 16])
    return bytes(output)
