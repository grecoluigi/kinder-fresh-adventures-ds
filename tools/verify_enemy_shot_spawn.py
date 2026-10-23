#!/usr/bin/env python3
"""Run kong spawn with the actual native40adc0 initializer; compare100bytes."""
import verify_kong as k
import verify_enemy_shots as s
import ctypes as C,json,struct
from unicorn.x86_const import *
k.real_init=True;k.available=True;k.shot=False;k.px=k.py=0;k.random_sample=123
cases=0
for facing in (0,1):
 for sample in range(120):
  raw=bytearray(k.records[sample%len(k.records)]);raw[43]=facing;struct.pack_into('<h',raw,98,10);struct.pack_into('<hhh',raw,12,30,26,3);struct.pack_into('<h',raw,18,3);struct.pack_into('<hh',raw,2,sample*32,sample*4)
  k.u.mem_write(k.OBJ,bytes(raw));k.u.mem_write(0x302000,bytes(100));k.u.mem_write(k.SP,struct.pack('<4I',0x4000,4,0,k.OBJ));k.u.reg_write(UC_X86_REG_ESP,k.SP);k.native_events.clear();k.u.emu_start(0x413cb0,0x4000,count=10000)
  original=bytes(k.u.mem_read(0x302000,100));x,y,vx,vy=struct.unpack_from('<4f',original,12)
  s.lib.enemy_shots_init();assert s.lib.enemy_shots_spawn(k.OBJ,x,y,vx,vy);actual=bytes(s.lib.enemy_shots_slots()[0]);assert actual==original,(sample,facing,[(i,a,b) for i,(a,b) in enumerate(zip(actual,original)) if a!=b]);cases+=1
result={'native_kong':'0x413cb0','native_initializer':'0x40adc0','cases':cases,'record_bytes_compared':100,'resource_handle':0,'owner_lookup':True};(k.OUT/'shot_spawn_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
