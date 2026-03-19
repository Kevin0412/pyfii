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

**核心改动：Web 化，不再向后兼容 OpenCV 方案**

- [ ] **架构设计**
  - 独立服务器模块：`pyfii-server` 提供前后端服务
  - 两种使用模式：
    1. **调试模式**（推荐）：先手动启动 `pyfii-server` 持久运行，之后运行 pyfii 脚本时直接连接服务器推送轨迹。修改运动轨迹后只需重新运行 Python 脚本，服务器保持运行无需重启。
    2. **集成模式**：pyfii 脚本内调用 `show()` 时启动服务器，Python 进程退出后服务器也关闭。适合单次运行场景。

- [ ] **Web 可视化**
  - 后端：FastAPI 解析 `.fii` 文件，返回无人机轨迹 JSON
  - 前端：React + Canvas 三视图（俯视/正视/侧视）+ Three.js 3D 视图
  - 控制：进度条拖动、播放/暂停、倍速
  - 视觉风格：迁移并对齐 pyfii 1.x 的 OpenCV 渲染风格，保证升级后观感差距可控
  - 设计目标：在继承 1.x 视觉语言基础上，逐步沉淀 pyfii 2.0 自有前端风格

- [ ] **PyPI 封装**：预编译前端
  - PyPI 包内包含 `static/` 目录（React 打包产物）
  - 安装即用，无需 Node.js 环境

- [ ] **未来展望：AI 辅助编队轨迹设计与编排**
  - 接入 Gemini 与 Qwen3.5 多模态能力（当前优先这两类支持原生视频理解、无需先拆分为图片的模型），用于理解编队飞行仿真视频并参与轨迹规划
  - 不仅复刻已有动作，更从头开始设计无人机飞行路径与动作编排
  - 设计每个动作后通过视频理解进行验证，逐步迭代，最终完成整套飞行动作
  - 该方向不保证短期落地，但会作为 pyfii 2.0 的重要探索
  - 面向后续多人使用场景，预留高并发任务处理与部署扩展能力