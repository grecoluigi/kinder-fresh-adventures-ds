"""Build and optionally run an isolated hardware2D tilemap/scroll/palette fixture.
Top pixels use DS display capture; bottomH/I is memory/register verification only.
"""
from rom_artifact import rom_path as resolve_rom
from pathlib import Path
import argparse,hashlib,json,shutil,struct,subprocess,time
import numpy as np
from tile_storage import unlz,lz10
from emulator_counters import RSP,NM
from emulator_output import BoundedOutput
from playtest import CONFIG,EMU,processes,section_option,write_config
R=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include <nds.h>
#include <filesystem.h>
#include <stdio.h>
#include <string.h>
#include "native_bg_assets.h"
#define CASES @CASES@
volatile unsigned fixture_done,fixture_error,fixture_mismatches[CASES],fixture_diffs[CASES][3],fixture_hashes[CASES][2];
volatile unsigned fixture_sub_mismatches,fixture_cache_mismatches,fixture_max_slots;
volatile unsigned fixture_registers[8];
static NativeBGAssets asset;
static uint16_t expected[49152],map_entries[2048],tile[32];
static uint32_t keys[960],pages[9][256],page_ids[9];
__attribute__((noinline)) void fixture_checkpoint(void){asm volatile("" ::: "memory");}
static bool load(FILE *f,void *p,unsigned bytes){return fread(p,1,bytes,f)==bytes;}
static uint16_t parallax(unsigned x,unsigned y){return RGB15((x/16)%32,(y/8)%32,5)|32768;}
int main(void){
 FILE *f=NULL;unsigned active=0;
 videoSetMode(MODE_5_2D|DISPLAY_BG_EXT_PALETTE);
 videoSetModeSub(MODE_5_2D);
 vramSetBankA(VRAM_A_LCD);vramSetBankB(VRAM_B_TEXTURE_SLOT1);
 vramSetBankC(VRAM_C_MAIN_BG_0x06000000);vramSetBankD(VRAM_D_MAIN_BG_0x06040000);
 vramSetBankE(VRAM_E_LCD);vramSetBankF(VRAM_F_TEX_PALETTE_SLOT0);vramSetBankG(VRAM_G_TEX_PALETTE_SLOT1);
 vramSetBankH(VRAM_H_SUB_BG);vramSetBankI(VRAM_I_SUB_BG_0x06208000);
 int bg=bgInit(1,BgType_Text8bpp,BgSize_T_512x256,30,0);bgSetPriority(bg,1);bgHide(bg);
 int back=bgInit(3,BgType_Bmp16,BgSize_B16_256x256,16,0);bgSetPriority(back,3);bgWrapOff(back);
 int sub=bgInitSub(3,BgType_Bmp8,BgSize_B8_256x256,0,0);bgSetPriority(sub,0);bgWrapOff(sub);
 for(unsigned i=0;i<256;i++)BG_PALETTE_SUB[i]=RGB15(i&31,(i*3)&31,(i*7)&31);
 volatile uint16_t *bottom=(volatile uint16_t *)0x06200000;
 for(unsigned y=0;y<192;y++)for(unsigned x=0;x<256;x+=2){
  unsigned l=(x+y*3)%255+1,r=(x+1+y*3)%255+1;bottom[y*128+x/2]=(uint16_t)(l|(r<<8));
 }
 volatile uint16_t *cache=(volatile uint16_t *)0x06010000;
 for(unsigned i=0;i<24576;i++)cache[i]=(uint16_t)(0x1200+(i%251));
 volatile uint16_t *background=bgGetGfxPtr(back);
 for(unsigned y=0;y<192;y++)for(unsigned x=0;x<256;x++)background[y*256+x]=parallax(x,y);
 lcdMainOnTop();bgUpdate();
 if(!nitroFSInit(NULL)){fixture_error=1;goto finish;}
 f=fopen("nitro:/cases.bin","rb");unsigned count;
 if(!f||!load(f,&count,4)||count!=CASES){fixture_error=2;goto finish;}
 for(active=0;active<CASES;active++){
  unsigned length,camera[2];char path[128];
  if(!load(f,&length,4)||length>=100||!load(f,path,length)||!load(f,camera,8)||!load(f,expected,sizeof(expected))){fixture_error=3;goto finish;}path[length]=0;
  bgHide(bg);swiWaitForVBlank();native_bg_close(&asset);
  if(!native_bg_open(&asset,path)){fixture_error=4;goto finish;}
  vramSetBankE(VRAM_E_LCD);for(unsigned i=0;i<32768;i++)VRAM_E[i]=0x5a5a;
  for(unsigned i=0;i<4096;i++)VRAM_E[4096+i]=asset.palette[i];
  vramSetBankE(VRAM_E_BG_EXT_PALETTE);
  memset(map_entries,0,sizeof(map_entries));for(unsigned i=0;i<9;i++)page_ids[i]=0xffffffff;
  if(!native_bg_tile(&asset,0,(uint8_t *)tile)){fixture_error=5;goto finish;}
  volatile uint16_t *gfx=bgGetGfxPtr(bg);for(unsigned i=0;i<32;i++){if(tile[i]){fixture_error=6;goto finish;}gfx[i]=0;}
  unsigned used=1,page_count=0;keys[0]=0;
  for(unsigned y=camera[1]/8;y<=(camera[1]+191)/8;y++)for(unsigned x=camera[0]/8;x<=(camera[0]+255)/8;x++){
   if(x>=asset.width||y>=asset.height){fixture_error=7;goto finish;}
   unsigned page=(y/16)*((asset.width+15)/16)+x/16,pi=0;
   while(pi<page_count&&page_ids[pi]!=page)pi++;
   if(pi==page_count){if(page_count==9||!native_bg_page(&asset,page,pages[pi])){fixture_error=8;goto finish;}page_ids[pi]=page;page_count++;}
   unsigned word=pages[pi][(y%16)*16+x%16],id=word&0x0fffffff,slot=0;
   while(slot<used&&keys[slot]!=id)slot++;
   if(slot==used){if(used==960||!native_bg_tile(&asset,id,(uint8_t *)tile)){fixture_error=9;goto finish;}keys[used++]=id;for(unsigned i=0;i<32;i++)gfx[slot*32+i]=tile[i];}
   unsigned map_at=(y%32)*32+(x%32)+((x%64)/32)*1024;
   map_entries[map_at]=(uint16_t)(slot|((word>>28)<<12));
  }
  if(used>fixture_max_slots)fixture_max_slots=used;
  volatile uint16_t *map=bgGetMapPtr(bg);for(unsigned i=0;i<2048;i++)map[i]=map_entries[i];
  bgSetScroll(bg,camera[0]%512,camera[1]%256);bgShow(bg);bgUpdate();for(unsigned i=0;i<3;i++)swiWaitForVBlank();
  REG_DISPCAPCNT=DCAP_ENABLE|DCAP_MODE(DCAP_MODE_A)|DCAP_SRC_A(DCAP_SRC_A_COMPOSITED)|DCAP_SIZE(DCAP_SIZE_256x192)|DCAP_BANK(0);
  unsigned timeout=0;while((REG_DISPCAPCNT&DCAP_ENABLE)&&timeout++<4)swiWaitForVBlank();
  if(REG_DISPCAPCNT&DCAP_ENABLE){fixture_error=10;goto finish;}
  unsigned wanted=2166136261u,actual=2166136261u;
  for(unsigned i=0;i<49152;i++){
   uint16_t color=VRAM_A[i];wanted=(wanted^expected[i])*16777619u;actual=(actual^color)*16777619u;
   if(color!=expected[i]){if(!fixture_mismatches[active]){fixture_diffs[active][0]=i;fixture_diffs[active][1]=expected[i];fixture_diffs[active][2]=color;}fixture_mismatches[active]++;}
  }
  fixture_hashes[active][0]=wanted;fixture_hashes[active][1]=actual;
  for(unsigned y=0;y<192;y++)for(unsigned x=0;x<256;x+=2){unsigned l=(x+y*3)%255+1,r=(x+1+y*3)%255+1;if(bottom[y*128+x/2]!=(uint16_t)(l|(r<<8)))fixture_sub_mismatches++;}
  for(unsigned i=0;i<24576;i++)if(cache[i]!=(uint16_t)(0x1200+(i%251)))fixture_cache_mismatches++;
 }
 if(fgetc(f)!=EOF)fixture_error=11;
 finish:
 if(f)fclose(f);
 native_bg_close(&asset);
 fixture_registers[0]=VRAM_C_CR;fixture_registers[1]=VRAM_D_CR;fixture_registers[2]=VRAM_E_CR;fixture_registers[3]=VRAM_H_CR;fixture_registers[4]=VRAM_I_CR;fixture_registers[5]=REG_BG1CNT;fixture_registers[6]=REG_BG3CNT_SUB;fixture_registers[7]=REG_DISPCNT;
 fixture_done=1;fixture_checkpoint();while(1)swiWaitForVBlank();
}
'''
def decode(blob):
 _,v,w,h,n,g,m,pa,tr,pr,po,flags=struct.unpack_from('<4s11I',blob);assert v==1 and g==16 and not flags
 palettes=np.frombuffer(blob,dtype='<u2',count=4096,offset=pa).reshape(16,256);patterns=[];pages=[]
 for at,count,target in [(tr,n,patterns),(pr,m,pages)]:
  for i in range(count):
   off,length=struct.unpack_from('<II',blob,at+8*i);target.append(unlz(blob[po+off:po+off+length]))
 return w,h,palettes,patterns,pages

def synthetic():
 patterns=[bytes(64),bytes((x+y*8)%256 for y in range(8)for x in range(8)),bytes([1])*64,bytes([255])*64];palette=np.zeros((16,256),dtype='<u2')
 for bank in range(16):
  for i in range(1,256):palette[bank,i]=32768|((i*7+bank)&31)|(((i*11+bank*3)&31)<<5)|(((i*13+bank*5)&31)<<10)
  palette[bank,1]=32768
 pages=[]
 for py in range(4):
  for px in range(8):pages.append(b''.join(struct.pack('<I',1+(x+y)%3|(((x*3+y*5)%16)<<28))for y in range(py*16,py*16+16)for x in range(px*16,px*16+16)))
 payload=bytearray();records=[]
 for raw in patterns+pages:
  packed=bytes(lz10(raw));records.append((len(payload),len(packed)));payload.extend(packed);payload.extend(bytes(-len(payload)%4))
 tr=8240;pr=tr+len(patterns)*8;po=pr+len(pages)*8
 return struct.pack('<4s11I',b'KNTB',1,128,64,len(patterns),16,len(pages),48,tr,pr,po,0)+palette.tobytes()+b''.join(struct.pack('<II',*v)for v in records)+payload

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--study-dir',type=Path,default=R/'research/rendering/native-bg-asset-study');p.add_argument('--run',action='store_true');p.add_argument('--streaming',action='store_true');p.add_argument('--prototype-dir',type=Path,default=R/'research/rendering/native-bg-prototype');p.add_argument('--foreground',action='store_true',help='Hidden-transition 3D actor probes plus native scenery depth restoration');a=p.parse_args();prototype=a.prototype_dir.resolve();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
 canonical=resolve_rom(R / 'ds');before=hashlib.sha256(canonical.read_bytes()).hexdigest();(out/'nitrofs/native').mkdir(parents=True);(out/'source').mkdir();cases=[]
 sources=[('synthetic.ntb',synthetic(),None)]+[(path.name,path.read_bytes(),path)for path in sorted(a.study_dir.glob('*.ntb'))]
 assert not(a.foreground and a.streaming),'Foreground fixture uses hidden transitions, not old-front publication proof'
 study={row['map']:row for row in json.loads((a.study_dir/'report.json').read_text())['maps']}
 with (out/'nitrofs/cases.bin').open('wb')as f:
  # Prepare camera schedules before emitting the count.
  selections=[]
  for name,blob,path in sources:
   w,h,palettes,patterns,pages=decode(blob)
   if path is None:positions=[(x,x%192)for x in [0,1,7,8,15,16,255,256,511,512]]
   else:
    cx,cy=study[path.stem]['preview_camera'];maxx=w*8-256;maxy=h*8-192;positions=[(cx,cy),(min(maxx,cx+7),min(maxy,cy+7)),(maxx,maxy),(maxx//2,maxy//2)]
   if a.streaming:
    maxx=w*8-256;maxy=h*8-192
    if path is None:
     route=list(range(19))+list(range(17,-1,-1));positions=[(239+16*i,31+2*(i%5))for i in route]
    else:
     sx=min(study[path.stem]['preview_camera'][0],maxx//2);sy=min(study[path.stem]['preview_camera'][1],maxy//2)
     route=list(range(17))+list(range(15,-1,-1));positions=[(min(maxx,sx+4*i),min(maxy,sy+2*(i%5)))for i in route]
     positions +=[(min(maxx,sx+2*(i%4)),min(maxy,sy+4*i))for i in range(1,9)]
   selections.append((name,blob,path,w,h,palettes,patterns,pages,positions))
  f.write(struct.pack('<I',sum(len(s[-1])for s in selections)))
  for name,blob,path,w,h,palettes,patterns,pages,positions in selections:
   destination=out/'nitrofs/native'/name
   if path:destination.symlink_to(path.resolve())
   else:destination.write_bytes(blob)
   owner_cells={}
   if a.foreground and path:
    owner_bytes=path.with_suffix('.owners').read_bytes();assert len(owner_bytes)%260==0
    for i in range(0,len(owner_bytes),260):owner_cells[struct.unpack_from('<I',owner_bytes,i)[0]]=np.frombuffer(owner_bytes,dtype='u1',count=256,offset=i+4).reshape(16,16)
   for cx,cy in positions:
    y,x=np.indices((192,256));expected=(((x//16)%32)|(((y//8)%32)<<5)|(5<<10)|32768).astype('<u2')
    native_alpha=np.zeros((192,256),dtype=bool)
    for yy in range(cy//8,(cy+191)//8+1):
     for xx in range(cx//8,(cx+255)//8+1):
      word=struct.unpack_from('<I',pages[(yy//16)*((w+15)//16)+xx//16],((yy%16)*16+xx%16)*4)[0];pixels=palettes[word>>28,np.frombuffer(patterns[word&0xfffffff],dtype='u1')].reshape(8,8)
      sx=xx*8-cx;sy=yy*8-cy;l=max(0,sx);r=min(256,sx+8);t=max(0,sy);b=min(192,sy+8);src=pixels[t-sy:b-sy,l-sx:r-sx];dst=expected[t:b,l:r];mask=(src&32768)!=0;dst[mask]=src[mask];native_alpha[t:b,l:r]=mask
    extra=b''
    if a.foreground:
     owners=np.zeros((192,256),dtype='u1')
     if path:
      for yy in range(cy//16,(cy+191)//16+1):
       for xx in range(cx//16,(cx+255)//16+1):
        cell=owner_cells.get(yy*(w//2)+xx)
        if cell is None:continue
        sx=xx*16-cx;sy=yy*16-cy;l=max(0,sx);r=min(256,sx+16);t=max(0,sy);b=min(192,sy+16)
        owners[t:b,l:r]=cell[t-sy:b-sy,l-sx:r-sx]
     else:owners[:]=np.where(native_alpha,((x//8+y//8)%7)+1,0)
     # Three overlapping probes with distinct painter ranks; full-screen
     # independent pixel reference is deliberately separate from depth meshes.
     ranks=np.unique(owners[owners>0]);mid=int(ranks[len(ranks)//2])if len(ranks)else 1
     actors=[(72,65,133,135,0,31),(100,83,158,151,mid,31<<5),(125,52,181,119,255,31<<10)]
     for l,t,r,b,order,color in actors:
      region=expected[t:b,l:r];mask=owners[t:b,l:r]<=order;region[mask]=32768|color
     # Later foreground restores the base above each actor. Earlier actors
     # already survive only where their own rank permits, as in painter order.
     extra=owners.tobytes()+b''.join(struct.pack('<6I',*actor)for actor in actors)
    native=('nitro:/native/'+name).encode();f.write(struct.pack('<I',len(native))+native+struct.pack('<II',cx,cy)+expected.tobytes()+extra);cases.append({'map':name,'camera':[cx,cy]})
 source=(prototype/('foreground_fixture.c'if a.foreground else 'stream_fixture.c')).read_text()if(a.streaming or a.foreground)else SOURCE
 (out/'source/main.c').write_text(source.replace('@CASES@',str(len(cases))))
 headers=[prototype/'native_bg_assets.h',R/'ds/source/tile_codec.h']
 if a.streaming or a.foreground:headers +=[prototype/name for name in ['native_bg_cache.h','native_bg_stream.h']]
 if a.foreground:headers +=[prototype/'native_bg_sample.h',R/'ds/source/depth_mesh.h']
 for src in headers:(out/'source'/src.name).write_bytes(src.read_bytes())
 (out/'Makefile').write_text('WONDERFUL_TOOLCHAIN ?= $(HOME)/.local/share/wonderful\nBLOCKSDS := $(WONDERFUL_TOOLCHAIN)/thirdparty/blocksds/core\nNAME := native_bg_fixture\nGAME_TITLE := Native BG fixture\nNITROFSDIR := nitrofs\nCFLAGS := -Wall -Wextra -Werror\ninclude $(BLOCKSDS)/sys/default_makefiles/rom_arm9/Makefile\n')
 report={'scope':__doc__,'streaming':a.streaming,'foreground':a.foreground,'cases':cases,'emulator_closed':True,'canonical_rom_unchanged':True}
 try:
  with (out/'build.log').open('w')as log:subprocess.run(['make','-C',str(out),'-j4'],stdout=log,stderr=subprocess.STDOUT,check=True)
  report['rom_sha256']=hashlib.sha256((out/'native_bg_fixture.nds').read_bytes()).hexdigest()
  if a.run:
   if processes():raise RuntimeError('An emulator is already open; leaving it untouched')
   original=CONFIG.read_text()
   try:
    config=section_option(original,'Instance0.Gdb','Enabled','true');config=section_option(config,'DLDI','Enable','false');write_config(config)
    with BoundedOutput([str(EMU),'-b','always',str(out/'native_bg_fixture.nds')])as native:
     proc=native.process
     try:
      deadline=time.monotonic()+20
      while str(proc.pid)not in subprocess.run(['lsof','-nP','-iTCP:3333','-sTCP:LISTEN'],capture_output=True,text=True).stdout:
       if proc.poll()is not None or time.monotonic()>deadline:raise RuntimeError('Debugger did not start')
       time.sleep(.2)
      lines=subprocess.check_output([str(NM),'-a',str(out/'build/native_bg_fixture.elf')],text=True);sym={p[2]:int(p[0],16)for line in lines.splitlines()if len(p:=line.split())==3}
      rsp=RSP(3333);rsp.sock.settimeout(240);stop=f'0,{sym["fixture_checkpoint"]:x},2';assert rsp.command('Z'+stop)=='OK';rsp.resume();assert rsp.receive().startswith(('S','T'))
      def words(name,n):return struct.unpack('<'+str(n)+'I',rsp.read(sym[name],4*n))
      report['done']=words('fixture_done',1)[0];report['error']=words('fixture_error',1)[0];m=words('fixture_mismatches',len(cases));diff=words('fixture_diffs',len(cases)*3);hashes=words('fixture_hashes',len(cases)*2)
      for i,case in enumerate(cases):case.update(mismatches=m[i],first_difference=list(diff[i*3:i*3+3]),expected_hash=hashes[i*2],actual_hash=hashes[i*2+1])
      if a.streaming or a.foreground:
       fields=['prepare_us','uploads','page_reads','map_writes','cold','front_mismatches','evictions']
       if a.foreground:fields.remove('front_mismatches')
       if 'fixture_asset_reads' in sym:fields+=['asset_reads','asset_bytes']
       for field in fields:
        values=words('fixture_'+field,len(cases))
        for i,case in enumerate(cases):case[field]=values[i]
      report['bottom_memory_mismatches']=words('fixture_sub_mismatches',1)[0];report['row_cache_mismatches']=words('fixture_cache_mismatches',1)[0];report['maximum_slots']=words('fixture_max_slots',1)[0];report['registers']=list(words('fixture_registers',8));rsp.sock.close()
     finally:
      if proc.poll()is None:proc.terminate()
      try:proc.wait(timeout=10)
      except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
      native.save(out/'emulator-tail.log')
   finally:write_config(section_option(original,'Instance0.Gdb','Enabled','false'));report['emulator_closed']=not processes()
 finally:
  report['canonical_rom_unchanged']=hashlib.sha256(canonical.read_bytes()).hexdigest()==before;report['limits']=['Standalone2Dfixture; no gameplay, full audio workload or physical hardware FPS proof. Cold loads are hidden; streaming mode checks old-front stability during warm uploads.','H/I bottom pixels/registers and C tail cache are read back; actual bottom-screen visual output is not captured.',('3D solid-color actor probes with real painter-owner masks and sampled native-color foreground. Hidden transitions; no texture double-buffer publication or actual animated actor assets.'if a.foreground else 'A used for capture, B/F/G reserved as textures/palettes but no actual3Dactors or foreground ordering rendered.')];(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 assert report['canonical_rom_unchanged']
 if a.streaming and a.run:assert all(not c['front_mismatches']for c in cases),'Old displayed frame changed during uploads'
 if a.run:assert report.get('done')==1 and not report.get('error') and not report['bottom_memory_mismatches']and not report['row_cache_mismatches']and all(not c['mismatches']for c in cases),'Fixture failed; inspect report.json'
 print(json.dumps({k:v for k,v in report.items()if k!='cases'}))
if __name__=='__main__':main()
