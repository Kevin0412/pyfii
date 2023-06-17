# 原理

1. 小鸟飞飞文件

        test
        ├── 动作组
        │   ├── 动作组1
        |   │   ├── transfile
        |   |   |   └── 1001.ls
        |   |   ├── offlineExcuteScript.py
        |   |   ├── webCodeAll.py
        |   |   └── webCodeAll.xml
        |   ├── 动作组2
        |   │   ├── transfile
        |   |   |   └── 2002.ls
        |   |   ├── offlineExcuteScript.py
        |   |   ├── webCodeAll.py
        |   |   └── webCodeAll.xml
        |   ...
        │   ├── checksums.xml
        │   └── xxx.mp3
        └── test.fii

    其中，
    
    test.fii文件记录了起飞位置、无人机ip、无人机型号、地毯尺寸、音乐文件名称和inittime的时间

    checksums.xml文件暂不清楚它的用处

    xxx.mp3就是你的音乐

    webCodeAll.xml是你写的单个无人机的飞行程序

    webCodeAll.py是小鸟飞飞的伪代码，只要有webCodeAll.xml，伪代码文件会自动生成，猜测是模拟时用的

    offlineExcuteScript.py在点击上传时会出现，猜测这是编译至无人机可执行的代码的源代码

    .ls文件我猜测是上传给无人机的二进制文件，上传成功就会有这个文件

2. pyfii生成文件

    pyfii-1.4.0以前

        test
        ├── 动作组
        │   ├── 动作组1
        |   |   └── webCodeAll.xml
        |   ├── 动作组2
        |   |   └── webCodeAll.xml
        |   ...
        │   ├── checksums.xml
        │   └── xxx.mp3
        └── test.fii

    pyfii-1.1.1和pyfii-1.5.0及后续版本，加入了[脚本模式](script_mode.md)

        test
        ├── 动作组
        │   ├── 动作组1
        |   |   ├── pyfiiCode.py
        |   |   └── webCodeAll.xml
        |   ├── 动作组2
        |   |   ├── pyfiiCode.py
        |   |   └── webCodeAll.xml
        |   ...
        │   ├── checksums.xml
        │   └── xxx.mp3
        ├── readme.md
        ├── test.md
        └── test.py
    
3. pyfii模拟

    1. 读入文件

        ```python
        data,t0,music,feild=pf.read_fii(name,getfeild=True)
        ```

        其中

        data是一个列表，列表的长度是无人机数，每一个元素也是列表

        data[n]列表储存了第n+1架无人机飞行轨迹及旋转数据，每一个元素是长度为5的元组

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
        
        t0表示模拟结束的帧数（t0/200即动作时长多少秒）

        music表示音乐，数据类型为列表，长度为1或2，元素的数据类型为字符串

        ```python
        music=[musicdir,musicname] # musicname不需要后缀
        
        music=[musicname] # musicname为音乐的完整路径
        ```

        feild表示地毯大小，4表示4米毯，6表示6米毯

    