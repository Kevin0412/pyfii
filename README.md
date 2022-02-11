# pyfii
This program enables us to write .fii files (Xiaoniaofeifei formation drone) in a more convenient way via python.It also enables us to see the simulate flying in three-view(front,right,and over),which is more clear than the original one. 

Pyfii1.0.1 is on the Pipy,you can install it via "pip install pyfii".

pyfii1.0.1已上传pipy,可直接pip install.

这个库的功能是可以让我们用python写Fii的无人机程序，以解决原软件无运算能力，无循环模块，一块块拖太烦等问题。此外，这个库有三视图模拟飞行的功能，模拟飞行更方便观看。

使用方法:
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
#在第几秒

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
data,t0=pf.read_fii(name)
pf.show(data,t0)
#把所在文件夹的路径写下来即可

直接在python中展示
pf.show(F.dots,F.t0)

可以不看展示直接知道能不能飞
pf.show(F.dots,F.t0,show=False)

保存为视频
pf.show(F.dots,F.t0,save='ceshi')#文件名不能用中文

保存为视频时可用FPS参数来调整视频质量，改变输出视频速度，如：
pf.show(F.dots,F.t0,save='ceshi',FPS=25)
#FPS越小，视频帧率越小，视频输出速度越快

模拟飞行：空格暂停，q后退，e前进，Esc退出

教学视频：https://www.bilibili.com/video/BV1Eh411t7NW/
