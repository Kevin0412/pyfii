import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

A,B,C,D,E,F = [i for i in range(6)]
AFTER, BEFORE = 'after', 'before'

d1=pf.Drone(40,40,pf.drone_config_6m)

# 无人机动作
d1.takeoff(1,1000000000000000000)

d1.inittime(4)
d1.VelXY(200,400)
d1.VelZ(200,400)
d1.move2(520,520,250, A)
d1.delay(100000000000000, B)    # 故意的错误
d1.delay(2999, C)
d1.delay(500, D)
d1.inittime(9)
d1.land(E)

# 独立编写灯光
d1.TurnOnAll('#ffff00', A, AFTER)
d1.TurnOnAll((0,255,0), B, AFTER)
d1.TurnOnAll([
    '#ffff00','#ffff00','#ffff00','#ffff00',
    '#ffff00','#ffff00','#ffff00','#ffff00',
    '#ffff00','#ffff00','#ffff00','#ffff00'
], C, AFTER)
d1.TurnOnAll([
    (255,0,0),(255,0,0),(255,0,0),(255,0,0),
    (255,0,0),(255,0,0),(255,0,0),(255,0,0),
    (255,0,0),(255,0,0),(255,0,0),(255,0,0)
],D,AFTER)
d1.BlinkFastAll(['#ff0000',(255,255,0),'#00ff00'], E, BEFORE)


d1.end()    # 整合动作和灯光

name='light_6m'
F=pf.Fii(name,[d1])
F.save(feild=6)
