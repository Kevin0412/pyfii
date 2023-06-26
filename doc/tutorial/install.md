- ## 安装python

    这里有安装python的两条路线

    1. 安装Anaconda/Miniconda，并使用conda管理python环境

    2. 从官网下载python并安装

    为了避免和你之前在电脑上安装过的python冲突，建议安装Miniconda，安装Miniconda可以参考[我在b站的视频](https://www.bilibili.com/video/BV1Rh411h7HB)
    
    在参照视频配置完成后，你需要了解基本的conda命令

        conda create -n 环境名 python=3.9

    环境名比如 : pyfii_env

    这个命令创建了一个名叫`环境名`的虚拟环境，且python版本为3.9

        conda env list

    这个命令会列出所有conda的虚拟环境

        conda activate 环境名

    这个命令会切换当前环境为`环境名`

    这时候命令提示符会在前面显示一个括号包裹的`环境名`

    在你当前创建的环境下使用pip install命令安装pyfii

        pip install -i https://pypi.org/simple pyfii==1.5

    这个命令会从pypi官网下载pyfii

        pip install opencv-python pygame ffmpy 
    
    这个命令会从镜像源下载pyfii的依赖库

    安装就完成了

    你可以运行pyfii源码库的示例程序测试安装是否成功