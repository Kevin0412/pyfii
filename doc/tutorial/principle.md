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
    
    ```test.fii```文件记录的是工程级元数据。按当前源码实现，pyfii在导出时会写入无人机型号、地毯尺寸、音乐名、动作组列表、每架无人机的动作组名、UAVID、起飞位置以及控制时间标记；读入时则主要解析```MusicName```、```Actions```、```AreaL```、```DeviceType```和各动作组起飞坐标等信息。

    ```checksums.xml```文件在当前pyfii实现中会为每个动作组写入一个```CheckSums```节点，用来补全工程结构；但仓库内暂未看到进一步消费这个文件的解析逻辑，因此更适合把它理解为工程打包所需的配套元数据，而不是仿真核心输入。

    ```xxx.mp3```就是你的音乐，渲染预览时由pygame加载，导出视频后再由FFmpeg混流到mp4中。

    ```webCodeAll.xml```是单机动作的核心表示。pyfii并不是先生成python再转xml，而是由```Drone```类的方法直接拼接```Goertek_*```和```block_*```节点，形成块状XML程序。

    ```pyfiiCode.py```是脚本模式下的等价python表示。它和```webCodeAll.xml```是并行生成的：前者便于回放、覆写和二次编辑，后者才是fii工程中的主动作描述。

    ```offlineExcuteScript.py```与pyfii当前源码主链路没有直接耦合；从仓库现状看，它更像是官方软件上传或离线执行阶段生成的中间脚本。

    ```.ls```文件同样不在pyfii当前实现的生成与解析范围内，更可能属于官方工具链面向设备下发的产物。

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
        data,t0,music,field=pf.read_fii(name,getfield=True,fps=200)
        ```

        这一模块实现了读入小鸟飞飞文件并输出飞行轨迹的功能

        其中

        ```fps```是能够生成视频的最大帧率，动作采样率，值越小，运行速度越快

        ```name```是```.fii```文件所在的文件夹

        ```data```是一个列表，列表的长度是无人机数，每一个元素也是列表

        ```data[n]```列表储存了第n+1架无人机飞行轨迹及旋转数据，每一个元素是长度为6的元组

        ```python
        data=[
            [(time,x,y,z,degree,(R,G,B)),(time,x,y,z,degree,(R,G,B)),...],
            [(time,x,y,z,degree,(R,G,B)),(time,x,y,z,degree,(R,G,B)),...],
            ...
        ]
        # time单位为ms，每隔5ms一个动作数据采样
        # x,y,z单位为cm
        # degree单位为°
        # (R,G,B)表示颜色，如果值为-1则表示不亮
        ```
        
        ```t0```表示模拟结束的帧数（即动作时长```t0/fps```秒）

        ```music```表示音乐，数据类型为列表，长度为1或2，元素的数据类型为字符串

        ```python
        music=[musicdir,musicname] # musicname不需要后缀
        
        music=[musicname] # musicname为音乐的路径及名称，包括后缀
        ```

        ```field```表示地毯大小，```4```表示4米毯，```6```表示6米毯

        如果目标是复刻这个库，那么`read.py`这一层应该理解为“从块状XML到统一时序IR，再到离散轨迹”的执行器，而不是普通读文件工具。

        一个可复刻的最小设计可以拆成四步：

        1. 工程发现：`read_fii()`先遍历目录找到顶层`.fii`，读取其中的`MusicName`、`Actions`、`AreaL`、`DeviceType`和每个动作组的起飞坐标。

        2. 单机程序读取：对每个动作组读取`webCodeAll.xml`，并先用`read_xml_points()`预扫所有`Goertek_Point`命名点，构造点名到三维坐标的字典。

        3. 指令编译：`read_xml()`把XML文本按行拆开，只保留去掉前导缩进后的块描述，同时记录每一行的缩进层级。之后不走通用XML解析器，而是用“扫描当前块类型 + 按固定偏移读取后续field”的办法识别指令，并编译成统一事件列表`dots`。

        4. 轨迹求值：`dots2angle()`、`dots2led()`、`dots2line()`分别把`dots`解释为姿态、灯光和位移序列，最后合并成仿真输出。不同无人机互不依赖，`read_fii()`默认按`min(CPU核心数, 无人机数)`启用进程池并行求值；传`workers=1`可恢复串行，传正整数可指定上限。

        从实现角度看，`dots`就是这个库最核心的中间表示。它不是抽象语法树，而是已经带执行语义的时间轴事件流，例如：

        ```python
        [time, x, y, z, vel, acc, "move2"]
        [time, dx, dy, dz, vel, acc, "move"]
        [time, angle, w, "turn"]
        [time, angle, w, "turn2"]
        [time, color, "TurnOnAllSingleColor"]
        [time, "land"]
        ```

        如果按“xml格式的api封装 / 代码转译 / xml编译器”来拆分，这里的技术路径其实分成三层：

        1. API封装层：`Drone`把`takeoff`、`move2`、`VelXY`、`Yaw2`、`TurnOnAll`等动作封装成Python方法，对外暴露的是类型化、带边界检查的编程接口。

        2. 转译层：这些方法调用时不会立刻写文件，而是把动作封装成`DroneAction`/`LightAction`回调，等到`drone.end()`时统一执行，生成`outputString`与`outpy`两份中间结果。前者是块状XML程序，后者是线性Python脚本。

        3. “编译”层：`read_xml()`再反向把块状XML扫描成统一的事件表示`dots`。从编译器视角看，`dots`就相当于一个更接近执行语义的IR，后续的`dots2line`、`dots2angle`、`dots2led`则分别把它编译到位置、姿态和灯光三条时间序列上。

        `read_xml()`本身的关键不是语法，而是状态维护。它在单次扫描中持续维护`time, x, y, z, vel, acc, w, points`这几个运行时状态：

        - `block_inittime`直接把时间光标跳到绝对时刻。
        - `block_delay`把时间光标向后推进。
        - `Goertek_HorizontalSpeed`和`Goertek_AngularVelocity`更新后续动作默认使用的速度参数。
        - `Goertek_MoveToCoord`和`Goertek_Move`把当前位置变化编译成位移事件。
        - `Goertek_Point` / `Goertek_MoveToPoint`把命名点解析成坐标跳转。
        - `controls_repeat`通过缩进层级截出子程序文本，再递归调用`read_xml()`展开循环体。

        因而它更像一个单遍解释器：边扫描、边更新运行时状态、边发出IR事件，而不是先建树再执行。

        不过，如果要做新一代实现，我更推荐另一条编译路线：先把XML解析成树，再用DFS访问语法树。当前版本依赖“块类型后面第几行就是哪个field”的文本偏移规则，写起来快，但对格式变化比较脆弱；而DFS路线可以把`next`、`statement`、`controls_repeat`这些嵌套结构显式建成树节点，再在遍历过程中维护同样的运行时状态`time/x/y/z/vel/acc/w/points`。这样做的好处是：

        1. 结构更稳，不依赖缩进和行号偏移；
        2. 更容易支持新块类型；
        3. 更适合把“编译XML到dots IR”单独做成一个清晰模块；
        4. 循环、条件、嵌套statement在语义上更容易解释清楚。

        也就是说，当前仓库的`read.py`适合学习“最小可用实现”，而如果目标是复刻并长期维护，建议把它重写成“XML树 → DFS遍历 → dots IR”的编译器。

        真正难复刻的是`dots2line()`，因为它内部写了一个离散时间状态机。可以把它理解成“取当前有效移动事件 → 生成一段局部运动计划 → 逐帧执行 → 随时检查是否被下一条指令打断”。

        这套状态机至少有四层状态：

        1. 指令选择状态：通过遍历`dots`找到“当前时间之前最后一条生效的 move/move2/land/moved 指令”，其索引存入`k`。

        2. 动作类型状态：把当前指令解释成绝对移动`move2`、相对移动`move`、降落`land`或空动作`moved`，统一得到位移向量`(X,Y,Z)`。

        3. 速度曲线状态：若位移长度为`R`，则计算加速距离`s=v^2/(2a)`。若`R >= 2s`，使用“加速-匀速-减速”的梯形速度曲线；否则使用“加速-减速”的三角速度曲线。

        4. 帧推进状态：按`1000/fps`毫秒推进，每帧根据所处阶段计算当前位置`r`、速度`v`和加速度向量，并写入`lines`。

        也就是说，这里不是解析完后一次性解出闭式轨迹，而是逐帧仿真。这样做的直接好处是：旋转、灯光、视频导出都能共享同一个采样频率。

        pyfii计算飞行轨迹时，将运动过程近似为：先由静止开始做加速度与速度方向相同的匀加速直线运动，再做匀速直线运动，然后做加速度与速度方向相反的匀加速直线运动，最后静止。

        从运动学实现上看，`dots2line()`对每一段位移都会先计算总位移长度`R`、给定速度`vel`和加速度`acc`下的加速距离`s=v^2/(2a)`，再判断这段动作是“梯形速度曲线”还是“达不到峰值速度的三角速度曲线”。随后按采样频率`fps`逐帧积分，得到每个时刻的`(x,y,z)`，并同时给出当前加速度向量，这个加速度向量后面会被3D渲染拿去近似机体倾斜姿态。

        如果在一半位移处未到达最高速度，则直接开始减速。

        对于无人机未到达目标点时有新的移动指令时，状态机会进入源码里的`slow=True`分支：先以固定最大减速度（有加速度模型时取400cm/s^2）把当前速度刹到0，再从当前刹停点重新接下一条指令。因此它不是“硬切换目标点”，而是“先刹车再重规划”，这也是文档里所谓“动作未完成”的真实实现含义。

        对于速度加速度未定义的情况，`read_xml()`会写入默认值：水平速度60cm/s、水平加速度100cm/s^2、角速度60°/s，并追加warning。这意味着默认值是在编译XML到IR时注入的，不是在渲染层补的。

        对于旋转与移动的耦合，当前实现是解耦处理的：平移由```dots2line```生成，朝向由```dots2angle```按角速度单独积分，灯光由```dots2led```独立采样，最后在统一时间轴上按索引合并。因此当前仿真没有建模角加速度，也没有让姿态反作用于位移。

        `dots2angle()`也使用了一个简化状态机：它总是取当前生效的转向事件，如果是`turn`就解释成相对旋转，如果是`turn2`就解释成绝对朝向；随后以`w/fps`的角步长逐帧逼近目标角。为了避免跨越0/360度时走远路，它会先把当前角和目标角调整到最近角距离。

        `dots2led()`则最简单：它只维护“当前灯光颜色”这一个状态，并在时间轴上遇到开灯/关灯事件时更新状态，再逐帧复制到输出序列。

        `ignore_acc=True`模式也不是另一套算法，而是把加速度近似设为一个极大值`2**512`，从而退化成几乎瞬时达到巡航速度的运动模型。换句话说，它通过参数极限而不是分支重写，复用了同一套状态机。

        对于进阶动作，pyfii不会模拟；在当前结构里，它们可以被成功导出到XML，但不会进入这套位移/角度/灯光求值器。

        对于水平和竖直速度加速度，pyfii模拟时只认水平速度加速度，建议在编程时，水平和竖直速度加速度相统一，避免模拟误差。

    2. 渲染

        ```python
        show(data,t0,music,field=6,device="F400",show=True,save="",FPS=200,max_fps=200,ThreeD=False,imshow=[120,-15],d=(600,450),track=[],skin=1,workers=None)
        ```

        这里参数比较多，需要一一介绍

        ```data,t0,music,field```这四个在上文介绍过了，这里不多赘述

        ```max_fps```需要与上文```read_fii()```中的```fps```一致，否则视频速率会不正常

        ```show=False```时，直接打印是否存在距离过近的情况，没有图像渲染

        ```python
        pf.show(data,t0,music,field,show=False,max_fps=200)
        ```

        ```show==True```时，要分类讨论，```show```默认为```True```，不用写

        二维模拟：

        二维模拟时，需要的参数有```skin```，因为只有二维模拟时有皮肤

        ```python
        pf.show(data,t0,music,field,max_fps=200,skin=1)
        #有0,1,2三种皮肤
        ```

        三维模拟：

        三维模拟时，需要的参数有```ThreeD,imshow,d```

        ```python
        pf.show(data,t0,music,field,max_fps=200,ThreeD=True,imshow=[120,-15],d=(1,0))
        # 正交
        pf.show(data,t0,music,field,max_fps=200,ThreeD=True,imshow=[90,0],d=(600,450))
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

        视频导出默认按`min(CPU核心数, 输出帧数)`并行绘制帧，仍由主线程按时间顺序写入`VideoWriter`，因此不会打乱视频。`workers=1`可关闭并行，正整数可指定线程数。

        ```python
        pf.show(data,t0,music,field,max_fps=200,save='test',FPS=25)
        # skin默认值为1，可不写
        ```
        这就是生成二维模拟的视频的方法，输出的视频为```test.mp4```，25帧/秒

        三维视频以次类推

         ```python
        pf.show(data,t0,music,field,max_fps=200,save='test',FPS=25,ThreeD=True,imshow=[120,-15],d=(1,0))
        # 正交
        pf.show(data,t0,music,field,max_fps=200,save='test',FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))
        # 透视
        ```

        例外，

        全景模式不能跳出窗口，只能生成视频，这里需要```ThreeD,save,FPS,track```四个参数
        ```python
        pf.show(data,t0,music,field,max_fps=200,ThreeD=True,save='test',FPS=20,track=[0])
        # 无人机1的视角全景
        pf.show(data,t0,music,field,max_fps=200,ThreeD=True,save='test',FPS=20,track=(280,280,165))
        # (280,280,165)为中心的视角全景
        ```

        ```track```有两种使用法，
        
        当它为长度为1的列表```[n]```时，表示以第n+1架无人机的视角生成全景视频

        当它为元组```(x,y,z)```时，表示以(x,y,z)为中心的视角生成全景视频

        原理是用OpenCV完成2D/视频帧绘制，pygame负责预览时的音乐同步播放，导出视频时先由OpenCV写入无声```*_process.mp4```，再用FFmpeg把背景音乐混流成最终mp4。2D渲染会分别绘制俯视、正视、侧视三视图；3D渲染则调用```cv3d```里的投影器，把三维对象列表投到二维画面。

        `show()`本身的核心并不复杂，本质上就是“一个时钟驱动的离散帧渲染器”：维护当前帧索引`k`，把它映射到`data[a][k]`这类采样结果上，再根据当前时间渲染一帧。源码里实时预览模式直接取

        ```python
        k = int((time.time() - time_read) * max_fps)
        ```

        所以它本质上是“墙上时钟驱动采样索引”；而视频导出模式改为维护一个累加器`K`，每渲染一帧就执行

        ```python
        K += max_fps / FPS
        k = int(K + 0.5)
        ```

        也就是按固定步长从高采样率轨迹中抽帧。因此`show()`并不负责物理计算，它只负责按统一时间轴消费前面已经算好的轨迹、姿态和灯光序列。

        图形学实现也分成两层，但如果目标是复刻整个库，优先级其实是：先复刻2D和碰撞告警，再决定是否补3D；`cv3d`不是最核心依赖。

        1. 视图层：`show.py`负责决定画什么。二维情况下，它把同一架无人机投到三个正交视图；三维情况下，它先把无人机拆成球、线、圆环等几何元，并附带文字、坐标轴、地毯边框和告警标记。

        2. 投影层：`cv3d/transfer.py`提供坐标变换，`cv3d/IIID.py`把三维点旋转到观察坐标系后做正交或透视投影，再按深度排序渲染。`d=(1,0)`表示正交投影，`d=(600,450)`这类参数表示观察者距离和透视缩放基准。

        如果直接顺着源码看，这套3D渲染最好理解成“轨迹驱动的几何元投影器”，而不是完整的网格渲染器。

        1. `show.py`先从`data[a][k]`取出某一帧的无人机位置、偏航角、灯光和加速度。
        2. `drone3d()`再把一架无人机拆成4个桨环、2根连杆和1个中心球，加入`aixs`对象列表。
        3. `iiid_rotate()`根据当前加速度和重力方向构造机体倾斜矩阵，把这些局部几何元旋到世界坐标里。
        4. `IIID.show()`对对象列表按深度排序，再逐个调用`sphere()`、`line()`、`ring()`画到OpenCV图像上。圆环不会再用固定方向的二维椭圆近似，而是根据法向量构造圆环平面正交基，采样真实三维圆周后逐点投影，因此正交、透视和全景模式都支持任意朝向。

        所以这里真正被渲染的从来不是“无人机网格模型”，而是`[(几何参数...), "line"|"ring"|"sphere"|"text"]`这种对象列表。也正因如此，pyfii的3D部分非常容易复刻：你只要能重新生成同样的几何元，再实现一套等价的投影器，视觉结果就能基本对齐。

        如果只看复刻所需的实现细节，`cv3d`最重要的不是“画得多漂亮”，而是它的数据流非常简单：输入是`[(几何参数...), "line"|"ring"|"sphere"|"text"]`这种对象列表；核心步骤是坐标平移到观察中心、按观察角旋转、做正交/透视投影、按深度排序、最后调用OpenCV基本图元绘制。

        `IIID.py`里的`iiid2iid()`就是投影核心。设世界点为

        ```math
        p=(X,Y,Z)
        ```

        观察中心为

        ```math
        c=(c_x,c_y,c_z)
        ```

        那么先做平移

        ```math
        p_0=p-c=(X-c_x,Y-c_y,Z-c_z)
        ```

        当前实现没有直接写一个3×3总旋转矩阵，而是调用`rotate3d()`顺序做两次二维旋转：

        1. 先在`xy`平面绕`z`轴转方位角`a`；
        2. 再在`xz`平面绕`y`轴转俯仰角`b`。

        若记二维旋转矩阵为

        ```math
        R(\theta)=
        \begin{bmatrix}
        \cos\theta & -\sin\theta\\
        \sin\theta & \cos\theta
        \end{bmatrix}
        ```

        那么这一步等价于：

        ```math
        \begin{aligned}
        \begin{bmatrix}x_1\\y_1\end{bmatrix}&=R(-a)\begin{bmatrix}X-c_x\\Y-c_y\end{bmatrix} \\
        \begin{bmatrix}x_2\\z_2\end{bmatrix}&=R(-b)\begin{bmatrix}x_1\\Z-c_z\end{bmatrix}
        \end{aligned}
        ```

        最终观察坐标系中的点为

        ```math
        p'=(x_2,y_1,z_2)
        ```

        然后才进入投影。

        正交投影时，源码分支`d[1]==0`对应的就是

        ```math
        u = x_{screen} - y_1\,s
        ```
        ```math
        v = y_{screen} - z_2\,s
        ```
        ```math
        depth = x_2
        ```

        其中`s=d[0]`表示比例尺。可以看出它把观察方向当作新的`x`轴，屏幕平面取观察坐标系的`yz`平面。

        透视投影时，源码使用

        ```math
        u = x_{screen} - \frac{y_1 f}{x_2+d_0}
        ```
        ```math
        v = y_{screen} - \frac{z_2 f}{x_2+d_0}
        ```
        ```math
        depth = x_2+d_0
        ```

        其中`d_0=d[0]`可理解为观察者离观察中心的距离，`f=d[1]`可理解为焦距或“距离观察者多远处比例为1”的缩放基准。这正是最基础的小孔成像公式：横纵坐标都按`1/depth`缩放，所以近大远小。

        函数第三个返回值不是屏幕坐标，而是“相对观察者深度”，专门给排序用。`IIID.py`没有做真正的隐藏面消除，而是采用画家算法：对线、球、环按深度从远到近排序后依次绘制。对于这个项目的几何复杂度，这已经够用，而且实现成本远低于Z-buffer。

        如果继续往`cv3d`源码里深挖，会发现它的很多视觉效果其实都能直接落到简单公式上。

        1. `eye_vector(a,b)`给出观察方向单位向量：

        ```math
        e=(\cos a\cos b,\;\sin a\cos b,\;\sin b)
        ```

        2. `eye_axis(a,b,d_0)`给出观察者相对观察中心的位置：

        ```math
        o=-d_0 e
        ```

        这两个量主要被`ring()`用来判断一个圆环在当前视角下应该压扁成多扁的椭圆。

        对正交投影，`ring()`直接计算圆环法向量`n`与视线方向`e`的夹角余弦：

        ```math
        ratio = \left|\frac{e\cdot n}{\|n\|}\right|
        ```

        然后把圆环画成半长轴为`r`、半短轴为`r\cdot ratio`的椭圆。直觉上看：如果法向量正对观察者，`ratio\approx1`，看到的是圆；如果法向量几乎与视线垂直，`ratio\approx0`，看到的就是一条被压扁的线。

        对透视投影，`ring()`先算观察者到圆心的视线向量

        ```math
        v = p' - o
        ```

        然后改用

        ```math
        ratio = \left|\frac{v\cdot n}{\|v\|\|n\|}\right|
        ```

        并把整个椭圆半径再按透视比例乘上

        ```math
        \frac{f}{depth}
        ```

        所以源码里圆环的显示半径本质上是

        ```math
        r_{screen}=r\cdot\frac{f}{depth}
        ```

        而短轴还要再乘一个视角压缩系数`ratio`。这就是为什么桨环在不同视角下既会缩放，又会从圆逐渐变成扁椭圆。

        `sphere()`和`line()`则更直接：球体半径只是在透视模式下按`r\cdot f/depth`缩放，线段则把两个端点分别投影后直接连线。因此`cv3d`其实没有“曲面渲染”，只有“点/线/圆环”三种基础图元的屏幕映射。

        `IIID2.py`对应的是全景渲染路线。它先把空间点转成球坐标`(a,b,r)`，其中方向角`a`和仰角`b`来自`polar3d()`。接着直接把角度摊平成图像坐标：

        ```math
        u = \frac{(-a+180)\bmod 360}{360}\,W
        ```
        ```math
        v = \frac{-b+90}{180}\,H
        ```

        其中`W,H`是全景图宽高。这本质上就是一张等矩形投影图：横轴对应`360°`方位角，纵轴对应`180°`俯仰角。

        `IIID2.py`里还有一个很关键的工程细节：如果一条线段投影后跨越了全景图左右边界，源码会判断两端横坐标差是否大于半张图宽；如果是，就拆成两段，分别画在左右两边。这样才能避免一条本来穿过`±180°`边界的短线，被错误地画成“绕整张全景图一大圈”的长线。

        如果要补一点IIID相关的三维图形学基础，可以把它理解成以下四个初等步骤：世界坐标系选点 -> 以观察中心做平移 -> 按方位角/俯仰角旋转到相机坐标系 -> 用正交或透视公式投影到二维。这里没有矩阵库、没有光照、没有网格、没有面片裁剪，本质上就是“几何变换 + 深度排序 + OpenCV画图元”。这也是为什么它很适合教学和轻量仿真。

        另外，当前无人机3D姿态并不是独立的飞控仿真结果，而是由当前加速度向量与重力向量合成“桨盘受力方向”，再据此构造旋转矩阵，把四个桨环和机身连杆倾斜出来，所以它更像一种基于动力学直觉的可视化近似，而不是严格刚体动力学解算。

        设轨迹求值器给出的加速度向量为

        ```math
        a=(a_x,a_y,a_z)
        ```

        重力向量固定为

        ```math
        g=(0,0,-980)
        ```

        那么源码先构造“桨盘受力方向”

        ```math
        f=a-g
        ```

        再单位化为

        ```math
        \hat f=(x,y,z)=\frac{f}{\|f\|}
        ```

        然后直接写出一个旋转矩阵

        ```math
        M=
        \begin{bmatrix}
        \frac{x^2z+y^2}{x^2+y^2} & -\frac{xy}{z+1} & x\\
        -\frac{xy}{z+1} & \frac{x^2+y^2z}{x^2+y^2} & y\\
        -x & -y & z
        \end{bmatrix}
        ```

        当`x=y=0`时退化为单位阵。这个矩阵的用途不是做通用姿态解算，而是把机体局部坐标下的四个桨环偏移向量

        ```math
        r_i=(R\cos\theta_i,R\sin\theta_i,0)
        ```

        变成世界坐标中的倾斜位置

        ```math
        r_i'=Mr_i
        ```

        再平移到无人机中心`(x,y,z)`附近。于是机体会沿“需要提供升力的方向”倾斜，看起来像是在为当前加速度服务。

        如果从更一般的三维图形学角度看，当前实现其实只用了“旋转矩阵的一种特殊构造”。一个更完整的姿态系统通常会显式维护旋转矩阵、欧拉角或四元数。

        1. 旋转矩阵：最直接，适合把局部坐标系中的点、向量、法向量统一变换到世界坐标系。优点是作用在线性代数上最自然，缺点是长期数值积分时容易失去正交性，需要重正交化。

        2. 欧拉角：把姿态拆成三个依次执行的旋转，例如 yaw-pitch-roll。它直观、便于UI输入，也方便和“方位角/俯仰角”这种当前接口对接。但欧拉角依赖旋转顺序，而且会遇到万向节锁：当中间角接近`±90°`时，两个旋转轴会重合，导致自由度退化。

        若写成矩阵乘积，常见yaw-pitch-roll可表示为

        ```math
        R = R_z(\psi)R_y(\theta)R_x(\phi)
        ```

        这里`\psi,\theta,\phi`分别是偏航、俯仰、滚转。

        3. 四元数：更适合做连续姿态插值、姿态积分和避免万向节锁。单位四元数通常写成

        ```math
        q = w + xi + yj + zk
        ```

        或向量形式

        ```math
        q=(w,x,y,z),\quad w^2+x^2+y^2+z^2=1
        ```

        若绕单位轴`n=(n_x,n_y,n_z)`旋转角度`\theta`，对应的单位四元数为

        ```math
        q=\left(\cos\frac{\theta}{2},\;n_x\sin\frac{\theta}{2},\;n_y\sin\frac{\theta}{2},\;n_z\sin\frac{\theta}{2}\right)
        ```

        四元数特别适合把多个旋转复合、做SLERP插值，再在最后一步转换为旋转矩阵去画图。因此如果未来要把pyfii的3D姿态从“加速度驱动的可视化近似”升级成“稳定的刚体姿态系统”，推荐路线通常是：内部用四元数积累姿态，渲染前转成旋转矩阵，UI层再按需显示欧拉角。

        当然，如果目标不是教学，而是更快做出稳定三维效果，也完全可以不手搓这一套。可以考虑直接用现成方案，如 matplotlib 3D、pyqtgraph、vispy、Open3D、moderngl，甚至 Unity/Three.js 这类更完整的渲染引擎。对pyfii而言，真正不可替代的是前面的动作编译与轨迹求值，三维显示层是可以替换的。

        `IIID2.py`则是另一条更轻量的全景渲染路线：它不再模拟相机透视，而是先把三维点转成以观察中心为原点的球坐标，再把方位角/俯仰角直接铺到二维全景图上。跨越全景左右边界的线段，会被拆成两段分别画在图像两端，从而避免“绕屏幕一大圈”的伪连线。

        在渲染过程中，pyfii会持续计算无人机之间在xy平面上的距离。当前实现里，F400以51cm为风险阈值、F600以33cm为风险阈值；告警文案会再按17cm或11cm步长向上取整，给出“距离小于多少厘米”的提示，并在画面中叠加红色高亮标记。

        注意：模拟是理想状态，一切以实际为准

        我们建议，音乐时长比设计动作的时长长至少三秒，否则可能会报错

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

        d1.TurnOnAll(color)
        # 点亮所有灯，颜色

        d1.TurnOffAll()
        # 熄灭所有灯

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

        d1.TurnOnAll(colors)
        # 点亮所有灯，颜色

        d1.TurnOffSingle(Id)
        # 熄灭某一盏灯

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
        pyfii 1.5.0及后续版本中加入了灯光模拟支持，但是只支持显示点灯和灭灯

        在编写移动时，建议使用```d1.move2(x,y,z)```，如果想要使用```d1.move(x,y,z)```，可以使用```d1.move2(d1.x+x,d1.y+y,d1.z+z)```代替

        ```d1.outputString```表示写入```webCodeAll.xml```的内容

        ```d1.outpy```表示写入```pyfiiCode.py```的内容

        Python转XML这一步本身也值得单独讲，因为这是整个库最像“编译器前端”的部分。当前实现不是用模板把整份XML一次性填出来，而是每个动作方法各自负责生成自己对应的XML片段。

        以`takeoff / intime / move2 / delay / VelXY / Yaw2 / land`为例，它们的回调函数都会做三件事：

        1. 根据动作类型更新内部状态，如`self.x/self.y/self.z/self.time`；
        2. 根据当前`self.space / self.block / self.inT`决定是否先补一个`<next>`，以及当前块该缩进多少层；
        3. 把对应的`<block type="Goertek_*"> ... </block>`片段直接追加到`self.outputString`，同时把同语义的Python语句追加到`self.outpy`。

        也就是说，pyfii不是先构建一棵XML对象树再序列化，而是维护了一个“块结构写出状态机”。其中：

        - `self.space`表示当前处于第几个`statement`嵌套层；
        - `self.block`表示当前未闭合的block/next层数；
        - `self.inT`表示当前`inittime`语句块里是否已经有动作，如果已有动作，下一个动作前要先写`<next>`；
        - `end()`负责在最后统一把尚未闭合的`</block>`、`</next>`、`</statement>`和`</xml>`全部补齐。

        从复刻角度说，有两条路线：

        1. 完全复刻当前实现：继续使用字符串拼接 + 写出状态机，优点是简单直接，且与现有工程格式完全一致；
        2. 更稳的重写实现：先构造动作块树，再统一序列化为XML，优点是结构清晰、便于支持更多块类型。

        如果只是为了做出兼容版，我建议先复刻当前字符串写出方案；如果目标是长期维护的二代实现，则建议把“Python动作序列 -> 块树 -> XML”独立成正式后端。

    2. ```Fii```类

        ```python
        F=pf.Fii(name,drones,music)
        ```

        ```name```为字符串，即文件名

        ```drones```为一个列表，列表里每一个元素都是```drone```类

        ```Fii```类的功能是整合多个```drone```类

        ```music```是一个字符串，是音乐的文件名，如```"xxx.mp3"```，如果不写```music```就是没音乐

        ```python
        F.save(field=4)
        ```

        这就是储存文件

        ```field```为地毯大小

        从源码看，`Fii`类做的不是单纯“存文件”，而是工程装配。它一方面把每架无人机在`drone.end()`后生成的`outputString`落盘为各自的`webCodeAll.xml`，另一方面把工程级信息写入顶层`.fii`：包括`DeviceType`、场地尺寸、音乐、动作组目录、动作组与UAVID映射、起飞坐标和控制时间节点。

        如果不是`infii`模式，`Fii.save()`还会额外生成一个可回放的`test.py`骨架：它逐个读取`pyfiiCode.py`并用`exec()`重新驱动`Drone`对象，再次构造出整个工程。这说明pyfii实际维护了两套等价表示：一套是给官方工程使用的XML，一套是给脚本回放与再加工使用的Python线性脚本。
        
        ```inFii```参数为脚本模式使用

        ```addlights```功能是覆写灯光

        如

        ```python
        F.save(addlights=True,field=6)
        ```

        此时，pyfii会删去原来的灯光，覆写上新的

        具体原理是读入脚本模式的脚本，删去原来的灯光，写入新的灯光，运行脚本，完成覆写

    3. DroneAction类和LightAction类

        在解释DroneAction类和LightAction类的原理之前，你可能需要一些关于回调函数(callback)的知识

        你可以查看[tests/class_callback_test.py](../../tests/class_callback_test.py)来了解回调函数的行为

        使用回调函数，是为了延迟函数或方法的执行。可以实现写一段代码（即回调函数），但不立即执行，之后可以对回调函数进行重新排序，在需要的时间被调用。

        为了实现独立编写灯光和动作的目的，`Drone`对象有`action_list`和`light_actions`两个属性，用来记录动作和灯光的回调函数，为了能在时间轴上对齐动作和灯光，封装了`DroneAction`类和`LightAction`类，引入`timestamp`并将其与回调函数打包在一起，为了协调动作和灯光的前后顺序，在`LightAction`类中加入了`order`属性

        在`drone.end()`操作之后，`Drone`类会遍历`action_list`，并按动作的`timestamp`到`light_actions`字典里查找`before/after`灯光，再依次执行封装的回调函数。这时才真正把pyfii代码转译为`webCodeAll.xml`与`pyfiiCode.py`字符串，因此这个过程本质上是“回调驱动的代码生成器”，而不是即时解释执行。

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

        `drone.end`方法就是这样查找一个动作有没有和其对应的灯光，并拼接为正确的顺序。进一步看源码可以发现，很多动作方法会先立即更新`self.x/self.y/self.z`，以便用户在编程阶段读取当前位置；等到回调真正执行时，再重复一次位置计算并把对应XML/Python片段写入输出缓冲区。

        因而从软件结构上说，pyfii并不是“直接操作XML字符串的一堆函数”，而是：面向领域的动作API → 延迟执行的动作/灯光对象 → 两种代码生成后端（XML / Python）→ 再由读取器把XML重新编译成仿真IR。这个分层解释了为什么它既能导出官方工程，又能保留脚本模式与模拟能力。

        如果学弟学妹要复刻这个库，建议按下面的最小顺序做：

        1. 先实现`Drone`与`Fii`，能稳定导出`.fii + webCodeAll.xml + pyfiiCode.py`。
        2. 再实现“Python动作序列 -> XML块程序”的生成后端，确保`outputString/outpy`双输出一致。
        3. 再实现`read_xml()`，把XML编译成统一`dots`事件流。
        4. 然后实现`dots2line / dots2angle / dots2led`三套求值器，其中`dots2line`是核心。
        5. 接着实现二维`show()`，先把俯视图和距离告警做对。
        6. 最后再补3D与全景渲染，这部分不是库成立的前提。

        以现在这份文档来看，已经足够支撑“按架构复刻整个项目”了：核心的数据流、状态机、编译路径、渲染时钟、工程装配关系都已经讲到。但如果要做到“逐函数一比一重写”，仍然建议配合源码一起看，尤其是灯光块、特殊动作块和F400/F600差异这些枚举性细节。换句话说，这份文档现在已经能指导重建系统设计，但还不是逐行替代源码的规范书。

5. 脚本模式

    见[脚本模式](script_mode.md)

    原理是使用python的```exec()```功能执行单行代码
