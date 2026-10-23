"""Run verified ISO-to-native conversion stages in a fresh output directory.

Requiring an explicit --through prevents treating the partial native packing
pipeline as a complete source release. Current playable assets are not changed.
"""
from pathlib import Path
import argparse,json,subprocess,sys
from extract_source import extract

STAGES=('collision','scene-definitions','audio','ui','hud','characters','entities','scenes','actors','scenery')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iso',type=Path,required=True)
 p.add_argument('--output',type=Path,default=Path('build/assets'));p.add_argument('--through',choices=STAGES,required=True)
 a=p.parse_args();output=a.output.resolve();tools=Path(__file__).resolve().parent
 try:source=extract(a.iso,output)
 except(ValueError,RuntimeError,OSError,subprocess.CalledProcessError)as error:p.exit(1,str(error)+'\n')
 game=output/source['game_directory'];decoded=output/'decoded';maps=output/'maps';collision=output/'collision'
 decoded_args=['--assets',str(decoded)]
 mapped_args=decoded_args+['--maps',str(maps)]
 groups=[
  [('decode',['assets_decode.py','--source',str(game/'GData'),'--out',str(decoded)]),
   ('maps',['maps_export.py','--gdata',str(game/'GData'),'--out',str(maps)]),
   ('collision',['collision_assets_build.py',*mapped_args,'--output',str(collision)])],
  [('scene-definitions',['compile_scene_definitions.py',*mapped_args,'--output',str(output/'native_scenery')])],
  [('music',['audio_build.py','--source',str(game/'GData/SDat'),'--output',str(output/'audio')]),
   ('effects',['sound_build.py','--source',str(game),'--output',str(output/'sounds')]),
   ('hardware-audio',['sound_hw_build.py','--sounds-dir',str(output/'sounds'),'--table',str(output/'sounds/sound_assets.inc'),
                      '--audio-dir',str(output/'audio'),'--output',str(output/'hardware_audio')])],
  [('menu',['menu_build.py',*decoded_args,'--output',str(output/'menu')]),
   ('credits',['credits_build.py',*decoded_args,'--output',str(output/'credits')]),
   ('end-titles',['end_titles_build.py',*decoded_args,'--output',str(output/'end_titles')]),
   ('highscores',['highscore_build.py',*decoded_args,'--source',str(game),'--output',str(output/'highscores')])],
  [('hud-patches',['hud_build.py',*decoded_args,'--output',str(output/'hud_intermediate')]),
   ('native-hud',['stage_native_bottom_assets.py','--source-dir',str(output/'hud_intermediate'),'--output-dir',str(output/'native_bottom')]),
   ('score-popups',['score_popup_build.py',*decoded_args,'--output',str(output/'score_popups')])],
  [('players',['player_build.py',*decoded_args,'--output',str(output/'players')]),
   ('player-projectiles',['projectiles_build.py',*decoded_args,'--output',str(output/'projectiles')]),
   ('enemy-projectiles',['enemy_shots_build.py',*decoded_args,'--output',str(output/'enemy_shots')])],
  [('enemy-objects',['enemy_graphics_build.py',*mapped_args,'--output',str(output/'enemies')]),
   ('pickup-entities',['entity_graphics_build.py',*mapped_args,'--output',str(output/'entities')]),
   ('object-geometry',['resource_metadata_build.py',*mapped_args,'--output',str(output/'geometry')])],
  [('scene-metadata',['world_build.py',*mapped_args,'--collision',str(collision),'--output',str(output/'scenes')]),
   ('backgrounds',['background_build.py',*decoded_args,'--output',str(output/'backgrounds')])],
  [('gpu-actors',['convert_native_actor_catalog.py','--players',str(output/'players'),
                  '--enemies',str(output/'enemies/enemies.frames'),'--pickups',str(output/'entities/pickups.frames'),
                  '--output-dir',str(output/'native_actors')])],
  [('scenery-tiles',['compile_scenery_tiles.py',*mapped_args,'--output',str(output/'scenery_intermediate/ordered')]),
   ('scenery-palettes',['stage_shared_scenery_palette.py','--source-dir',str(output/'scenery_intermediate/ordered'),'--output-dir',str(output/'scenery_intermediate/shared')]),
   ('native-tiles',['stage_native_bg_assets.py','--source-dir',str(output/'scenery_intermediate/shared'),'--output-dir',str(output/'scenery_intermediate/native_pages')]),
   ('native-tile-locality',['repack_native_bg_locality.py','--source-dir',str(output/'scenery_intermediate/native_pages'),'--output-dir',str(output/'scenery_intermediate/reordered')]),
   ('native-depth',['build_offline_depth_packets.py','--source-dir',str(output/'scenery_intermediate/ordered'),'--output-dir',str(output/'scenery_intermediate/depth')]),
   ('native-scenery',['assemble_scenery_assets.py','--tiles',str(output/'scenery_intermediate/reordered'),'--depth',str(output/'scenery_intermediate/depth'),'--definitions',str(output/'native_scenery')])]
 ]
 assert len(groups)==len(STAGES)
 limit=STAGES.index(a.through)
 manifest={'disc':source['disc'],'through':a.through,'steps':[],
           'asset_generation_complete':False,
           'remaining':['Complete asset assembly and clean ROM build verification.']}
 manifest['remaining'] += ['Later verified conversion stages: '+', '.join(STAGES[limit+1:])] if limit+1<len(STAGES) else []
 for group in groups[:limit+1]:
  for name,args in group:
   log=output/(name+'.log')
   with log.open('w')as stream:
    result=subprocess.run([sys.executable,str(tools/args[0]),*args[1:]],stdout=stream,stderr=subprocess.STDOUT)
   manifest['steps'].append({'name':name,'returncode':result.returncode,'log':log.name})
   (output/'generation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
   if result.returncode:p.exit(1,name+' failed; see '+str(log)+'\n')
   print(name+' complete',flush=True)
 manifest['asset_generation_complete']=limit==len(STAGES)-1
 (output/'generation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
