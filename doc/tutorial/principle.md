# 原理

1. 小鸟飞飞文件

        test
        ├── 动作组
        │   ├── 动作组1
        │   │   ├── transfile
        │   │   │   └── 1001.ls
        │   │   ├── offlineExcuteScript.py
        │   │   ├── webCodeAll.py
        │   │   └── webCodeAll.xml
        │   ├── 动作组2
        │   │   ├── transfile
        │   │   │   └── 2002.ls
        │   │   ├── offlineExcuteScript.py
        │   │   ├── webCodeAll.py
        │   │   └── webCodeAll.xml
        │   ...
        │   ├── checksums.xml
        │   └── xxx.mp3
        └── test.fii

    其中，
    
    ```test.fii```文件记录了起飞位置、无人机ip、无人机型号、地毯尺寸、音乐文件名称和inittime的时间

    ```checksums.xml```文件暂不清楚它的用处，猜测保存了每架无人机的主机地址

    ```xxx.mp3```就是你的音乐

    ```webCodeAll.xml```是你写的单个无人机的飞行程序

    ```webCodeAll.py```是小鸟飞飞的伪代码，只要有```webCodeAll.xml```，伪代码文件会自动生成，猜测是模拟时用的

    ```offlineExcuteScript.py```在点击上传时会出现，猜测这是编译至无人机可执行的代码的源代码

    ```.ls```文件我猜测是上传给无人机的二进制文件，上传成功就会有这个文件

2. pyfii生成文件

    pyfii-1.4.0以前

        test
        ├── 动作组
        │   ├── 动作组1
        │   │   └── webCodeAll.xml
        │   ├── 动作组2
        │   │   └── webCodeAll.xml
        │    ...
        │   ├── checksums.xml
        │   └── xxx.mp3
        └── test.fii

    pyfii-1.1.1和pyfii-1.5.0及后续版本，加入了[脚本模式](script_mode.md)

        test
        ├── 动作组
        │   ├── 动作组1
        │   │   ├── pyfiiCode.py
        │   │   └── webCodeAll.xml
        │   ├── 动作组2
        │   │   ├── pyfiiCode.py
        │   │   └── webCodeAll.xml
        │   ...
        │   ├── checksums.xml
        │   └── xxx.mp3
        ├── readme.md
        ├── test.md
        └── test.py
    
3. pyfii模拟

    1. 读入文件并计算轨迹

        ```python
        data,t0,music,feild=pf.read_fii(name,getfeild=True)
        ```

        这一模块实现了读入小鸟飞飞文件并输出飞行轨迹的功能

        其中

        ```name```是```.fii```文件所在的文件夹

        ```data```是一个列表，列表的长度是无人机数，每一个元素也是列表

        ```data[n]```列表储存了第n+1架无人机飞行轨迹及旋转数据，每一个元素是长度为5的元组

        ```python
        data=[
            [(time,x,y,z,degree),(time,x,y,z,degree),...],
            [(time,x,y,z,degree),(time,x,y,z,degree),...],
            ...
        ]
        # time单位为ms，每隔5ms一个动作数据采样
        # x,y,z单位为cm
        # degree单位为°
        ```
        
        ```t0```表示模拟结束的帧数（即动作时长```t0/200```秒）

        ```music```表示音乐，数据类型为列表，长度为1或2，元素的数据类型为字符串

        ```python
        music=[musicdir,musicname] # musicname不需要后缀
        
        music=[musicname] # musicname为音乐的路径及名称，包括后缀
        ```

        ```feild```表示地毯大小，```4```表示4米毯，```6```表示6米毯

        原理是读入文件，字符串处理，将```webCodeAll.xml```转化为飞行指令，之后再转化为飞行轨迹

        pyfii计算飞行轨迹时，将运动过程被近似为先由静止开始做加速度与速度方向相同的匀加速直线运动，再做匀速直线运动，然后做加速度与速度方向相反的匀加速直线运动，最后静止

        如果在一半位移处未到达最高速度，则直接开始减速

        对于无人机未到达目标点时有新的移动指令时，pyfii会提示你动作未完成，让无人机以最大加速度（400cm/s^2）减速至速度为零，再执行移动到目标点的动作，这一操作会与实际存在一定偏差

        对于速度加速度未定义的情况，pyfii将使用默认值，默认值存在误差，建议起飞后移动前先定义速度加速度

        对于旋转与移动是否存在冲突，并未有研究，在pyfii模拟中，认为旋转与移动不冲突，且未引入角加速度

        对于进阶动作，pyfii不会模拟

        对于水平和竖直速度加速度，pyfii模拟时只认水平速度加速度，建议在编程时，水平和竖直速度加速度相统一，避免模拟误差

    2. 渲染

        ```python
        show(data,t0,music,feild,show=True,save="",FPS=200,ThreeD=False,imshow=[120,-15],d=(600,450),track=[],skin=1)
        ```

        这里参数比较多，需要一一介绍

        ```data,t0,music,feild```这四个在上文介绍过了，这里不多赘述

        ```show=False```时，直接打印是否存在距离过近的情况，没有图像渲染

        ```python
        pf.show(data,t0,music,feild,show=False)
        ```

        ```show==True```时，要分类讨论，```show```默认为```True```，不用写

        二维模拟：

        二维模拟时，需要的参数有```skin```，因为只有二维模拟时有皮肤

        ```python
        pf.show(data,t0,music,feild,skin=1)
        #有0,1,2三种皮肤
        ```

        三维模拟：

        三维模拟时，需要的参数有```ThreeD,imshow,d```

        ```python
        pf.show(data,t0,music,feild,ThreeD=True,imshow=[120,-15],d=(1,0))
        # 正交
        pf.show(data,t0,music,feild,ThreeD=True,imshow=[90,0],d=(600,450))
        # 透视
        ```

        其中，

        三维渲染使用的是cv3d，由github@Kevin0412编写，右手系
        
        ```imshow```这个列表表示观察者视线向量的方位角和俯仰角

        ```imshow[0]==90```时，相当于视线的方位角为y轴正方向，即观察者位于正前方

        ```imshow[1]```为正，相当于抬头看，为负，相当于低头看

        ```d```这个元组，第一个值表示观察者距离画面中心的距离，第二个值表示距离观察者多远处画面大小比例为1（1个像素代表1cm）（可以理解为缩放或视角大小）

        对透视渲染有所了解的人就会知道，近大远小，当距离为0时，画面会无限大，这是不可能的，因此当第二个值为```0```时，就是正交投影，此时第一个值为画面大小比例（多少像素代表1cm）

        推荐透视模拟6米毯时，```d=(600,450)```，4米毯时，```d=(600,550)```

        为了便于理解，我讲一讲小鸟飞飞官方软件模拟所涉及的参数。官方的三维模拟涉及了三个可由用户调整的参数，分别是方位角、俯仰角和距离。

        上述模拟都会跳出一个窗口，窗口可由键盘控制

        二维模拟时，按空格暂停或继续，长按q后退，长按e前进，按esc退出

        三维模拟时，长按空格暂停，长按q后退，长按e前进，按esc退出，在暂停时，可以通过按w,a,s,d转动视角，此时需要按esc退出暂停状态

        在三维模拟的窗口中，```imshow```的两个参数会显示在画面左上角

        此外，如果在上述模拟的参数不变的前提下，加入```save,FPS```参数，就会生成视频，此时不会跳出窗口

        ```python
        pf.show(data,t0,music,feild,save='test',FPS=25)
        # skin默认值为1，可不写
        ```
        这就是生成二维模拟的视频的方法，输出的视频为```test.mp4```，25帧/秒

        三维视频以次类推

         ```python
        pf.show(data,t0,music,feild,save='test',FPS=25,ThreeD=True,imshow=[120,-15],d=(1,0))
        # 正交
        pf.show(data,t0,music,feild,save='test',FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))
        # 透视
        ```

        例外，

        全景模式不能跳出窗口，只能生成视频，这里需要```ThreeD,save,FPS,track```四个参数
        ```python
        pf.show(data,t0,music,feild,ThreeD=True,save='test',FPS=20,track=[0])
        # 无人机1的视角全景
        pf.show(data,t0,music,feild,ThreeD=True,save='test',FPS=20,track=(280,280,165))
        # (280,280,165)为中心的视角全景
        ```

        ```track```有两种使用法，
        
        当它为长度为1的列表```[n]```时，表示以第n+1架无人机的视角生成全景视频

        当它为元组```(x,y,z)```时，表示以(x,y,z)为中心的视角生成全景视频

        原理是用openCV渲染图像，pygame播放音乐，生成视频时，用openCV生成视频，之后用FFmpeg将背景音乐加到视频中

        在渲染过程中，pyfii会计算两架无人机之间在xy平面上投影的距离，以51cm、34cm和17cm为界，分别对应官方模拟中的轻微警告、一般警告和严重警告

        注意：模拟是理想状态，一切以实际为准

4. pyfii编程

    pyfii编程主要涉及了```drone```和```Fii```两个类

    1. ```drone```类
        ```python
        d1=pf.Drone(x,y,config)
        ```
        新建一架无人机```d1```，起飞位置(x,y)
        
        ```config```是一个字典，记录了无人机的参数

        pyfii内置的```config```有两种，一种是```pf.drone_config_6m```，另一种是```pf.drone_config_4m```，分别对应F400飞6米毯和4米毯

        ```python
        drone_config_6m={
            'xyRange':(0,560), # xy坐标范围，单位cm
            'zRange':(80,250), # z坐标范围，单位cm
            'velRange':(20,200), # 速度范围，单位cm/s
            'accRange':(50,400), # 加速度范围，单位cm/s^2
            'ArateRange':(5,60), # 角速度范围，单位°/s
        }

        drone_config_4m={
            'xyRange':(0,360),
            'zRange':(80,250),
            'velRange':(20,200),
            'accRange':(50,400),
            'ArateRange':(5,60),
        }
        ```

        上述参数可以修改，比方说你想让最大速度更大一点，你可以

        ```python
        d1.config['velRange']=(20,250)
        ```

        这样做存在一定危险，但实践已经证明了，F400可以飞到300cm的高度
        
        对此，可以对于超出小鸟飞飞官方程序所设定的参数范围进行一定尝试

        此时，实际飞行显得尤为重要，虽然F400飞到了300cm，但在比赛时，它吸上了上层防护网，造成了失分

        不过，通过合理地扩大参数范围，可以使你在创造时有更大的发挥空间，做到官方软件所做不到的动作，在比赛中脱颖而出

        ```python
        d1.X=100
        d1.Y=100
        ```

        修改起飞位置至(100,100)

        ```python
        d1.takeoff(1,100)
        ```

        1秒时，起飞，高度100cm

        ```python
        d1.inittime(4)
        d1.VelXY(200,400)
        d1.VelZ(200,400)
        d1.move2(250,250,250)

        d1.end()
        ```

        在第4秒

        水平速度200cm/s

        水平加速度400cm/s

        竖直速度200cm/s

        竖直加速度400cm/s

        直线移动至(250,250,250)

        ```python
        d1.inittime(7）
        d1.land()
        ```

        在第7秒

        降落

        ```python
        d1.end()
        ```

        结束
        
        以上是一个示例，下文将介绍```drone```类pyfii1.1.1中的所有模块

        ```python
        d1.takeoff(1,100)
        # 第一个值是起飞时间，第二个值是起飞高度，必须等待1秒后再起飞

        d1.inittime(t)
        # 在第几秒

        d1.move(x,y,z)
        # 移动距离(x,y,z)

        d1.move2(x,y,z)
        # 直线移动至(x,y,z)

        d1.delay(t)
        # 等待几毫秒

        d1.VelXY(v,a)
        # 速度加速度为多少

        d1.AccXY(a)
        # 加速度为多少

        d1.ARate(w)
        # 角速度（角速度）

        d1.Yaw(a)
        # 转动（角度）正逆负顺

        d1.Yaw2(a)
        # 转向（角度）正逆负顺

        d1.land()
        # 降落

        d1.end()
        # 结束时必加
        ```

        以上动作支持pyfii模拟飞行，此外由于未对其运动轨迹进行研究，有部分动作不支持pyfii中的模拟飞行，但会保存在```.fii```中

        ```python
        d1.VelZ(v,a)
        # 竖直速度（速度,加速度）

        d1.AccZ(a)
        # 竖直加速度（加速度）

        d1.nod(direction,distance)
        # 点头 沿 direction 方向急速平移 distance cm

        d1.SimpleHarmonic2(direction,amplitude)
        # 波浪运动 沿 direction 方向以整幅 amplitude cm 运动

        d1.RoundInAir(startpos,centerpos,height,vilocity)
        # 绕圈飞行 起点 startpos 圆心 centerpos 高度 height 速度 vilocity(正逆时针,负顺时针)

        d1.TurnOnSingle(Id,color)
        # 点亮某一盏灯，颜色

        d1.TurnOffSingle(Id)
        # 熄灭某一盏灯

        d1.TurnOnAll(colors)
        # 点亮所有灯，颜色

        d1.TurnOffAll()
        # 熄灭所有灯

        d1.BlinkSingle(Id,color)
        # 闪烁某一盏灯，颜色

        d1.Breath(color)
        # 呼吸灯，颜色

        d1.BlinkFastAll(colors)
        # 快速闪烁所有灯(颜色)

        d1.BlinkSlowAll(colors)
        # 慢速闪烁所有灯(颜色)

        d1.HorseRace(colors)
        # 走马灯(颜色)
        ```
        pyfii 1.5.0及后续版本中加入了灯光模拟支持，但是只支持显示点灯和灭灯，不支持闪烁和走马灯，如果12个灯颜色不一致，模拟视频会显示第一个灯的颜色

        在编写移动时，建议使用```d1.move2(x,y,z)```，如果想要使用```d1.move(x,y,z)```，可以使用```d1.move2(d1.x+x,d1.y+y,d1.z+z)```代替

        ```d1.outputString```表示写入```webCodeAll.xml```的内容

        ```d1.outpy```表示写入```pyfiiCode.py```的内容

    2. ```Fii```类

        ```python
        F=pf.Fii(name,drones,music)
        ```

        ```name```为字符串，即文件名

        ```drones```为一个列表，列表里每一个元素都是```drone```类

        ```Fii```类的功能是整合多个```drone```类

        ```music```是一个字符串，是音乐的文件名，如```"xxx.mp3"```，如果不写```music```就是没音乐

        ```python
        F.save(feild=4)
        ```

        这就是储存文件

        ```feild```为地毯大小

        在这里面，
        
        ```inFii```参数为脚本模式使用

        ```addlights```功能是覆写灯光

        如

        ```python
        F.save(addlights=True,feild=6)
        ```

        此时，pyfii会删去原来的灯光，覆写上新的

        具体原理是读入脚本模式的脚本，删去原来的灯光，写入新的灯光，运行脚本，完成覆写

    3. DroneAction类和LightAction类

        在解释DroneAction类和LightAction类的原理之前，你可能需要一些关于回调函数(callback)的知识

        你可以查看[tests/class_callback_test.py](../../tests/class_callback_test.py)来了解回调函数的行为

        使用回调函数，是为了延迟函数或方法的执行。可以实现写一段代码（即回调函数），但不立即执行，之后可以对回调函数进行重新排序，在需要的时间被调用。

        为了实现独立编写灯光和动作的目的，`Drone`对象有`action_list`和`light_actions`两个属性，用来记录动作和灯光的回调函数，为了能在时间轴上对齐动作和灯光，封装了`DroneAction`类和`LightAction`类，引入`timestamp`并将其与回调函数打包在一起，为了协调动作和灯光的前后顺序，在`LightAction`类中加入了`order`属性

        在d`rone.end()`操作之后，`Drone`类会使用`timestamp`和`order`属性对齐动作和灯光，这时调用封装在动作类和灯光类里的回调函数，`Drone`类才真正开始处理输出到`webCodeAll.xml`和`pyfiiCode.py`里的字符串，即将pyfii代码转化为fii工程文件

        实际情况还要复杂一些。实际上，无人机的动作方法在被调用的时候没有立即将pyfii代码转为fii工程文件，而是将其作为回调函数封装到`DroneAction`中，但是修改无人机坐标的操作却立即执行了，因为在pyfii编程过程中，有些时候想要知道无人机当前的位置来进行相对移动。

        以上叙述可能理解起来比较复杂，这里举个例子：

        ```python
        # Drone类中
            def move2(self, x, y, z, timestamp=None):
                # 代码段 1
                x,y,z=int(x+0.5),int(y+0.5),int(z+0.5)
                if self.outRange(x,'xyRange') or self.outRange(y,'xyRange') or self.outRange(z,'zRange'):   # 超出范围提醒
                    raise Warning("Out of range.超出范围。")
                self.x, self.y, self.z = x, y, z
                # 代码段 1 结束
                def move2_callback(self, x, y, z):
                    # 代码段 2
                    x,y,z=int(x+0.5),int(y+0.5),int(z+0.5)
                    self.x, self.y, self.z = x, y, z
                    # 代码段 2 结束
                    # 代码段 3
                    spaces='  '*(self.space+self.block)
                    if self.inT:
                        self.outputString += spaces+'''<next>
            '''
                        self.block+=1
                        spaces+='  '
                    self.outputString += spaces+'''<block type="Goertek_MoveToCoord">
        '''+spaces+'''  <field name="X">'''+str(x)+'''</field>
        '''+spaces+'''  <field name="Y">'''+str(y)+'''</field>
        '''+spaces+'''  <field name="Z">'''+str(z)+'''</field>
        '''
                    self.block+=1
                    self.inT=True
                    self.outpy+='''move2('''+str(x)+''','''+str(y)+''','''+str(z)+''')
        '''
                    # 代码段 3 结束
                self.append_action(DroneAction(move2_callback, [self, x,y,z], timestamp))   # 将动作添加到动作列表里去

        ```
        示例代码是移动无人机到特定位置的代码，代码段1计算了无人机位置（`self.x, self.y, self.z`储存无人机当前位置），同时给出超出范围提醒。代码段23在`move2_callback`这个回调函数当中，代码段2又重复了一遍代码段1的操作，但是没有超出范围提醒，因为在合并动作和灯光时，会将无人机放回起始位置，之后重复一遍位置计算，这是因为第一次位置计算用来方便用户调取d`rone.x，drone.y, drone.z`的位置信息，第二次位置计算用来生成fii工程。

        代码段3主要修改了`self.outputString`和`self.outpy`，这两个变量分别写入到`webCodeAll.xml`和`pyfiiCode.py`中，`self.inT`和`self.block`主要来满足xml文件的格式要求。

        最后一行代码创建了一个`DroneAction`对象，其定义如下：

        ```python
        DroneAction(self, action_callback, parameter, timestamp)
        ```

        这是`DroneActon`的构造函数，`action_callback`是无人机动作回调函数，`parameter`是回调函数的参数，`timestamp`是时间戳。

        可见最后一段代码创建了一个无人机动作并将其添加到无人机动作列表里。

        观察`Drone`类的无人机动作方法，大致如下：

        ```python

        def action(self, ..., timestamp):
            # 首先计算位置

            # 再输出提示信息

            def action_callback(self, ...):
                # 相同的计算位置

                # 但是没有提示信息

                # 在fii工程文件变量里添加动作对应的字符串
            
            self.append_action(DroneAction(action_callback, [self, ...], timestamp))
            # 把动作添加到无人机动作列表

        ```

        灯光的原理也类似，只不过没有计算位置这一步。但是灯光没有填`timestamp`参数时是按序执行的，因此如果不分开编写，灯光方法其实等同于动作，只有分开编写时，灯光才会放到`drone.light_actions`字典里。

        使用字典存储灯光动作使查询的时间复杂度为O(1)，字典的键是`timestamp`和`order`共同组成的，字典的值是这个`timestamp`和`order`对应的灯光动作，之后将动作的`timestamp`分别加上`before`和`after`在字典中查询是否有灯光就行了。

        `drone.end`方法就是这样查找一个动作有没有和其对应的灯光，并拼接为正确的顺序。
