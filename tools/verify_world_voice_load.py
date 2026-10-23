"""Player idle/switch voice branches use this backend load's actual result.
Exercise valid, absent and truncated packs through the real world event binding.
"""
from pathlib import Path
import ast,json,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
source=(R/'tools/verify_world_tutorials.py').read_text()
names=ast.literal_eval(next(line.strip().split('=',1)[1]for line in source.splitlines()if line.strip().startswith('names=')))
with tempfile.TemporaryDirectory(prefix='kinder-voice-load-')as tmp:
 t=Path(tmp);pack=t/'samples.pcm';wrapper=t/'probe.c';exe=t/'probe'
 wrapper.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
static unsigned loads,volumes;
static int32_t fixed_random(void *context){(void)context;return 1;}
static void observed(void *context,PlayerEventType type,int id,int argument){
 if(type==PLAYER_SOUND_LOAD)loads++;
 if(type==PLAYER_SOUND_VOLUME)volumes++;
 player_audio_event(context,type,id,argument);
}
int main(int argc,char **argv){
 assert(argc==2);bool expected=atoi(argv[1])!=0;
 for(unsigned actor=0;actor<2;actor++)for(unsigned switching=0;switching<2;switching++){
  sound_events_stop();loads=volumes=0;
  Player p={0};GameBody b={0};p.state=actor?17:1;p.character=(int)actor;p.health=100;
  p.penguin.opaque_44=p.milk.opaque_44=switching?2:0;
  player_environment=(PlayerEnvironment){.grounded=true,.world_stage=0,.sound_load_ok=!expected,.random=fixed_random,.event=observed};
  unsigned keys=switching?PLAYER_SWITCH:0;int32_t velocity=0;
  assert(player_case(&p,&b,&keys,&velocity,&player_environment));
  assert(loads==1&&volumes==(unsigned)expected);
  assert(player_environment.sound_load_ok==expected&&sound_channel_active(17)==expected);
 }
 sound_events_stop();puts("4 idle/switch voice paths pass");return 0;
}
''')
 subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(R/'ds/source'),f'-DSOUND_PACK="{pack}"',str(wrapper),*[str(R/'ds/source'/f'{n}.c')for n in names],'-o',str(exe)],check=True)
 modes=[]
 for mode in ('valid','missing','truncated'):
  if pack.exists():pack.unlink()
  if mode=='valid':pack.symlink_to(R/'ds/nitrofs/sounds/samples.hw')
  elif mode=='truncated':pack.write_bytes(b'KFS1')
  subprocess.run([str(exe),'1'if mode=='valid'else'0'],check=True);modes.append({'pack':mode,'cases':4,'success':mode=='valid'})
 result={'scope':__doc__,'cases':12,'pack_modes':modes,'sanitizers':['address','undefined'],'limits':['Load/volume branch binding only; original branch logic has separate native comparison tests. No DS storage timing/listening proof.']}
 (R/'research/audio/world-voice-load-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
