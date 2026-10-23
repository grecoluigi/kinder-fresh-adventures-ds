"""Sanitized production world/update/render/effects/voice soak on all12stages.
Deterministic input pattern and automatic resets are not complete playthroughs.
"""
from pathlib import Path
import ast,json,subprocess,tempfile,os
R=Path(__file__).resolve().parents[1];source=(R/'tools/verify_world_tutorials.py').read_text();names=ast.literal_eval(next(line.strip().split('=',1)[1]for line in source.splitlines()if line.strip().startswith('names=')))
with tempfile.TemporaryDirectory(prefix='kinder-world-sanitizers-')as tmp:
 t=Path(tmp);main=t/'soak.c';main.write_text('#include "'+str(R/'ds/source/world.c')+'"\n'+'''
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "world.h"
#include "scene.h"
#include "game_save.h"
#include "sound_events.h"
#include "player.h"
static uint16_t pixels[49152],bottom[49152];
int main(int argc,char**argv){
 assert(argc==2);assert(game_save_open_directory(argv[1]));
 uint16_t *arena=malloc(272*1024+4);assert(arena);arena[0]=0x1234;arena[272*1024/2+1]=0x5678;
 scene_set_decoded_row_cache(arena+1,272*1024);
 const unsigned keys[]={8,8|16,8,8|32,0,64,4,4|16,2,1,0,16};
 unsigned total_ticks=0,total_renders=0,total_resets=0,total_transitions=0;
 for(unsigned world=0;world<8;world++)for(unsigned tutorial=0;tutorial<(world<4?2u:1u);tutorial++){
  assert(world_open_stage(world,tutorial!=0));unsigned resets=0,transitions=0,renders=0,composite_renders=0,fallback_renders=0;
  unsigned long long states=0;int min_x=body.motion.x/4096,max_x=min_x,min_y=body.motion.y/4096,max_y=min_y;
  for(unsigned step=0;step<1200;step++){
   sound_events_poll();bool ok=world_tick(keys[(step/30)%12]);total_ticks++;
   int ps=world_player_state();if(ps>=0&&ps<64)states|=1ull<<ps;
   int x=body.motion.x/4096,y=body.motion.y/4096;if(x<min_x)min_x=x;if(x>max_x)max_x=x;if(y<min_y)min_y=y;if(y>max_y)max_y=y;
   unsigned n=(step+1)*22050/60-step*22050/60;int16_t pcm[368];sound_events_mix(pcm,n,127);
   if(step%2==0){assert(world_render(pixels));if(scene_composite_active())composite_renders++;else fallback_renders++;world_render_hud(bottom,step%60==0);renders++;total_renders++;}
   int target=world_transition_target();
   if(target>=0){assert(game_save_flush_tutorials());assert(world_open((unsigned)target));transitions++;total_transitions++;}
   else if(!ok||world_finished()){assert(world_open_stage(world,tutorial!=0));resets++;total_resets++;}
   assert(arena[0]==0x1234&&arena[272*1024/2+1]==0x5678);
  }
  world_close();printf("{\\"world\\":%u,\\"tutorial\\":%u,\\"ticks\\":1200,\\"renders\\":%u,\\"resets\\":%u,\\"transitions\\":%u}\\n",world,tutorial,renders,resets,transitions);printf("{\\\"composite_renders\\\":%u,\\\"fallback_renders\\\":%u,\\\"states_mask\\\":%llu,\\\"x_range\\\":[%d,%d],\\\"y_range\\\":[%d,%d]}\\n",composite_renders,fallback_renders,states,min_x,max_x,min_y,max_y);fflush(stdout);
 }
 scene_set_decoded_row_cache(NULL,0);free(arena);
 printf("{\\"total_ticks\\":%u,\\"total_renders\\":%u,\\"total_resets\\":%u,\\"total_transitions\\":%u}\\n",total_ticks,total_renders,total_resets,total_transitions);
 return 0;
}
''')
 texture=os.environ.get('KF_TEST_TEXTURE_PREFIX')=='1'
 hardware=os.environ.get('KF_TEST_HARDWARE_BACKGROUND')=='1' or texture
 if hardware:
  code=main.read_text().replace('272*1024','144*1024')
  code=code.replace('static uint16_t pixels[49152],bottom[49152];','static uint16_t pixels[49152],bottom[49152],gpu[65536+2];')
  code=code.replace('const unsigned keys[]={','gpu[0]=0x1234;gpu[65537]=0x5678;scene_set_hardware_background(gpu+1,128*1024);\n const unsigned keys[]={')
  code=code.replace('assert(world_render(pixels));','assert(world_render(pixels));assert(scene_hardware_background_active());assert(gpu[0]==0x1234&&gpu[65537]==0x5678);for(unsigned p=0;p<49152;p++)assert(!pixels[p]||(pixels[p]&0x8000));')
  code=code.replace('scene_set_decoded_row_cache(NULL,0);free(arena);','scene_set_hardware_background(NULL,0);scene_set_decoded_row_cache(NULL,0);free(arena);')
  main.write_text(code)
 if texture:
  code=main.read_text().replace('144*1024','48*1024')
  code=code.replace('#include "player.h"','#include "player.h"\n#include "composite.h"\n#include "frame_transfer.h"')
  code=code.replace('static uint16_t pixels[49152],bottom[49152],gpu[65536+2];','static uint16_t pixels[49152],bottom[49152],gpu[65536+2],reference[49152],flattened[49152],textures[2][65536+2];')
  code=code.replace('const unsigned keys[]={','for(unsigned b=0;b<2;b++){textures[b][0]=0x1234;textures[b][65537]=0x5678;}\n const unsigned keys[]={')
  code=code.replace('assert(world_render(pixels));','''
   PlayerBlinkView saved_blink=blink_view;bool saved_advanced=blink_advanced;
   composite_enable_texture_prefix(false);assert(world_render(reference));
   blink_view=saved_blink;blink_advanced=saved_advanced;
   composite_enable_texture_prefix(true);assert(world_render(pixels));
   assert(composite_texture_prefix_active());unsigned bank=renders&1u,uploaded=0;
   assert(composite_upload_texture_prefix(bank,textures[bank]+1,&uploaded));assert(uploaded<=49152);
   int px,py;assert(composite_texture_prefix_camera(&px,&py));
   for(unsigned yy=0;yy<192;yy++)for(unsigned xx=0;xx<256;xx++){
    unsigned p=yy*256+xx;uint16_t foreground=pixels[p];
    uint16_t composed=foreground&32768?foreground:textures[bank][1+(((unsigned)py+yy)&255)*256+(((unsigned)px+xx)&255)];
    assert(composed==reference[p]);
   }
   assert(composite_snapshot_texture_prefix(flattened,pixels));assert(!memcmp(flattened,reference,sizeof(reference)));
   frame_snapshot_background(flattened,flattened,gpu+1,scene_hardware_background_offset());
   for(unsigned yy=0;yy<192;yy++)for(unsigned xx=0;xx<256;xx++){
    unsigned p=yy*256+xx;uint16_t expected=reference[p]&32768?reference[p]:gpu[1+yy*256+((xx+scene_hardware_background_offset())&255)];assert(flattened[p]==expected);
   }
   for(unsigned b=0;b<2;b++)assert(textures[b][0]==0x1234&&textures[b][65537]==0x5678);
''')
  code=code.replace('world_close();printf(', 'world_close();assert(!composite_texture_prefix_active());printf(')
  main.write_text(code)
 defs={'SCENE_ROOT':R/'ds/nitrofs/scenes','PLAYER_ROOT':R/'ds/nitrofs/players','HUD_PATH':R/'ds/nitrofs/hud_bottom.bin','HUD_BACKGROUND_ROOT':R/'ds/nitrofs/hud_backgrounds','PROJECTILE_ROOT':R/'ds/nitrofs/projectiles','ENEMY_SHOT_ROOT':R/'ds/nitrofs/enemy_shots','END_TITLE_ROOT':R/'ds/nitrofs/end_titles','SOUND_PACK':R/'ds/nitrofs/sounds/samples.hw'};exe=t/'soak';subprocess.run(['cc','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-I'+str(R/'ds/source'),*[f'-D{k}="{v}"'for k,v in defs.items()],str(main),*[str(R/'ds/source'/f'{n}.c')for n in names+(['frame_transfer']if texture else[])],'-o',str(exe)],check=True)
 result=subprocess.run([str(exe),str(t/'save')],capture_output=True,text=True);print(result.stdout,end='',flush=True)
 if result.returncode:print(result.stderr,flush=True);raise SystemExit(result.returncode)
 records=[json.loads(v)for v in result.stdout.splitlines()];report={'scope':__doc__,'sanitizers':['address','undefined'],'cases':[dict(records[i],**records[i+1])for i in range(0,len(records)-1,2)],'totals':records[-1],'cache_canaries':True,'hardware_background':hardware,'texture_prefix':texture,'limits':['Deterministic input/reset fixtures exercise production update/render/audio paths,not complete traversal/combat/endings.','Host sanitizer execution,not DS IRQ/VRAM/FAT timing or hardware FPS.','Texture comparison restores blink presentation state between two renders of each simulation frame; mode toggles invalidate texture windows, so this fixture does not measure strip upload savings.']if texture else ['Deterministic input/reset fixtures exercise production update/render/audio paths,not complete traversal/combat/endings.','Host sanitizer execution,not DS IRQ/VRAM/FAT timing or hardware FPS.']};(R/'research/gameplay'/('world-texture-sanitized-soak-verification.json'if texture else'world-hardware-sanitized-soak-verification.json'if hardware else'world-sanitized-soak-verification.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='cases'}))
