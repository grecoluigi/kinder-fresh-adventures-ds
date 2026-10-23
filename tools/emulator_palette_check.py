"""Read actual F/G controls and validate gameplay/UI palette ownership via RSP."""
import struct
def check(rsp,symbols):
 if 'gpu_palette_owned' not in symbols:return None
 owned=bool(rsp.read(symbols['gpu_palette_owned'],1)[0])
 direct=owned and 'gpu_direct_storage'in symbols and bool(rsp.read(symbols['gpu_direct_storage'],1)[0])
 indexed='gpu_indexed_foreground'in symbols and bool(rsp.read(symbols['gpu_indexed_foreground'],1)[0])
 controls=list(rsp.read(0x04000245,2))
 expected=([0x93,0x9b]if direct or indexed else[0x83,0x8b])if owned else[0x91,0x99]
 assert controls==expected,('palette ownership disagrees with hardware registers',owned,controls,expected)
 display=struct.unpack('<I',rsp.read(0x04000000,4))[0]
 if owned:assert not display&(1<<10),'gameplay palette banks overlap visible BG2 bitmap'
 native='gpu_native_bg_storage'in symbols and bool(rsp.read(symbols['gpu_native_bg_storage'],1)[0])
 e=rsp.read(0x04000244,1)[0];assert e==(0x83 if indexed or direct else 0x84 if native else 0x81),('scenery palette ownership disagrees with E',direct,native,indexed,e)
 if indexed:assert not display&(1<<30),'indexed foreground expects the regular BG palette'
 return {'owned':owned,'direct':direct,'indexed_foreground':indexed,'epoch':struct.unpack('<I',rsp.read(symbols['gpu_palette_epoch'],4))[0],'E':e,'F':controls[0],'G':controls[1],'BG2_visible':bool(display&(1<<10))}
