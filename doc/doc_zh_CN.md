使用方法：

1. 导入
    ```python
    import pyfii as pf
    ```

2. 添加无人机
    添加F400
    ```python
    d1=pf.Drone(100,100)
    #100,100分别为起飞位置的x坐标和y坐标，想添加其他无人机如d2、d3……以此类推
    ```
    添加F600
    ```python
    d1=pf.Drone6(100,100)
    #100,100分别为起飞位置的x坐标和y坐标，想添加其他无人机如d2、d3……以此类推
    ```

3. 动作编排
    ```python
    #d1.X, d1.Y=200,300
    #修改起飞位置为(200,300)
    #起飞前可以通过如上参数修改起飞位置，

    d1.takeoff(1,100)
    #第一个值是起飞时间，第二个值是起飞高度，必须等待1秒后再起飞

    d1.inittime(t)
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

    d1.TurnOnAll(color)
    #点亮所有灯，颜色

    d1.TurnOffAll()
    #熄灭所有灯

    d1.land()
    #降落

    d1.end()
    #结束时必加
    ```

    以上动作支持pyfii模拟飞行，此外由于未对其运动轨迹进行研究，有部分动作不支持pyfii中的模拟飞行，但会保存在```.fii```中

    pyfii 1.5.0及后续版本中加入了灯光模拟支持，但是只支持显示点灯和灭灯

    ```python
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

    d1.TurnOnSingle(Id,color)
    #点亮某一盏灯，颜色

    d1.TurnOnAll(colors)
    #点亮所有灯，颜色

    d1.TurnOffSingle(Id)
    #熄灭某一盏灯

    d1.BlinkSingle(Id,color)
    #闪烁某一盏灯，颜色

    d1.Breath(color)
    #呼吸灯，颜色

    d1.BlinkFastAll(colors)
    #快速闪烁所有灯(颜色)

    d1.BlinkSlowAll(colors)
    #慢速闪烁所有灯(颜色)

    d1.HorseRace(colors)
    #走马灯(颜色)
    ```

4. 保存为.fii
    ```python
    F=pf.Fii('测试',[d1,d2],music='xx.mp3')#命名,[所有无人机名],music选择性添加
    F.save()
    ```
5. 模拟飞行

    读取.fii
    ```python
    name='比赛现场程序'
    track=pf.from_fii(name)
    pf.show(track)
    #把所在文件夹的路径写下来即可
    ```

    原来的参数调用仍然可用：
    ```python
    data,t0,music,field,device=pf.read_fii(name)
    pf.show(data,t0,music,field=field,device=device)
    ```

    直接在python中展示
    ```python
    pf.show(F.dots,F.t0,[F.music],skin=1)
    #有0,1,2三种皮肤
    ```

    三维展示

    正交：
    ```python
    pf.show(F.dots,F.t0,F.music,ThreeD=True,imshow=[120,-15],d=(1,0))
    ```
    评委视角透视：
    ```python
    pf.show(F.dots,F.t0,F.music,ThreeD=True,imshow=[90,0],d=(600,450))
    ```
    无人机视角全景：
    ```python
    pf.show(F.dots,F.t0,F.music,ThreeD=True,save='1',FPS=20,track=[0])
    ```
    定点全景：
    ```python
    pf.show(F.dots,F.t0,F.music,ThreeD=True,save='1',FPS=20,track=(280,280,165))
    #imshow参数为初始观察视角
    #d为渲染模式，(1,0)表示正交展示，画面比例为1;(600,450)表示观察者在距画面中心600处，距观察者450处的画面比例为1
    #track：[]表示正交或透视;[1]表示以无人机2的视角，全景观察（python列表的特性）;(280,280,165)表示以这个坐标为中心进行全景观察
    #全景建议生成视频
    ```

    可以不看展示直接知道能不能飞
    ```python
    pf.show(F.dots,F.t0,[F.music],show=False)
    ```
    保存为视频
    ```python
    pf.show(F.dots,F.t0,[F.music],save='ceshi')#文件名不能用中文
    ```
    保存为视频时可用```FPS```参数来调整视频质量，改变输出视频速度，如：
    ```python
    pf.show(F.dots,F.t0,[F.music],save='ceshi',FPS=25)
    #FPS越小，视频帧率越小，视频输出速度越快
    ```

    模拟飞行：空格暂停，q后退，e前进，Esc退出，三维模拟时空格暂停后按w,a,s,d转动视角，按esc退出暂停，三维模拟中需要长按键盘操控

    教学视频：https://www.bilibili.com/video/BV1Eh411t7NW/

    脚本模式：贴近原版

    运行
    ```python
    from pyfii import *

    d1=Drone()
    d2=Drone()
    d3=Drone()
    d4=Drone()
    d5=Drone()
    d6=Drone()
    d7=Drone()
    ds=[d1,d2,d3,d4,d5,d6,d7]

    F=Fii('测试',ds,music='xx.mp3')
    F.save()
    ```

    之后生成一文件夹
    里面有```.py```文件，也有```.fii```文件，运行```.py```文件即可预览动作设计
    此外，编辑动作组中的```pyfiiCode.py```可以编写飞行动作
    同时内置```readme.md```方便编程

6. 小技巧（参赛经验）

    1. ```d.X,d.Y```两个变量表示无人机起飞位置的坐标，在起飞指令前，修改有效

    2. ```d.x,d.y,d.z```三个变量表示当前移动的目标点，通过对这个的应用，可以使程序变简单

    3. 综合使用for循环，if判断，列表等的方式进行编程

    4. 比赛时可以两名参赛队员各写一半，然后合并

    5. 建议提前设计动作

    6. 实践是检验真理的唯一标准，不要被模拟的假象所迷惑

7. GUI 原型

    仓库中新增了独立 Web GUI 原型，路径为：

    ```text
    apps/pyfii-gui/
    ```

    它用于上传 Fii 项目 zip、读回轨迹、查看安全日志，并用 Canvas 2D 显示 Pyfii 经典三视图。GUI 不属于 `src/pyfii/` core 包，依赖方向是 `pyfii-gui -> pyfii core`。

    后端启动：

    ```bash
    cd apps/pyfii-gui/backend
    pip install -e .
    uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
    ```

    前端启动：

    ```bash
    cd apps/pyfii-gui/frontend
    npm install
    npm run dev
    ```

    默认可在局域网访问：

    ```text
    http://<开发机局域网IP>:5173
    ```

    详细说明见 [Pyfii GUI 原型](pyfii_gui.md)。
