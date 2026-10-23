"""Pack adapted PCM into independently decodable 2048-frame KFS1 sound blocks."""
import hashlib
import struct
import numpy as np
from tile_storage import lz10, unlz

BLOCK_FRAMES = 2048

def pack_samples(assets, raw):
    pack = bytearray(b'KFS1'+struct.pack('<I', len(assets)))
    rows = []
    blocks = raw_blocks = 0
    for asset in assets:
        begin = len(pack)
        pcm = raw[asset['offset']:asset['offset']+asset['frames']*2]
        if len(pcm) != asset['frames']*2:
            raise ValueError('Truncated adapted sound')
        decoded = bytearray()
        for at in range(0, len(pcm), BLOCK_FRAMES*2):
            block = pcm[at:at+BLOCK_FRAMES*2]
            values = np.frombuffer(block, dtype='<u2').astype(np.int32)
            delta = (values-np.concatenate(([0], values[:-1]))) & 65535
            planes = (delta & 255).astype('u1').tobytes()+(delta >> 8).astype('u1').tobytes()
            compressed = bytes(lz10(planes))
            plain = len(compressed) >= len(block)
            payload = block if plain else compressed
            size = len(payload) | (0x8000 if plain else 0)
            pack.extend(struct.pack('<HH', len(values), size))
            pack.extend(payload)
            pack.extend(bytes(-len(pack) % 4))
            if plain:
                restored = block
                raw_blocks += 1
            else:
                data = unlz(payload)
                n = len(values)
                d = np.frombuffer(data[:n], dtype='u1').astype(np.uint16) | (np.frombuffer(data[n:], dtype='u1').astype(np.uint16) << 8)
                restored = (np.cumsum(d, dtype=np.uint64) & 65535).astype('<u2').tobytes()
            assert restored == block, (hex(asset['va']), at)
            decoded.extend(restored)
            blocks += 1
        assert bytes(decoded) == pcm
        rows.append(dict(asset, packed_offset=begin, stored_bytes=len(pack)-begin,
                         pcm_sha256=hashlib.sha256(decoded).hexdigest()))
    return bytes(pack), rows, {'blocks': blocks, 'raw_blocks': raw_blocks, 'pcm_bytes': len(raw)}
