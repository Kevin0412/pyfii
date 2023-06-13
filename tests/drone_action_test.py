import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

d1=pf.Drone(100,100)

#100,100分别为起飞位置的x坐标和y坐标，想添加其他无人机如d2、d3……以此类推

actions = [
    [d1.takeoff, [1,100], 100],
    [d1.intime, [4], 200],
    [d1.move, [200,200,100], 300],
    [d1.move2, [100, 150, 100], 400],
    [d1.land, [], 500],
    [d1.end, [], 600]
]

d1.append_actions(pf.actionfy(actions, pf.DroneAction))
d1.take_actions()

F=pf.Fii('测试',[d1])#命名,[所有无人机名],music选择性添加

F.save()