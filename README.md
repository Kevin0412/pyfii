# PyFii

PyFii 是一个用 Python 编排、生成和检查 Fii 无人机编队工程的开源项目。它把原本需要逐块拖动的动作、灯光和时间轴编排写成可复用的 Python 脚本，并提供 `.fii` 工程读写、轨迹解析、安全检查、二维/三维模拟和视频导出。

项目由两个相互独立的部分组成：

- `src/pyfii/`：可单独安装和使用的 Python core。
- `apps/pyfii-gui/`：建立在 core 之上的 Web GUI，不把 FastAPI、Vue 等依赖引入 core。

## 目录

- [在线使用](#在线使用)
- [主要能力](#主要能力)
- [快速开始](#快速开始)
  - [安装 core](#安装-core)
  - [编写并预览一个工程](#编写并预览一个工程)
  - [本地启动 GUI](#本地启动-gui)
- [文档目录](#文档目录)
- [仓库结构](#仓库结构)
- [GUI 部署提示](#gui-部署提示)
- [依赖安全](#依赖安全)
- [项目方向](#项目方向)
- [许可证与作者](#许可证与作者)

## 在线使用

**[pyfii.cn](https://pyfii.cn/)** 已部署当前仓库的最新 GUI 版本，不安装本地环境也可以阅读文档或使用飞行工作台。

- [首页](https://pyfii.cn/)：了解项目、观看视频教程并进入各项功能。
- [文档与教程](https://pyfii.cn/docs)：浏览仓库 `doc/` 中的完整文档。
- [飞行工作台](https://pyfii.cn/studio)：上传完整 Fii 工程 zip，检查并预览编队飞行。
- [B 站视频教程](https://www.bilibili.com/video/BV1Ms4y1F7fM/)：通过实际演示了解基本操作。

在线工作台支持：

- 二维三视图和 WebGL 三维模拟，包含加速度投影、机身倾斜和连续航向旋转。
- 根据手机、平板和桌面设备调整布局，并在移动端保留三维坐标信息。
- 显示确定的工程加载进度，并提供首次使用引导和全屏预览。
- 区分会阻止操作的 error 与不阻止预览的 warning；未拼接积木等 core warning 会直接展示。
- 在浏览器中完成交互预览，由后端复用 core 渲染器导出 MP4；工程包含音乐时使用 FFmpeg 合并音频。

![PyFii GUI 截图](docs/images/pyfii-gui-screenshot.png)

GUI 的本地开发、生产依赖和部署配置见 [apps/pyfii-gui/README.md](apps/pyfii-gui/README.md)。

## 主要能力

- 使用 Python API 编排 F400、F600 等 Fii 无人机的动作、灯光和时间轴。
- 生成 Fii 工程，也可以读回 `.fii` 文件和动作组 XML。
- 通过 `DroneTrack` 统一承载解析后的轨迹、灯光和飞行信息。
- 使用 `FiiRender2D`、`FiiRender3D` 和 `FiiRenderPanorama` 预览或保存画面。
- 保留原有 `show()`、`fiiRead()` 等兼容入口，现有脚本无需立即迁移。
- 在预览和导出前检查距离、动作完整性等安全问题，并分别报告 error 与 warning。

模拟与安全检查用于编排复核，不能替代真机测试、现场安全评估和 Fii 官方软件的最终检查。

## 快速开始

### 安装 core

安装已发布版本：

```bash
python -m pip install pyfii
```

从源码使用当前版本：

```bash
git clone https://github.com/Kevin0412/pyfii.git
cd pyfii
python -m pip install -e .
```

仓库采用 `src/` 布局。开发时使用 editable install，可以确保依赖、导入路径和版本元数据正确。

### 编写并预览一个工程

```python
import pyfii as pf

drone = pf.Drone(60, 60, config=pf.drone_config_4m)
drone.takeoff(1, 100)
drone.inittime(4)
drone.VelXY(100, 200)
drone.move2(120, 120, 100)
drone.inittime(8)
drone.land()
drone.end()

project = "output/demo"
pf.Fii(project, [drone]).save()

track = pf.from_fii(project)
pf.show(track)
```

完整的动作、灯光、工程生成和渲染接口见 [PyFii core 文档](doc/doc_zh_CN.md)。

### 本地启动 GUI

Linux 下可从仓库根目录一键安装依赖并启动前后端：

```bash
./apps/pyfii-gui/start.sh
```

依赖已经安装时可以跳过安装：

```bash
./apps/pyfii-gui/start.sh --no-install
```

默认前端地址是 `http://localhost:5173`，后端地址是 `http://localhost:8000`。每次运行的前后端日志会分别保存到 `apps/pyfii-gui/logs/<启动时间>-<进程号>/`，每行包含本地时间和时区。

## 文档目录

- [文档与教程中心](doc/pyfii_docs.md)：普通用户的阅读入口。
- [安装教程](doc/tutorial/install.md)：Python、编辑器与 PyFii 安装。
- [脚本模式教程](doc/tutorial/script_mode.md)：从动作脚本到 Fii 工程。
- [PyFii core 文档](doc/doc_zh_CN.md)：动作、灯光、工程、读取与渲染 API。
- [GUI 使用引导](doc/pyfii_gui_guide.md)：上传、warning、预览和视频导出。
- [GUI 架构与部署](doc/pyfii_gui.md)：开发、配置、依赖和生产部署。
- [内部原理](doc/tutorial/principle.md)：面向维护者的格式与实现说明。
- [完整文档索引](doc/INDEX.md)：编舞、Choreo Agent、工程研究和其他专题资料。

线上 [文档与教程](https://pyfii.cn/docs) 直接使用仓库中的文档源；文档修改随 GUI 新版本一起发布，避免维护另一份内容副本。

## 仓库结构

```text
pyfii/
├── src/pyfii/               # Python core、工程读写、解析和渲染
├── apps/pyfii-gui/          # Vue 前端与 FastAPI 后端
├── doc/                     # 用户文档、教程和研究资料
├── tools/choreo_agent/      # AI 编舞实验与工具
├── tests/                   # core 测试
└── output/                  # 示例与本地生成的 Fii 工程
```

core 中的重要入口：

- `drone.py`：无人机动作和灯光指令。
- `fii.py`：组织无人机与音乐并保存 Fii 工程。
- `fii_parser.py`、`xml_parser.py`：树形解析 `.fii` 和动作组 XML。
- `read.py`：兼容读取入口与轨迹计算。
- `fiiRead.py`：`DroneTrack` 和二维/三维渲染器。
- `show.py`：保留旧调用方式的预览兼容入口。

## GUI 部署提示

- 后端需要 Python 3.9 或更高版本；前端构建需要符合当前 lockfile 要求的 Node.js 和 npm。
- 导出无声 MP4 使用 OpenCV；工程包含音乐时还需要系统中的 `ffmpeg`。Ubuntu 可运行 `sudo apt install ffmpeg`。
- 备案信息来自部署实例自己的 `deploy.json` 或环境变量，默认关闭且不显示，真实备案号不会提交到仓库。
- 当前后端不依赖数据库或任务队列，上传工程和导出任务状态保存在单个后端进程内。
- 生产环境应构建并托管前端 `dist/`，使用 Nginx、Caddy 等服务器反向代理 `/api`，不要使用 Vite 开发服务器代替生产静态服务。

详细安装命令、Ubuntu 依赖、配置项和反向代理方式见 [GUI 部署文档](apps/pyfii-gui/README.md#生产部署依赖)。

## 依赖安全

仓库会在依赖清单变化和每周定时任务中运行前端 `npm audit`，并使用固定版本的 `pip-audit` 检查 core 与 GUI 后端。Python 检查同时覆盖当前可解析版本和声明的直接依赖最低版本，避免安全修复只存在于较新版本、但依赖下界仍允许安装已知漏洞版本。Dependabot 会为 GitHub Actions、npm 和两个 Python 项目分别提交依赖更新。

## 项目方向

项目继续保持“编队 core、轨迹与安全检查、渲染、上层应用”之间的清晰边界。近期工作包括统一 `DroneTrack` 渲染入口、保留旧路径兼容、完善 Web GUI，以及使用本地读回、密采样和安全检查验证 Choreo Agent 生成的编舞结果。

这些是代码职责边界，不代表仓库中已经存在名为 `pyfii-core`、`pyfii-render` 或 `pyfii-app` 的独立发行包。

## 许可证与作者

本项目使用 [GNU General Public License v3.0](LICENSE)。

- 主要作者：[Kevin0412](https://github.com/Kevin0412)
- 贡献者：[miaooo0000OOOO](https://github.com/miaooo0000OOOO)
