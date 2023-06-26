import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

name='output/开启新征程 加速版715'
data,t0,music,feild=pf.read_fii(name,getfeild=True)
pf.show(data,t0,music,feild=feild,skin=1)
pf.show(data,t0,music,feild=feild,ThreeD=True,imshow=[120,-30],d=(1,0))

data,t0,music,feild=pf.read_fii(name,getfeild=True,fps=60)
pf.show(data,t0,music,feild=feild,save=name,FPS=60,max_fps=60)
pf.show(data,t0,music,feild=feild,save=name+'_3D',ThreeD=True,imshow=[90,3],d=(600,500),FPS=60,max_fps=60)
