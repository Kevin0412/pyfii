import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

d1=pf.Drone(100,100)

#100,100分别为起飞位置的x坐标和y坐标，想添加其他无人机如d2、d3……以此类推

d1.takeoff(1,100)
#第一个值是起飞时间，第二个值是起飞高度，必须等待1秒后再起飞

d1.intime(4)
#在第几秒

d1.move(200, 200, 100)
#移动距离(x,y,z)

d1.move2(100, 150, 100)
#直线移动至(x,y,z)

d1.delay(5000)

d1.land()
#降落

d1.end()
#结束时必加

F=pf.Fii('output/测试',[d1])#命名,[所有无人机名],music选择性添加

F.save()