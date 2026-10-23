#!/usr/bin/env python3
"""Original animation instruction stage followed by eight native enemy bodies."""
import ctypes as C,importlib,json,struct
from maps_render import Renderer
from unicorn.x86_const import *
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];r=Renderer(ROOT/'generated/assets',ROOT/'generated/maps');counts={}
configs=[('eagle',6,0x40a700),('small_yeti',7,0x41b8b0),('snowman',8,0x41aa50),('small_robot',11,0x413450),('egg_robot',12,0x40feb0),('flying_robot',13,0x4106c0),('bee',16,0x40bba0),('small_octopus',17,0x412f70)]
for name,id,address in configs:
 m=importlib.import_module('verify_'+name);f=getattr(m.lib,'enemy_'+name+'_callback');script=r.scripts[id]
 m.ranges=[(script.get('StartAnim'+k,0),script.get('EndAnim'+k,0)) for k in ('Left','Right','Up','Do','LeftUp','LeftDo','RightUp','RightDo','IdleLeft','IdleRight','IdleUp','IdleDo','IdleLeftUp','IdleLeftDo','IdleRightUp','IdleRightDo','Attack','Freeze')];m.u.mem_write(m.RESOURCE+0x39,b''.join(struct.pack('<hh',*v) for v in m.ranges));m.lib.entity_advance_animation.argtypes=[C.POINTER(m.Entity),C.c_int16];m.lib.entity_advance_animation.restype=C.c_uint
 total=0;states=set();events={}
 for record in m.records:
  raw=bytearray(record);struct.pack_into('<h',raw,98,0);entity=m.Entity.from_buffer_copy(raw);g=m.Globals();m.u.mem_write(m.OBJ,bytes(raw));m.u.mem_write(0x45ed2c,struct.pack('<i',0));host=[]
  @m.Contact
  def contact(x,y,w,h,d,c):host.append(('contact',(x,y,w,h,d)));return False
  @m.Contact
  def projectile(x,y,w,h,d,c):
   host.append(('shot',(x,y,w,h,d)))
   return m.shot and (name!='small_octopus' or m.sample%2==0 or sum(t[0]=='shot' for t in host)>1)
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
  if name in ('bee','flying_robot'):
   @m.Ambient
   def ambient(x,y,slot,c):host.append(('ambient',(x,y,slot)))
   world=m.WorldEnv(env,88,100,88,100,ambient);argument=world
  else:argument=env
  for tick in range(1500):
   x,y=struct.unpack_from('<hh',bytes(entity),2);m.px=x-100 if entity.bytes[43]==0 else x+200;m.py=y+(350 if name in ('eagle','bee') else 100);env.player_x=m.px;env.player_y=m.py;m.random_sample=(tick*713+891)%32768;m.available=False;m.shot=tick in(900,1100,1400);m.sample=tick
   if name in ("bee","flying_robot"):world.enemy.player_x=m.px;world.enemy.player_y=m.py
   m.lib.entity_advance_animation(C.byref(entity),0);m.u.mem_write(0x303000+0x1735,struct.pack('<h',0));m.u.reg_write(UC_X86_REG_ESI,m.OBJ);m.u.reg_write(UC_X86_REG_EBP,0x303000);m.u.reg_write(UC_X86_REG_ESP,m.SP);m.u.mem_write(m.SP+0x50,struct.pack('<I',4));m.u.emu_start(0x4337a1,0x43383f,count=1000)
   assert bytes(entity)==bytes(m.u.mem_read(m.OBJ,186)),(name,tick,'animation')
   before=bytes(entity);host.clear();assert f(C.byref(entity),C.byref(g),C.byref(argument));m.native_events.clear();m.u.mem_write(m.SP,struct.pack('<4I',0x4000,4,0,m.OBJ));m.u.reg_write(UC_X86_REG_ESP,m.SP);m.u.emu_start(address,0x4000,count=10000)
   actual=bytes(m.u.mem_read(m.OBJ,186));assert bytes(entity)==actual,(name,tick,struct.unpack_from('<hhhh',before,31),struct.unpack_from('<4f',before,148),[(i,a,b) for i,(a,b) in enumerate(zip(bytes(entity),actual)) if a!=b]);assert host==m.native_events,(name,tick,host,m.native_events);assert g.score==struct.unpack('<i',m.u.mem_read(0x45ed2c,4))[0]
   states.add(struct.unpack_from('<h',actual,98)[0]);total+=1
   for key,args in host:events[key]=events.get(key,0)+1
 counts[name]={'ticks':total,'states_observed':sorted(states),'events':events};print(name,total,flush=True)
result={'native_animation_and_callbacks':counts,'entity_bytes_compared':186,'limits':['Native resource animation ranges from extracted AOMscripts','Visibility/update selection outside animation stage not executed','Player query outcomes supplied','Allocation unavailable in trajectory runs; allocation and native spawn-record overwrite cases covered by separate callback oracles','Bee and flyingRobot frame-size providers supplied; actual graphics integration verified separately']};(ROOT/'research/enemies/world_trajectory_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
