- ## 安装python

    这里有安装python的两条路线

    1. 安装Anaconda/Miniconda，并使用conda管理python环境

    2. 从官网下载python并安装

    为了避免和你之前在电脑上安装过的python冲突，建议安装Miniconda，安装Miniconda可以参考[我在b站的视频](https://www.bilibili.com/video/BV1Rh411h7HB)
    
    在参照视频配置完成后，你需要了解基本的conda命令

        conda create -n 环境名 python=3.10

    环境名比如 : pyfii_env

    这个命令创建了一个名叫`环境名`的虚拟环境，且python版本为3.10及以上

        conda env list

    这个命令会列出所有conda的虚拟环境

        conda activate 环境名

    这个命令会切换当前环境为`环境名`

    这时候命令提示符会在前面显示一个括号包裹的`环境名`

    在你当前创建的环境下使用pip install命令安装pyfii

        pip install -i https://pypi.org/simple pyfii

    这个命令会从pypi官网下载pyfii。若需要固定版本，可以在包名后追加版本号，例如：

        pip install -i https://pypi.org/simple pyfii==1.5.0

    如果你正在开发本仓库源码版本，可以在仓库根目录安装为可编辑包：

        pip install -e .

        pip install opencv-python pygame ffmpy

    这个命令会从镜像源下载pyfii的依赖库

    安装就完成了

    你可以运行pyfii源码库的示例程序测试安装是否成功

- ## GUI 原型开发环境

    Pyfii 的 Web GUI 原型位于 `apps/pyfii-gui/`，它是独立应用，不属于 `src/pyfii/` core 包。开发 GUI 前建议先在仓库根目录安装 core：

        pip install -e .

    启动后端：

        cd apps/pyfii-gui/backend
        pip install -e .
        uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000

    启动前端：

        cd apps/pyfii-gui/frontend
        npm install
        npm run dev

    前端默认监听 `0.0.0.0:5173`，可在局域网另一台设备访问：

        http://<开发机局域网IP>:5173

    更多说明见 [Pyfii GUI 原型](../pyfii_gui.md)。
