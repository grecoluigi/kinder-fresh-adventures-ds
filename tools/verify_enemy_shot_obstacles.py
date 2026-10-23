#!/usr/bin/env python3
"""Execute complete native412bf0 selection, ID filter and point-in-rectangle."""
import verify_enemy_shots as m
import ctypes as C,json,struct
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
class Geometry(C.Structure):_fields_=[(k,C.c_int16) for k in ('id','x','y','active','width','height','align_x','align_y')]+[('solid',C.c_uint8),('top_trim',C.c_uint8),('object_index',C.c_int32)]
m.lib.enemy_shot_obstacle_test.argtypes=[C.POINTER(Geometry),C.c_int,C.c_int,C.c_int];m.lib.enemy_shot_obstacle_test.restype=C.c_bool
BASE=0x304000;LIST=0x303000;m.full_obstacle=True;m.u.mem_write(LIST+2,struct.pack('<I',BASE))
def hook(u,at,size,c):
 esp=u.reg_read(UC_X86_REG_ESP)
 if at==0x4308c0:m.ret(LIST)
 elif at==0x431300:
  i=(m.word(esp+4)-BASE)//186;o=objects[i]
  for offset,value in [(8,o.width),(12,o.height),(16,o.align_x),(20,o.align_y)]:u.mem_write(m.word(esp+offset),struct.pack('<h',value))
  m.ret(1,pop=20)
m.u.hook_add(UC_HOOK_CODE,hook);tested=0
for sample in range(1200):
 n=m.rng.randrange(1,30);objects=(Geometry*n)();raw=bytearray(n*186)
 for i in range(n):
  o=Geometry(m.rng.randrange(72,93),m.rng.randrange(-100,500),m.rng.randrange(-100,500),m.rng.randrange(2),m.rng.randrange(101),m.rng.randrange(101),m.rng.randrange(-40,41),m.rng.randrange(-40,41),m.rng.randrange(2),0,i);objects[i]=o
  struct.pack_into('<hhhh',raw,i*186,o.id,o.x,o.y,o.active);raw[i*186+26]=o.solid
 m.u.mem_write(BASE,bytes(raw));m.u.mem_write(0x4e0aac,struct.pack('<i',n));m.u.mem_write(0x4dac78,struct.pack('<'+str(n)+'i',*range(n)))
 target=objects[m.rng.randrange(n)];left=target.x+target.align_x;top=target.y+target.align_y
 for x,y in [(left,top),(left+target.width,top),(left,top+target.height),(left+target.width-1,top+target.height-1),(left-1,top-1),(m.rng.randrange(600),m.rng.randrange(600))]:
  want=m.lib.enemy_shot_obstacle_test(objects,n,x,y);m.u.mem_write(m.SP,struct.pack('<3I',0x4000,x&0xffffffff,y&0xffffffff));m.u.reg_write(UC_X86_REG_ESP,m.SP);m.u.emu_start(0x412bf0,0x4000,count=10000);actual=m.u.reg_read(UC_X86_REG_EAX);assert bool(actual)==want,(sample,x,y,want,actual);tested+=1
result={'native_function':'0x412bf0','cases':tested,'blocking_ids':[76,78,83,86,87],'limits':['Native geometry bounds431300 substituted with caller-resolved frame dimensions/alignment','Selected indices supplied in ascending native order; source selection primitive covered separately']};(m.OUT/'shot_obstacle_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
