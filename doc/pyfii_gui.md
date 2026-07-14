# PyFii GUI 架构与部署

`pyfii-gui` 是 Pyfii 仓库中的独立 Web GUI，目录为 `apps/pyfii-gui/`。它用于上传 Fii 项目、读回轨迹、查看安全日志、进行 2D/3D 预览，并通过 core renderer 导出 MP4。

它不属于 `src/pyfii/` core 包，也不改变 pyfii 作为独立 PyPI 库的定位。依赖方向只能是：

```text
pyfii-gui -> pyfii core
```

## 架构边界

- core 代码仍在 `src/pyfii/`，负责 Fii 读写、轨迹采样、OpenCV 预览和原有 warning。
- GUI 后端在 `apps/pyfii-gui/backend/`，使用 FastAPI 做薄适配层。
- GUI 前端在 `apps/pyfii-gui/frontend/`，使用 Vue 3、Vite、TypeScript 和 Pinia。
- 后端只适配 `pyfii.read.read_fii`、core 的无窗口校验能力和 `FiiRender2D/FiiRender3D`，不把 FastAPI、Vue、Electron 或 GUI 专属代码放进 core。
- 浏览器交互预览使用 Canvas 2D / Three.js；交付视频使用后端 core renderer。两条路径消费同一份轨迹，但绘制后端不同。

## 后端职责

后端 API 入口为 `pyfii_gui_api.main:app`，主要接口：

- `GET /api/health`：健康检查。
- `POST /api/projects`：上传 `.zip` Fii 项目，安全解压，调用 `read_fii()` 解析。
- `GET /api/projects/{project_id}`：返回项目元信息。
- `GET /api/projects/{project_id}/tracks?fps=60`：返回前端渲染用轨迹，支持简单降采样。
- `GET /api/projects/{project_id}/safety`：返回结构化安全日志。
- `POST /api/projects/{project_id}/video-exports`：创建异步 MP4 任务。
- `GET /api/projects/{project_id}/video-exports/{export_id}`：读取任务状态。
- `GET /api/projects/{project_id}/video-exports/{export_id}/download`：下载完成的 MP4。
- `DELETE /api/projects/{project_id}`：删除缓存和临时文件。

上传 zip 会经过 zip slip 检查、上传体积限制、解压后总体积限制、文件数量限制和单文件大小限制。运行时文件默认放在：

```text
apps/pyfii-gui/backend/.runtime/projects/
```

也可以通过 `PYFII_GUI_RUNTIME_DIR` 覆盖。

## 安全日志来源

当前 GUI 不重新实现一套独立 Fii 解析器。安全日志主要来自 pyfii core：

- `read_fii()` 捕获的 warning，例如动作未完成。
- `show(track, show=False)` 捕获的 warning，例如无人机间距过近。

GUI 后端会把这些 warning 结构化成前端可展示的事件，例如 `action_incomplete`、`min_distance` 和 `core_warning`。这保证 GUI 的安全判断尽量贴近现有 pyfii core 行为。

无法归入距离或动作未完成的 core warning 不再丢弃，而是保留原消息、无人机前缀和 `core_warning` 类别。近期树形 XML 解析器的“未拼接积木”提示会走这条路径。warning 不阻止项目加载、预览或导出；压缩包无效、解析异常和视频任务失败仍作为 fatal error 终止对应操作。

已知老版本 Fii 项目可能无法被当前 core 解析，例如 `output/d/比赛用无人机` 使用早期 XML/LED 格式；批量回归脚本会把这类样例记录为 `expected_failure`，不把它当作 GUI 回归失败。

## 前端职责

前端是包含门户、静态文档和飞行工作台的单页应用。站点首页 `/` 提供项目简介、GitHub、B 站视频教程和主要入口，`/studio` 承载原模拟器。主要能力：

没有保存过主题偏好时，内容页面默认浅色，`/studio` 默认深色；用户手动切换后以本地保存的选择为准。

- 上传 Fii 项目 zip。
- 项目载入使用确定进度条：ZIP 上传阶段由浏览器按已发送字节计算并映射到 0–25%，后端解压和解析完成时到 50%，轨迹与安全日志响应各完成后依次到 75% 和 100%。解析 core 当前没有内部逐动作回调，因此解析期间数值停在 25%，只更新阶段文字，不用循环动画伪造百分比。
- 展示项目名、field、device、无人机数量、时长、FPS、安全等级。
- 请求并缓存轨迹和安全日志。
- 用 Canvas 2D 绘制经典 Pyfii 三视图：top / front / right。
- 用 Three.js 提供 3D 预览模式，支持正交/透视相机切换；默认 2D 首屏不加载 Three.js，第一次切换到 3D 时再按需加载。
- 3D 模式保留旧 `show(ThreeD=True)` 的 A/B 视角角、观察者距离和投影距离语义。
- 3D 模式默认评委视角 `imshow=[90,3]`、`d=(600,450)`，支持鼠标拖动转动视角和滚轮调整投影距离。
- 3D 模式显示高度标尺、地面投影、左上角时间/FPS/坐标 HUD，以及按 9 机编队设计的稳定机体颜色。
- 右下角信息栏使用 2 行 5 列布局：D1..D9 + STATUS。
- 时间轴播放、暂停、倍速、拖动跳转。
- 安全日志按距离、动作未完成和通用 core warning 五类展示，并支持类似 Excel/文件夹列表的按列筛选和排序。
- 距离事件沿用 core 的 51cm / 34cm / 17cm 档位，分别对应距离过近、碰撞风险、碰撞警告。
- 点击安全日志跳转到对应时间。
- 音乐文件播放和基础时间轴同步。
- 第一次访问显示逐控件聚焦的六步使用引导，顶部可随时重新打开；其中会明确指出模拟区域右上角的全屏按钮。
- `/docs` 是统一文档中心；`/docs/index` 提供全部文档索引，`/docs/guide`、`/docs/core`、`/docs/gui` 和 `/docs/tutorial/*` 分别提供 Guide、PyFii core 文档、GUI 部署说明和专题教程，`/docs/choreo/*` 收录编舞与 Agent 资料，`/docs/research/*` 收录工程研究。
- `/doc`、`/guide`、`/tutorial/*` 和旧 `#/...` 链接会转换到新的 `/docs/...` 层级，`/gui` 兼容跳转到 `/studio`。
- 后端异步 MP4 导出，前端只负责创建任务、轮询状态、展示失败和下载。

移动布局按设备类型和屏幕方向处理，而不是只按浏览器窗口宽度处理。普通电脑缩窄窗口仍保持电脑端界面；手机和平板竖屏的工作台都把模拟画布放在项目信息之前，画布按 `2:1` 占满屏幕宽度；平板横屏保持电脑端工作台。手机文档页将完整目录折叠在当前文档标题下，桌面和平板目录默认展开，其中平板竖屏显示双列目录。

Canvas 内部虚拟画布固定为 `1200x600`，按容器缩放显示。渲染器位于 `frontend/src/renderer/`，不依赖 Vue，便于后续复用。

Three.js 预览从轨迹帧读取加速度，并沿用 core 的 `wing_force = acceleration - (0, 0, -980)`：先把单位升力方向从 PyFii 坐标映射到 Three.js 坐标，再叠加航向角，因此机体会随加速度产生俯仰和横滚。地面投影仍保持水平，用来表示实际 XY 位置。

静态文档在 Vite 构建时收集 `doc/` 下全部 Markdown 源，每篇正文通过 dynamic import 独立打包，访问某一页时只加载该页正文，再经 `marked` 渲染。这样既避免复制文档，也不会让 Guide 首屏携带全部研究资料。`doc/images/` 中由真实飞行分析引用的图表和指标文件也会作为前端资源打包。

站点控件支持中文/英文切换；当前导入的 Markdown 正文只有中文版本，切换到英文时导航会翻译，但正文仍显示中文。

## 视频渲染封装

`backend/src/pyfii_gui_api/services/video_export.py` 是 GUI 与 core 的边界：

1. 把已解析的 `ProjectRecord` 数据装入 core `DroneTrack`。
2. 把 GUI 的 2D/3D、FPS、缩放和相机参数转换为现有 renderer config。
3. 2D 选择 `FiiRender2D`，3D 选择 `FiiRender3D`，统一调用 `save()`。
4. 单线程任务池控制同时导出的项目数；core renderer 内部仍可按 `PYFII_GUI_VIDEO_RENDER_WORKERS` 并行画帧。
5. core 负责 OpenCV MP4 编码和现有 ffmpeg 音频封装，GUI 不复制逐帧渲染逻辑。

任务状态存在后端内存中。`FiiRender.save()` 的可选回调在主进程每写入一帧后报告 `(completed, total)`，不改变未使用回调时的 core 行为。GUI 将真实帧进度映射为 0–95%，剩余区间用于视频/音频封装，完成后为 100%。

## 开发启动

仓库根目录提供一键启动脚本：

```bash
./apps/pyfii-gui/start.sh
```

脚本会同时启动前后端，并在 `apps/pyfii-gui/logs/<启动时间>-<进程号>/` 中分别保存两端日志；文件中的每一行带本地时间和时区，终端仍会实时显示服务原始输出。日志根目录可通过 `PYFII_GUI_LOG_DIR` 覆盖。

脚本会检查 Python、Node.js 和 npm，缺少这些必需命令时停止。FFmpeg 只用于把工程音乐封装进导出视频，因此缺少时只显示 warning 并继续启动；无声 MP4 导出仍可使用。

先安装 pyfii core：

```bash
cd <repo-root>
pip install -e .
```

启动后端：

```bash
cd apps/pyfii-gui/backend
pip install -e .
uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
```

启动前端：

```bash
cd apps/pyfii-gui/frontend
npm install
npm run dev
```

Vite dev server 默认监听 `0.0.0.0:5173`。局域网另一台设备可以打开：

```text
http://<开发机局域网IP>:5173
```

开发态前端默认通过 Vite proxy 请求 `/api`，proxy target 默认为 `http://localhost:8000`。如果后端在另一台机器上，可设置：

```bash
VITE_API_PROXY_TARGET=http://<后端局域网IP>:8000 npm run dev
```

## 生产部署依赖

GUI 的生产服务由 Python 后端和前端 `dist/` 静态文件组成：

- Python 3.9 或更高版本运行 PyFii core 与 FastAPI。应分别安装仓库根目录和 `apps/pyfii-gui/backend` 的 `pyproject.toml`；根目录 `requirements.txt` 还包含 GUI 生产环境不需要的分析和打包工具。
- 后端只使用 OpenCV 图像绘制和 `VideoWriter`，headless 能力已经足够，不调用 `imshow`，也不要求桌面或 GPU。当前 core 的默认包元数据仍声明完整版 `opencv-python`，所以按现有 `pyproject.toml` 安装时，最小化 Ubuntu 可能仍要提供该 wheel 导入时使用的 OpenGL / GLib 兼容库。
- OpenCV 负责写入无声 MP4。工程包含音乐时，core 通过 `ffmpy` 调用系统中的 `ffmpeg` 做音频封装；只安装 Python 包 `ffmpy` 不够。
- Node.js 和 npm 只负责构建 Vue 静态文件。当前 lockfile 要求 Node 18.x 或 Node 20 及以上、npm 8 及以上；部署已经构建好的 `dist/` 时不需要在服务器常驻 Node。
- Nginx 是推荐但可替换的静态服务器和反向代理，不是 Python 后端依赖。

core 的直接 Python 依赖是 `opencv-python`、`PyQt5`、`tqdm`、`numpy`、`pygame`、`ffmpy` 和 `joblib`；GUI API 的直接依赖是 `fastapi`、`uvicorn[standard]`、`python-multipart`、`pydantic`、`orjson` 和 `pyfii`。pip 会处理它们的传递依赖。前端的 Vue、Pinia、Three.js、Marked、Vite 和 TypeScript 依赖由 `package-lock.json` 锁定，使用 `npm ci` 安装。

不要在同一个虚拟环境中同时安装 `opencv-python` 和 `opencv-python-headless`，两者都提供 `cv2`，会互相覆盖。GUI 后端在功能上适合 headless wheel，但当前 core 尚未提供与默认桌面依赖互斥的 headless 安装入口；本节的安装命令因此仍以当前包元数据为准。

后端渲染不需要 GPU、桌面会话或声卡；3D 交互由客户端浏览器的 WebGL 完成。当前服务也不依赖数据库、Redis 或独立任务队列，项目和导出状态因此只存在单个后端进程中。Node 应选择仍处于安全维护期、且满足上述版本约束的 LTS 版本。

Ubuntu 24.04 和 22.04 的基础系统包：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg
```

安装 Python 包后运行 `.venv/bin/python -c "import cv2"`。如果当前完整版 wheel 报告缺少 `libGL.so.1` 或 GLib / GThread，再按 Ubuntu 版本安装兼容库：

```bash
# Ubuntu 24.04
sudo apt install -y libgl1 libglib2.0-0t64

# Ubuntu 22.04
sudo apt install -y libgl1 libglib2.0-0
```

需要 Nginx 时另行安装 `sudo apt install -y nginx`。Python 包和前端应分别安装、构建：

```bash
cd /path/to/pyfii
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
.venv/bin/python -m pip install apps/pyfii-gui/backend

cd apps/pyfii-gui/frontend
npm ci
VITE_API_BASE_URL= npm run build
```

运行前用 `node --version` 和 `npm --version` 检查构建环境。生产服务器只提供构建得到的 `frontend/dist/`，不使用 Vite dev server 或 `vite preview`。

## 配置

后端常用环境变量：

```bash
PYFII_GUI_APP_TITLE="Pyfii GUI API"
PYFII_GUI_RUNTIME_DIR=/var/lib/pyfii-gui/projects
PYFII_GUI_CORS_ORIGINS=https://gui.example.com
PYFII_GUI_CORS_ORIGIN_REGEX='^https://.*\.example\.com$'
PYFII_GUI_CORS_ALLOW_CREDENTIALS=true
PYFII_GUI_DEFAULT_IMPORT_FPS=60
PYFII_GUI_TRAJECTORY_WORKERS=4
PYFII_GUI_VIDEO_EXPORT_JOBS=1
PYFII_GUI_VIDEO_RENDER_WORKERS=4
PYFII_GUI_MAX_UPLOAD_BYTES=104857600
PYFII_GUI_MAX_UNCOMPRESSED_BYTES=524288000
PYFII_GUI_MAX_ZIP_FILES=5000
PYFII_GUI_ENABLE_LOCAL_PROJECT_IMPORT=false
PYFII_GUI_DEPLOY_CONFIG=/path/to/deploy.json
```

ICP备案配置示例为 `apps/pyfii-gui/deploy.example.json`。复制得到的 `apps/pyfii-gui/deploy.json` 是被 git 忽略的云服务器实例配置；其中 `domain` 只填写主机名，Vite 开发服务器和 `vite preview` 会将其加入 `allowedHosts`。示例中的备案字段为空，默认备案区域不存在。只有在该文件或 `PYFII_GUI_ICP_BEIAN` / `PYFII_GUI_GONGAN_BEIAN` 中明确填写后才在门户页 footer 显示，公安备案项同时显示标准备案图标。仓库不包含真实备案号，工作台和文档页也不显示备案信息。

前端构建环境变量：

```bash
# 同源部署时留空，浏览器请求 /api
VITE_API_BASE_URL=

# 前后端分域部署时指定 API origin
VITE_API_BASE_URL=https://api.example.com
```

生产部署建议使用同源反向代理：

```text
https://gui.example.com/      -> frontend dist
https://gui.example.com/api/  -> FastAPI backend
```

这种方式不需要在前端写死 API 主机。

生产环境必须显式设置一个可写的 `PYFII_GUI_RUNTIME_DIR`，用于上传工程、解压目录和导出视频。若使用备案配置，`PYFII_GUI_DEPLOY_CONFIG` 应使用绝对路径。Uvicorn 不使用 `--reload`，并保持单 worker，因为项目缓存和视频任务状态当前都在进程内：

```bash
cd /path/to/pyfii
PYFII_GUI_RUNTIME_DIR=/var/lib/pyfii-gui/projects \
PYFII_GUI_DEPLOY_CONFIG=/absolute/path/to/deploy.json \
.venv/bin/python -m uvicorn pyfii_gui_api.main:app \
  --host 127.0.0.1 --port 8000 --workers 1
```

不使用备案时可以省略 `PYFII_GUI_DEPLOY_CONFIG`。运行 Uvicorn 的系统用户必须对 runtime 目录有读写和删除权限。

无 hash 页面使用浏览器 History API。Nginx 需要同时配置 SPA fallback、API 反向代理和上传大小；`proxy_pass` 不带末尾 `/`，以保留后端需要的 `/api` 前缀：

```nginx
server {
    listen 80;
    server_name gui.example.com;

    root /path/to/pyfii/apps/pyfii-gui/frontend/dist;
    index index.html;
    client_max_body_size 100m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

`client_max_body_size` 应与 `PYFII_GUI_MAX_UPLOAD_BYTES` 保持一致。部署后检查 Python 导入、FFmpeg、前端产物和健康接口：

```bash
cd /path/to/pyfii
.venv/bin/python -c "import cv2, pyfii; from pyfii_gui_api.main import app; print(pyfii.__version__, app.title)"
ffmpeg -version
test -f apps/pyfii-gui/frontend/dist/index.html
.venv/bin/python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/api/health').read().decode())"
```

## 回归测试

基础检查：

```bash
python -m compileall apps/pyfii-gui/backend/src apps/pyfii-gui/backend/scripts
python -m pytest -q tests/test_frontend_docs.py
PYTHONPATH=apps/pyfii-gui/backend/src:src pytest -q apps/pyfii-gui/backend/tests
cd apps/pyfii-gui/frontend
npm run test:geometry
npm run typecheck
npm run build
npm audit --omit=dev
```

批量导入人类作品经验池：

```bash
cd <repo-root>
python apps/pyfii-gui/backend/scripts/batch_import_human_pool.py \
  --mode both \
  --fps 60 \
  --timeout 180 \
  --json /tmp/pyfii-gui-human-pool-both.json
```

`--mode modern` 只跑 `ignore_acc=False`，`--mode visual` 只跑 `ignore_acc=True`。

## 当前不做

- 不做 Electron。
- 不做跨进程持久化视频队列、取消/恢复和音频封装内部的细粒度进度。
- 不做专业级音视频编辑和通用转码服务。
- 不完整复刻旧 OpenCV/cv3d 的全部 3D 机体细节。
- 不把 GUI 后端或前端移入 `src/pyfii/`。
- 不为了 GUI 兼容旧项目而修改 core 行为。
- 不保证浏览器 Three.js 预览和 core OpenCV 3D 导出逐像素一致。

未来可在保持 core/GUI 分离的前提下补充持久化任务队列、音频封装进度、更完整的 Three.js 3D 交互和更完整的 F400/F600 机体外形复刻。
