import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

<<<<<<< HEAD
name='output/1'
data,t0,music,feild=pf.read_fii(name,getfeild=True,fps=60)
pf.show(data,t0,music,feild=feild,save=name,FPS=60,max_fps=60)
pf.show(data,t0,music,feild=feild,save=name+'_3D',ThreeD=True,imshow=[90,3],d=(600,500),FPS=60,max_fps=60)
=======
name='output/...'
data,t0,music=pf.read_fii(name)
pf.show(data,t0,music)
>>>>>>> 28b7c2174f689a22da54a0bdb491fa9b77a28eca
