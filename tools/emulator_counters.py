#!/usr/bin/env python3
"""Read live melonDS ARM9 counters via RSP; no pixels or disk-ROM edits.

Run after launching melonDS with GDB enabled, JIT disabled, and this workspace's
canonical ROM. Uses ELF symbols, rejects mismatched keysHeld machine code, then
selects Jungle and replaces keysHeld in emulator RAM only for scripted input.
Always restores the original instructions. Close melonDS after the session.
"""
from rom_artifact import rom_path as resolve_rom
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import re
from functools import lru_cache
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = Path(os.environ.get('KF_DS_ARTIFACT_DIR', ROOT / 'ds')).resolve()
NM = Path.home() / '.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin/arm-none-eabi-nm'
prefix_hash_cache={}
def prefix_hash(map_name,x,y,overlay=False,all_static=False):
    key=(map_name,x,y,overlay,all_static)
    if key in prefix_hash_cache:return prefix_hash_cache[key]
    # Independent packed-resource sampling; the interpreter needs the existing
    # asset venv's numpy when the DS GPU path is active.
    from scenery_codec import unpack
    name=map_name+('.enemy'if map_name.lower()in ('welt1.w02','welt1t.w02')else '')
    atlas=(ROOT/'ds/nitrofs/composite'/(name+'.atlas')).read_bytes();idx=(ROOT/'ds/nitrofs/composite'/(name+'.index')).read_bytes()
    n=struct.unpack_from('<I',atlas,4)[0];base=8+n*8;w,h,nc,npairs=struct.unpack_from('<HHII',idx,4);kind,begin,count=struct.unpack_from('<III',idx,20);assert kind==0
    image=[0]*49152;decoded={}
    passes=[(begin,count)]
    if overlay or all_static:
        for command in range(1,nc):
            k,b,n=struct.unpack_from('<III',idx,20+command*12)
            if k==0 and (all_static or n>=128):
                passes.append((b,n))
                if not all_static:break
    for begin,count in passes:
        for i in range(begin,begin+count):
            cell,tile=struct.unpack_from('<HH',idx,20+nc*12+i*4);tx=(cell%w)*16;ty=(cell//w)*16
            left=max(x,tx);right=min(x+256,tx+16);top=max(y,ty);bottom=min(y+192,ty+16)
            if left>=right or top>=bottom:continue
            if tile not in decoded:
                offset,length=struct.unpack_from('<II',atlas,8+tile*8);decoded[tile]=unpack(atlas[base+offset:base+offset+length])
            pixels=decoded[tile]
            for yy in range(top,bottom):
                for xx in range(left,right):
                    color=int(pixels[(yy-ty)*16+xx-tx])
                    if color&32768:image[(yy-y)*256+xx-x]=color
    value=2166136261
    for color in image:value=((value^color)*16777619)&0xffffffff
    prefix_hash_cache[key]=value;return value


class RSP:
    def __init__(self, port):
        self.sock = socket.create_connection(('127.0.0.1', port), 5)
        self.sock.settimeout(5)
        # melonDS 1.1 requires an initial acknowledgement before any packet.
        self.sock.sendall(b'+')
        if self.sock.recv(1) != b'+':
            raise RuntimeError('melonDS initial acknowledgement missing')

    def command(self, text):
        payload = text.encode()
        self.sock.sendall(b'$' + payload + b'#' + f'{sum(payload) & 255:02x}'.encode())
        return self.receive()

    def receive(self):
        while True:
            byte = self.sock.recv(1)
            if not byte:
                raise RuntimeError('debugger disconnected before packet')
            if byte == b'$':
                break
        response = bytearray()
        while True:
            byte = self.sock.recv(1)
            if not byte:
                raise RuntimeError('debugger disconnected')
            if byte == b'#':
                break
            response.extend(byte)
        checksum = self.sock.recv(1) + self.sock.recv(1)
        if int(checksum, 16) != sum(response) & 255:
            raise RuntimeError('RSP checksum mismatch')
        self.sock.sendall(b'+')
        return response.decode()

    def read(self, address, size):
        # melonDS rejects replies larger than its bounded RSP packet buffer.
        # Existing telemetry reads fit; decoded PCM needs multiple requests.
        if size>256:
            return b''.join(self.read(address+offset,min(256,size-offset))
                            for offset in range(0,size,256))
        result = self.command(f'm{address:08x},{size:x}')
        if result.startswith('E'):
            raise RuntimeError(result)
        data = bytes.fromhex(result)
        if len(data) != size:
            raise RuntimeError('short debugger memory read')
        return data

    def write(self, address, data):
        if self.command(f'M{address:08x},{len(data):x}:{data.hex()}') != 'OK':
            raise RuntimeError('debugger write failed')

    def resume(self):
        # Continue has an acknowledgement, but no response until a stop event.
        self.sock.sendall(b'$c#63')
        if self.sock.recv(1) != b'+':
            raise RuntimeError('continue acknowledgement missing')


def symbols():
    lines = subprocess.check_output([str(NM), '-a', str(ARTIFACT_DIR / 'build/kinder_fresh.elf')], text=True)
    return {parts[2]: int(parts[0], 16) for line in lines.splitlines()
            if len(parts := line.split()) == 3}


@lru_cache(maxsize=None)
def module_bss_symbol(module,name):
    """Local names can repeat; the linker map identifies their owning object."""
    content=(ARTIFACT_DIR/'build/kinder_fresh.map').read_text()
    matches=re.findall(r' \.bss\.'+re.escape(name)+r'\s+(0x[0-9a-f]+)\s+0x[0-9a-f]+ build/kinder_fresh/source/'+re.escape(module)+r'\.c\.o',content)
    if len(matches)!=1:raise RuntimeError((module,name,matches))
    return int(matches[0],16)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=3333)
    parser.add_argument('--seconds', type=int, default=12, help='seconds per input phase')
    parser.add_argument('--world',type=int,choices=range(4),default=0,
                        help='native world:0 Jungle,1 Ice,2 Factory,3 Fantasy')
    parser.add_argument('--walk-only',action='store_true',help='walk without holding jump in movement phases')
    parser.add_argument('--output', type=Path, default=ROOT / 'research/rendering/emulator-counter-samples.json')
    args = parser.parse_args()
    sym = symbols()
    sound_reference={}
    if 'sound_last_block' in sym:
        packed=(ROOT/'ds/nitrofs/sounds/samples.hw').read_bytes()
        reference=(ROOT/'generated/audio-lossless/reference.pcm').read_bytes()
        manifest=json.loads((ROOT/'research/audio/lossless-staging.json').read_text())
        assert hashlib.sha256(packed).hexdigest()==manifest['stored_sha256']
        assert hashlib.sha256(reference).hexdigest()==manifest['reference_sha256']
        for asset in manifest['assets']:
            offset=asset['storage_offset'];pcm=asset['reference_offset'];left=asset['frames']
            while left:
                count,flags=struct.unpack_from('<HH',packed,offset)
                assert 0<count<=min(left,2048)
                sound_reference[offset]=(count,flags,reference[pcm:pcm+count*2])
                left-=count;pcm+=count*2;offset=(offset+4+(flags&32767)+3)&~3
            assert offset==asset['storage_offset']+asset['stored_bytes']
    rsp = RSP(args.port)
    held = sym['keysHeld']
    original = rsp.read(held, 4)
    if original != bytes.fromhex('014b1888'):
        raise RuntimeError('ELF/ROM mismatch or unexpected keysHeld instructions')
    # Connecting enters a stopped debugger session even with BreakOnStartup off.
    rsp.resume()
    rows = []
    active_breakpoint=None
    try:
        deadline = time.monotonic() + 30
        while struct.unpack('<I', rsp.read(sym['fps'], 4))[0] == 0:
            if time.monotonic() > deadline:
                raise RuntimeError('startup did not reach the frame loop')
            time.sleep(.25)
        # menu selection is consumed by the production dispatcher.
        rsp.write(sym['selection'],bytes([(0,2,3,1)[args.world]]))
        deadline = time.monotonic() + 30
        while struct.unpack('<I', rsp.read(sym['updates_per_second'], 4))[0] == 0:
            if time.monotonic() > deadline:
                raise RuntimeError('requested world did not start simulation')
            time.sleep(.25)
        if 'gpu_prefix_hash_request'in sym:rsp.write(sym['gpu_prefix_hash_request'],struct.pack('<I',1))
        if 'gpu_capture_request'in sym:rsp.write(sym['gpu_capture_request'],struct.pack('<I',2))
        phases = [('tutorial_idle', 0), ('right_jump', 17), ('left_jump', 33), ('idle_after', 0)]
        if args.walk_only:phases=[('tutorial_idle',0),('right_walk',16),('left_walk',32),('idle_after',0)]
        start = time.monotonic()
        for phase, buttons in phases:
            # Thumb: movs r0,#buttons; bx lr. Normal input filtering stays intact.
            rsp.write(held, struct.pack('<HH', 0x2000 | buttons, 0x4770))
            for _ in range(args.seconds):
                time.sleep(1)
                # Stop at the next frame-loop entry, after the previous render
                # and transfer. Stats cannot be cleared midway through reads.
                breakpoint = f'0,{sym["performance_frame"]:x},2'
                if rsp.command('Z' + breakpoint) != 'OK':
                    raise RuntimeError('frame breakpoint failed')
                active_breakpoint=breakpoint
                if not rsp.receive().startswith(('T', 'S')):
                    raise RuntimeError('frame breakpoint stop missing')
                row = {'phase': phase, 'host_seconds': round(time.monotonic() - start, 3)}
                for key in ('fps', 'updates_per_second', 'audio', 'update', 'render', 'transfer'):
                    row[key] = struct.unpack('<I', rsp.read(sym[key], 4))[0]
                fields = ('read_calls', 'read_bytes', 'tile_misses', 'sprite_misses', 'sprite_cache_bytes',
                          'setup_us', 'tiles_us', 'objects_us', 'callback_us', 'sample_misses',
                          'sample_cache_bytes', 'live_row_decodes', 'live_row_hits', 'background_us')
                row.update(zip(fields, struct.unpack('<14I', rsp.read(sym['render_stats'], 56))))
                row['music_underruns']=struct.unpack('<I',rsp.read(module_bss_symbol('audio','underruns'),4))[0]
                row['effect_underruns']=struct.unpack('<I',rsp.read(symbols()['sound_dropped'],4))[0]
                assert row['music_underruns']==0 and row['effect_underruns']==0,'audio ring underflow'
                for key in ('sound_pack_reads','sound_pack_bytes','sound_blocks_decoded'):
                    if key in sym:row[key]=struct.unpack('<I',rsp.read(sym[key],4))[0]
                if sound_reference and row.get('sound_blocks_decoded',0):
                    offset,count,flags=struct.unpack('<3I',rsp.read(sym['sound_last_block'],12))
                    expected_count,expected_flags,pcm=sound_reference[offset]
                    assert (count,flags)==(expected_count,expected_flags), 'live sound block metadata'
                    assert rsp.read(sym['sound_decoded'],count*2)==pcm, 'live DS PCM differs from reference'
                    row['sound_verified_block_offset']=offset
                    row['sound_verified_block_frames']=count
                    row['sound_verified_block_compressed']=not bool(flags&32768)
                if 'composite_prefix_us' in sym:
                    row['prefix_us']=struct.unpack('<I',rsp.read(sym['composite_prefix_us'],4))[0]
                    row['remaining_scenery_us']=struct.unpack('<I',rsp.read(sym['composite_remaining_us'],4))[0]
                    if 'composite_overlay_us' in sym:
                        row['overlay_us']=struct.unpack('<I',rsp.read(sym['composite_overlay_us'],4))[0]
                    passes=struct.unpack('<64I',rsp.read(sym['composite_pass_us'],256))
                    row['scenery_pass_us']={str(i):value for i,value in enumerate(passes) if value}
                row['player_state'] = struct.unpack('<i', rsp.read(sym['player'] + 200, 4))[0]
                row['dialogue_state']=struct.unpack('<i',rsp.read(sym['player']+240,4))[0]
                row['direction_latch']=struct.unpack('<i',rsp.read(sym['player']+260,4))[0]
                if 'npc_voice_key'in sym:row['NPC_voice_key']=hex(struct.unpack('<I',rsp.read(sym['npc_voice_key'],4))[0])
                x, y = struct.unpack('<ii', rsp.read(sym['body'] + 36, 8))
                row['player_x'], row['player_y'] = x / 4096, y / 4096
                camera = rsp.read(sym['camera'], 124)
                reference = struct.unpack_from('<h', camera, 120)[0]
                tx, ty, ox, oy = struct.unpack_from('<4h', camera, reference * 12)
                row['camera_x'], row['camera_y'] = tx * 32 - ox, ty * 32 - oy
                if 'hardware_background_ready' in sym:
                    row['hardware_background_active']=bool(rsp.read(sym['hardware_background_ready'],1)[0])
                    row['hardware_background_x']=struct.unpack('<I',rsp.read(sym['hardware_background_x'],4))[0]
                    row['display_control']=struct.unpack('<I',rsp.read(0x04000000,4))[0]
                    row['bg2_control']=struct.unpack('<H',rsp.read(0x0400000c,2))[0]
                    row['bg3_control']=struct.unpack('<H',rsp.read(0x0400000e,2))[0]
                    row['bg3_x_readback']=struct.unpack('<I',rsp.read(0x04000038,4))[0]
                    row['vram_d_control']=rsp.read(0x04000243,1)[0]
                    if row['hardware_background_active']:
                        assert row['display_control'] & (1<<10) and row['display_control'] & (1<<11), 'both hardware layers must be enabled'
                        assert row['vram_d_control']==0x91, 'D must map mainBG at06040000'
                        assert row['bg2_control'] & 3==0 and row['bg3_control'] & 3==3, 'foreground/background priorities'
                        assert row['bg3_control'] & (1<<13) and (row['bg3_control']>>8)&31==16, 'background wrap/base'
                        row['hardware_background_hash']=struct.unpack('<I',rsp.read(sym['hardware_background_hash'],4))[0]
                        route=struct.unpack('<I',rsp.read(sym['active_route'],4))[0]
                        row['native_world']=struct.unpack('<I',rsp.read(route+12,4))[0]
                        row['tutorial']=bool(rsp.read(route+16,1)[0])
                        assert row['native_world']==args.world,'menu/native world mapping'
                        map_pointer=struct.unpack('<I',rsp.read(route,4))[0]
                        row['map']=rsp.read(map_pointer,32).split(b'\0')[0].decode('ascii')
                        stem=row['map'].split('.')[0].lower()
                        if stem.endswith('e'):stem=stem[:-1]
                        expected_hashes=json.loads((ROOT/'research/rendering/background-vram-hashes.json').read_text())
                        assert row['hardware_background_hash']==expected_hashes[stem+'.par'], 'uploaded VRAM checksum'
                        row['bg3_shadow_x'],row['bg3_shadow_y']=struct.unpack('<ii',rsp.read(sym['bgState']+3*40+20,8))
                        row['bg3_dirty']=bool(rsp.read(sym['bgState']+3*40+36,1)[0])
                        assert row['bg3_shadow_x']==row['hardware_background_x']*256 and row['bg3_shadow_y']==0 and not row['bg3_dirty'], 'VBlank library scroll publication'
                if 'gpu_mode'in sym:
                    row['gpu_mode']=bool(rsp.read(sym['gpu_mode'],1)[0])
                    if row['gpu_mode']:
                        row['texture_static_ready']=bool(rsp.read(sym['texture_static_ready'],1)[0])if 'texture_static_ready'in sym else False
                        row['texture_overlay_ready']=bool(rsp.read(sym['texture_overlay_ready'],1)[0])if 'texture_overlay_ready'in sym else False
                        row['gpu_prefix_visible']=bool(rsp.read(sym['gpu_prefix_visible'],1)[0]);assert row['gpu_prefix_visible'],'GPU prefix must be visible during gameplay'
                        for name in ('gpu_prefix_pixels','gpu_prefix_bank','gpu_prefix_x','gpu_prefix_y','gpu_prefix_hash','gpu_prefix_hash_x','gpu_prefix_hash_y'):row[name]=struct.unpack('<I',rsp.read(sym[name],4))[0]
                        row['VRAM_controls']=list(rsp.read(0x04000240,10));assert row['VRAM_controls'][:7]+row['VRAM_controls'][8:]==[0x83,0x8b,0x84,0x91,0x81,0x91,0x99,0x80,0x80],'GPU/bitmap/cache bank mapping'
                        row['bg0_control']=struct.unpack('<H',rsp.read(0x04000008,2))[0];assert row['bg0_control']&3==1 and row['display_control']&(1<<8)and row['display_control']&8,'3D priority/enable'
                        row['rendered_lines']=struct.unpack('<I',rsp.read(0x04000320,4))[0]
                        row['3D_control']=struct.unpack('<H',rsp.read(0x04000060,2))[0];assert not row['3D_control']&(3<<12),'3D render underflow/overflow'
                        assert row['gpu_prefix_x']==(row['camera_x']*8+12)//25 and row['gpu_prefix_y']==(row['camera_y']*8+12)//25,'GPU/foreground camera must agree'
                        if row['gpu_prefix_hash']:
                            assert row['gpu_prefix_hash']==prefix_hash(row['map'],row['gpu_prefix_hash_x'],row['gpu_prefix_hash_y'],row['texture_overlay_ready'],row['texture_static_ready']),'uploaded foreground texture differs from packed resources'
                            row['gpu_texture_hash_verified']=True
                        if 'gpu_capture_kind'in sym:
                            for name in ('gpu_capture_kind','gpu_capture_hash','gpu_capture_expected','gpu_capture_x','gpu_capture_y'):row[name]=struct.unpack('<I',rsp.read(sym[name],4))[0]
                            if row['gpu_capture_kind']:
                                if 'gpu_capture_mismatches'in sym:
                                    row['gpu_capture_mismatches']=struct.unpack('<I',rsp.read(sym['gpu_capture_mismatches'],4))[0];assert row['gpu_capture_mismatches']==0,'rendered pixel differences'
                                row['gpu_capture_equal']=bool(rsp.read(sym['gpu_capture_equal'],1)[0]);assert row['gpu_capture_equal'],'actual rendered output differs from CPU composition'
                                if row['gpu_capture_kind']==1:assert row['gpu_capture_hash']==prefix_hash(row['map'],row['gpu_capture_x'],row['gpu_capture_y'],row['texture_overlay_ready'],row['texture_static_ready']),'3D-only output differs from packed scenery'
                rows.append(row)
                if rsp.command('z' + breakpoint) != 'OK':
                    raise RuntimeError('frame breakpoint removal failed')
                active_breakpoint=None
                rsp.resume()
                print(json.dumps(row), flush=True)
    finally:
        try:
            if active_breakpoint is not None:rsp.command('z'+active_breakpoint)
            rsp.write(held, original)
            if active_breakpoint is not None:rsp.resume()
        finally:
            rsp.sock.close()
        result = {'rom_sha256': hashlib.sha256((resolve_rom(ARTIFACT_DIR)).read_bytes()).hexdigest(),
                  'native_world_requested':args.world,
                  'walk_only':args.walk_only,
                  'method': 'melonDS 1.1 ARM9 RSP memory reads; keysHeld RAM-only scripted input',
                  'scope': 'emulator samples at next performance_frame entry, not hardware timings; debugger pauses are excluded from emulated time',
                  'samples': rows}
        checked=[row for row in rows if 'sound_verified_block_offset' in row]
        blocks={row['sound_verified_block_offset']:row for row in checked}
        if checked:
            result['live_sound_pcm']={
                'snapshots':len(checked),'unique_blocks':len(blocks),
                'unique_frames':sum(row['sound_verified_block_frames'] for row in blocks.values()),
                'compressed_blocks':sum(row['sound_verified_block_compressed'] for row in blocks.values()),
                'raw_blocks':sum(not row['sound_verified_block_compressed'] for row in blocks.values()),
                'all_byte_equal':True}
        args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
