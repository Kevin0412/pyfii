1. 灯光

    可使用的灯光方法如下：
    ```python

    d1.TurnOnSingle(Id,color)
    #点亮某一盏灯，颜色

    d1.TurnOffSingle(Id)
    #熄灭某一盏灯

    d1.TurnOnAll(colors)
    #点亮所有灯，颜色

    d1.TurnOffAll()
    #熄灭所有灯

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

    其中，color可填六位十六进制色彩的字符串或长度为三的元组，遵循RGB顺序

    例如

    ```python
    '#66ccff'
    # 等同于
    (102,204,255)
    # 显示为淡蓝色
    ```
    
    colors为一个列表，列表中至少有一个元素，每个元素写法与color相同

    例如

    ```python
    ['#66ccff']
    # 12个灯全部为淡蓝色

    ['#ff0000',(0,255,0)]
    # 12个灯交替为红绿

    [(255,0,0),(255,255,0),(0,255,0)]
    # 12个灯交替为红黄绿
    ```

    以此类推

    例外

    ```python
    d1.TurnOnAll(colors)
    #点亮所有灯，颜色
    ```
    这里的colors兼具color的特性

    Id为无人机灯的编号，一架无人机共有12个灯，具体请参照官方软件

2. 灯光的编写

    灯光可以按顺序编写，类似于官方软件的编写模式

    例如

    ```python
    import pyfii as pf

    d1=pf.Drone(40,40,pf.drone_config_6m)

    d1.takeoff(1,80)

    d1.inittime(4)
    d1.VelXY(200,400)
    d1.VelZ(200,400)
    d1.move2(520,520,250)
    d1.TurnOnAll('#ffff00')
    d1.delay(500)
    d1.TurnOnAll((0,255,0))
    d1.delay(2999)
    d1.TurnOnAll([
        '#ffff00','#ffff00','#ffff00','#ffff00',
        '#ffff00','#ffff00','#ffff00','#ffff00',
        '#ffff00','#ffff00','#ffff00','#ffff00'
    ])
    d1.delay(500)
    d1.TurnOnAll([
        (255,0,0),(255,0,0),(255,0,0),(255,0,0),
        (255,0,0),(255,0,0),(255,0,0),(255,0,0),
        (255,0,0),(255,0,0),(255,0,0),(255,0,0)
    ])

    d1.inittime(9)
    d1.BlinkFastAll(['#ff0000',(255,255,0),'#00ff00'])
    d1.land()

    d1.end()
    # ...
    ```
    这个程序来自编队飞行示例

    但是为了开发效率，也可以将灯光与动作分开来写

    例如
    ```python
    import pyfii as pf

    A,B,C,D,E,F = [i for i in range(6)]
    AFTER, BEFORE = 'after', 'before'

    d1=pf.Drone(40,40,pf.drone_config_6m)

    # 无人机动作
    d1.takeoff(1,80)

    d1.inittime(4)
    d1.VelXY(200,400)
    d1.VelZ(200,400)
    d1.move2(520,520,250, A) 
    # 因为A和C的灯光相同，上一行的A也可以替换为C
    d1.delay(500, B)
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


    d1.end()    # 整合动作和灯光，必须在灯光和动作之后
    # ...
    ```
    这两个程序等效

    独立编写灯光可以减少重复代码，也更方便修改

    pyfii通过timestamp(时间戳)来同步动作和灯光，灯光和动作的时间戳相同时，pyfii会对齐两者的时间

    灯光方法还有order(顺序)参数，表示灯光对齐到动作的前还是后，'after'表示灯光在动作之后，'before'反之

    timestamp本质是整数，因此当使用循环编写动作时，你可以使用循环变量作为时间戳

    不过请注意不要混淆不同动作的时间戳

    不同无人机使用相同的时间戳不会混淆
    
    某架无人机的时间戳和其对应的灯光方法不能被另一架无人机调用

    你可以使用hash(散列)函数避免混淆

    例如

    ```python
    # 循环变量i
    i = 1
    timestamp = hash(f'action_name {i}')
    ```

    此外，动作与灯光分开编写还有第二种方法

    新建一个python文件，不用写动作（起飞除外），只需要写灯光即可

    例如

    ```python
    import pyfii as pf

    # 七架F400,6m毯
    d1=pf.Drone(0,0,pf.drone_config_6m)
    d2=pf.Drone(0,0,pf.drone_config_6m)
    d3=pf.Drone(0,0,pf.drone_config_6m)
    d4=pf.Drone(0,0,pf.drone_config_6m)
    d5=pf.Drone(0,0,pf.drone_config_6m)
    d6=pf.Drone(0,0,pf.drone_config_6m)
    d7=pf.Drone(0,0,pf.drone_config_6m)

    ds=[d1,d2,d3,d4,d5,d6,d7]

    for d in ds:
        d.takeoff(1,80)

        d.inittime(4)
        d.TurnOnAll((255,255,255))

        d.end()

    # 保存
    name='group_flight_6m_2'
    F=pf.Fii(name,ds)
    F.save(addlights=True,feild=6)
    ```

    其中，最关键的一行是

    ```python
    F.save(addlights=True,feild=6)
    ```

    运行结果就是原来的灯光被删除，新的灯光被加入了进去


