这个软件可以让我们用python写Fii的无人机程序。
以下是功能介绍：
程序编写

FiiTest.py
from PyFii import PyFii as f
file=open('test.xml',"w+")
f.takeoff(100,100,100,file)
f.intime(3,file)
f.move2(200,200,150,file)
f.delay(1000,file)
f.move2(250,250,125,file)
f.endtime(file)
f.intime(10,file)
f.move2(300,300,175,file)
f.endtime(file)
f.end(file)

或

FiiTest2.py
from PyFii import main
file = open('test.xml',"w")
d = main.Drone(file)
d.takeoff(100,100,100)
d.intime(3)
d.move2(200,200,150)
d.delay(1000)
d.move2(250,250,125)
d.endtime()
d.intime(10)
d.move2(300,300,175)
d.endtime()
d.end()
print(d.outputString)

输出均为test.xml

test.xml
<xml xmlns="http://www.w3.org/1999/xhtml">
  <variables></variables>
  <block type="Goertek_Start" x="100" y="100">
    <next>
      <block type="block_inittime">
        <field name="time">00:00</field>
        <field name="color">#cccccc</field>
        <statement name="functionIntit">
          <block type="Goertek_UnLock">
            <next>
              <block type="block_delay">
                <field name="delay">0</field>
                <field name="time">1000</field>
                <next>
                  <block type="Goertek_TakeOff">
                    <field name="alt">100</field>
                  </block>
                </next>
              </block>
            </next>
          </block>
        </statement>
        <next>
          <block type="block_inittime">
            <field name="time">00:03</field>
            <field name="color">#cccccc</field>
            <statement name="functionIntit">
              <block type="Goertek_MoveToCoord">
                <field name="X">200</field>
                <field name="Y">200</field>
                <field name="Z">150</field>
                <next>
                  <block type="block_delay">
                    <field name="delay">0</field>
                    <field name="time">1000</field>
                    <next>
                          <block type="Goertek_MoveToCoord">
                        <field name="X">250</field>
                        <field name="Y">250</field>
                        <field name="Z">125</field>
                      </block>
                    </next>
                  </block>
                </next>
              </block>
            </statement>
            <next>
              <block type="block_inittime">
                <field name="time">00:10</field>
                <field name="color">#cccccc</field>
                <statement name="functionIntit">
                  <block type="Goertek_MoveToCoord">
                    <field name="X">300</field>
                    <field name="Y">300</field>
                    <field name="Z">175</field>
                  </block>
                </statement>
              </block>
            </next>
          </block>
        </next>
      </block>
    </next>
  </block>
</xml>

模拟飞行见cv2show.py和cv3dshow.py（可直接运行）
效果见视频

curve.py为半成品，为的是更方便地编写弧线飞行轨迹。

PyFii.py为原作者编写。
main.py为原作者一位同学修改PyFii.py而成。

仅限徐汇区青少年活动中心无人机比赛项目使用。

2021-6文件夹和2020-12文件夹为原作者两次参加比赛时的程序，仅供参考。

编写缘由：嫌原本的编程软件一块一块拖太麻烦，于是用python，并且可以实现使用函数和循环编写无人机程序，同时这程序也解决了为解锁盘而争抢的烦恼。