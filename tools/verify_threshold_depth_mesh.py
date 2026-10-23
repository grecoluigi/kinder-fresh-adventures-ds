"""Verify overlapping threshold meshes preserve maximum scenery depth and actor visibility."""
from pathlib import Path
import json
import numpy as np
from threshold_depth_mesh import threshold_mesh
R=Path(__file__).resolve().parents[1]
rng=np.random.default_rng(2001);cases=0;actor_cases=0
for case in range(120):
 height=1+case%19;width=1+case%29
 orders=rng.integers(0,1+case%17,(height,width),dtype=np.uint8)
 if case%10==0:orders[:]=0
 if case%10==1:orders[:]=255
 rectangles=threshold_mesh(orders)
 for slot in (0,1,7,16,254,255):
  # A textured rectangle samples the final scenery color. Zero ownership is
  # transparent; other colors are deliberately independent of their depth.
  colors=rng.integers(32768,65536,(height,width),dtype=np.uint16);colors[orders==0]=0
  rendered=np.zeros_like(colors);depth=np.zeros_like(orders)
  for left,top,right,bottom,ordinal in rectangles:
   source=colors[top:bottom,left:right];z=depth[top:bottom,left:right];dest=rendered[top:bottom,left:right]
   visible=(source&32768!=0)&(ordinal>=z);dest[visible]=source[visible];z[visible]=ordinal
  mask=rng.integers(0,2,(height,width),dtype=np.uint8)!=0;color=np.uint16(0xffff)
  visible=mask&(slot>=depth);rendered[visible]=color
  expected=colors.copy();expected[mask&(slot>=orders)]=color
  assert np.array_equal(rendered,expected)
  actor_cases+=1
 cases+=1
report={'scope':__doc__,'ownership_planes':cases,'actor_depth_cases':actor_cases,'limits':['Offline integer model with synthetic planes; no C builder, DS depth quantization or GPU submission.','Overlapping quads preserve maximum depth but can increase raster fill and texture fetches; performance remains unmeasured.']}
(R/'research/rendering/threshold-depth-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
