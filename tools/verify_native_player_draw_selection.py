"""Execute the released41a780 draw callback and record selected animations.
Distinguish a loaded/reset Puff resource from an animation actually drawn here.
"""
from pathlib import Path
import json,struct,hashlib
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EAX,UC_X86_REG_EIP
R=Path(__file__).resolve().parents[1];binary=R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'
pe=pefile.PE(str(binary));u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x200000,0x10000);u.mem_map(0x2000,4096)
draws=[];enabled=True
def hook(uc,at,size,ctx):
 if at==0x2000:uc.emu_stop();return
 if at not in(0x432cc0,0x434510,0x40af50):return
 sp=uc.reg_read(UC_X86_REG_ESP);ret=struct.unpack('<I',uc.mem_read(sp,4))[0];value=0
 if at==0x432cc0:value=int(enabled);pop=0
 elif at==0x434510:
  layer,x,y,xp,yp=struct.unpack('<5I',uc.mem_read(sp+4,20));assert(layer,x,y)==(2,0,0)
  uc.mem_write(xp,struct.pack('<i',111));uc.mem_write(yp,struct.pack('<i',222));pop=20
 else:
  anim,x,y=struct.unpack('<Iii',uc.mem_read(sp+4,12));draws.append((anim,x,y));pop=12
 uc.reg_write(UC_X86_REG_ESP,sp+4+pop);uc.reg_write(UC_X86_REG_EAX,value);uc.reg_write(UC_X86_REG_EIP,ret)
u.hook_add(UC_HOOK_CODE,hook);cases=0
for enabled in(False,True):
 for character in(0,1):
  for puff in range(14):
   for mask in(0,1,0x155,0x3ff):
    u.mem_write(0x4e1020,struct.pack('<I',character));u.mem_write(0x4e1048,bytes(100));u.mem_write(0x4e1048,struct.pack('<I',1));u.mem_write(0x4e1074,struct.pack('<I',puff))
    for i in range(10):u.mem_write(0x4e0b48+i*100+64,struct.pack('<I',(mask>>i)&1))
    draws.clear();u.mem_write(0x208000,struct.pack('<I',0x2000));u.reg_write(UC_X86_REG_ESP,0x208000);u.emu_start(0x41a780,0x2000,count=5000)
    expected=[(0x4e0fa8 if character else 0x4e0f30,-111,-222)]+[(0x4e0b48+i*100,-111,-222)for i in range(10)if mask&(1<<i)]if enabled else[]
    assert draws==expected,(enabled,character,puff,mask,draws,expected);cases+=1
result={'scope':__doc__,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'native_cases':cases,'character_then_active_projectiles':True,'puff_selected_in_callback':False,'limits':['Map-draw gate, camera projection and low-level blitter are supplied services. This verifies selection/order, not raster pixels.','Bounded to the released player draw callback; no claim that no other indirect path can ever reference Puff.']}
(R/'research/gameplay/player-draw-selection-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
