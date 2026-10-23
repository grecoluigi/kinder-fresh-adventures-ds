#!/usr/bin/env python3
"""Couple verified native entity animation stage with native enemy callbacks."""
import ctypes as C,json,struct
import verify_kong as k
import verify_parrot as p
from unicorn.x86_const import *
counts={}
for m,name,address in [(k,'kong',0x413cb0),(p,'parrot',0x415ff0)]:
 f=getattr(m.lib,'enemy_'+name+'_callback')
 m.lib.entity_advance_animation.argtypes=[C.POINTER(m.Entity),C.c_int16];m.lib.entity_advance_animation.restype=C.c_uint
 total=0;states=set()
 for record in m.records:
  raw=bytearray(record);struct.pack_into('<h',raw,98,0)
  entity=m.Entity.from_buffer_copy(raw);g=m.Globals();g.score=0;m.u.mem_write(m.OBJ,bytes(raw));m.u.mem_write(0x45ed2c,struct.pack('<i',0));host=[]
  @m.Contact
  def contact(x,y,w,h,d,c):host.append(('contact',(x,y,w,h,d)));return False
  @m.Contact
  def projectile(x,y,w,h,d,c):host.append(('shot',(x,y,w,h,d)));return m.shot
  @m.Popup
  def popup(x,y,s,c):host.append(('popup',(x,y,s)))
  @m.Sound
  def sound(ch,s,c):host.append(('sound',(ch,s)))
  @m.Random
  def random_call(c):host.append(('random',()));return m.random_sample
  @m.Allocate
  def allocate(c):host.append(('allocate',()));return m.available
  @m.Spawn
  def spawn(owner,x,y,vx,vy,c):host.append(('spawn',(x,y,vx,vy)))
  env=m.Env(((C.c_int16*2)*18)(*((C.c_int16*2)(*v) for v in m.ranges)),contact,projectile,popup,sound,123,456,None,0,0,random_call,allocate,spawn,789)
  for tick in range(1200):
   x,y=struct.unpack_from('<hh',bytes(entity),2);m.px=x-100 if entity.bytes[43]==0 else x+200;m.py=y+(100 if name=='kong' else 350);env.player_x=m.px;env.player_y=m.py;m.random_sample=(tick*713+891)%32768;m.available=False;m.shot=tick==900

   m.lib.entity_advance_animation(C.byref(entity),0)
   m.u.mem_write(0x303000+0x1735,struct.pack('<h',0));m.u.reg_write(UC_X86_REG_ESI,m.OBJ);m.u.reg_write(UC_X86_REG_EBP,0x303000);m.u.reg_write(UC_X86_REG_ESP,m.SP);m.u.mem_write(m.SP+0x50,struct.pack('<I',4));m.u.emu_start(0x4337a1,0x43383f,count=1000)
   assert bytes(entity)==bytes(m.u.mem_read(m.OBJ,186)),(name,tick,'animation')
   host.clear();assert f(C.byref(entity),C.byref(g),C.byref(env));m.native_events.clear();m.u.mem_write(m.SP,struct.pack('<4I',0x4000,4,0,m.OBJ));m.u.reg_write(UC_X86_REG_ESP,m.SP);m.u.emu_start(address,0x4000,count=10000)
   actual=bytes(m.u.mem_read(m.OBJ,186));assert bytes(entity)==actual,(name,tick,[(i,a,b) for i,(a,b) in enumerate(zip(bytes(entity),actual)) if a!=b]);assert host==m.native_events,(name,tick,host,m.native_events);assert g.score==struct.unpack('<i',m.u.mem_read(0x45ed2c,4))[0]
   states.add(struct.unpack_from('<h',actual,98)[0]);total+=1
 counts[name]={'ticks':total,'states_observed':sorted(states)}
result={'native_animation_and_callbacks':counts,'entity_bytes_compared':186,'limitations':['Object selection/update gating outside animation stage not executed','Player contact and projectile outcomes supplied','Projectile allocation intentionally unavailable in trajectory run; covered separately by kong callback oracle']}
(k.OUT/'trajectory_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
