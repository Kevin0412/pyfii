import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf
name='4m_tests/1'
data,t0,music,feild=pf.read_fii(name,getfeild=True)
'''for d in data[0]:
    print(d)'''
#print(music)
pf.show(data,t0,music,feild=feild,save=name,FPS=25)
pf.show(data,t0,music,feild=feild,save=name+'_3D',ThreeD=True,imshow=[90,0],d=(600,450),FPS=25)

