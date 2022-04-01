# pyfii
This program enables us to write .fii files (Xiaoniaofeifei formation drone) in a more convenient way via python.It also enables us to see the simulate flying in three-view(front,right,and over),which is clearer than the original one. 

Pyfii1.0.1 is on the Pipy,you can install it via "pip install pyfii".

pyfii1.0.1已上传pipy,可直接pip install.

这个库的功能是可以让我们用python写Fii的无人机程序，以解决原软件无运算能力，无循环模块，一块块拖太烦等问题。此外，这个库有三视图模拟飞行的功能，模拟飞行更方便观看。

使用方法：
1、导入
import pyfii as pf

2、添加无人机
d1=pf.Drone(100,100)
#100,100分别为起飞位置的x坐标和y坐标，想添加其他无人机如d2、d3……以此类推

3、动作编排
d1.takeoff(1,100)
#第一个值是起飞时间，第二个值是起飞高度，必须等待1秒后再起飞

d1.intime(t)
#在第几秒

d1.move(x,y,z)
#移动距离(x,y,z)

d1.move2(x,y,z)
#直线移动至(x,y,z)

d1.delay(t)
#等待几毫秒

d1.VelXY(v,a)
#速度加速度为多少

d1.AccXY(a)
#加速度为多少

d1.ARate(w)
#角速度（角速度）

d1.Yaw(a)
#转动（角度）正逆负顺

d1.Yaw2(a)
#转向（角度）正逆负顺

d1.land()
#降落

d1.end()
#结束时必加

以上动作支持pyfii模拟飞行，此外由于未对其运动轨迹进行研究，有部分动作不支持pyfii中的模拟飞行，但会保存在.fii中
d1.VelZ(v,a)
#竖直速度（速度,加速度）

d1.AccZ(a)
#竖直加速度（加速度）

d1.nod(direction,distance)
#点头 沿 direction 方向急速平移 distance cm

d1.SimpleHarmonic2(direction,amplitude)
#波浪运动 沿 direction 方向以整幅 amplitude cm 运动

d1.RoundInAir(startpos,centerpos,height,vilocity)
#绕圈飞行 起点 startpos 圆心 centerpos 高度 height 速度 vilocity(正逆时针,负顺时针)

4、保存为.fii
F=pf.Fii('测试',[d1,d2],music='xx.mp3')#命名,[所有无人机名],music选择性添加
F.save()

5、模拟飞行
读取.fii
name='比赛现场程序'
data,t0,music=pf.read_fii(name)
pf.show(data,t0,music)
#把所在文件夹的路径写下来即可

直接在python中展示
pf.show(F.dots,F.t0,F.music)

三维展示
正交：pf.show(F.dots,F.t0,F.music,ThreeD=True,imshow=[120,-15],d=(1,0))
评委视角透视：pf.show(F.dots,F.t0,F.music,ThreeD=True,imshow=[90,0],d=(495,330))
无人机视角全景：pf.show(F.dots,F.t0,F.music,ThreeD=True,save='1',FPS=20,track=[0])
定点全景：pf.show(F.dots,F.t0,F.music,ThreeD=True,save='1',FPS=20,track=(280,280,165))
#imshow参数为初始观察视角
#d为渲染模式，(1,0)表示正交展示，画面比例为1;(495,330)表示观察者在距画面中心495处，距观察者330处的画面比例为1
#track：[]表示正交或透视;[1]表示以无人机2的视角，全景观察（python列表的特性）;(280,280,165)表示以这个坐标为中心进行全景观察
#全景建议生成视频

可以不看展示直接知道能不能飞
pf.show(F.dots,F.t0,F.music,show=False)

保存为视频
pf.show(F.dots,F.t0,F.music,save='ceshi')#文件名不能用中文

保存为视频时可用FPS参数来调整视频质量，改变输出视频速度，如：
pf.show(F.dots,F.t0,F.music,save='ceshi',FPS=25)
#FPS越小，视频帧率越小，视频输出速度越快

模拟飞行：空格暂停，q后退，e前进，Esc退出，三维模拟时空格暂停后按w,a,s,d转动视角，按esc退出暂停，三维模拟中需要长按键盘操控

教学视频：https://www.bilibili.com/video/BV1Eh411t7NW/

3D engine三维引擎:https://github.com/Kevin0412/OpenCV_3D

项目开始时间：2021/6/16

draft中有一个非常好用的获取图像坐标工具：read_img.py，它可以读取图片然后用openCV展示出来，点击哪里，它就会输出该位置的坐标
