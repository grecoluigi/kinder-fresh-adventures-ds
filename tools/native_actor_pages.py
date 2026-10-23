"""Exact GPU page encoder and bounded residency model used by the callback audit."""
from native_page_encoder import NativePageEncoder,Page,page_regions
import ctypes as C
import hashlib
import json
import numpy as np

def sha(data): return hashlib.sha256(data).hexdigest()
def align(n,a=8): return (n+a-1)//a*a

class AreaCache:
 """Host-only virtual VRAM. Alignment is byte-address alignment, not texture size."""
 def __init__(self,size):
  self.memory=bytearray(size);self.entries={};self.epoch=0;self.allowed=[]
 def begin(self,allowed,poison=False):
  self.epoch+=1;self.allowed=allowed
  if poison:
   end=0
   for a,b in allowed:
    self.memory[end:a]=b'\x37'*(a-end);end=b
   self.memory[end:]=b'\x37'*(len(self.memory)-end)
  self.entries={k:e for k,e in self.entries.items() if any(a<=e[0] and e[0]+e[1]<=b for a,b in allowed)}
 def _space(self,n):
  used=sorted((v[0],v[0]+v[1]) for v in self.entries.values())
  for a,b in self.allowed:
   at=align(a)
   for x,y in used:
    if y<=at or x>=b:continue
    if at+n<=x:return at
    at=align(max(at,y))
   if at+n<=b:return at
  return None
 def get(self,key,data):
  if key in self.entries:
   offset,n,_=self.entries[key];assert n==len(data)
   assert self.memory[offset:offset+n]==data,'Retained VRAM differs from immutable page'
   self.entries[key]=(offset,n,self.epoch);return True
  n=len(data);offset=self._space(n)
  while offset is None:
   old=[(e[2],k) for k,e in self.entries.items() if e[2]!=self.epoch]
   if not old:raise BufferError('Current-frame working set does not fit allocator')
   del self.entries[min(old,key=lambda item:item[0])[1]];offset=self._space(n)
  self.memory[offset:offset+n]=data;self.entries[key]=(offset,n,self.epoch)
  return False

class NativePageAudit(NativePageEncoder):
 def __init__(self,root,strip_height=8,trim_rows=False,adaptive_orientation=False,local_palettes=False):
  assert strip_height in (8,16,32)
  self.strip_height=strip_height
  self.trim_rows=trim_rows
  assert not adaptive_orientation or strip_height==32
  self.adaptive_orientation=adaptive_orientation
  self.local_palettes=local_palettes
  self.vertical_frames=0
  self.root=root;self.output=root/'research/rendering/native-actor-pages-assets';self.output.mkdir(exist_ok=True)
  self.artifacts={};self.bindings={};self.cases=[];self.active=False;self.errors=[];self._reset_case()
 def _reset_case(self):
  self.images={};self.frame=0;self.records=[];self.working=[]
  self.texture_caches=[AreaCache(128*1024) for _ in range(2)]
  self.palette_caches=[AreaCache(16*1024) for _ in range(2)]
 def begin_frame(self):
  self.active=True;self.working=[];self.camera_y=None;self.production_actor_bytes=0
 def _encode(self,image,kind,frameid,transient=False):
  return self.encode(image,transient)
 def observe(self,pointer,w,h,stride,left,top,kind,frameid,cx,cy):
  if not self.active:return
  try:
   assert w and h and w<=4096 and h<=4096 and stride>=w
   image=np.ctypeslib.as_array(pointer,shape=(h*stride,)).reshape(h,stride)[:,:w].copy()
   if self.camera_y is None:self.camera_y=cy
   assert cy==self.camera_y
   self.production_actor_bytes+=max(0,min(256,left+w)-max(0,left))*max(0,min(192,top+h)-max(0,top))*2
   key=(kind,frameid)
   if kind<=2:
    normalized=np.where(image&32768,image,0).astype('<u2');fingerprint=sha(normalized.tobytes())
    if key in self.images:
     old,pages=self.images[key];assert old==(w,h,fingerprint),'Asset identity changed pixels'
    else:
     pages=self._encode(image,kind,frameid);self.images[key]=((w,h,fingerprint),pages)
   else:pages=self._encode(image,kind,frameid,transient=True)
   for p in pages:
    if not p.opaque or left+p.source_x>=256 or left+p.source_x+p.draw_width<=0 or top+p.source_y>=192 or top+p.source_y+p.height<=0:continue
    # Transient pages are never assumed to survive beyond this frame.
    key=p.key if kind<=2 else (self.frame,kind,frameid,p.source_x,p.source_y)
    self.working.append((key,p))
  except Exception as e:self.errors.append(repr(e))
 def end_frame(self,production_failed=False,static_quads=65535):
  self.active=False
  assert not self.errors,self.errors
  if self.camera_y is None:self.frame+=1;return
  bank=self.frame&1;cy=self.camera_y&255;start=(cy+192)&255
  intervals=[(start*512,(start+64)*512)] if start+64<=256 else [(0,(start+64-256)*512),(start*512,128*1024)]
  texture=self.texture_caches[bank];palette=self.palette_caches[bank]
  texture.begin(intervals,poison=True);palette.begin([(0,16*1024)])
  baseline=sum(p.width*p.texture_height*2 for _,p in self.working)
  needed={k:p for k,p in self.working}
  unique_palettes={sha(p.palette):p.palette for p in needed.values() if p.palette}
  working_tex=sum(len(p.texels) for p in needed.values());working_pal=sum(len(v) for v in unique_palettes.values())
  upload=pal_upload=hits=0;failed=False
  try:
   for key,p in self.working:
    if p.palette:
     if not palette.get(sha(p.palette),p.palette):pal_upload+=len(p.palette)
    if texture.get(key,p.texels):hits+=1
    else:upload+=len(p.texels)
   # Verify all pinned entries after every allocation/eviction has completed.
   for key,p in self.working:
    offset,n,age=texture.entries[key];assert age==texture.epoch and texture.memory[offset:offset+n]==p.texels
  except BufferError:
   failed=True;self.texture_caches[bank]=AreaCache(128*1024);self.palette_caches[bank]=AreaCache(16*1024)
  self.records.append({'frame':self.frame,'camera_y':self.camera_y,'pages':len(self.working),'unique_pages':len(needed),'static_quads_conservative':static_quads,'combined_quads_conservative':static_quads+len(self.working)+1,'geometry_over_budget':static_quads+len(self.working)+1>1536,'texture_working_bytes':working_tex,'palette_working_bytes':working_pal,'texture_miss_bytes':upload,'palette_miss_bytes':pal_upload,'hits':hits,'failed':failed,'production_failed':bool(production_failed),'production_actor_bytes':self.production_actor_bytes,'padded_direct_baseline_bytes':baseline})
  self.frame+=1
 def end_case(self,name,mode):
  bindings=self.bindings.setdefault(name,{})
  for (kind,frameid),(source,pages) in self.images.items():
   key=f'{kind}:{frameid}'
   binding={'kind':kind,'frame_id':frameid,'width':source[0],'height':source[1],'source_normalized_sha256':source[2],'pages':[{'key':p.key,'source_x':p.source_x,'source_y':p.source_y,'draw_width':p.draw_width,'draw_height':p.height} for p in pages]}
   if key in bindings:assert bindings[key]==binding
   bindings[key]=binding
  r=self.records;accepted=[x for x in r if not x['failed']]
  case={'map':name,'mode':mode,'observed_frames':self.frame,'eligible_frames':len(r),'capacity_failures':sum(x['failed'] for x in r),'new_capacity_failures':sum(x['failed'] and not x['production_failed'] for x in r),'max_texture_working_bytes':max((x['texture_working_bytes'] for x in r),default=0),'max_palette_working_bytes':max((x['palette_working_bytes'] for x in r),default=0),'max_submitted_pages':max((x['pages'] for x in r),default=0),'accepted_texture_upload_bytes':sum(x['texture_miss_bytes'] for x in accepted),'accepted_palette_upload_bytes':sum(x['palette_miss_bytes'] for x in accepted),'accepted_page_hits':sum(x['hits'] for x in accepted),'records':r}
  case.update(max_combined_quads_conservative=max((x['combined_quads_conservative'] for x in r),default=0),geometry_over_budget_frames=sum(x['geometry_over_budget'] for x in r))
  matched=[x for x in r if not x['failed'] and not x['production_failed'] and not x['geometry_over_budget']]
  old=sum(x['production_actor_bytes'] for x in matched);new=sum(x['texture_miss_bytes']+x['palette_miss_bytes'] for x in matched)
  case.update(matched_frames=len(matched),matched_production_actor_bytes=old,matched_native_upload_bytes=new,matched_upload_reduction_percent=round(100*(1-new/old),2) if old else 0)
  self.cases.append(case);print('native-pages '+json.dumps({k:v for k,v in case.items() if k!='records'}),flush=True);self._reset_case()
 def finish(self,rom_sha):
  assert not self.errors,self.errors
  manifest={'scope':'Actual callback art converted losslessly to hardware-readable 4/8-bit indexed or RGB555 texture strips; research assets only.','rom_sha256':rom_sha,'bindings':self.bindings,'pages':list(self.artifacts.values()),'texture_bytes':sum(p['texel_bytes'] for p in self.artifacts.values()),'unique_palettes':len({p['palette'] for p in self.artifacts.values() if p['palette']}),'palette_bytes':sum((self.output/f).stat().st_size for f in {p['palette'] for p in self.artifacts.values() if p['palette']}),'limits':['Observed frames only, not a complete shipped asset conversion.','GPU palette entry zero is transparent; opaque palette RGB retains all source RGB555 bits.','Eight-row strips split at 64 source pixels, with transparent columns trimmed, power-of-two width and zero padding. No quantization or filtering.','Native sampler outputs are modeled as transient direct color and are not exported as immutable assets.']}
  (self.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
  report={'scope':'Host indexed-page residency with real callback images and keys. No production source/ROM changes.','rom_sha256':rom_sha,'cases':self.cases,'assets_manifest':'native-actor-pages-assets/manifest.json','limits':['No GPU/ARM9 timing, palette binding or publication test; bytes are not FPS. Conservative geometry admission uses the untrimmed visible static mesh plus every submitted actor page and the base quad.','Assumes two independent 16 KiB palette banks, which the current renderer does not have. Releasing foreground bitmap VRAM requires a separately verified replacement for every CPU/UI publication path.','Each actor bank still shares unused byte intervals with the RGB555 scenery texture. Camera movement invalidates overwritten page intervals.','Per-frame geometry can grow because strips align to source rows rather than clipped screen rows.','Additional texture/palette metadata and offline asset lookup RAM not admitted to the DS heap yet.','No saving, sound, complete-level or physical hardware validation in this experiment.']}
  (self.root/'research/rendering/native-actor-pages-feasibility.json').write_text(json.dumps(report,indent=2)+'\n')
