import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

d1=pf.Drone6(40,40,pf.drone_config_4m)
d1.ip="192.168.51.51"

d1.takeoff(1,100)

d1.inittime(4)
d1.VelXY(200,400)
d1.VelZ(200,400)
d1.move2(320,320,250)
d1.AllOn('#ffff00')
d1.delay(500)
d1.AllOn((0,255,0))
d1.delay(1655)
d1.AllOn('#ffff00')
d1.delay(500)
d1.AllOn((255,0,0))

d1.inittime(8)
d1.AllOn((255,255,0))

d1.land()

d1.end()

name='output/group_flight_4m_1'
F=pf.Fii(name,[d1])
F.save(field=4)

data,t0,music,field,*_=pf.read_fii(name,getfield=True)
pf.show(data,t0,music,field=field,save=name,FPS=25)
pf.show(data,t0,music,field=field,save=name+'_3D',ThreeD=True,imshow=[90,0],d=(600,550),FPS=25)

'''
单机飞行示例，
如果灯光与无人机运动状态相符，
说明无人机性能良好，
且能达到设置的速度加速度。
'''