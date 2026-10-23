"""Export read-only route planning evidence from production collision and entities.

The overview is not artwork: it distinguishes solid pixels, one-way surfaces,
hazards, and climbable tiles. No world updates or progression writes are made.
"""
import argparse
import ast
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw

R = next(p for p in Path(__file__).resolve().parents if (p / 'ds/source/world.c').is_file())


def export(output, worlds, scale):
    source = (R / 'tools/verify_world_tutorials.py').read_text()
    names = ast.literal_eval(next(x.strip().split('=', 1)[1] for x in source.splitlines()
                                  if x.strip().startswith('names=')))
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kinder-navigation-') as tmp:
        t = Path(tmp)
        wrapper, library = t / 'probe.c', t / 'world.dylib'
        wrapper.write_text('#include "' + str(R / 'ds/source/world.c') + '"\n' + r'''
void nav_metadata(int32_t *v){
 const CollisionMap*m=scene_collision_map();
 v[0]=m->width*m->tile_width;v[1]=m->height*m->tile_height;
 v[2]=body.motion.x/4096;v[3]=body.motion.y/4096;v[4]=body.layer;
}
void nav_grid(uint8_t*out,int step){
 const CollisionMap*m=scene_collision_map();
 int w=m->width*m->tile_width,h=m->height*m->tile_height;
 for(int y=0;y<h;y+=step)for(int x=0;x<w;x+=step){
  unsigned bits=collision_point(m,body.layer,x,y);
  const uint8_t*c=collision_cell(m,body.layer,x/32,y/32);
  if(c&&(c[1]!=255||c[2]!=255)&&((c[1]|c[2]<<8)>>9&1))bits|=8;
  *out++=(uint8_t)bits;
 }
}
int nav_entities(int32_t*out,int capacity){
 size_t count;GameEntity*e=scene_entities(&count);int n=0;
 for(size_t i=0;i<count&&n<capacity;i++)if(entity_active(e+i)){
  EntityEnvironment env={0};scene_entity_environment(i,&env);
  out[n*7]=i;out[n*7+1]=entity_id(e+i);out[n*7+2]=entity_x(e+i);
  out[n*7+3]=entity_y(e+i);out[n*7+4]=entity_layer(e+i);
  out[n*7+5]=env.width;out[n*7+6]=env.height;++n;
 }
 return n;
}
int nav_paths(int32_t*out,int capacity){
 size_t count;GameEntity*e=scene_entities(&count);int n=0;
 for(size_t i=0;i<count&&n<capacity;i++){
  unsigned id=entity_id(e+i);
  if(id!=2&&id!=200&&id!=201&&id!=202&&id!=210&&id!=220&&(id<230||id>233)&&id!=414)continue;
  int32_t*v=out+n*13;v[0]=i;v[1]=id;v[2]=entity_x(e+i);v[3]=entity_y(e+i);
  for(unsigned j=0;j<4;j++){int16_t bound;memcpy(&bound,e[i].bytes+31+j*2,2);v[4+j]=bound;}
  v[8]=e[i].bytes[28];v[9]=e[i].bytes[29];v[10]=e[i].bytes[39];v[11]=e[i].bytes[40];v[12]=e[i].bytes[42];++n;
 }
 return n;
}
''')
        defs = {'SCENE_ROOT': R / 'ds/nitrofs/scenes', 'PLAYER_ROOT': R / 'ds/nitrofs/players',
                'HUD_PATH': R / 'ds/nitrofs/hud_bottom.bin', 'PROJECTILE_ROOT': R / 'ds/nitrofs/projectiles',
                'ENEMY_SHOT_ROOT': R / 'ds/nitrofs/enemy_shots', 'END_TITLE_ROOT': R / 'ds/nitrofs/end_titles',
                'SOUND_PACK': R / 'ds/nitrofs/sounds/samples.hw'}
        subprocess.run(['cc', '-dynamiclib', '-O2', '-Wall', '-Wextra', '-Werror',
                        *[f'-D{k}="{v}"' for k, v in defs.items()], str(wrapper),
                        *[str(R / 'ds/source' / f'{n}.c') for n in names], '-o', str(library)], check=True)
        c = C.CDLL(str(library))
        c.world_open_stage.restype = C.c_bool
        c.world_map_name.restype = C.c_char_p
        for world in worlds:
            assert c.world_open_stage(world, False)
            meta = (C.c_int32 * 5)()
            c.nav_metadata(meta)
            w, h = (meta[0] + scale - 1) // scale, (meta[1] + scale - 1) // scale
            grid = (C.c_uint8 * (w * h))()
            c.nav_grid(grid, scale)
            rows = (C.c_int32 * (8192 * 7))()
            count = c.nav_entities(rows, 8192)
            assert count < 8192, 'Entity export capacity reached'
            entities = [dict(zip(('index', 'id', 'x', 'y', 'layer', 'width', 'height'), rows[i*7:i*7+7]))
                        for i in range(count)]
            ingredients = [e for e in entities if 53 <= e['id'] <= 58]
            paths = (C.c_int32 * (8192 * 13))()
            path_count = c.nav_paths(paths, 8192)
            assert path_count < 8192
            moving_paths = [dict(zip(('index','id','x','y','left','top','right','bottom','enabled','speed','direction','wait','top_trim'),paths[i*13:i*13+13])) for i in range(path_count)]
            assert sorted(e['id'] for e in ingredients) == list(range(53, 59))
            image = Image.new('RGB', (w, h))
            image.putdata([(194, 74, 66) if b & 2 else (118, 90, 193) if b & 8 else
                           (231, 180, 56) if b & 4 else (151, 167, 177) if b & 1 else
                           (23, 30, 38) for b in grid])
            draw = ImageDraw.Draw(image)
            for x in range(0, meta[0], 512):
                draw.line((x//scale, 0, x//scale, h), fill=(42, 52, 62))
                draw.text((x//scale+2, 2), str(x), fill='white')
            for y in range(0, meta[1], 512):
                draw.line((0, y//scale, w, y//scale), fill=(42, 52, 62))
                draw.text((2, y//scale+2), str(y), fill='white')
            for e in entities:
                if e['layer'] != meta[4] and e not in ingredients:
                    continue
                x, y = e['x']//scale, e['y']//scale
                if e in ingredients:
                    draw.ellipse((x-4, y-4, x+4, y+4), fill=(255, 235, 100))
                    label=str(e['id'])+(f" L{e['layer']}" if e['layer']!=meta[4] else '')
                    draw.text((x+5, y-5), label, fill='white')
                elif e['id'] in (76, 78, 83, 86, 87):
                    draw.rectangle((x, y, x+max(2,e['width']//scale), y+max(2,e['height']//scale)), outline='cyan')
            x, y = meta[2]//scale, meta[3]//scale
            draw.ellipse((x-4, y-4, x+4, y+4), fill=(80, 255, 120))
            stem = output / ('jungle', 'ice', 'factory', 'fantasy')[world]
            image.save(stem.with_suffix('.png'))
            stem.with_suffix('.collision.bin').write_bytes(bytes(grid))
            result = {'world': world, 'map': c.world_map_name().decode(), 'width': meta[0], 'height': meta[1],
                      'spawn': list(meta[2:4]), 'collision_layer': meta[4], 'grid_step': scale,
                      'grid_width': w, 'grid_height': h, 'ingredients': ingredients, 'entities': entities,
                      'moving_paths': moving_paths,
                      'legend': {'1': 'solid pixel', '2': 'hazard', '4': 'one-way surface', '8': 'climbable tile'},
                      'limits': ['Static collision and initial entity positions; moving geometry is not baked into the grid.',
                                 'Downsampled overview can miss narrow surfaces. Runtime probes remain authoritative.'],
                      'production_source_sha256': {n: hashlib.sha256((R/'ds/source'/f'{n}.c').read_bytes()).hexdigest()
                                                   for n in ['world', *names]}}
            stem.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps({k: result[k] for k in ('map', 'width', 'height', 'spawn', 'ingredients')}))
            c.world_close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--world', type=int, choices=range(4), action='append')
    p.add_argument('--scale', type=int, choices=(1, 2, 4, 8), default=4)
    args = p.parse_args()
    export(args.output, args.world if args.world is not None else range(4), args.scale)
