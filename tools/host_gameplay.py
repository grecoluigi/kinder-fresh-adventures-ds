"""Compile actual gameplay for headless navigation; display calls fail closed."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GAMEPLAY_SOURCES = [
    'scene', 'player_graphics', 'player', 'animation', 'body', 'physics',
    'collision', 'camera', 'tile_queries', 'native_rng', 'hazards', 'hud',
    'native_bottom', 'effects', 'entities', 'projectiles', 'geometry', 'platforms', 'enemies',
    'enemy_shots', 'sound_events', 'blocks', 'world_objects', 'world_enemies',
    'boss_factory', 'boss_valley', 'boss_mountain_jungle', 'end_titles',
    'world_routes', 'game_save', 'persistence', 'persistence_store', 'save_archive',
]


def compile_logic(wrapper, library):
    definitions = {
        'SCENE_ROOT': 'scenes', 'PLAYER_ROOT': 'players',
        'HUD_NATIVE_ROOT': 'native_bottom', 'PROJECTILE_ROOT': 'projectiles',
        'ENEMY_SHOT_ROOT': 'enemy_shots', 'END_TITLE_ROOT': 'end_titles',
        'SOUND_PACK': 'sounds/samples.hw', 'NATIVE_SCENERY_ROOT': 'native_scenery',
    }
    subprocess.run([
        'cc', '-dynamiclib', '-O2', '-Wall', '-Wextra', '-Werror',
        *['-D'+key+'='+json.dumps(str(ROOT/'ds/nitrofs'/value))
          for key, value in definitions.items()],
        '-I'+str(ROOT/'ds/source'), str(wrapper),
        *[str(ROOT/'ds/source'/(name+'.c')) for name in GAMEPLAY_SOURCES],
        str(ROOT/'ds/tests/world_logic_backend.c'), '-o', str(library),
    ], check=True)


def source_fingerprint():
    files = [p for p in (ROOT/'ds/source').iterdir()
             if p.suffix in ('.c', '.h', '.inc')]
    files.append(ROOT/'ds/tests/world_logic_backend.c')
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}
