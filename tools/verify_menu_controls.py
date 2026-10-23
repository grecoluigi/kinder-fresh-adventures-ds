"""DS menu default focus, direction wrap, touch rectangles and one-shot actions.
This validates the portable menu controller, not native Windows or DS UI runtime.
"""
from pathlib import Path
import ctypes as C,json,re,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kinder-menu-controls-')as tmp:
 so=Path(tmp)/'menu.dylib';subprocess.run(['cc','-dynamiclib','-O2','-Wall','-Wextra','-Werror',str(R/'ds/source/menu.c'),'-o',str(so)],check=True);c=C.CDLL(str(so));c.menu_init();assert c.menu_focus_index()==0;c.menu_activate();assert c.menu_take_selection()==0 and c.menu_take_selection()==-1
 for direction in(-1,1):
  c.menu_init()
  for step in range(18):
   c.menu_move(direction);assert c.menu_focus_index()==((step+1)*direction)%6
   c.menu_activate();assert c.menu_take_selection()==c.menu_focus_index() and c.menu_take_selection()==-1
 for selection in range(6):
  c.menu_focus(selection);assert c.menu_focus_index()==selection;c.menu_activate();assert c.menu_take_selection()==selection and c.menu_take_selection()==-1
 for invalid in(-1,6,99):c.menu_focus(invalid);assert c.menu_focus_index()==5
 header=(R/'ds/source/menu_hitboxes.h').read_text();bounds=[tuple(map(int,re.findall(r'-?\d+',row)))for row in re.findall(r'\{([^{}]+)\}',header)if len(re.findall(r'-?\d+',row))==4];assert len(bounds)==6;hits=0
 for y in range(-1,193):
  for x in range(-1,257):
   expected=next((i for i,(left,top,right,bottom)in enumerate(bounds)if left<=x<right and top<=y<bottom),-1);assert c.menu_hit_test(x,y)==expected,(x,y);hits+=1
 result={'scope':__doc__,'Jungle_initial_focus_and_A_action':True,'direction_wrap_steps':36,'all_six_selections_consumed_once':True,'touch_hit_positions':hits,'limits':['Controller checks do not prove screen placement; actual DS button/touch/screen presentation pending.','Default initial Jungle focus is a requested DS UX adaptation.']};(R/'research/gameplay/menu-controls-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
