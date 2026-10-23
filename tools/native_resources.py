"""Native AOM resource alignment443e9d and mirror geometry431300."""
def signed16(value):return (value+32768)%65536-32768
def asset_source(script):
 source='/'.join(p for p in script['FileName'].replace('\\','/').split('/') if p).removeprefix('GData/').lower()
 # Explicit inventory aliases for the two extracted Latin-1 filenames.
 return {'animation/bär.w01':'animation/b_r.w01','animation/f_nüsse.w01':'animation/f_n_sse.w01'}.get(source,source)
def frame_alignment(script,asset,frame):
 f=asset['frames'][frame];base=asset['frames'][0] if script.get('CorrectAlignToNull') else {'x':0,'y':0}
 return signed16(f['x']-base['x']),signed16(f['y']-base['y'])
def frame_metadata(script,asset,frame,mirror=False):
 f=dict(asset['frames'][frame]);x,y=frame_alignment(script,asset,frame)
 f['x']=signed16(script.get('ReferenceSprWidth',0)-f['width']-x) if mirror else x;f['y']=y;return f
