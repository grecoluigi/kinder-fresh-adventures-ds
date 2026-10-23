"""Execute SDK-compiled pair/scalar rows on Unicorn ARM946; check aligned accesses and exact ends.
This is instruction/correctness emulation, not DS memory latency or FPS measurement.
"""
from pathlib import Path
import subprocess,tempfile,struct,random,json
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_MODE_LITTLE_ENDIAN,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_MEM_WRITE
from unicorn.arm_const import UC_CPU_ARM_946,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR
R=Path(__file__).resolve().parents[1]
import argparse,hashlib
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--header',type=Path,default=R/'research/rendering/rgb555_blit_aligned_pair_experiment.h');args=parser.parse_args();header=args.header.resolve();gcc=Path.home()/'.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin/arm-none-eabi-gcc';rng=random.Random(2001)
results={}
with tempfile.TemporaryDirectory(prefix='kinder-pair-arm-')as td:
 t=Path(td);src=t/'copy.c';src.write_text('#include "'+str(header)+'"\nvoid copy_row(uint16_t*d,const uint16_t*s,unsigned n){rgb555_blit_masked(d,s,n);}\n')
 for name,flags in [('paired',[]),('scalar',['-DRGB555_SCALAR_BLIT'])]:
  elf=t/(name+'.elf');binary=t/(name+'.bin')
  subprocess.run([str(gcc),'-O2','-mcpu=arm946e-s+nofp','-marm','-ffreestanding','-fno-builtin','-nostdlib',*flags,'-Wl,-Ttext=0x10000,-e,copy_row,--build-id=none',str(src),'-o',str(elf)],check=True)
  subprocess.run([str(gcc.with_name('arm-none-eabi-objcopy')),'-O','binary',str(elf),str(binary)],check=True)
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM|UC_MODE_LITTLE_ENDIAN);u.ctl_set_cpu_model(UC_CPU_ARM_946)
  u.mem_map(0x10000,0x10000);u.mem_write(0x10000,binary.read_bytes());u.mem_map(0x20000,0x10000);u.mem_map(0x40000,0x20000)
  source_begin=source_end=dest_begin=dest_end=0;accesses=0
  def check_access(uc,kind,address,size,value,context):
   global accesses
   if 0x40000<=address<0x60000:
    assert size in (1,2,4) and (size<4 or address%4==0),(name,address,size)
    if 0x50000<=address:assert kind!=UC_MEM_WRITE and source_begin<=address and address+size<=source_end,(name,'source range',address,size)
    else:assert dest_begin<=address and address+size<=dest_end,(name,'destination range',address,size)
    accesses+=1
  u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,check_access)
  cases=0
  for count in (0,1,2,3,7,15,16,17,31,64,256):
   for sp in (0,1):
    for dp in (0,1):
     for mode in (0,1,2,3,4):
      source_begin=0x50020+sp*2;source_end=source_begin+count*2;dest_begin=0x40020+dp*2;dest_end=dest_begin+count*2
      colors=[rng.randrange(32768)|((mode==1 or mode==2 and i%2==0 or mode==3 and i%2==1 or mode==4 and rng.randrange(2))<<15)for i in range(count)]
      initial=[rng.randrange(65536)for _ in colors];expected=[s if s&32768 else d for s,d in zip(colors,initial)]
      before=bytes([0x12])*1024;u.mem_write(0x40000,before);u.mem_write(0x50000,bytes([0x34])*1024)
      if count:u.mem_write(source_begin,struct.pack('<'+'H'*count,*colors));u.mem_write(dest_begin,struct.pack('<'+'H'*count,*initial))
      guarded=bytearray(u.mem_read(0x40000,1024));guarded[dest_begin-0x40000:dest_end-0x40000]=struct.pack('<'+'H'*count,*expected)
      source_before=bytes(u.mem_read(0x50000,1024));u.reg_write(UC_ARM_REG_R0,dest_begin);u.reg_write(UC_ARM_REG_R1,source_begin);u.reg_write(UC_ARM_REG_R2,count);u.reg_write(UC_ARM_REG_SP,0x2fff0);u.reg_write(UC_ARM_REG_LR,0x60000)
      u.emu_start(0x10000,0x60000,count=100000)
      assert bytes(u.mem_read(0x40000,1024))==guarded and bytes(u.mem_read(0x50000,1024))==source_before,(name,count,sp,dp,mode)
      cases+=1
  results[name]=dict(cases=cases,code_bytes=binary.stat().st_size,checked_data_accesses=accesses)
report=dict(scope=__doc__,header=str(header),header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),cpu='ARM946',variants=results,aligned_word_accesses=True,no_pixel_access_outside_requested_row=True,source_unchanged=True)
(R/'research/rendering/rgb555-pair-arm-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
