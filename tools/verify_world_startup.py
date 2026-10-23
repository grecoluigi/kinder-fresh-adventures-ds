"""Native4118c8..411964 marker consumption and geometry selection versus production.
Resource-manager count/index accessors are supplied; native loops execute fully.
"""
from pathlib import Path
import ctypes as C,json,struct,subprocess,tempfile
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX,UC_X86_REG_EBX
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-world-startup-') as temporary:
 t=Path(temporary);wrapper=t/'world.c';wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
unsigned test_selected_count(void){return (unsigned)selected_count;}
unsigned test_selected_layer(void){return geometry_layer;}
unsigned test_selected_index(unsigned i){return geometry_indices[i];}
int test_marker_active(void){size_t n;GameEntity*e=scene_entities(&n);for(size_t i=0;i<n;i++)if(entity_id(e+i)==1000&&entity_active(e+i))return 1;return 0;}
int test_start_x(void){return scene_metadata()->start_x;}int test_start_y(void){return scene_metadata()->start_y;}
''')
 names=['scene','player_graphics','player','animation','body','physics','collision','camera','tile_queries','composite','native_rng','hazards','hud','effects','entities','projectiles','geometry','platforms','enemies','enemy_shots','sound_events','blocks','world_objects','world_enemies','boss_factory','boss_valley','boss_mountain_jungle','end_titles','world_routes','game_save','persistence','persistence_store','save_archive']
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'}
 so=t/'world.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',*[f'-D{k}="{v}"' for k,v in defs.items()],str(wrapper),*[str(R/'ds/source'/f'{n}.c') for n in names],'-o',str(so)],check=True);c=C.CDLL(str(so));c.world_open_stage.restype=C.c_bool;c.world_map_name.restype=C.c_char_p
 pe=pefile.PE(str(R/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'));u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x200000);u.mem_write(0x400000,pe.get_memory_mapped_image());u.mem_map(0x300000,0x50000);u.mem_map(0x200000,0x10000);base=0x300000;sp=0x208000;count=0
 def ret(value,pop=0):
  esp=u.reg_read(UC_X86_REG_ESP);address=struct.unpack('<I',u.mem_read(esp,4))[0];u.reg_write(UC_X86_REG_EAX,value);u.reg_write(UC_X86_REG_ESP,esp+4+pop);u.reg_write(UC_X86_REG_EIP,address)
 def hook(uc,address,size,context):
  if address==0x430b80:ret(count)
  elif address==0x430d60:
   esp=uc.reg_read(UC_X86_REG_ESP);index=struct.unpack('<I',uc.mem_read(esp+4,4))[0];assert index<count;ret(base+index*186,4)
 u.hook_add(UC_HOOK_CODE,hook);cases=[]
 for world in range(8):
  for tutorial in ((False,True) if world<4 else (False,)):
   assert c.world_open_stage(world,tutorial);name=c.world_map_name().decode();raw=(R/'ds/nitrofs/scenes'/f'{name}.entities').read_bytes();count=struct.unpack_from('<I',raw,4)[0];u.mem_write(base,raw[8:]);u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EBX,0);u.mem_write(sp+16,struct.pack('<2i',100,100));u.emu_start(0x4118c8,0x411964,count=50000)
   n=struct.unpack('<I',u.mem_read(0x4e0aac,4))[0];selected=list(struct.unpack('<'+'I'*n,u.mem_read(0x4dac78,n*4)));actual=[c.test_selected_index(i) for i in range(c.test_selected_count())];assert selected==actual,(name,'selection')
   x,y=struct.unpack('<2i',u.mem_read(sp+16,8));assert (x,y)==(c.test_start_x(),c.test_start_y()) and not c.test_marker_active(),name
   for i in range(count):
    entity=u.mem_read(base+i*186,186)
    if struct.unpack_from('<H',entity)[0]==1000:assert struct.unpack_from('<H',entity,6)[0]==0
   cases.append({'map':name,'start':[x,y],'selected_layer':c.test_selected_layer(),'selected_count':n,'marker_art_hidden':True});c.world_close()
 result={'scope':__doc__,'maps':cases,'limits':['Initialization/selection loops, not complete collision or traversal.','Independent original-pixel scenery proof separately checks hidden marker artwork.']};(R/'research/gameplay/world-startup-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
