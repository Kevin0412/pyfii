# Pyfii

## 简介

这个库的功能是可以让我们用 python 写 Fii 的无人机程序，以解决原软件无运算能力，无循环模块，一块块拖太烦等问题。此外，这个库有三视图模拟飞行的功能，模拟飞行更方便观看。

### Pyfii GUI（网页版）

`apps/pyfii-gui/` 是 pyfii 的 Web GUI，已成功部署上线：**[pyfii.cn](https://pyfii.cn/)**

首页是 PyFii 门户；统一文档与教程中心位于 `/docs`，飞行工作台位于 `/studio`。

![Pyfii GUI 截图](docs/images/pyfii-gui-screenshot.png)

支持功能：

- **二维三视图模拟**：top / front / right 三个视角实时预览无人机编队飞行轨迹
- **加速度感知模拟**：模拟基于实际加速度数据，真实还原无人机飞行动态
- **清晰的 error / warning 展示**：距离、动作未完成和其他 core warning 分开展示，支持按列筛选和排序，点击带时间事件可跳转
- 门户页提供项目简介、GitHub 入口和 B 站视频教程；备案信息保持部署配置为空时不显示
- 上传 Fii 项目 zip，由 FastAPI 后端调用 pyfii core 完成轨迹解析和安全分析，浏览器提供可视化预览
- 首次使用 Guide，以及直接复用 `doc/` 下全部 Markdown 源的文档、教程、编舞与 Agent、工程研究静态页
- 复用 core `FiiRender2D/FiiRender3D` 的后端 MP4 导出

GUI 作为 pyfii core 的上层应用，依赖方向为：

```text
pyfii-gui -> pyfii core
```

FastAPI、Vue、Vite 等 GUI 依赖都放在 `apps/pyfii-gui/` 下，不放进 `src/pyfii/`。详细启动和部署说明见 [apps/pyfii-gui/README.md](apps/pyfii-gui/README.md)。

## 安装
1. 使用 pip install 安装

    在命令行输入

        pip install pyfii

2. 下载源代码

    在命令行输入

        git clone https://github.com/Kevin0412/pyfii.git
        cd pyfii
        python -m pip install -e .

    仓库使用 `src/` 布局，不要只复制仓库中的某个文件夹；使用 editable install 才能确保依赖和版本元数据正确。

## 文档索引

- [文档与教程中心](doc/pyfii_docs.md)：普通用户从这里开始。
- [PyFii core 文档](doc/doc_zh_CN.md)：动作、工程、读取和渲染接口。
- [GUI 使用引导](doc/pyfii_gui_guide.md)：上传、warning、预览和视频导出。
- [GUI 架构与部署](doc/pyfii_gui.md)：开发、配置和生产部署。
- [内部原理](doc/tutorial/principle.md)：面向维护或复刻项目的开发者。
- [仓库完整文档索引](doc/INDEX.md)：编舞与 Agent、工程研究及全部专题资料。

## 目录结构说明

    src/pyfii
    ├── cv3d
    │   ├── IIID2.py
    │   ├── IIID.py
    │   └── transfer.py
    ├── drone.py
    ├── fii.py
    ├── fii_parser.py
    ├── xml_parser.py
    ├── read.py
    ├── fiiRead.py
    ├── show.py
    └── __init__.py

项目结构 (核心部分) 如上图

其中 cv3d 是使用 OpenCV 实现的 3d 图形库

drone.py 定义了 Drone 类，实现无人机的基本指令

fii.py 定义了 Fii 类，保存无人机和音乐，并能将其保存为*.fii 文件

fii_parser.py 和 xml_parser.py 负责树形 XML 解析，read.py 负责兼容入口和轨迹计算

fiiRead.py 封装 DroneTrack 与二维/三维渲染器，show.py 提供兼容的预览入口

GUI 位于 `apps/pyfii-gui/`，详细结构见 [apps/pyfii-gui/README.md](apps/pyfii-gui/README.md)。

## 许可证和作者

- 许可证：GNU General Public License v3 (GPLv3)

- 作者：

    主要作者：github@Kevin0412

    代码开发，无人机测试，编写说明文档，在 bilibili.com 上传演示视频等工作

    次要作者：github@miaooo0000OOOO

    上传模块到 pypi，debug，无人机测试，写这个 README

## 项目方向

pyfii 2.0 的重点不是简单 Web 化，而是把编队核心、轨迹采样、安全审查、渲染/预览拆成可替换模块。`apps/pyfii-gui/` 是这一方向的 Web 实现，已部署上线，core 仍然保持独立 PyPI 库定位。

- `pyfii-core`：`.fii` 读写、动作 DSL、轨迹采样、灯光时间轴、安全规则。
- `pyfii-render`：统一渲染接口，保留 OpenCV 参考后端，并试验桌面 3D / Web viewer。
- `pyfii-app`：面向实际调试的交互式预览工具。

AI 编舞探索、人工/AI 产物蒸馏和 Cannon 复盘共同构成 Choreo Agent 的研究资料，入口见 [仓库完整文档索引](doc/INDEX.md)；当前主线是强模型生成 motion brief / phrase spec / PyFii 脚本，再由本地读回、密采样、安全检查和 2D/3D 视频验收。
