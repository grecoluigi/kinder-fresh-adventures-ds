#!/usr/bin/env python3
"""Build original highscore screens and native glyph metrics, using the original font and draw metrics."""
from pathlib import Path
import argparse,hashlib,json,struct
from types import SimpleNamespace
from decoded_assets import DecodedAssets
import pefile
from PIL import Image
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_ESP,UC_X86_REG_EIP
def build(decoded,game,output):
 ROOT=Path(__file__).resolve().parents[1];OUT=output;OUT.mkdir(parents=True,exist_ok=False)
 RESEARCH=OUT/'verification';RESEARCH.mkdir()
 assets=DecodedAssets(decoded);inv=assets.inventory
 font=inv['animation/interface/schrift.w01']['frames']
 pe=pefile.PE(str(game/'JR_FERRERO.exe'));im=pe.get_memory_mapped_image()
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(im)+4095)&~4095);u.mem_write(0x400000,im)
 u.mem_map(0x200000,0x50000);u.mem_map(0x4000,0x1000)
 draws=[]
 def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def ret(pop=0,value=0):
  esp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_EIP,word(esp));u.reg_write(UC_X86_REG_ESP,esp+pop+4)
 def hook(uc,address,size,data):
  esp=uc.reg_read(UC_X86_REG_ESP)
  if address==0x41ecbc:
   frame=word(esp+8);assert frame<len(font);ret(8,0x240000+frame*64)
  elif address==0x41d615:
   draws.append({'frame':(word(esp+4)-0x240000)//64,'x':word(esp+8),'y':word(esp+12)});ret(12)
 u.hook_add(UC_HOOK_CODE,hook)
 for f in font:u.mem_write(0x240000+f['index']*64+13,struct.pack('<I',f['width']))
 u.mem_write(0x230000,struct.pack('<II',1,0))
 def run(entry,args):
  u.mem_write(0x220000,struct.pack('<'+'I'*(len(args)+1),0x4000,*args));u.reg_write(UC_X86_REG_ESP,0x220000);u.reg_write(UC_X86_REG_ECX,0x230000);u.emu_start(entry,0x4000,count=2000000);assert u.reg_read(UC_X86_REG_EIP)==0x4000;return u.reg_read(UC_X86_REG_EAX)
 metrics=[]
 for character in range(256):
  glyph=run(0x401190,[character,0]);glyph=glyph if glyph<0x80000000 else glyph-0x100000000
  draws.clear();u.mem_write(0x210000,bytes([character,0]));run(0x4012f0,[0x210000,0,100,100])
  advance=run(0x401460,[character,0]);dy=draws[0]['y']-100 if draws else 0
  metrics.append({'character':character,'frame':glyph,'advance':advance,'dy':dy})
 records=[];pixels=bytearray()
 for f in font:
  records.append(struct.pack('<IHH',len(pixels)//2,f['width'],f['height']))
  for r,g,b,a in assets.image(f).get_flattened_data():pixels+=struct.pack('<H',0 if not a else 0x8000|(r>>3)|((g>>3)<<5)|((b>>3)<<10))
 (OUT/'font.bin').write_bytes(b'KHS1'+struct.pack('<II',len(font),len(pixels)//2)+b''.join(records)+pixels)
 names=['GIUNGLA','VALLE','MONTAGNA','FABBRICA1','INDIETRO'];world_for_focus=[0,3,1,2]
 background=assets.image(inv['pics/highscorebg.bmp'])
 boss=inv['animation/interface/gegner.w01']['frames'];hitboxes=[]
 for name in names:
  f=inv[f'animation/interface/{name.lower()}.w01']['frames'][0]
  hitboxes.append([f['x'],f['y'],f['x']+f['width'],f['y']+f['height']])
 screens=[]
 for world in range(4):
  for focus in range(-1,5):
   screen=background.copy();f=boss[world];screen.alpha_composite(assets.image(f),(f['x'],f['y']))
   for i,name in enumerate(names):
    frames=inv[f'animation/interface/{name.lower()}.w01']['frames'];index=4 if i<4 and world_for_focus[i]==world else int(i==focus)
    f=frames[index];screen.alpha_composite(assets.image(f),(f['x'],f['y']))
   sp=screen.convert('RGB').resize((256,192),Image.Resampling.LANCZOS).load();raw=bytearray();preview=Image.new('RGB',(256,192));pp=preview.load()
   for y in range(192):
    for x in range(256):
     r,g,b=sp[x,y];v=0x8000|(r>>3)|((g>>3)<<5)|((b>>3)<<10);raw+=struct.pack('<H',v);pp[x,y]=((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31)
   filename=f'world{world}_focus{focus+1}.bin';(OUT/filename).write_bytes(raw);screens.append({'world':world,'focus':focus,'file':filename,'sha256':hashlib.sha256(raw).hexdigest()})
   if focus==-1:preview.save(RESEARCH/f'world{world}-background.png')
 keyboard0=list(pe.get_data(0x4550e8-0x400000,87));keyboard1=list(pe.get_data(0x455140-0x400000,87))
 header='/* Original401190/4012f0/401460 glyph observations; generated. */\n'
 header+='typedef struct { int16_t frame; uint8_t advance; int8_t dy; } HighscoreGlyph;\n'
 header+='static const HighscoreGlyph highscore_glyphs[256] = {\n'+''.join(f"    {{{m['frame']}, {m['advance']}, {m['dy']}}},\n"for m in metrics)+'};\n'
 header+='static const uint8_t highscore_scancode_chars[2][87] = {\n'+''.join('    {'+', '.join(map(str,row))+'},\n'for row in [keyboard0,keyboard1])+'};\n'
 header+='static const int16_t highscore_hitboxes[5][4] = {\n'+''.join('    {'+', '.join(map(str,row))+'},\n'for row in hitboxes)+'};\n'
 (OUT/'highscore_assets.h').write_text(header)
 manifest={'native_glyph_functions':['0x401190','0x4012f0','0x401460'],'glyph_metrics':metrics,'glyph_pixel_bytes':len(pixels),'font_file_bytes':(OUT/'font.bin').stat().st_size,'screens':screens,'hitboxes_source_pixels':hitboxes,'world_for_focus':world_for_focus,'limitations':['Native glyph lookup/layout routines execute with mocked resource-frame lookup and sprite draw calls; no Windows execution.','Background and sprite composition follow observed draw order; native input/draw command verification is separate.']}
 (RESEARCH/'assets.json').write_text(json.dumps(manifest,indent=2)+'\n');print(f'55 native glyphs, {len(pixels)} resident pixel bytes,24 streamed screens.')

 return SimpleNamespace(ROOT=ROOT,u=u,word=word,ret=ret,run=run,draws=draws,font=font,inv=inv,boss=boss,names=names,world_for_focus=world_for_focus,keyboard0=keyboard0,keyboard1=keyboard1)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.assets,a.source,a.output)
