"""Offline mesh experiment: transparent and later-owned pixels may share a lower quad.

Every opaque texel must still receive its exact maximum scenery order. Extra
lower-depth coverage is harmless only beneath its correct later-owned quad.
"""
import numpy as np

def threshold_mesh(orders):
 rectangles=[]
 for ordinal in np.unique(orders):
  if not ordinal:continue
  allowed=(orders==0)|(orders>=ordinal);active={}
  def emit(left,top,right,bottom):
   if np.any(orders[top:bottom,left:right]==ordinal):
    rectangles.append((left,top,right,bottom,int(ordinal)))
  for y,line in enumerate(allowed):
   starts=np.r_[0,np.flatnonzero(line[1:]!=line[:-1])+1];ends=np.r_[starts[1:],len(line)];current={}
   for a,b in zip(starts,ends):
    if line[a]:current[(int(a),int(b))]=active.get((int(a),int(b)),y)
   for (left,right),top in active.items():
    if (left,right) not in current:emit(left,top,right,y)
   active=current
  for (left,right),top in active.items():emit(left,top,right,len(orders))
 restored=np.zeros_like(orders)
 for left,top,right,bottom,ordinal in rectangles:
  region=orders[top:bottom,left:right]
  assert np.all((region==0)|(region>=ordinal))
  target=restored[top:bottom,left:right]
  np.maximum(target,np.where(region!=0,ordinal,0).astype(orders.dtype),out=target)
 assert np.array_equal(restored,orders)
 return rectangles
