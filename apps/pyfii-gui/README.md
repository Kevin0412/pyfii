# Pyfii GUI

`pyfii-gui` 是 Pyfii 的独立 GUI 项目，放在 `apps/pyfii-gui/` 下，不属于 `src/pyfii/` core 包。

Pyfii core 仍然保持独立 PyPI 库定位。GUI 的依赖方向只允许是：

```text
pyfii-gui -> pyfii core
```

GUI 后端是 `read_fii()`、无窗口校验和 `FiiRender2D/FiiRender3D` 的薄适配层，不把 FastAPI、Vue、Electron 或前端代码放进 `src/pyfii/`。

## 开发启动

### 一键启动

从仓库根目录运行：

```bash
./apps/pyfii-gui/start.sh
```

脚本会安装 core、GUI 后端和前端依赖，然后同时启动后端 `:8000` 与前端 `:5173`；按 `Ctrl+C` 会停止两个服务。依赖已经安装时可以跳过安装，也可以调整端口：

```bash
./apps/pyfii-gui/start.sh --no-install
./apps/pyfii-gui/start.sh --port 9000 --frontend-port 5174
```

每次启动都会在 `apps/pyfii-gui/logs/<启动时间>-<进程号>/` 下分别保存 `backend.log` 和 `frontend.log`；日志每行带本地时间和时区，同时保留终端实时输出。可用 `PYFII_GUI_LOG_DIR=/path/to/logs` 修改日志根目录。

可通过 `PYTHON=/path/to/python` 指定 Python 环境。其余 `PYFII_GUI_*` 部署配置会原样传给后端。

### 分别启动

后端依赖当前仓库的 PyFii 1.6 renderer。请从仓库根目录先安装 core，再安装 GUI backend：

```bash
python -m pip install -e .
python -m pip install -e apps/pyfii-gui/backend
PYTHONPATH=apps/pyfii-gui/backend/src:src \
uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
```

两个 editable 包的版本均从各自的 `__version__` 生成；当前 core 安装元数据应为 `1.6.0`。可这样确认 pip 看到的版本：

```bash
python -c "from importlib.metadata import version; print(version('pyfii'), version('pyfii-gui-api'))"
```

`PYTHONPATH=apps/pyfii-gui/backend/src:src` 会同时优先加载 GUI backend 和本仓库 core，适合 monorepo 开发。editable install 完成后也可以省略 `PYTHONPATH`，直接运行 uvicorn。

前端：

```bash
cd apps/pyfii-gui/frontend
npm install
npm run dev
```

本地开发时，前端默认通过 Vite proxy 访问 `/api`，proxy target 默认为 `http://localhost:8000`。可通过环境变量覆盖：

```bash
VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

Vite dev server 默认监听 `0.0.0.0:5173`，局域网设备可直接打开：

```text
http://<开发机局域网IP>:5173
```

## 生产部署依赖

生产部署由“Python 后端运行环境”和“已经构建好的前端静态文件”组成。依赖范围如下：

| 依赖 | 实际要求 | 用途 |
| --- | --- | --- |
| Python | 3.9 或更高版本 | 运行 PyFii core、FastAPI 和视频渲染任务 |
| Python 包 | 分别安装仓库根目录和 `apps/pyfii-gui/backend` 的 `pyproject.toml` | pip 自动安装下列直接依赖及其传递依赖 |
| OpenCV | headless 能力已经足够 | 后端只使用图像绘制和 `VideoWriter`，不调用 `imshow`，不要求桌面或 GPU |
| OpenGL / GLib 运行库 | 后端功能本身不需要 | 当前 core 的默认依赖仍是完整版 `opencv-python`；在最小化 Linux 上导入这个 wheel 时可能需要这些兼容库 |
| FFmpeg 可执行文件 | 完整视频导出需要 | OpenCV 生成无声 MP4；工程包含音乐时，`ffmpy` 会调用系统 `ffmpeg` 把音频封装进最终 MP4。`ffmpy` 本身不包含 FFmpeg |
| Node.js / npm | Node 18.x 或 Node 20 及以上，npm 8 及以上 | 只在构建 Vue 前端时使用；服务器若直接接收构建好的 `dist/`，运行时不需要 Node |
| Nginx | 可选，可换成其他静态服务器或反向代理 | 提供 `dist/`、处理 SPA fallback，并把 `/api/` 转发给 Uvicorn |

core 的直接依赖是 `opencv-python`、`PyQt5`、`tqdm`、`numpy`、`pygame`、`ffmpy` 和 `joblib`；GUI API 的直接依赖是 `fastapi`、`uvicorn[standard]`、`python-multipart`、`pydantic`、`orjson` 和 `pyfii`。前端的 Vue、Pinia、Three.js、Marked、Vite 和 TypeScript 依赖由 `package-lock.json` 锁定并通过 `npm ci` 安装，不需要逐项安装。

仓库根目录的 `requirements.txt` 还包含音频分析、打包和终端工具等非 GUI 生产依赖。部署 GUI 时不要用它代替两个 `pyproject.toml`。

这里需要区分代码需求和当前包元数据：GUI 后端可以使用 `opencv-python-headless`，但当前 `pyfii` 默认安装仍声明 `opencv-python`。不要在同一个虚拟环境中同时安装两者，因为它们都提供 `cv2`，文件会互相覆盖。在 core 提供互斥的 desktop/headless 安装入口前，按当前 `pyproject.toml` 安装会得到完整版 wheel。

后端预览与视频渲染是 CPU 路径，不要求服务器 GPU、桌面会话或声卡；浏览器使用 3D 模式时由客户端提供 WebGL。当前实现也不依赖数据库、Redis 或独立任务队列，但这意味着项目与导出任务状态只存在单个后端进程中。

Ubuntu 24.04 和 22.04 安装后端及完整视频功能的基础系统包相同：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg
```

完成 Python 安装后先执行 `.venv/bin/python -c "import cv2"`。如果当前完整版 OpenCV wheel 在最小化服务器上报告缺少 `libGL.so.1`、`libglib-2.0.so.0` 或 `libgthread-2.0.so.0`，再安装它实际需要的兼容库。Ubuntu 24.04 使用：

```bash
sudo apt install -y libgl1 libglib2.0-0t64
```

Ubuntu 22.04 使用：

```bash
sudo apt install -y libgl1 libglib2.0-0
```

如果使用 Nginx，再安装：

```bash
sudo apt install -y nginx
```

Node 只需要出现在执行前端构建的机器上。可以使用 Ubuntu 包或其他 Node 安装方式，但必须先检查版本；不满足当前 Vite lockfile 要求时不要继续构建。技术最低版本之外，部署时应选择仍处于安全维护期的 Node LTS：

```bash
node --version
npm --version
```

Python 包建议安装到虚拟环境，避免 Ubuntu 的系统 Python 限制和包冲突：

```bash
cd /path/to/pyfii
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
.venv/bin/python -m pip install apps/pyfii-gui/backend
```

使用 lockfile 构建前端；同源部署保持 API 地址为空：

```bash
cd /path/to/pyfii/apps/pyfii-gui/frontend
npm ci
VITE_API_BASE_URL= npm run build
```

构建完成后，生产服务器只需提供 `frontend/dist/`，不应使用 Vite dev server 或 `vite preview` 代替生产静态服务器。

## 配置

后端通过环境变量配置，不需要改代码：

```bash
PYFII_GUI_APP_TITLE="Pyfii GUI API"
PYFII_GUI_RUNTIME_DIR=/var/lib/pyfii-gui/projects
PYFII_GUI_CORS_ORIGINS=https://gui.example.com,https://admin.example.com
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
PYFII_GUI_LOCAL_PROJECT_ROOTS=/path/to/pyfii/tools/choreo_agent/agent_projects
PYFII_GUI_DEPLOY_CONFIG=/path/to/deploy.json
```

默认 CORS 允许 `http://localhost:5173` 和常见私有局域网 IP 的 `:5173` 开发源；生产部署建议显式设置 `PYFII_GUI_CORS_ORIGINS`。

前端构建时通过环境变量配置 API 地址：

```bash
# 同源部署时留空，浏览器会请求 /api
VITE_API_BASE_URL=

# 前后端分域部署时显式指定 API origin
VITE_API_BASE_URL=https://api.example.com
```

Vite dev server 也可配置：

```bash
VITE_DEV_HOST=0.0.0.0
VITE_DEV_PORT=5173
VITE_API_PROXY_TARGET=http://localhost:8000
```

## 本地 Agent 项目导入

云端部署默认只允许浏览器上传 zip。后端本地路径导入默认关闭，避免公网实例暴露服务器文件读取能力。

在本机联调 `tools/choreo_agent` 时，可以显式开启：

```bash
cd apps/pyfii-gui/backend
PYTHONPATH=src:../../../src \
PYFII_GUI_ENABLE_LOCAL_PROJECT_IMPORT=true \
PYFII_GUI_LOCAL_PROJECT_ROOTS=/path/to/pyfii/tools/choreo_agent/agent_projects \
uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
```

开启后，前端会显示“本地路径”输入框，可填 agent project 目录或其 `output/` 目录，例如：

```text
tools/choreo_agent/agent_projects/stability_flash_3
tools/choreo_agent/agent_projects/stability_flash_3/output
```

生产环境不要开启 `PYFII_GUI_ENABLE_LOCAL_PROJECT_IMPORT`。

## 部署备案配置

备案号属于部署实例配置，不提交到 git。默认配置为空，门户页不会显示备案信息。需要启用时复制示例文件：

```bash
cp apps/pyfii-gui/deploy.example.json apps/pyfii-gui/deploy.json
```

填写部署实例自己的信息；下面仍是占位示例，不是真实备案号：

```json
{
  "domain": "gui.example.com",
  "icp_beian": "ICP备案号",
  "icp_url": "https://beian.miit.gov.cn/",
  "gongan_beian": "公安备案号",
  "gongan_url": "公安备案链接"
}
```

`domain` 只填写主机名，不带 `https://`、端口或路径。Vite 开发服务器和 `vite preview` 会把非空值加入 `allowedHosts`；修改后需要重启前端进程。正式使用 Nginx 提供构建产物时，域名放行仍由 Nginx 配置负责。

`deploy.json` 是云服务器实例的本地配置，已被 `.gitignore` 忽略；后端和 Vite 默认读取该文件。也可以通过 `PYFII_GUI_DEPLOY_CONFIG` 指向服务器上的其他路径，或通过环境变量逐项覆盖备案字段：

```bash
PYFII_GUI_ICP_BEIAN=
PYFII_GUI_ICP_URL=
PYFII_GUI_GONGAN_BEIAN=
PYFII_GUI_GONGAN_URL=
```

## 服务器部署建议

`PYFII_GUI_RUNTIME_DIR` 用来保存上传后解压的工程和导出视频，运行 Uvicorn 的系统用户必须能够创建、读取和删除其中的文件。生产环境应显式设置该目录；如果使用备案配置，也应给 `PYFII_GUI_DEPLOY_CONFIG` 传入绝对路径，避免安装位置改变默认路径。

启动后端（生产环境**不要加 `--reload`**，否则上传项目后 WatchFiles 检测 `.runtime/` 下的文件变化会触发重载，内存缓存清空导致 tracks/safety/music/video exports 全部失效）：

```bash
cd /path/to/pyfii
PYFII_GUI_RUNTIME_DIR=/var/lib/pyfii-gui/projects \
PYFII_GUI_DEPLOY_CONFIG=/absolute/path/to/deploy.json \
.venv/bin/python -m uvicorn pyfii_gui_api.main:app \
  --host 127.0.0.1 --port 8000 --workers 1
```

如果不配置备案，可以省略 `PYFII_GUI_DEPLOY_CONFIG`。`/var/lib/pyfii-gui/projects` 需要提前创建，并把所有权交给实际运行 Uvicorn 的用户。后端只供同机反向代理访问时监听 `127.0.0.1`；只有明确需要局域网或外部直连时才使用 `0.0.0.0`。

推荐同源反向代理：

```text
https://gui.example.com/      -> frontend dist
https://gui.example.com/api/  -> FastAPI backend
```

这种模式下前端不需要写死 API 主机，`VITE_API_BASE_URL` 保持空值即可。如果前端和后端分域部署，需要同时设置：

- 前端：`VITE_API_BASE_URL=https://api.example.com`
- 后端：`PYFII_GUI_CORS_ORIGINS=https://gui.example.com`

前端使用 History API 路由。生产静态服务器必须把不存在的文件路径回退到 `index.html`，否则直接打开 `/docs/guide`、`/docs/tutorial` 或 `/studio` 会返回 404。下面的 Nginx 示例同时保留 `/api` 前缀，并把上传上限设置为与后端默认的 100 MiB 一致：

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

如果修改 `PYFII_GUI_MAX_UPLOAD_BYTES`，还要同步调整 `client_max_body_size`。Vite 开发服务器已经提供 SPA 回退，不需要这段 Nginx 配置。

当前项目和视频任务使用进程内缓存，生产环境应先使用单个 Uvicorn worker。多 worker 或多实例部署需要先增加共享项目存储和任务队列，否则同一项目的后续请求可能落到另一个进程。

部署后可先做依赖和产物检查，再访问 `/api/health`：

```bash
cd /path/to/pyfii
.venv/bin/python -c "import cv2, pyfii; from pyfii_gui_api.main import app; print(pyfii.__version__, app.title)"
ffmpeg -version
test -f apps/pyfii-gui/frontend/dist/index.html
.venv/bin/python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/api/health').read().decode())"
```

## 文档与教程中心

站点首页 `/` 是门户页，包含项目简介、主要页面入口、GitHub 链接和 B 站视频教程。Guide、core 文档和专题教程共用 `/docs` 文档中心，不再作为三个并列的站点入口。模拟器第一次打开会显示逐控件聚焦的六步使用引导，依次指出上传、视图、时间轴、全屏、安全日志和导出；之后仍可从工作台顶部“使用引导”按钮重新打开。文档中心内部路径为：

- `/docs`：文档与教程总览；`/doc` 是兼容入口。
- `/docs/index`：`doc/` 下全部 Markdown 的索引。
- `/docs/guide`：完整 GUI 使用引导和常见问题。
- `/docs/core`：直接打包仓库 `doc/doc_zh_CN.md`。
- `/docs/gui`：GUI 架构和部署说明。
- `/docs/tutorial`：教程目录；各子页直接打包 `doc/tutorial/*.md`。
- `/docs/choreo/*`：人类/AI 编舞蒸馏、编码模式、Agent 经验、路线图和 Cannon 复盘。
- `/docs/research/*`：真实飞行分析和 fwfii 集成调研。
- `/studio`：工程校验、飞行预览和视频导出工作台；`/gui` 是兼容入口。

旧的 `/guide`、`/tutorial/*` 和 `#/...` 链接会在浏览器中自动转换到 `/docs/...` 新路径。两个内容为空的旧教程入口“编程挑战”和“进阶用法”不再展示，旧地址回到教程目录。

文档在构建时从 `doc/` 下全部 22 篇 Markdown 源导入，每篇正文单独生成按需加载的前端 chunk；打开 Guide 时不会同时下载其他研究文档。这样既避免维护复制内容，也不增加工作台首次加载的文档体积。真实飞行分析使用的 `doc/images/` 图表和指标文件也由 Vite 一并打包。

备案信息只显示在门户页 footer。只有后端返回了显式配置的 ICP 或公安备案号时该区域才存在；公安备案项会显示标准备案图标，链接使用 `gongan_url`。文档页和工作台不重复展示。

## 当前支持

- 上传 Fii 项目 zip。
- 项目载入显示确定百分比：ZIP 已上传字节映射到 0–25%，后端解压和解析完成后到 50%，轨迹与安全日志两个响应各完成后推进到 75% 和 100%；不会用循环动画冒充进度。
- 项目门户页和跨页面一致的站点导航。
- 未保存主题选择时，门户、Guide、文档和教程默认浅色，飞行工作台默认深色；支持手动切换并记住用户选择。界面控件支持中文/英文切换，当前 Markdown 文档正文以中文为准。
- 移动布局区分手机、平板和屏幕方向，不会因为电脑浏览器窗口变窄就切到手机界面。手机和平板竖屏的工作台都让画布按 `2:1` 铺满屏幕宽度并优先显示；平板横屏沿用电脑端工作台。手机文档目录默认折叠，平板竖屏显示双列目录。
- 统一的文档与教程中心，内部包含 Guide、PyFii 文档、专题教程、编舞与 Agent、工程研究静态页。
- 安全解压并调用 `read_fii()` 解析轨迹。
- GUI 默认只把一半 CPU 核心分配给单次轨迹解析，为并发请求预留资源；可通过 `PYFII_GUI_TRAJECTORY_WORKERS` 调整。
- 将解析结果装入 `DroneTrack`，调用 `show(track, show=False)` 走 pyfii core 的无渲染距离检查。
- 返回项目元信息、轨迹数据和由 core warnings 结构化得到的安全日志。
- Canvas 2D 三视图预览：top / front / right。
- Three.js 3D 预览模式，支持正交/透视相机切换；默认 2D 首屏不下载 Three.js，第一次切换到 3D 时再加载。
- 3D 模式保留旧 `show(ThreeD=True)` 的 A/B 视角角、观察者距离和投影距离语义。
- 3D 模式默认评委视角 `imshow=[90,3]`、`d=(600,450)`，支持鼠标拖动转动视角和滚轮调整投影距离。
- 3D 模式显示高度标尺、地面投影、左上角时间/FPS/坐标 HUD，以及按 9 机编队设计的稳定机体颜色；机体姿态沿用 core 的重力与加速度合成关系，根据合成升力方向显示倾斜。
- 右下角 2 行 5 列无人机信息栏：D1..D9 + STATUS。
- 安全日志以 pyfii core warning 为准，GUI 后端只做结构化整理。
- 安全日志按距离、动作未完成和通用 core warning 五类展示，并支持类似 Excel/文件夹列表的按列筛选和排序。
- 新 XML 解析器产生的未拼接积木 warning 会作为 `core_warning` 展示；warning 不阻止预览，工程导入失败等 fatal error 仍终止当前操作。
- 距离事件沿用 core 的 51cm / 34cm / 17cm 档位，分别对应距离过近、碰撞风险、碰撞警告。
- 点击安全日志跳转到对应时间。
- 音乐文件播放和基础时间轴同步。
- 后端异步 MP4 导出。2D/3D 分别复用 core 的 `DroneTrack + FiiRender2D/FiiRender3D.save()`，前端创建任务、轮询状态并下载结果，不再使用浏览器 MediaRecorder 录屏。
- core 能定位到音乐且服务器可执行 ffmpeg 时，视频导出沿用 core 的音频封装流程。

视频接口：

- `POST /api/projects/{project_id}/video-exports`：创建任务。
- `GET /api/projects/{project_id}/video-exports/{export_id}`：读取 `queued/running/completed/failed` 状态。
- `GET /api/projects/{project_id}/video-exports/{export_id}/download`：下载完成的 MP4。

core renderer 在每帧写入后通过可选回调报告真实帧进度。后端把逐帧阶段映射为 0–95%，剩余区间表示视频/音频封装，任务完成时为 100%；排队、渲染和封装在前端进度条中分别显示。

## 批量导入回归

后端单元/API 测试和前端构建：

```bash
cd <repo-root>
PYTHONPATH=apps/pyfii-gui/backend/src:src pytest -q apps/pyfii-gui/backend/tests
python -m compileall -q apps/pyfii-gui/backend/src apps/pyfii-gui/backend/tests
cd apps/pyfii-gui/frontend
npm run test:geometry
npm run typecheck
npm run build
npm audit --omit=dev
```

可用后端脚本把 `doc/ai_choreography_exploration.md` 中的人类作品经验池跑一遍，覆盖 clean zip 打包、安全解压、`read_fii()`、`show(show=False)`、安全日志和轨迹 JSON 序列化：

```bash
cd <repo-root>
python apps/pyfii-gui/backend/scripts/batch_import_human_pool.py \
  --mode both \
  --fps 60 \
  --timeout 180 \
  --json /tmp/pyfii-gui-human-pool-both.json
```

`--mode modern` 只跑 `ignore_acc=False`，`--mode visual` 只跑 `ignore_acc=True`。已知老版本不兼容项目会记录为 `expected_failure`，不作为 GUI 回归失败处理。

## 当前不支持

- Electron。
- 跨进程共享的持久化项目缓存、任务队列、取消/恢复和音频封装内部的细粒度进度。
- 专业级音频/视频编辑、时间线混音和多格式转码。
- 完整复刻旧 OpenCV/cv3d 的全部 3D 机体细节。
- 保证浏览器 Three.js 预览与 core OpenCV 3D 视频逐像素一致；两者共享轨迹和相机语义，但使用不同绘制后端。

## 未来计划

- 持久化视频任务、取消和音频封装进度。
- 更完整的 Three.js 3D 交互、轨迹尾迹和相机预设。
- 更完整的 F400/F600 机体外形复刻。
