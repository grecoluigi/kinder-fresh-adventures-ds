"""Read the current ARM32 NativeSourceCache at an opt-in debugger sample.

Checks the linked object's size and arena invariants before reporting occupancy.
This adds debugger traffic; use a separate run from phase timing comparisons.
"""
import re
import struct


def occupancy(rsp, address, link_map):
    # ARM32: three pointers, two unsigned lengths, callback pointer; 256
    # 16-byte entries, then clock/count and 128 u16 hints. Reject ABI drift.
    records = re.findall(r' \.bss\.source_cache\s+0x[0-9a-f]+\s+(0x[0-9a-f]+) build/kinder_fresh/source/native_actors\.c\.o', link_map)
    assert len(records) == 1 and int(records[0], 16) == 4384, 'NativeSourceCache ABI changed'
    memory, extra, other, extra_bytes, other_bytes, writer = struct.unpack('<6I', rsp.read(address, 24))
    clock, count = struct.unpack('<2I', rsp.read(address+4120, 8))
    assert memory and count <= 256 and not writer, 'Expected exclusively owned native arenas'
    assert bool(extra) == bool(extra_bytes) and bool(other) == bool(other_bytes)
    capacity = 32768+extra_bytes+other_bytes
    ranges = ((0, 32768), (32768, 32768+extra_bytes), (32768+extra_bytes, capacity))
    occupied = small = previous_end = 0
    data = rsp.read(address+24, count*16) if count else b''
    for index in range(count):
        offset, at, age, size = struct.unpack_from('<IIIH', data, index*16)
        assert size and size <= 32768 and age <= clock and at >= previous_end
        assert any(at >= start and at+size <= end for start, end in ranges)
        assert offset+size <= 0xffffffff
        occupied += size
        small += size <= 1024
        previous_end = at+size
    result = {'native_cache_entries': count, 'native_cache_entry_limit': 256,
            'native_cache_resident_bytes': occupied, 'native_cache_capacity_bytes': capacity,
            'native_cache_free_bytes': capacity-occupied, 'native_cache_small_ranges': small,
            'native_cache_record_limit_reached': count == 256}

    metadata = re.findall(r' \.bss\.metadata_cache\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+) build/kinder_fresh/source/native_actors\.c\.o', link_map)
    if metadata:
        assert len(metadata) == 1 and int(metadata[0][1], 16) == 276, 'NativeMetadataCache ABI changed'
        data = rsp.read(int(metadata[0][0], 16), 276)
        metadata_memory = struct.unpack_from('<I', data)[0]
        valid, metadata_clock, hits, misses = struct.unpack_from('<4I', data, 260)
        assert metadata_memory and memory == metadata_memory+32768, 'Expected disjoint player-arena partitions'
        for index in range(32):
            if valid & (1 << index):
                offset = struct.unpack_from('<I', data, 4+index*4)[0]
                age = struct.unpack_from('<I', data, 132+index*4)[0]
                assert not offset % 1024 and age <= metadata_clock
        result.update(native_metadata_entries=valid.bit_count(), native_metadata_capacity_bytes=32768,
                      native_metadata_hits=hits, native_metadata_misses=misses,
                      native_total_capacity_bytes=capacity+32768)
    return result
