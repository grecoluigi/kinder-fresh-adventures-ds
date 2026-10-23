#!/usr/bin/env python3
"""Symbolize statistical ARM9 PC samples written by emulator_autoplay.py --pc-samples.

Samples are taken while melonDS is halted, so emulated timing is not extended
by the debugger. Shares are statistical estimates of emulated ARM9 time, not
hardware measurements; BIOS samples include VBlank waits (idle time).
"""
import argparse,bisect,collections,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NM=Path.home()/'.local/share/wonderful/toolchain/gcc-arm-none-eabi/bin/arm-none-eabi-nm'
MODES={0x10:'user',0x11:'fiq',0x12:'irq',0x13:'supervisor',0x17:'abort',0x1b:'undefined',0x1f:'system'}
def functions(elf):
 rows=[]
 for line in subprocess.check_output([str(NM),'-n','-S','-C',str(elf)],text=True).splitlines():
  parts=line.split(None,3)
  if len(parts)==4 and parts[2].lower()=='t':rows.append((int(parts[0],16),int(parts[1],16),parts[3]))
 rows.sort();return rows
def name(table,starts,address):
 address&=~1
 if address>=0xffff0000:return 'BIOS (SWI/VBlank wait)'
 i=bisect.bisect_right(starts,address)-1
 if i>=0:
  start,size,label=table[i]
  if address<start+max(size,4):return label
 return 'unknown@%08x'%address
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('samples',type=Path,nargs='+');p.add_argument('--elf',type=Path,default=ROOT/'ds/build/kinder_fresh.elf');p.add_argument('--top',type=int,default=40);p.add_argument('--output',type=Path)
 args=p.parse_args();table=functions(args.elf);starts=[r[0] for r in table]
 records=[json.loads(line) for path in args.samples for line in path.read_text().splitlines() if line.strip()]
 total=len(records);own=collections.Counter();caller=collections.defaultdict(collections.Counter);modes=collections.Counter()
 for r in records:
  f=name(table,starts,r['pc']);own[f]+=1;caller[f][name(table,starts,r['lr'])]+=1
  modes[MODES.get((r.get('cpsr') or 0)&0x1f,'unknown')]+=1
 report={'samples':total,'scope':'Statistical emulator PC samples; emulated time frozen during halts. Not hardware timing.',
  'modes':{k:round(v/total,4) for k,v in modes.most_common()},
  'functions':[{'function':f,'share':round(n/total,4),'samples':n,'lr_callers':[[c,m] for c,m in caller[f].most_common(4)]} for f,n in own.most_common(args.top)]}
 text=json.dumps(report,indent=1)
 if args.output:args.output.write_text(text+'\n')
 print('samples',total,'modes',report['modes'])
 for row in report['functions']:print(f"{row['share']*100:6.2f}% {row['samples']:5d} {row['function'][:60]:60s} <- {row['lr_callers'][:2]}")
if __name__=='__main__':main()
