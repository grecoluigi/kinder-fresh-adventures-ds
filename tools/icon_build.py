"""Fit icon.jpg into a DS banner and verify the packed ROM icon.

Run with tools/assets-venv/bin/python tools/icon_build.py [--verify-rom].
Palette index 0 is reserved for transparency; the JPEG remains opaque.
"""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import argparse
import hashlib
import json
import struct
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def crc16(data):
    crc = 0xffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xa001 if crc & 1 else 0)
    return crc


def build(source=None, output=None, preview_dir=None):
    source = Path(source) if source is not None else ROOT / 'icon.jpg'
    output = Path(output) if output is not None else ROOT / 'ds/icon.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    if preview_dir is not None:
        preview_dir = Path(preview_dir)
        preview_dir.mkdir(parents=True, exist_ok=True)
    image = ImageOps.exif_transpose(Image.open(source)).convert('RGB')
    fitted = ImageOps.contain(image, (32, 32), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (32, 32), image.getpixel((0, 0)))
    canvas.paste(fitted, ((32 - fitted.width) // 2, (32 - fitted.height) // 2))
    quantized = canvas.quantize(colors=15, method=Image.Quantize.MEDIANCUT,
                                dither=Image.Dither.NONE)
    palette = quantized.getpalette()[:45]
    # Prequantize to the actual RGB555 gamut. ndstool reserves zero too.
    palette = [(component >> 3) << 3 for component in palette]
    result = Image.new('P', (32, 32))
    result.putpalette([0, 0, 0] + palette + [0] * (768 - 48))
    result.putdata([index + 1 for index in quantized.get_flattened_data()])
    result.save(output, transparency=0, optimize=True)
    if preview_dir is not None:
        result.convert('RGBA').save(preview_dir / 'icon.png')
        result.convert('RGBA').resize((256, 256), Image.Resampling.NEAREST).save(
            preview_dir / 'icon_enlarged.png')
    report = dict(source=source.name, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  source_size=list(image.size), fitted_size=list(fitted.size),
                  dimensions=[32, 32], visible_colors=len(set(result.get_flattened_data())),
                  palette_format='RGB555, index 0 reserved for transparency',
                  resampling='Lanczos, full image, no crop', dithering='none')
    output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


def verify():
    rom_path = resolve_rom(ROOT / 'ds')
    rom = rom_path.read_bytes()
    offset = struct.unpack_from('<I', rom, 0x68)[0]
    banner = rom[offset:offset + 0x840]
    assert len(banner) == 0x840 and offset > 0
    assert crc16(banner[0x20:0x840]) == struct.unpack_from('<H', banner, 2)[0]
    colors = struct.unpack_from('<16H', banner, 0x220)
    packed = banner[0x20:0x220]
    pixels = []
    indices = []
    for y in range(32):
        for x in range(32):
            pos = ((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
            index = (packed[pos] >> (4 * (x % 2))) & 15
            indices.append(index)
            color = colors[index]
            pixels.append(((color & 31) << 3, ((color >> 5) & 31) << 3,
                           ((color >> 10) & 31) << 3))
    expected = Image.open(ROOT / 'ds/icon.png').convert('RGB')
    assert pixels == list(expected.get_flattened_data()), 'Packed ROM icon differs from converted JPEG'
    assert 0 not in indices, 'Opaque JPEG pixels must not become transparent'
    decoded = Image.new('RGB', (32, 32))
    decoded.putdata(pixels)
    decoded.save(ROOT / 'ds/previews/icon_rom.png')
    report = dict(rom_sha256=hashlib.sha256(rom).hexdigest(), banner_offset=offset,
                  banner_version=struct.unpack_from('<H', banner)[0],
                  crc_valid=True, pixels_matched=1024, accidental_transparent_pixels=0)
    (ROOT / 'ds/icon_verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-rom', action='store_true')
    parser.add_argument('--source', type=Path, help='User-supplied icon image')
    parser.add_argument('--output', type=Path, help='Converted 32x32 indexed PNG')
    parser.add_argument('--preview-dir', type=Path)
    args = parser.parse_args()
    if args.verify_rom and (args.source or args.output or args.preview_dir):
        parser.error('--verify-rom uses the current playable ROM and icon')
    verify() if args.verify_rom else build(args.source, args.output, args.preview_dir)
