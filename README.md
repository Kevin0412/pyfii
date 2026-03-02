# Pyfii

## 简介
这个库的功能是可以让我们用 python 写 Fii 的无人机程序，以解决原软件无运算能力，无循环模块，一块块拖太烦等问题。

此外，这个库有三视图模拟飞行的功能，模拟飞行更方便观看。

## 安装
1. 使用 pip install 安装

    在命令行输入

        pip install pyfii

2. 下载源代码

    在命令行输入

        git clone https://github.com/Kevin0412/pyfii.git

    pyfii 就会被下载到当前目录下，使用时将 pyfii 文件夹复制到项目目录下

## 使用教程

请见./doc/doc_zh_CN.md

## 目录结构说明

    src/pyfii
    ├── cv3d
    │   ├── IIID2.py
    │   ├── IIID.py
    │   └── transfer.py
    ├── drone.py
    ├── fii.py
    ├── __init__.py
    ├── read.py
    └── show.py

项目结构 (核心部分) 如上图

其中 cv3d 是使用 OpenCV 实现的 3d 图形库

drone.py 定义了 Drone 类，实现无人机的基本指令

fii.py 定义了 Fii 类，保存无人机和音乐，并能将其保存为*.fii 文件

read.py 用来读取和转换无人机动作文件

show.py 用来预览无人机飞行效果

## 许可证和作者

- 许可证：GNU General Public License v3 (GPLv3)

- 作者：

    主要作者：github@Kevin0412

    代码开发，无人机测试，编写说明文档，在 bilibili.com 上传演示视频等工作

    次要作者：github@miaooo0000OOOO

    上传模块到 pypi，debug，无人机测试，写这个 README

## pyfii 2.0 计划

- [ ] **Web 可视化优化**：使用 Flask 后端 + React 前端替代原有 OpenCV 渲染
  - 后端：Flask 接收 `.fii` 文件，解析后返回无人机轨迹坐标 JSON
  - 前端：React 渲染飞行轨迹，支持进度条控制（播放/暂停/拖动/倍速）
  - 渲染：支持 2D 三视图（俯视图/正视图/侧视图）和 3D 视图（Three.js/React Three Fiber）
  - 优势：跨平台浏览器运行、交互灵活、易于扩展、前后端分离