"""Transfer-only zero-row elision vs full copies, including UI and destination changes."""
from pathlib import Path
import json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-foreground-band-') as td:
 t=Path(td);src=t/'test.c';src.write_text('#include "'+str(R/'research/rendering/foreground-band-candidate/frame_transfer.c')+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint16_t source[49152+32] __attribute__((aligned(32)));
static uint16_t targets[2][49152+32] __attribute__((aligned(32)));
static uint16_t expected[49152],other[49152];
int main(void){
 for(unsigned i=0;i<49152+32;i++)source[i]=targets[0][i]=targets[1][i]=0x1234;
 uint32_t rng=2001;unsigned partial=0,full=0,empty=0;uint64_t rows=0;
 for(unsigned frame=0;frame<20000;frame++){
  uint16_t *pixels=source+16,*dest=targets[(frame/111)%2]+16;
  memset(pixels,0,49152*2);
  unsigned first=192,last=0;
  unsigned patches=frame%13?1+frame%4:0;
  for(unsigned patch=0;patch<patches;patch++){
   rng=rng*1664525u+1013904223u;unsigned y=rng%192;
   rng=rng*1664525u+1013904223u;unsigned height=1+rng%35;if(height>192-y)height=192-y;
   rng=rng*1664525u+1013904223u;unsigned x=rng%256;
   rng=rng*1664525u+1013904223u;unsigned width=1+rng%101;if(width>256-x)width=256-x;
   for(unsigned yy=y;yy<y+height;yy++)for(unsigned xx=x;xx<x+width;xx++)pixels[yy*256+xx]=(uint16_t)(1+((yy*17+xx+frame)%65535));
   if(y<first)first=y;if(y+height>last)last=y+height;
  }
  /* Nonzero RGB with alpha clear, and every possible first/last row. */
  if(frame%19==0){unsigned y=frame%192;pixels[y*256+(frame%256)]=1;if(y<first)first=y;if(y+1>last)last=y+1;}
  bool force=false;
  if(frame%41==0){memset(dest,0x80,49152*2);frame_forget_foreground_transfer();force=true;}
  if(frame%47==0){frame_transfer(dest,other);force=true;}
  if(frame%53==0){frame_transfer(other,pixels);force=true;}
  memcpy(expected,pixels,sizeof(expected));
  frame_transfer_foreground(dest,pixels);
  assert(!memcmp(dest,expected,sizeof(expected)));
  assert(!memcmp(pixels,expected,sizeof(expected)));
  assert(frame_foreground_rows<=192);
  if(force)assert(frame_foreground_rows==192);
  if(frame_foreground_rows==192)full++;else partial++;
  if(!frame_foreground_rows)empty++;
  rows+=frame_foreground_rows;
  for(unsigned i=0;i<16;i++)assert(source[i]==0x1234&&source[49152+16+i]==0x1234&&targets[0][i]==0x1234&&targets[0][49152+16+i]==0x1234&&targets[1][i]==0x1234&&targets[1][49152+16+i]==0x1234);
 }
 assert(partial&&full);
 /* Two consecutive empty frames exercise a zero-byte transfer. */
 memset(source+16,0,49152*2);frame_transfer_foreground(targets[0]+16,source+16);frame_transfer_foreground(targets[0]+16,source+16);assert(!frame_foreground_rows);
 printf("{\"frames\":20000,\"additional_empty_frames\":2,\"partial_band_frames\":%u,\"full_frames\":%u,\"empty_transfers\":%u,\"rows_transferred\":%llu,\"full_copy_baseline_rows\":3840000}\n",partial,full,empty,(unsigned long long)rows);
 return 0;
}
''')
 exe=t/'test';subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ds/source'),str(src),'-o',str(exe)],check=True)
 r=json.loads(subprocess.check_output([str(exe)],text=True));r.update(scope=__doc__,sanitizers=['address','undefined'],pixel_and_source_equality=True,limits=['Synthetic complete framebuffer sequences; DS cache flush/DMA and actual UI transitions require separate emulator/hardware checks.'])
 (R/'research/rendering/foreground-band-transfer-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
