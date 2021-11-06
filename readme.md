这个库的功能是可以让我们用python写Fii的无人机程序，以解决原软件无运算能力，无循环模块，一块块拖太烦等问题。此外，这个库有三视图模拟飞行的功能，模拟飞行更方便观看。

使用方法：
首先确认电脑中已经有openCV,numpy,os,time这四个库，因为pyfii会使用到这些库。

之后如何编程：
1、导入
import pyfii as pf

2、添加无人机
d1=pf.Drone(100,100)
#100,100分别为起飞位置的x坐标和y坐标，想添加其他无人机如d2、d3……以此类推

3、动作编排
d1.takeoff(0,100)
#第一个值是起飞时间，第二个值是起飞高度

d1.intime(t)
# 在第几秒

d1. move2(x,y,z)
#直线移动至(x,y,z)

d1.delay(t)
#等待几毫秒

d1.land()
#降落

d1.end()
#结束时必加

4、保存为.fii
F=pf.Fii('测试',[d1,d2])#命名,[所有无人机名]
F.save()

5、模拟飞行
读取.fii
name='比赛现场程序'
pf.show(pf.read_fii(name)[0],pf.read_fii(name)[1])
#需注意的是文件夹名和文件名必须相同

直接在python中展示
pf.show(F.dots,F.t0)

可以不看展示直接知道能不能飞
pf.show(F.dots,F.t0,show=False)

保存为视频
pf.show(F.dots,F.t0,save='ceshi')#文件名不能用中文