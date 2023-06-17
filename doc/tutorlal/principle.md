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

    pyfii-1.1.1和pyfii-1.5.0及后续版本，加入了脚本模式

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
    
