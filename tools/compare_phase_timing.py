#!/usr/bin/env python3
"""Compare per-render phase timings of two playtest output directories.

Reads <case>.frames.csv written by emulator_autoplay.py. The first renders of
each route (cold map/asset loading) are reported separately from steady-state
medians and 95th percentiles. Timings are melonDS emulated microseconds taken
at debugger-halted frame boundaries; they are not hardware measurements, and
routes can diverge when the frame cadence changes.
"""
import argparse,csv,json,statistics
from pathlib import Path
PHASES=('update','render','transfer','audio')
def load(path,cold):
 rows=list(csv.DictReader(path.open()))
 for r in rows:r['sum']=sum(int(r[k] or 0) for k in PHASES)
 return rows[:cold],rows[cold:]
def summary(rows,key):
 values=sorted(int(r[key] or 0) for r in rows)
 return {'median':statistics.median(values),'p95':values[min(len(values)-1,int(len(values)*.95))],'max':values[-1]} if values else None
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline',type=Path);p.add_argument('candidate',type=Path);p.add_argument('--cold',type=int,default=5);p.add_argument('--output',type=Path)
 args=p.parse_args();report={'scope':__doc__.strip().splitlines()[0],'cold_renders_excluded':args.cold,'cases':{}}
 for base in sorted(args.baseline.glob('*.frames.csv')):
  other=args.candidate/base.name
  if not other.exists():continue
  case=base.name.removesuffix('.frames.csv');entry={}
  for label,path in (('baseline',base),('candidate',other)):
   cold,steady=load(path,args.cold)
   entry[label]={'renders':len(steady),'cold_max_sum_us':max((r['sum'] for r in cold),default=None),
    **{k:summary(steady,k) for k in (*PHASES,'sum','fps')}}
  b,c=entry['baseline'],entry['candidate']
  entry['change_percent']={k:{s:round((c[k][s]-b[k][s])*100/b[k][s],1) if b[k][s] else None for s in ('median','p95')} for k in (*PHASES,'sum')}
  report['cases'][case]=entry
  print(f"{case:18s} sum med {b['sum']['median']:7.0f}->{c['sum']['median']:7.0f} ({entry['change_percent']['sum']['median']:+.1f}%)  p95 {b['sum']['p95']:6d}->{c['sum']['p95']:6d} ({entry['change_percent']['sum']['p95']:+.1f}%)  render med {b['render']['median']:.0f}->{c['render']['median']:.0f}  fps med {b['fps']['median']:.0f}->{c['fps']['median']:.0f}")
 if args.output:args.output.write_text(json.dumps(report,indent=1)+'\n')
if __name__=='__main__':main()
